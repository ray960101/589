import streamlit as st
import sqlite3
import pandas as pd
import json
import base64
from openai import OpenAI

# ==========================================
# 1. 資料庫模組 (SQLite)
# ==========================================
def init_db():
    """初始化資料庫與建立資料表"""
    conn = sqlite3.connect('smart_expenses.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            store TEXT,
            amount REAL,
            category TEXT,
            items TEXT
        )
    ''')
    conn.commit()
    conn.close()


def insert_receipt(date, store, amount, category, items):
    """將確認後的記帳資料存入資料庫"""
    conn = sqlite3.connect('smart_expenses.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO receipts (date, store, amount, category, items)
        VALUES (?, ?, ?, ?, ?)
    ''', (date, store, amount, category, items))
    conn.commit()
    conn.close()


def get_all_data():
    """讀取所有記帳紀錄"""
    conn = sqlite3.connect('smart_expenses.db')
    df = pd.read_sql_query("SELECT * FROM receipts ORDER BY date DESC", conn)
    conn.close()
    return df


# ==========================================
# 2. AI 辨識模組 (OpenAI GPT-4o)
# ==========================================
def analyze_receipt(image_file, api_key):
    """將圖片轉為 Base64 並送給 OpenAI 進行智慧辨識"""
    client = OpenAI(api_key=api_key)
    base64_image = base64.b64encode(image_file.read()).decode('utf-8')

    prompt = """
    你是一個專業的收據與發票辨識專家。請分析這張圖片，精確提取資訊。
    請務必嚴格以 JSON 格式回傳，不要包含任何 Markdown 標記（例如不要寫 ```json）。

    期望的 JSON 格式如下：
    {
        "date": "YYYY-MM-DD (若找不到則填今天日期)",
        "store": "商店或品牌名稱",
        "amount": 總金額 (請填數字，不可有逗號),
        "category": "請從中選擇一個最符合的分類：餐飲、交通、娛樂、日用品、其他",
        "items": "購買品項的摘要"
    }
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            }
        ],
        response_format={"type": "json_object"}
    )

    try:
        content = response.choices[0].message.content
    except AttributeError:
        content = response.choices[0].message["content"]

    if isinstance(content, str):
        return json.loads(content)
    return content


# ==========================================
# 3. Streamlit 前端網頁介面
# ==========================================
init_db()

st.set_page_config(page_title="AI 智慧收據記帳系統", layout="wide", page_icon="🧾")
st.title("🧾 AI 智慧收據記帳系統")
st.markdown("上傳收據或發票照片，讓 AI 自動幫你辨識品項、金額並歸類記帳！")

with st.sidebar:
    st.header("⚙️ 系統設定")
    user_api_key = st.text_input("輸入你的 OpenAI API Key", type="password", help="請至 OpenAI 官網申請 API Key")
    st.markdown("---")
    st.info("💡 提示：本系統會將資料安全地儲存在本地 SQLite 資料庫中。")

tab1, tab2 = st.tabs(["📸 上傳記帳", "📊 歷史消費與統計"])

with tab1:
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("1. 選擇收據圖片")
        uploaded_file = st.file_uploader("支援 JPG, JPEG, PNG 格式", type=["jpg", "jpeg", "png"])

        if uploaded_file:
            st.image(uploaded_file, caption="已上傳的收據預覽", use_container_width=True)

            if st.button("🚀 開始 AI 智慧辨識"):
                if not user_api_key:
                    st.error("❌ 請先在左側欄位輸入您的 OpenAI API Key！")
                else:
                    with st.spinner("AI 正在極速辨識收據內容中..."):
                        try:
                            uploaded_file.seek(0)
                            result = analyze_receipt(uploaded_file, user_api_key)
                            st.session_state['parsed_data'] = result if isinstance(result, dict) else json.loads(result)
                            st.success("🎉 辨識完成！請在右側確認資料。")
                        except Exception as e:
                            st.error(f"辨識失敗，錯誤訊息：{e}")

    with col_right:
        st.subheader("2. AI 辨識結果確認")

        if 'parsed_data' in st.session_state:
            data = st.session_state['parsed_data']

            with st.form("confirm_form"):
                confirm_date = st.text_input("消費日期", value=data.get("date", ""))
                confirm_store = st.text_input("商店名稱", value=data.get("store", ""))
                confirm_amount = st.number_input("總金額", value=float(data.get("amount", 0)))

                categories = ["餐飲", "交通", "娛樂", "日用品", "其他"]
                default_cat = data.get("category", "其他")
                if default_cat not in categories:
                    default_cat = "其他"
                confirm_category = st.selectbox("消費分類", categories, index=categories.index(default_cat))

                confirm_items = st.text_area("品項明細摘要", value=data.get("items", ""))

                if st.form_submit_button("💾 確認正確，存入記帳本"):
                    insert_receipt(confirm_date, confirm_store, confirm_amount, confirm_category, confirm_items)
                    st.success(f"✅ 成功存入一筆來自「{confirm_store}」金額 ${confirm_amount} 的消費！")
                    st.balloons()
                    del st.session_state['parsed_data']
        else:
            st.info("👈 請先在左側上傳收據並點擊「開始 AI 智慧辨識」")

with tab2:
    st.subheader("📋 歷史消費紀錄")
    df_records = get_all_data()

    if not df_records.empty:
        st.dataframe(df_records[['date', 'store', 'category', 'amount', 'items']], use_container_width=True)
        st.markdown("---")
        st.subheader("📊 消費分類統計")
        chart_col1, chart_col2 = st.columns([1, 1])

        with chart_col1:
            cat_totals = df_records.groupby('category')['amount'].sum()
            st.write("各分類累積消費：")
            st.bar_chart(cat_totals)

        with chart_col2:
            total_spent = df_records['amount'].sum()
            st.metric(label="💰 累計總消費花費", value=f"${total_spent:,.0f} 元")
            st.write(f"目前總計有 {len(df_records)} 筆記帳紀錄。")
    else:
        st.info("目前還沒有任何記帳資料。快去上傳第一張收據吧！")
