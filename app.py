# 檔案 1: database.py (無需修改)
# ... (請保持您現有的 database.py 內容不變)

# 檔案 2: app.py (整合 NLP 功能的最終版本)
# ----------------------------------------------------
import streamlit as st
import pandas as pd
import database as db
import json # 用於處理從 AI 模型回傳的 JSON 格式資料
import asyncio # 用於處理非同步操作

# --- 代理定義 (Agent Definitions) ---

class RetrievalAgent:
    def add_return_from_form(self, form_data: dict):
        """從結構化的表單資料中，新增一筆退貨紀錄。"""
        try:
            new_order_id = db.add_return(
                product=form_data['product'],
                category=form_data['category'],
                return_reason=form_data['return_reason'],
                cost=form_data['cost'],
                approved_flag=form_data['approved_flag'],
                store_name=form_data['store_name']
            )
            return db.get_all_returns(), f"成功新增訂單 {new_order_id} 的退貨紀錄。"
        except Exception as e:
            return None, f"新增失敗：{e}"

    # <<< 新增：處理自然語言的函數 >>>
    async def add_return_from_nlp(self, user_prompt: str):
        """
        使用 LLM 解析自然語言，抽取出結構化資料後，新增一筆退貨紀錄。
        """
        # 步驟 1: 呼叫 LLM 進行資訊抽取
        st.info("🤖 正在呼叫 AI 模型解析您的指令...")
        
        # 定義我們希望 AI 回傳的 JSON 結構，這能讓 AI 的輸出更穩定
        json_schema = {
            "type": "OBJECT",
            "properties": {
                "product": {"type": "STRING"},
                "store_name": {"type": "STRING"},
                "cost": {"type": "NUMBER"},
                "return_reason": {"type": "STRING"},
            },
        }

        # 建立一個強力的提示 (Prompt)，告訴 AI 它的任務、目標以及輸出格式
        prompt_for_llm = f"""
        You are an intelligent assistant that extracts information from user text for a return management system.
        From the following user's return request, extract the product name, store name, cost, and return reason.
        If a piece of information is not present, use a default value. For cost, default to 0.0. For other string values, default to "Unknown".
        
        User request: "{user_prompt}"
        """
        
        try:
            # 建立 Gemini API 的請求內容
            chat_history = [{"role": "user", "parts": [{"text": prompt_for_llm}]}]
            payload = {
                "contents": chat_history,
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": json_schema,
                },
            }
            
            # <<< 修改開始：使用 st.secrets 安全地讀取 API 金鑰 >>>
            # 程式碼中不再包含任何敏感資訊。
            # 我們從 Streamlit 的秘密管理系統中，讀取一個名為 "GEMINI_API_KEY" 的金鑰。
            # 您需要在 Streamlit Cloud 的設定頁面中設定這個金鑰。
            api_key = st.secrets["GEMINI_API_KEY"]
            # <<< 修改結束 >>>

            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"
            
            # 使用 Streamlit 內建的非同步 HTTP 客戶端發送請求
            async with st.spinner('AI 正在解析中...'):
                response = await st.runtime.http.post(api_url, json=payload)
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

            # 步驟 2: 使用抽取出的資訊，新增退貨紀錄
            # 為表單中沒有的欄位提供預設值
            new_order_id = db.add_return(
                product=extracted_data.get('product', 'Unknown'),
                category='Unknown', # NLP 目前無法判斷類別，給予預設值
                return_reason=extracted_data.get('return_reason', 'From NLP'),
                cost=float(extracted_data.get('cost', 0.0)),
                approved_flag='No', # 透過 NLP 新增的紀錄，預設為未批准
                store_name=extracted_data.get('store_name', 'Unknown')
            )
            return db.get_all_returns(), f"透過自然語言成功新增訂單 {new_order_id} 的退貨紀錄。"

        except Exception as e:
            # 增加一個更明確的錯誤提示，方便除錯
            if "GEMINI_API_KEY" in str(e):
                st.error("錯誤：找不到 GEMINI_API_KEY。請確認您已在 Streamlit Cloud 的設定中新增了此秘密金鑰。")
                return None, "API 金鑰設定錯誤。"
            return None, f"處理自然語言指令時發生錯誤：{e}"
    # <<< 新增結束 >>>


class ReportAgent:
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

# --- 主函數，使用 async def 來支援非同步操作 ---
async def main():
    st.set_page_config(page_title="退貨洞察系統", layout="wide")
    st.title("🤖 退貨與保固洞察 AI 代理系統")

    if 'initialized' not in st.session_state:
        db.init_db()
        db.ingest_from_google_sheet()
        st.session_state.initialized = True
        st.toast("資料庫已準備就緒！")

    retrieval_agent = RetrievalAgent()
    report_agent = ReportAgent()

    # --- 新增一個分頁 (Tab) 介面，讓使用者可以選擇輸入方式 ---
    tab1, tab2 = st.tabs(["🗂️ 表單輸入 (建議)", "💬 自然語言輸入 (NLP)"])

    # --- Tab 1: 結構化表單輸入 ---
    with tab1:
        st.header("1. 新增退貨紀錄 (結構化表單)")
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

        if submit_button:
            error_messages = []
            if len(product.strip()) < 2: error_messages.append("產品名稱至少需要 2 個字元。")
            if len(store_name.strip()) < 2: error_messages.append("店家名稱至少需要 2 個字元。")
            if len(return_reason.strip()) == 0: error_messages.append("請填寫退貨原因。")
            if cost <= 0.0: error_messages.append("成本必須大於 0。")

            if not error_messages:
                form_data = {'product': product, 'category': category, 'return_reason': return_reason, 'cost': cost, 'approved_flag': approved_flag, 'store_name': store_name}
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
                # 呼叫新的非同步函數
                df, message = await retrieval_agent.add_return_from_nlp(nlp_prompt)
                if df is not None: st.success(message)
                else: st.error(message)
            else:
                st.warning("請輸入更詳細的退貨描述。")

    # --- 報告和資料顯示區塊 (共用) ---
    st.header("2. 產生報告 (由 Report Agent 處理)")
    if st.button("產生 Excel 報告"):
        success, message = report_agent.generate_report()
        if success:
            st.success(message)
            with open("returns_summary.xlsx", "rb") as file:
                st.download_button("� 點此下載報告", file, "returns_summary.xlsx")
        else:
            st.error(message)

    st.header("3. 目前所有退貨紀錄")
    st.dataframe(db.get_all_returns(), use_container_width=True)

# --- 程式進入點 ---
if __name__ == "__main__":
    # 使用 asyncio.run() 來啟動我們的非同步主函數
    asyncio.run(main())
