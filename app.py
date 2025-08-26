import streamlit as st 
import pandas as pd     
import database as db   

class RetrievalAgent:
    """
    檢索代理 (員工 A)：負責處理資料的存取。
    在這個版本中，它的主要工作是接收來自網頁表單的資料，並將其寫入資料庫。
    """
    def add_return_from_form(self, form_data: dict):
        """
        從一個包含表單資料的字典 (dictionary) 中，新增一筆退貨紀錄。
        :param form_data: 一個字典，鍵 (key) 是欄位名稱，值 (value) 是使用者輸入的內容。
        :return: 一個包含 (DataFrame, message) 的元組 (tuple)。
        """
        try:
            # 呼叫 database.py 中的 add_return 函數，將表單資料傳遞過去
            # 使用 **form_data (字典解包) 是一種更簡潔的寫法，但為了清晰，這裡逐一傳遞
            db.add_return(
                order_id=form_data['order_id'],
                product=form_data['product'],
                category=form_data['category'],
                return_reason=form_data['return_reason'],
                cost=form_data['cost'],
                approved_flag=form_data['approved_flag'],
                store_name=form_data['store_name']
            )
            # 如果成功，回傳更新後的完整資料表和一條成功訊息
            return db.get_all_returns(), f"成功新增訂單 {form_data['order_id']} 的退貨紀錄。"
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
            # 如果資料庫是空的，就不產生報告，直接回傳失敗訊息
            if all_returns.empty:
                return False, "資料庫中沒有任何紀錄可供報告。"

            # 使用 `with` 陳述式來建立 ExcelWriter，可以確保檔案操作完成後會被妥善關閉
            with pd.ExcelWriter('returns_summary.xlsx', engine='openpyxl') as writer:
                # --- 準備摘要工作表的數據 ---
                total_cost = all_returns['cost'].sum() # 計算總成本
                approved_returns = all_returns[all_returns['approved_flag'] == 'Yes'] # 篩選出已批准的退貨
                
                # 建立一個新的 DataFrame 來存放摘要資訊
                summary_df = pd.DataFrame({
                    '項目': ['總退貨筆數', '獨立店家數量', '已批准退貨數', '總退貨成本'],
                    '數值': [
                        len(all_returns), 
                        all_returns['store_name'].nunique(), # nunique() 用於計算不重複的項目數量
                        len(approved_returns), 
                        f"${total_cost:,.2f}" # 將成本格式化成美金格式，例如 $1,234.56
                    ]
                })
                # 將摘要 DataFrame 寫入名為 'Summary' 的工作表
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # 將完整的原始數據寫入名為 'Findings' 的工作表
                all_returns.to_excel(writer, sheet_name='Findings', index=False)
            
            # 如果成功，回傳 True 和成功訊息
            return True, "報告 'returns_summary.xlsx' 已成功產生！"
        except Exception as e:
            return False, f"報告產生失敗：{e}"

# --- Streamlit 網頁應用介面 ---
# 設定網頁的標題和佈局 (layout='wide' 表示使用寬版模式)
st.set_page_config(page_title="退貨洞察系統", layout="wide")
# 顯示網頁的主標題
st.title("🤖 退貨與保固洞察 AI 代理系統")

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

# `st.form` 可以將多個輸入元件群組在一起。
# 只有當使用者點擊表單內的「送出」按鈕時，所有輸入的資料才會一次性地被送出。
# 這可以避免使用者每填一個欄位，頁面就刷新一次，提供更好的使用者體驗。
with st.form(key='add_return_form'):
    st.subheader("請填寫退貨詳細資訊")
    
    # `st.columns(2)` 將介面切分為左右兩欄，讓版面更緊湊、更美觀。
    col1, col2 = st.columns(2)
    
    # --- 左半邊的表單欄位 ---
    with col1:
        order_id = st.number_input("訂單編號 (Order ID)", min_value=1, step=1)
        product = st.text_input("產品名稱 (Product)")
        # `st.selectbox` 建立一個下拉選單，可以防止使用者打錯字，確保資料乾淨。
        category = st.selectbox("產品類別 (Category)", 
                                options=['Electronics', 'Accessories', 'Unknown'], 
                                index=0) # index=0 表示預設選中第一個選項
        cost = st.number_input("成本 (Cost)", min_value=0.0, format="%.2f")

    # --- 右半邊的表單欄位 ---
    with col2:
        store_name = st.text_input("店家名稱 (Store Name)")
        return_reason = st.text_input("退貨原因 (Return Reason)")
        approved_flag = st.selectbox("是否批准 (Approved)", 
                                     options=['Yes', 'No'], 
                                     index=1) # index=1 表示預設選中第二個選項 'No'
    
    # `st.form_submit_button` 是表單專用的送出按鈕
    submit_button = st.form_submit_button(label='✨ 執行新增')

# 這段程式碼只有在使用者點擊了 `submit_button` 之後才會被執行
if submit_button:
    # 將所有表單欄位的值，打包成一個字典，方便傳遞
    form_data = {
        'order_id': order_id,
        'product': product,
        'category': category,
        'return_reason': return_reason,
        'cost': cost,
        'approved_flag': approved_flag,
        'store_name': store_name
    }
    # 這就是「協調器」的邏輯：將打包好的資料交給 retrieval_agent 處理
    df, message = retrieval_agent.add_return_from_form(form_data)
    # 根據代理回傳的結果，顯示成功或失敗的訊息
    if df is not None:
        st.success(message)
    else:
        st.error(message)

# --- 介面佈局：產生報告區塊 ---
st.header("2. 產生報告 (由 Report Agent 處理)")
# `st.button` 是一個普通的按鈕，點擊後會立即觸發一次頁面刷新
if st.button("產生 Excel 報告"):
    # 協調器邏輯：將任務交給 report_agent 處理
    success, message = report_agent.generate_report()
    if success:
        st.success(message)
        # 如果報告成功產生，就提供一個下載按鈕
        with open("returns_summary.xlsx", "rb") as file: # "rb" 表示以二進位模式讀取檔案
            st.download_button("📥 點此下載報告", file, "returns_summary.xlsx")
    else:
        st.error(message)

# --- 介面佈局：顯示目前所有資料區塊 ---
st.header("3. 目前所有退貨紀錄")
# `st.dataframe` 可以將一個 pandas DataFrame 渲染成一個漂亮的互動式表格
st.dataframe(db.get_all_returns(), use_container_width=True)
