# app.py
import streamlit as st
import re
import pandas as pd
import database as db

# --- 員工 A (Retrieval Agent) 的定義 ---
class RetrievalAgent:
    def add_return_from_prompt(self, prompt: str):
        match = re.search(r"訂單 (\d+) 的退貨，產品是 '([^']*)'，店家是 '([^']*)'", prompt)
        if not match:
            return None, "錯誤：無法解析指令。請嚴格遵守指定的格式。"
        order_id, product_name, store_name = match.groups()
        try:
            db.add_return(int(order_id), product_name, store_name)
            return db.get_all_returns(), f"成功新增訂單 {order_id} 的退貨紀錄。"
        except Exception as e:
            return None, f"新增失敗：{e}"

# --- 員工 B (Report Agent) 的定義 ---
class ReportAgent:
    def generate_report(self):
        try:
            all_returns = db.get_all_returns()
            if all_returns.empty:
                return False, "資料庫中沒有任何紀錄可供報告。"
            with pd.ExcelWriter('returns_summary.xlsx', engine='openpyxl') as writer:
                total_cost = all_returns['cost'].sum()
                approved_returns = all_returns[all_returns['approved_flag'] == 'Yes']
                summary_df = pd.DataFrame({
                    '項目': ['總退貨筆數', '獨立店家數量', '已批准退貨數', '總退貨成本'],
                    '數值': [len(all_returns), all_returns['store_name'].nunique(), len(approved_returns), f"${total_cost:,.2f}"]
                })
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                all_returns.to_excel(writer, sheet_name='Findings', index=False)
            return True, "報告 'returns_summary.xlsx' 已成功產生！"
        except Exception as e:
            return False, f"報告產生失敗：{e}"

# --- 網頁介面 (門面) & 指揮官 (協調器) ---
st.set_page_config(page_title="退貨洞察系統", layout="wide")
st.title("🤖 退貨與保固洞察 AI 代理系統")

if 'initialized' not in st.session_state:
    db.init_db()
    db.ingest_from_google_sheet()
    st.session_state.initialized = True
    st.toast("資料庫已準備就緒！")

retrieval_agent = RetrievalAgent()
report_agent = ReportAgent()

st.header("1. 新增退貨紀錄 (由 Retrieval Agent 處理)")
st.info("請嚴格遵守格式：`新增一筆訂單 [數字] 的退貨，產品是 '[產品名稱]'，店家是 '[店家名稱]'`")
add_prompt = st.text_input("輸入新增指令：", "新增一筆訂單 1101 的退貨，產品是 '無線充電板'，店家是 '台北信義店'")

if st.button("執行新增"):
    df, message = retrieval_agent.add_return_from_prompt(add_prompt)
    if df is not None: st.success(message)
    else: st.error(message)

st.header("2. 產生報告 (由 Report Agent 處理)")
if st.button("產生 Excel 報告"):
    success, message = report_agent.generate_report()
    if success:
        st.success(message)
        with open("returns_summary.xlsx", "rb") as file:
            st.download_button("📥 點此下載報告", file, "returns_summary.xlsx")
    else:
        st.error(message)

st.header("3. 目前所有退貨紀錄")
st.dataframe(db.get_all_returns(), use_container_width=True)