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

retrieval_agent = RetrievalAgent()
report_agent = ReportAgent()

# --- 介面佈局：新增退貨區塊 ---
st.header("1. 新增退貨紀錄 (由 Retrieval Agent 處理)")

# `st.form` 可以將多個輸入元件群組在一起。
# 只有當使用者點擊表單內的「送出」按鈕時，所有輸入的資料才會一次性地被送出。
# 這可以避免使用者每填一個欄位，頁面就刷新一次，提供更好的使用者體驗。
with st.form(key='add_return_form'):
    st.subheader("請填寫退貨詳細資訊")
    
    # 在表單載入時，就先呼叫資料庫函數取得下一個可用的訂單編號
    next_id = db.get_next_order_id()
    # 將編號顯示為不可編輯的文字，讓使用者知道即將新增的編號是多少
    st.markdown(f"**即將新增的訂單編號 (Order ID): `{next_id}`** (此編號由系統自動生成)")
    
    # `st.columns(2)` 將介面切分為左右兩欄，讓版面更緊湊、更美觀。
    col1, col2 = st.columns(2)
    
    # --- 左半邊的表單欄位 ---
    with col1:
        # `st.text_input` 建立一個文字輸入框
        product = st.text_input(
            "產品名稱 (Product)", 
            # `placeholder` 參數設定輸入框中的灰色提示文字
            placeholder="例如：無線充電板", 
            # `help` 參數設定當滑鼠停在元件上時，顯示的詳細說明
            help="請輸入完整的產品名稱"
        )
        # `st.selectbox` 建立一個下拉選單
        category = st.selectbox(
            "產品類別 (Category)", 
            options=['Electronics', 'Accessories', 'Unknown'], 
            index=1, # `index=1` 表示預設選中第二個選項 'Accessories'
            help="請從下拉選單中選擇產品類別"
        )
        # `st.number_input` 建立一個專門用來輸入數字的欄位
        cost = st.number_input(
            "成本 (Cost)", 
            min_value=0.0, # 設定允許的最小值
            value=0.0,     # 設定初始預設值
            format="%.2f", # 設定數字顯示的格式 (小數點後兩位)
            help="退貨成本必須大於 0"
        )

    # --- 右半邊的表單欄位 ---
    with col2:
        store_name = st.text_input(
            "店家名稱 (Store Name)", 
            placeholder="例如：台北信義店", 
            help="請輸入退貨的店家或平台名稱"
        )
        return_reason = st.text_input(
            "退貨原因 (Return Reason)", 
            placeholder="例如：商品有刮痕", 
            help="請簡要說明退貨原因"
        )
        approved_flag = st.selectbox(
            "是否批准 (Approved)", 
            options=['Yes', 'No'], 
            index=1, 
            help="請選擇這筆退貨是否已被批准"
        )
    
    # `st.form_submit_button` 是表單專用的送出按鈕
    submit_button = st.form_submit_button(label='✨ 執行新增')

# 這段程式碼只有在使用者點擊了 `submit_button` 之後才會被執行
if submit_button:
    # --- 資料驗證 (Validation) ---
    # 建立一個空的列表，用來收集所有驗證失敗的錯誤訊息
    error_messages = []

    # 驗證規則 1：產品名稱長度
    # `.strip()` 會移除字串前後的空白，避免使用者只輸入空格
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
    # 如果 `error_messages` 列表是空的，代表所有驗證都通過
    if not error_messages:
        # 將所有表單欄位的值，打包成一個字典，方便傳遞
        form_data = {
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
    else:
        # 如果有任何錯誤，就將所有錯誤訊息用 `st.error` 一次性顯示出來
        # `\n\n- ` 和 `"\n- ".join()` 是用來美化輸出的格式
        st.error("資料驗證失敗，請修正以下問題：\n\n- " + "\n- ".join(error_messages))

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
