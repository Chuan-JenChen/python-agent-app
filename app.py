import streamlit as st  
import pandas as pd     
import database as db   

class RetrievalAgent:
    """
    檢索代理 (員工 A)：負責處理資料的存取。
    它的主要工作是接收來自網頁表單的資料，並呼叫資料庫函數將其寫入資料庫。
    """
    def add_return_from_form(self, form_data: dict):
        """
        從一個包含表單資料的字典 (dictionary) 中，新增一筆退貨紀錄。
        """
        try:
            # 呼叫 database.py 中的 add_return 函數，將表單資料傳遞過去
            # 注意這裡不再傳遞 order_id，因為它將由資料庫層自動生成
            new_order_id = db.add_return(
                product=form_data['product'],
                category=form_data['category'],
                return_reason=form_data['return_reason'],
                cost=form_data['cost'],
                approved_flag=form_data['approved_flag'],
                store_name=form_data['store_name']
            )
            # 如果成功，回傳更新後的完整資料表和一條包含新訂單編號的成功訊息
            return db.get_all_returns(), f"成功新增訂單 {new_order_id} 的退貨紀錄。"
        except Exception as e:
            # 如果在寫入資料庫時發生任何錯誤，回傳 None 和一條錯誤訊息
            return None, f"新增失敗：{e}"

class ReportAgent:
    """
    報告代理 (員工 B)：負責產生 Excel 報告。
    """
    def generate_report(self):
        """
        從資料庫撈取所有資料，並產生一份包含摘要和詳細資料的 Excel 報告。
        """
        try:
            all_returns = db.get_all_returns()
            if all_returns.empty:
                return False, "資料庫中沒有任何紀錄可供報告。"

            with pd.ExcelWriter('returns_summary.xlsx', engine='openpyxl') as writer:
                # --- 準備摘要工作表的數據 ---
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
# 設定網頁的標題和佈局 (layout='wide' 表示使用寬版模式)
st.set_page_config(page_title="退貨洞察系統", layout="wide")
# 顯示網頁的主標題
st.title("� 退貨與保固洞察 AI 代理系統")

# `st.session_state` 是一個類似字典的物件，可以在使用者多次互動之間保存狀態。
# 我們用它來確保資料庫初始化和資料載入的動作，只在網頁第一次載入時執行一次。
if 'initialized' not in st.session_state:
    db.init_db()
    db.ingest_from_google_sheet()
    st.session_state.initialized = True  # 標記為已初始化
    st.toast("資料庫已準備就緒！") # 顯示一個短暫的彈出式通知

# 建立兩個代理的實例 (物件)
retrieval_agent = RetrievalAgent()
report_agent = ReportAgent()

# --- 介面佈局：新增退貨區塊 ---
st.header("1. 新增退貨紀錄 (由 Retrieval Agent 處理)")

# `st.form` 可以將多個輸入元件群組在一起，提升使用者體驗
with st.form(key='add_return_form'):
    st.subheader("請填寫退貨詳細資訊")
    
    # 在表單載入時，就先呼叫資料庫函數取得下一個可用的訂單編號
    next_id = db.get_next_order_id()
    # 將編號顯示為不可編輯的文字，讓使用者知道即將新增的編號是多少
    st.markdown(f"**即將新增的訂單編號 (Order ID): `{next_id}`** (此編號由系統自動生成)")
    
    # `st.columns(2)` 將介面切分為左右兩欄，讓版面更緊湊、更美觀。
    col1, col2 = st.columns(2)
    
    with col1:
        # 使用 value 參數來為輸入框預先填入範例文字，引導使用者
        product = st.text_input("產品名稱 (Product)", value="無線充電板", help="請輸入完整的產品名稱")
        category = st.selectbox("產品類別 (Category)", 
                                options=['Electronics', 'Accessories', 'Unknown'], 
                                index=1, # index=1 表示預設選中 'Accessories'
                                help="請從下拉選單中選擇產品類別")
        cost = st.number_input("成本 (Cost)", min_value=0.01, value=25.50, format="%.2f", help="退貨成本必須大於 0")

    with col2:
        store_name = st.text_input("店家名稱 (Store Name)", value="台北信義店", help="請輸入退貨的店家或平台名稱")
        return_reason = st.text_input("退貨原因 (Return Reason)", value="商品有刮痕", help="請簡要說明退貨原因")
        approved_flag = st.selectbox("是否批准 (Approved)", 
                                     options=['Yes', 'No'], 
                                     index=1, # index=1 表示預設選中 'No'
                                     help="請選擇這筆退貨是否已被批准")
    
    # `st.form_submit_button` 是表單專用的送出按鈕
    submit_button = st.form_submit_button(label='✨ 執行新增')

# 這段程式碼只有在使用者點擊了 `submit_button` 之後才會被執行
if submit_button:
    # --- 資料驗證 (Validation) ---
    error_messages = []
    if len(product.strip()) < 2: error_messages.append("產品名稱至少需要 2 個字元。")
    if len(store_name.strip()) < 2: error_messages.append("店家名稱至少需要 2 個字元。")
    if len(return_reason.strip()) == 0: error_messages.append("請填寫退貨原因。")
    if cost <= 0.0: error_messages.append("成本必須大於 0。")

    # --- 根據驗證結果執行不同操作 ---
    if not error_messages:
        # 如果驗證通過，將表單資料打包成字典
        form_data = {
            'product': product, 'category': category, 'return_reason': return_reason,
            'cost': cost, 'approved_flag': approved_flag, 'store_name': store_name
        }
        # 呼叫代理來執行新增
        df, message = retrieval_agent.add_return_from_form(form_data)
        if df is not None: st.success(message)
        else: st.error(message)
    else:
        # 如果驗證失敗，將所有錯誤訊息一次性顯示出來
        st.error("資料驗證失敗，請修正以下問題：\n\n- " + "\n- ".join(error_messages))

# --- 介面佈局：產生報告區塊 ---
st.header("2. 產生報告 (由 Report Agent 處理)")
if st.button("產生 Excel 報告"):
    success, message = report_agent.generate_report()
    if success:
        st.success(message)
        with open("returns_summary.xlsx", "rb") as file:
            st.download_button("📥 點此下載報告", file, "returns_summary.xlsx")
    else:
        st.error(message)

# --- 介面佈局：顯示目前所有資料區塊 ---
st.header("3. 目前所有退貨紀錄")
# `st.dataframe` 可以將一個 pandas DataFrame 渲染成一個漂亮的互動式表格
st.dataframe(db.get_all_returns(), use_container_width=True)