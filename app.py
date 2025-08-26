import streamlit as st      
import pandas as pd       
import database as db      
import json               
import asyncio             
import httpx                

class RetrievalAgent:
    """
    負責處理資料的存取。
    它有兩種新增資料的方式：從結構化表單，或從自然語言。
    """
    def add_return_from_form(self, form_data: dict):
        """
        從一個包含結構化表單資料的字典 (dictionary) 中，新增一筆退貨紀錄。
        :param form_data: 一個字典，鍵 (key) 是欄位名稱，值 (value) 是使用者輸入的內容。
        :return: 一個包含 (DataFrame, message) 的元組 (tuple)。
        """
        try:
            # 呼叫 database.py 中的 add_return 函數，將表單資料傳遞過去
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

    # `async def` 定義了一個非同步函數。這意味著當這個函數執行到需要等待的操作 (例如網路請求) 時，
    # 它可以暫時將控制權交還給主程式，讓主程式可以繼續處理其他事情 (例如保持介面流暢)，而不會整個卡住。
    async def add_return_from_nlp(self, user_prompt: str):
        """
        使用 LLM 解析自然語言，抽取出結構化資料後，新增一筆退貨紀錄。
        這是一個非同步函數，因為它需要等待 AI 模型的回應。
        """
        st.info("🤖 正在呼叫 AI 模型解析您的指令...")
        
        # 定義我們希望 AI 回傳的 JSON 結構。
        # 這麼做可以讓 AI 的輸出更穩定、更可預測，而不是隨意回傳一段文字。
        json_schema = {
            "type": "OBJECT",
            "properties": {
                "product": {"type": "STRING"},
                "store_name": {"type": "STRING"},
                "cost": {"type": "NUMBER"},
                "return_reason": {"type": "STRING"},
            },
        }

        # 建立一個強力的提示 (Prompt Engineering)。
        # 這個提示清楚地告訴 AI 它的角色、任務、輸入是什麼，以及在資訊不完整時該怎麼做。
        prompt_for_llm = f"""
        You are an intelligent assistant that extracts information from user text for a return management system.
        From the following user's return request, extract the product name, store name, cost, and return reason.
        If a piece of information is not present, use a default value. For cost, default to 0.0. For other string values, default to "Unknown".
        
        User request: "{user_prompt}"
        """
        
        try:
            # 準備要發送給 Gemini API 的請求內容 (payload)
            chat_history = [{"role": "user", "parts": [{"text": prompt_for_llm}]}]
            payload = {
                "contents": chat_history,
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": json_schema,
                },
            }
            
            # 使用 st.secrets 安全地讀取 API 金鑰。
            # 程式碼中不再包含任何敏感資訊。
            api_key = st.secrets.get("GEMINI_API_KEY")
            # 檢查是否成功讀取到金鑰，如果沒有，就顯示錯誤訊息並提前結束
            if not api_key:
                st.error("錯誤：找不到 GEMINI_API_KEY。請確認您已在 Streamlit 的秘密管理中設定了此金鑰。")
                return None, "API 金鑰設定錯誤。"

            # 組合出完整的 API 請求網址
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"
            
            # `st.spinner` 會在介面上顯示一個「載入中」的動畫，提升使用者體驗
            with st.spinner('AI 正在解析中...'):
                # `async with httpx.AsyncClient() as client:` 建立一個非同步的 HTTP 客戶端
                async with httpx.AsyncClient() as client:
                    # `await client.post(...)` 是真正執行非同步網路請求的地方。
                    # `await` 關鍵字會讓程式在這裡暫停，直到收到網路回應，但不會卡住整個應用程式。
                    response = await client.post(api_url, json=payload, timeout=60)
                
                # 檢查 HTTP 狀態碼，如果不是 2xx (例如 400, 500)，就會自動拋出一個錯誤
                response.raise_for_status() 
                result = response.json()

            # 檢查並解析 API 回應
            if 'candidates' in result and result['candidates']:
                extracted_text = result['candidates'][0]['content']['parts'][0]['text']
                extracted_data = json.loads(extracted_text)
                st.success("✅ AI 解析完成！以下是從您的句子中抽取的資訊：")
                st.json(extracted_data) # 在介面上顯示 AI 解析出的結果，讓使用者確認
            else:
                error_message = result.get('error', {}).get('message', '未知錯誤')
                st.error(f"AI 模型回應錯誤: {error_message}")
                return None, "AI 模型解析失敗。"

            # 使用 AI 抽取出的資訊，呼叫資料庫函數新增紀錄
            new_order_id = db.add_return(
                product=extracted_data.get('product', 'Unknown'),
                category='Unknown', # NLP 目前無法判斷類別，給予預設值
                return_reason=extracted_data.get('return_reason', 'From NLP'),
                cost=float(extracted_data.get('cost', 0.0)),
                approved_flag='No', # 透過 NLP 新增的紀錄，預設為未批准
                store_name=extracted_data.get('store_name', 'Unknown')
            )
            return db.get_all_returns(), f"透過自然語言成功新增訂單 {new_order_id} 的退貨紀錄。"

        except httpx.HTTPStatusError as http_err:
            # 專門處理網路請求失敗的錯誤，並顯示更詳細的錯誤訊息
            st.error(f"呼叫 AI 模型時發生網路錯誤：{http_err.response.status_code} - {http_err.response.text}")
            return None, "呼叫 AI 模型失敗。"
        except Exception as e:
            # 處理所有其他可能的錯誤
            return None, f"處理自然語言指令時發生錯誤：{e}"

