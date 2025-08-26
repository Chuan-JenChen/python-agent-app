import streamlit as st
import pandas as pd
import database as db

# --- 代理定義 (Agent Definitions) ---
# (這部分的程式碼也無需修改)
class RetrievalAgent:
    def add_return_from_form(self, form_data: dict):
        """從表單資料中新增一筆退貨紀錄。"""
        try:
            db.add_return(
                order_id=form_data['order_id'],
                product=form_data['product'],
                category=form_data['category'],
                return_reason=form_data['return_reason'],
                cost=form_data['cost'],
                approved_flag=form_data['approved_flag'],
                store_name=form_data['store_name']
            )
            return db.get_all_returns(), f"成功新增訂單 {form_data['order_id']} 的退貨紀錄。"
        except Exception as e:
            return None, f"新增失敗：{e}"

class ReportAgent:
    def generate_report(self):
        """從資料庫撈取所有資料，並產生一份包含摘要和詳細資料的 Excel 報告。"""
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

# --- Streamlit 網頁應用介面 ---
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

with st.form(key='add_return_form'):
    st.subheader("請填寫退貨詳細資訊")
    # 加入一個提示訊息，告訴使用者如何查看填寫規則
    st.info("提示：所有欄位皆為必填。請將滑鼠停在輸入框上查看詳細填寫規則。")

    col1, col2 = st.columns(2)
    
    with col1:
        order_id = st.number_input(
            "訂單編號 (Order ID)", 
            min_value=1, 
            step=1,
            # help 參數會在使用者滑鼠移到元件上時，顯示提示文字
            help="請輸入數字格式的訂單編號，例如 1101。"
        )
        product = st.text_input(
            "產品名稱 (Product)", 
            help="請輸入完整的產品名稱，至少需要 2 個字元。"
        )
        category = st.selectbox(
            "產品類別 (Category)", 
            options=['Electronics', 'Accessories', 'Unknown'], 
            index=0,
            help="請從下拉選單中選擇最接近的產品類別。"
        )
        cost = st.number_input(
            "成本 (Cost)", 
            min_value=0.0, 
            format="%.2f", 
            help="請輸入該產品的退貨成本，此數值必須大於 0。"
        )

    with col2:
        store_name = st.text_input(
            "店家名稱 (Store Name)", 
            help="請輸入退貨的店家或平台名稱，至少需要 2 個字元。"
        )
        return_reason = st.text_input(
            "退貨原因 (Return Reason)", 
            help="請簡要說明退貨原因，此欄位不可為空。"
        )
        approved_flag = st.selectbox(
            "是否批准 (Approved)", 
            options=['Yes', 'No'], 
            index=1,
            help="請選擇這筆退貨是否已被批准。"
        )
    
    # 表單的送出按鈕
    submit_button = st.form_submit_button(label='✨ 執行新增')

# 當使用者點擊送出按鈕後，才執行以下邏輯
if submit_button:
    # --- 資料驗證 (Validation) ---
    # 建立一個列表來收集所有錯誤訊息
    error_messages = []

    # 驗證規則 1：產品名稱長度
    # .strip() 會移除字串前後的空白，避免使用者只輸入空格
    if len(product.strip()) < 2:
        error_messages.append("產品名稱至少需要 2 個字元。")
    
    # 驗證規則 2：店家名稱長度
    if len(store_name.strip()) < 2:
        error_messages.append("店家名稱至少需要 2 個字元。")
        
    # 驗證規則 3：退貨原因不可為空
    if len(return_reason.strip()) == 0:
        error_messages.append("請填寫退貨原因。")
        
    # 驗證規則 4：成本必須大於 0
    if cost <= 0.0:
        error_messages.append("成本必須大於 0。")

    # --- 根據驗證結果執行不同操作 ---
    # 如果 error_messages 列表是空的，代表所有驗證都通過
    if not error_messages:
        # 將所有表單欄位打包成一個字典
        form_data = {
            'order_id': order_id,
            'product': product,
            'category': category,
            'return_reason': return_reason,
            'cost': cost,
            'approved_flag': approved_flag,
            'store_name': store_name
        }
        # 呼叫代理來執行新增
        df, message = retrieval_agent.add_return_from_form(form_data)
        if df is not None:
            st.success(message)
        else:
            st.error(message)
    else:
        # 如果有任何錯誤，就將所有錯誤訊息一次性顯示出來
        st.error("資料驗證失敗，請修正以下問題：\n\n- " + "\n- ".join(error_messages))

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
