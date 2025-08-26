# database.py
import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = 'returns.db'

def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL, product TEXT NOT NULL, category TEXT,
            return_reason TEXT, cost REAL, approved_flag TEXT,
            store_name TEXT NOT NULL, date TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def ingest_from_google_sheet():
    google_sheet_url = "https://docs.google.com/spreadsheets/d/1NN4bI9WJwvf6laA6C4bofZEoFMHRt_1-QvsPZLfhogc/export?format=csv"
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM returns")
    if cursor.fetchone()[0] == 0:
        try:
            df = pd.read_csv(google_sheet_url)
            df.to_sql('returns', conn, if_exists='append', index=False)
            print("資料庫為空，已從 Google Sheet 載入初始資料。")
        except Exception as e:
            print(f"從 Google Sheet 讀取失敗: {e}")
    else:
        print("資料庫中已有資料，跳過初始載入。")
    conn.close()

def add_return(order_id, product_name, store_name):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()
    today_date = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        INSERT INTO returns (order_id, product, category, return_reason, cost, approved_flag, store_name, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (order_id, product_name, 'Unknown', 'Added via Agent', 0.0, 'No', store_name, today_date))
    conn.commit()
    conn.close()

def get_all_returns():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM returns", conn)
    conn.close()
    return df
