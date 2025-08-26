import streamlit as st
import pandas as pd
import database as db  # 你自己的資料庫模組：提供 init_db/ingest_from_google_sheet/get_all_returns/add_return/get_next_order_id
import json
import asyncio
import httpx  # 用於非同步 HTTP 呼叫（打 Google Gemini API）

# --- 代理定義 (Agent Definitions) ---

class RetrievalAgent:
    def add_return_from_form(self, form_data: dict):
        """
        從『結構化表單』來新增退貨紀錄。
        邏輯：
          1) 呼叫 db.add_return(...) 寫入資料庫
          2) 回傳最新所有退貨資料（DataFrame）與成功訊息
        """
        try:
            new_order_id = db.add_return(
                product=form_data['product'],
                category=form_data['category'],
                return_reason=form_data['return_reason'],
                cost=form_data['cost'],
                approved_flag=form_data['approved_flag'],
                store_name=form_data['store_name']
            )
            # 新增成功後，取回資料庫目前全部退貨紀錄
            return db.get_all_returns(), f"成功新增訂單 {new_order_id} 的退貨紀錄。"
        except Exception as e:
            # 任一錯誤都會回傳 None + 錯誤訊息，方便上層顯示
            return None, f"新增失敗：{e}"

    async def add_return_from_nlp(self, user_prompt: str):
        """
        使用 LLM（Google Gemini）從自然語言句子抽取結構化欄位，再寫入資料庫。
        邏輯：
          1) 準備 JSON Schema（告訴模型要哪些欄位、型別）
          2) 組合提示詞，請模型輸出 JSON 格式
          3) 以 httpx.AsyncClient 發 POST 到 Gemini generateContent API
          4) 解析模型回傳，轉成 dict
          5) 將抽取到的資料寫入資料庫（缺資料就用預設值）
          6) 回傳所有退貨資料與訊息
        """
        st.info("🤖 正在呼叫 AI 模型解析您的指令...")

        # 要求模型輸出的資料「欄位與型別」定義
        json_schema = {
            "type": "OBJECT",
            "properties": {
                "product": {"type": "STRING"},
                "store_name": {"type": "STRING"},
                "cost": {"type": "NUMBER"},
                "return_reason": {"type": "STRING"},
            },
        }

        # 讓模型知道：若缺值要用預設（cost=0.0，其他字串="Unknown"）
        prompt_for_llm = f"""
        You are an intelligent assistant that extracts information from user text for a return management system.
        From the following user's return request, extract the product name, store name, cost, and return reason.
        If a piece of information is not present, use a default value. For cost, default to 0.0. For other string values, default to "Unknown".
        
        User request: "{user_prompt}"
        """

        try:
            # Google Generative Language API 的 payload 結構
            chat_history = [{"role": "user", "parts": [{"text": prompt_for_llm}]}]
            payload = {
                "contents": chat_history,
                "generationConfig": {
                    "responseMimeType": "application/json",  # 要求回傳 JSON
                    "responseSchema": json_schema,           # 並套用我們的 schema
                },
            }

            # 讀取 Streamlit secrets 中的 GEMINI_API_KEY
            api_key = st.secrets.get("GEMINI_API_KEY")
            if not api_key:
                st.error("錯誤：找不到 GEMINI_API_KEY。請確認您已在 Streamlit 的秘密管理中設定了此金鑰。")
                return None, "API 金鑰設定錯誤。"

            # 指向 Gemini 2.5 flash preview 的 generateContent 端點
            api_url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "gemini-2.5-flash-preview-05-20:generateContent"
                f"?key={api_key}"
            )

            # 用 spinner 給使用者「模型正在處理」的即時回饋
            # 注意：with st.spinner(...) 區塊內可以做 await 的 I/O
            with st.spinner('AI 正在解析中...'):
                # 非同步 client：避免阻塞 UI 執行緒
                async with httpx.AsyncClient() as client:
                    # 發送 POST，timeout 設 60 秒
                    response = await client.post(api_url, json=payload, timeout=60)

                # 若 HTTP 非 2xx，raise_for_status 會拋出 httpx.HTTPStatusError
                response.raise_for_status()
                result = response.json()

            # 依照 Google API 的回傳格式抓取第一個候選的文字內容
            if 'candidates' in result and result['candidates']:
                extracted_text = result['candidates'][0]['content']['parts'][0]['text']
                # 這裡期望是「純 JSON 字串」，因此直接 json.loads
                extracted_data = json.loads(extracted_text)

                # 把抽取出來的欄位顯示給使用者看（方便確認）
                st.success("✅ AI 解析完成！以下是從您的句子中抽取的資訊：")
                st.json(extracted_data)
            else:
                # 若沒有 candidates，從 error 欄位撈錯誤訊息（若有）
                error_message = result.get('error', {}).get('message', '未知錯誤')
                st.error(f"AI 模型回應錯誤: {error_message}")
                return None, "AI 模型解析失敗。"

            # 將抽取資料落地到資料庫（缺項目採預設值）
            new_order_id = db.add_return(
                product=extracted_data.get('product', 'Unknown'),
                category='Unknown',  # NLP 端目前未抽取類別，先固定 Unknown
                return_reason=extracted_data.get('return_reason', 'From NLP'),
                cost=float(extracted_data.get('cost', 0.0)),
                approved_flag='No',  # 透過 NLP 新增預設未批准
                store_name=extracted_data.get('store_name', 'Unknown')
            )

            # 寫入後回傳最新資料表與訊息
            return db.get_all_returns(), f"透過自然語言成功新增訂單 {new_order_id} 的退貨紀錄。"

        except httpx.HTTPStatusError as http_err:
            # API 回覆非 2xx 時的錯誤處理：把狀態碼與回應內文帶出
            st.error(f"呼叫 AI 模型時發生網路錯誤：{http_err.response.status_code} - {http_err.response.text}")
            return None, "呼叫 AI 模型失敗。"
        except Exception as e:
            # 其他錯誤（例如 JSON 解析失敗）集中處理
            return None, f"處理自然語言指令時發生錯誤：{e}"

