import sqlite3  # Python 內建的 SQLite 資料庫介面
import pandas as pd  # 用於數據處理，特別是讀取 CSV 和操作 DataFrame
from datetime import datetime  # 用於獲取當前日期

# 定義資料庫檔案的名稱，方便統一管理
DB_NAME = 'returns.db'

def init_db():
    """
    初始化資料庫。
    這個函數負責建立資料庫檔案，並在其中建立我們需要的 `returns` 表格。
    `IF NOT EXISTS` 語法可以確保如果表格已經存在，就不會重複建立而出錯。
    """
    # 連接到 SQLite 資料庫。如果檔案不存在，SQLite 會自動建立它。
    # `check_same_thread=False` 是為了讓 Streamlit 這種多線程的網頁應用能安全地存取資料庫。
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    # 建立一個 'cursor' 物件，用來執行 SQL 指令
    cursor = conn.cursor()
    # 執行 SQL 指令來建立表格，定義了所有欄位的名稱和資料型態
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product TEXT NOT NULL,
            category TEXT,
            return_reason TEXT,
            cost REAL, -- REAL 型態用來儲存浮點數 (有小數點的數字)
            approved_flag TEXT,
            store_name TEXT NOT NULL,
            date TEXT NOT NULL
        )
    ''')
    # 提交 (commit) 變更，將上述操作永久寫入資料庫
    conn.commit()
    # 關閉資料庫連線，釋放資源
    conn.close()

def ingest_from_google_sheet():
    """
    從公開的 Google Sheet 連結讀取初始資料。
    這個函數只會在資料庫完全為空時執行，以避免重複載入資料。
    """
    # 這是可以直接下載 CSV 內容的特殊 Google Sheet 網址
    google_sheet_url = "https://docs.google.com/spreadsheets/d/1NN4bI9WJwvf6laA6C4bofZEoFMHRt_1-QvsPZLfhogc/export?format=csv"
    
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    # 檢查 `returns` 表格中目前有幾筆資料
    cursor.execute("SELECT COUNT(*) FROM returns")
    # `fetchone()` 會取得查詢結果的第一筆，`[0]` 則是取出這筆結果中的第一個值 (也就是數量)
    if cursor.fetchone()[0] == 0:
        try:
            # 如果資料庫是空的，就使用 pandas 直接從網路 URL 讀取 CSV 資料
            df = pd.read_csv(google_sheet_url)
            # 使用 pandas 的 to_sql 功能，將整個 DataFrame 的內容快速寫入資料庫的 `returns` 表格
            # `if_exists='append'` 表示如果表格已存在，就將資料附加在後面
            # `index=False` 表示不要將 DataFrame 的索引 (0, 1, 2...) 寫入資料庫
            df.to_sql('returns', conn, if_exists='append', index=False)
            print("資料庫為空，已從 Google Sheet 載入初始資料。")
        except Exception as e:
            # 如果讀取失敗 (例如網路問題或網址錯誤)，印出錯誤訊息
            print(f"從 Google Sheet 讀取失敗: {e}")
    else:
        print("資料庫中已有資料，跳過初始載入。")
    conn.close()

def add_return(order_id, product, category, return_reason, cost, approved_flag, store_name):
    """
    新增一筆包含所有詳細資訊的退貨紀錄到資料庫。
    這個函數接收所有必要的欄位作為參數。
    """
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    # 獲取當天的日期，並格式化成 'YYYY-MM-DD' 的字串
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    # 執行 SQL 的 INSERT 指令，將新資料插入 `returns` 表格
    # 使用 `?` 作為佔位符可以防止 SQL 注入攻擊，是安全的做法
    cursor.execute('''
        INSERT INTO returns (order_id, product, category, return_reason, cost, approved_flag, store_name, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (order_id, product, category, return_reason, cost, approved_flag, store_name, today_date))
    conn.commit()
    conn.close()

def get_all_returns():
    """
    從資料庫查詢並回傳所有的退貨紀錄。
    """
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    # 使用 pandas 的 read_sql_query，可以直接將 SQL 查詢的結果轉換成一個 DataFrame，非常方便
    df = pd.read_sql_query("SELECT * FROM returns", conn)
    conn.close()
    # 回傳包含所有資料的 DataFrame
    return df