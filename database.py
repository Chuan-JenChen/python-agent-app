import sqlite3     
import pandas as pd     
from datetime import datetime 
DB_NAME = 'returns.db'

def init_db():
    """
    初始化資料庫。
    這個函數負責建立資料庫檔案，並在其中建立我們需要的 `returns` 表格。
    `IF NOT EXISTS` 語法可以確保如果表格已經存在，就不會重複建立而出錯。
    """
    # 連接到 SQLite 資料庫。如果檔案不存在，SQLite 會自動建立它。
    # `check_same_thread=False` 是一個重要的參數，它允許 Streamlit 這種多線程的網頁應用安全地存取同一個資料庫連線。
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    # 建立一個 'cursor' 物件，它就像是我們在資料庫中移動和操作的游標
    cursor = conn.cursor()
    # 執行 SQL 指令來建立表格，定義了所有欄位的名稱和資料型態
    # 加上 UNIQUE 關鍵字，讓資料庫層級來確保 order_id 不會重複，這是保護資料完整性的重要一步
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL UNIQUE,
            product TEXT NOT NULL,
            category TEXT,
            return_reason TEXT,
            cost REAL,
            approved_flag TEXT,
            store_name TEXT NOT NULL,
            date TEXT NOT NULL
        )
    ''')
    # 提交 (commit) 變更，將上述的 `CREATE TABLE` 操作永久寫入資料庫檔案
    conn.commit()
    # 關閉資料庫連線，這是一個好習慣，可以釋放資源
    conn.close()

def ingest_from_google_sheet():
    """
    從公開的 Google Sheet 連結讀取初始資料。
    這個函數只會在資料庫完全為空時執行，以避免使用者每次重整網頁時都重複載入資料。
    """
    # 這是可以直接下載 CSV 內容的特殊 Google Sheet 網址
    google_sheet_url = "https://docs.google.com/spreadsheets/d/1NN4bI9WJwvf6laA6C4bofZEoFMHRt_1-QvsPZLfhogc/export?format=csv"
    
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    # 檢查 `returns` 表格中目前有幾筆資料
    cursor.execute("SELECT COUNT(*) FROM returns")
    # `fetchone()` 會取得查詢結果的第一筆，`[0]` 則是取出這筆結果中的第一個值 (也就是資料的筆數)
    if cursor.fetchone()[0] == 0:
        try:
            # 如果資料庫是空的，就使用 pandas 直接從網路 URL 讀取 CSV 資料到一個 DataFrame 物件中
            df = pd.read_csv(google_sheet_url)
            # 使用 pandas 的 to_sql 功能，將整個 DataFrame 的內容快速寫入資料庫的 `returns` 表格
            df.to_sql('returns', conn, if_exists='append', index=False)
            print("資料庫為空，已成功從 Google Sheet 載入初始資料。")
        except Exception as e:
            # 如果讀取失敗 (例如網路問題或網址錯誤)，在後台印出錯誤訊息，方便除錯
            print(f"從 Google Sheet 讀取失敗: {e}")
    else:
        print("資料庫中已有資料，跳過初始載入。")
    conn.close()

def get_next_order_id():
    """
    查詢資料庫中最大的訂單編號，並回傳加一後的值，作為下一個可用的編號。
    這是實現訂單編號自動生成的關鍵函數。
    """
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    # 使用 MAX() SQL 函數來有效率地找到目前 `returns` 表格中 `order_id` 欄位的最大值
    cursor.execute("SELECT MAX(order_id) FROM returns")
    max_id = cursor.fetchone()[0]
    conn.close()
    
    # 處理特殊情況：如果資料庫是空的，MAX(order_id) 會回傳 None
    if max_id is None:
        # 我們讓第一個自動生成的編號從 1101 開始，以接續 Google Sheet 中的範例資料 (最大到 1100)
        return 1101
    else:
        # 如果資料庫中有資料，就回傳最大編號加一
        return max_id + 1

def add_return(product, category, return_reason, cost, approved_flag, store_name):
    """
    新增一筆退貨紀錄到資料庫，訂單編號由系統自動生成。
    注意這個函數的參數中已經沒有 order_id 了。
    """
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    
    # 在執行插入操作之前，先呼叫我們寫好的函數來取得下一個可用的訂單編號
    next_order_id = get_next_order_id()
    # 獲取當天的日期，並格式化成 'YYYY-MM-DD' 的字串
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    # 執行 SQL 的 INSERT 指令，將新資料插入 `returns` 表格
    # 使用 `?` 作為佔位符可以防止 SQL 注入攻擊，是一種安全的標準做法
    cursor.execute('''
        INSERT INTO returns (order_id, product, category, return_reason, cost, approved_flag, store_name, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (next_order_id, product, category, return_reason, cost, approved_flag, store_name, today_date))
    conn.commit()
    conn.close()
    # 回傳這次新增所使用的訂單編號，這樣前端介面才能顯示「成功新增訂單 XXX」的訊息
    return next_order_id

def get_all_returns():
    """
    從資料庫查詢並回傳所有的退貨紀錄。
    """
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    # 使用 pandas 的 read_sql_query，可以直接將 SQL 查詢的結果轉換成一個 DataFrame，非常方便
    df = pd.read_sql_query("SELECT * FROM returns", conn)
    conn.close()
    # 回傳包含所有資料的 DataFrame 物件
    return df