class ReportAgent:
    def generate_report(self):
        """
        產生 Excel 報告（returns_summary.xlsx）。
        邏輯：
          1) 取出所有退貨資料 DataFrame
          2) Summary 工作表：總筆數/獨立店家數/已批准數/總成本
          3) Findings 工作表：完整明細
        """
        try:
            all_returns = db.get_all_returns()
            if all_returns.empty:
                return False, "資料庫中沒有任何紀錄可供報告。"

            # 用 openpyxl 引擎寫 Excel；with 區塊會自動關檔
            with pd.ExcelWriter('returns_summary.xlsx', engine='openpyxl') as writer:
                total_cost = all_returns['cost'].sum()
                approved_returns = all_returns[all_returns['approved_flag'] == 'Yes']

                # 建一張簡單的摘要表
                summary_df = pd.DataFrame({
                    '項目': ['總退貨筆數', '獨立店家數量', '已批准退貨數', '總退貨成本'],
                    '數值': [
                        len(all_returns),
                        all_returns['store_name'].nunique(),
                        len(approved_returns),
                        f"${total_cost:,.2f}"
                    ]
                })
                summary_df.to_excel(writer, sheet_name='Summary', index=False)

                # 明細全丟到 Findings
                all_returns.to_excel(writer, sheet_name='Findings', index=False)

            return True, "報告 'returns_summary.xlsx' 已成功產生！"
        except Exception as e:
            return False, f"報告產生失敗：{e}"