class ReportAgent:
    """
    負責產生 Excel 報告。
    """
    def generate_report(self):
        try:
            all_returns = db.get_all_returns()
            if all_returns.empty: return False, "資料庫中沒有任何紀錄可供報告。"
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

# `async def main()`: 我們將主程式也定義為非同步，這樣才能在裡面使用 `await` 關鍵字
async def main():
    # 設定網頁的標題和佈局
    st.set_page_config(page_title="退貨洞察系統", layout="wide")
    st.title("🤖 退貨與保固洞察 AI 代理系統")

    # 使用 `st.session_state` 來確保初始化動作只在網頁第一次載入時執行
    if 'initialized' not in st.session_state:
        db.init_db()
        db.ingest_from_google_sheet()
        st.session_state.initialized = True
        st.toast("資料庫已準備就緒！")

    # 建立兩個代理的實例 (物件)
    retrieval_agent = RetrievalAgent()
    report_agent = ReportAgent()

    # `st.tabs` 建立一個分頁介面，讓使用者可以在不同功能之間切換
    tab1, tab2 = st.tabs(["🗂️ 表單輸入 (建議)", "💬 自然語言輸入 (NLP)"])

    # --- Tab 1: 結構化表單輸入 ---
    with tab1:
        st.header("1. 新增退貨紀錄 (結構化表單)")
        # `st.form` 可以將多個輸入元件群組在一起，提升使用者體驗
        with st.form(key='add_return_form'):
            st.subheader("請填寫退貨詳細資訊")
            next_id = db.get_next_order_id()
            st.markdown(f"**即將新增的訂單編號 (Order ID): `{next_id}`** (此編號由系統自動生成)")
            col1, col2 = st.columns(2)
            with col1:
                product = st.text_input("產品名稱", placeholder="例如：無線充電板")
                category = st.selectbox("產品類別", options=['Electronics', 'Accessories', 'Unknown'], index=1)
                cost = st.number_input("成本", min_value=0.0, value=0.0, format="%.2f")
            with col2:
                store_name = st.text_input("店家名稱", placeholder="例如：台北信義店")
                return_reason = st.text_input("退貨原因", placeholder="例如：商品有刮痕")
                approved_flag = st.selectbox("是否批准", options=['Yes', 'No'], index=1)
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
                form_data = {'product': product, 'category': category, 'return_reason': return_reason, 'cost': cost, 'approved_flag': approved_flag, 'store_name': store_name}
                # 協調器邏輯：將打包好的資料交給 retrieval_agent 處理
                df, message = retrieval_agent.add_return_from_form(form_data)
                if df is not None: st.success(message)
                else: st.error(message)
            else:
                st.error("資料驗證失敗，請修正以下問題：\n\n- " + "\n- ".join(error_messages))

    # --- Tab 2: 自然語言輸入 ---
    with tab2:
        st.header("1. 新增退貨紀錄 (自然語言)")
        st.info("您可以嘗試用一句話描述退貨資訊，AI 會自動為您解析。")
        nlp_prompt = st.text_area("輸入您的退貨指令：", 
                                  "我想要退一個在台北信義店買的無線充電板，價格是 25.5 元，因為上面有刮痕。")
        if st.button("透過 AI 新增", key="nlp_add"):
            if len(nlp_prompt.strip()) > 10:
                # 協調器邏輯：呼叫 retrieval_agent 的非同步方法來處理 NLP
                # `await` 關鍵字表示我們需要等待這個非同步函數完成
                df, message = await retrieval_agent.add_return_from_nlp(nlp_prompt)
                if df is not None: st.success(message)
                else: st.error(message)
            else:
                st.warning("請輸入更詳細的退貨描述。")

    # --- 報告和資料顯示區塊 (兩個分頁共用) ---
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

if __name__ == "__main__":
    asyncio.run(main())