async def main():
    """
    Streamlit 主流程（這裡寫成 async，方便 await NLP 的非同步函式）。
    邏輯：
      1) 設定頁面 → 首次載入做 DB 初始化與 seed 資料匯入
      2) 建立兩個分頁：表單輸入 / 自然語言輸入
      3) 下方提供『產生報告』按鈕與『目前資料』表格
    """
    st.set_page_config(page_title="退貨洞察系統", layout="wide")
    st.title("🤖 退貨與保固洞察 AI 代理系統")

    # 只在第一次載入時 init + ingest，避免每次重繪都重置資料
    if 'initialized' not in st.session_state:
        db.init_db()                   # 建立資料表（若不存在）
        db.ingest_from_google_sheet()  # 從 Google Sheet 匯入初始 CSV/資料
        st.session_state.initialized = True
        st.toast("資料庫已準備就緒！")

    retrieval_agent = RetrievalAgent()
    report_agent = ReportAgent()

    # 分頁：表單/自然語言
    tab1, tab2 = st.tabs(["🗂️ 表單輸入 (建議)", "💬 自然語言輸入 (NLP)"])

    # -------------------------
    # 分頁 1：表單新增
    # -------------------------
    with tab1:
        st.header("1. 新增退貨紀錄 (結構化表單)")

        # form：把多個輸入與送出按鈕綁在一起；按下才提交
        with st.form(key='add_return_form'):
            st.subheader("請填寫退貨詳細資訊")
            next_id = db.get_next_order_id()  # 取得下一個自動編號（給使用者參考）
            st.markdown(f"**即將新增的訂單編號 (Order ID): `{next_id}`** (此編號由系統自動生成)")

            # 左右兩欄排版
            col1, col2 = st.columns(2)
            with col1:
                product = st.text_input("產品名稱", placeholder="例如：無線充電板")
                category = st.selectbox("產品類別", options=['Electronics', 'Accessories', 'Unknown'], index=1)
                cost = st.number_input("成本", min_value=0.0, value=0.0, format="%.2f")
            with col2:
                store_name = st.text_input("店家名稱", placeholder="例如：台北信義店")
                return_reason = st.text_input("退貨原因", placeholder="例如：商品有刮痕")
                approved_flag = st.selectbox("是否批准", options=['Yes', 'No'], index=1)

            # 送出鈕：觸發 form 的提交
            submit_button = st.form_submit_button(label='✨ 執行新增')

        # 提交後的伺服器端驗證（基本欄位檢查）
        if submit_button:
            error_messages = []
            if len(product.strip()) < 2: error_messages.append("產品名稱至少需要 2 個字元。")
            if len(store_name.strip()) < 2: error_messages.append("店家名稱至少需要 2 個字元。")
            if len(return_reason.strip()) == 0: error_messages.append("請填寫退貨原因。")
            if cost <= 0.0: error_messages.append("成本必須大於 0。")

            if not error_messages:
                # 打包成 dict 給 RetrievalAgent
                form_data = {
                    'product': product,
                    'category': category,
                    'return_reason': return_reason,
                    'cost': cost,
                    'approved_flag': approved_flag,
                    'store_name': store_name
                }
                df, message = retrieval_agent.add_return_from_form(form_data)
                if df is not None:
                    st.success(message)
                else:
                    st.error(message)
            else:
                # 顯示所有驗證錯誤
                st.error("資料驗證失敗，請修正以下問題：\n\n- " + "\n- ".join(error_messages))

    # -------------------------
    # 分頁 2：自然語言新增
    # -------------------------
    with tab2:
        st.header("1. 新增退貨紀錄 (自然語言)")
        st.info("您可以嘗試用一句話描述退貨資訊，AI 會自動為您解析。")

        # 讓使用者輸入自然語言描述
        nlp_prompt = st.text_area(
            "輸入您的退貨指令：",
            "我想要退一個在台北信義店買的無線充電板，價格是 25.5 元，因為上面有刮痕。"
        )

        # 點下按鈕後，呼叫 NLP 解析 → 寫入 DB
        if st.button("透過 AI 新增", key="nlp_add"):
            if len(nlp_prompt.strip()) > 10:
                # 呼叫非同步函式（await）
                df, message = await retrieval_agent.add_return_from_nlp(nlp_prompt)
                if df is not None:
                    st.success(message)
                else:
                    st.error(message)
            else:
                st.warning("請輸入更詳細的退貨描述。")

    # -------------------------
    # 產生報告（ReportAgent）
    # -------------------------
    st.header("2. 產生報告 (由 Report Agent 處理)")
    if st.button("產生 Excel 報告"):
        success, message = report_agent.generate_report()
        if success:
            st.success(message)
            # 產生成功就提供下載鈕（讀檔並回傳）
            with open("returns_summary.xlsx", "rb") as file:
                st.download_button("📥 點此下載報告", file, "returns_summary.xlsx")
        else:
            st.error(message)

    # -------------------------
    # 目前所有退貨紀錄（即時預覽）
    # -------------------------
    st.header("3. 目前所有退貨紀錄")
    st.dataframe(db.get_all_returns(), use_container_width=True)

if __name__ == "__main__":
    asyncio.run(main())