🤖 退貨與保固洞察 AI 代理系統
🚀 線上展示 (Live Demo)

我已經將這個專案部署上線，您可以透過以下連結直接與它互動：

點此前往線上展示

✨ 設計理念與核心功能

在這個專案中，我設計了一個由兩個核心代理組成的系統，它們各自負責不同的任務，並透過一個簡單的介面進行協調。

1. 檢索代理 (Retrieval Agent) - 資料庫的心臟

最初的題目提示是使用自然語言來新增資料，但我認為一個結構化的表單能帶來更好的使用者體驗，並且更重要的是，能從源頭確保資料品質，避免使用者輸入模稜兩可或不完整的內容。

我為這個代理實現了幾個關鍵功能：

自動化主鍵：
Order ID 由系統自動生成，會抓取資料庫中最新的訂單編號並加一，完全避免主鍵重複或無效的風險。

雲端資料來源：
應用程式啟動時，會自動從 Google Sheet 讀取資料，而不是依賴固定的本地 CSV 檔。只要更新 Google Sheet，應用程式重啟後就能抓到最新資料，無需重新部署。

前端驗證：
在送出前，系統會檢查輸入的基本格式，例如：產品名稱至少 2 個字元、店家名稱至少 2 個字元、成本必須大於 0。

🔧 新增的程式邏輯 (程式碼更新部分)

在最新的版本中，我對 檢索代理 (Retrieval Agent) 進行了幾個重要的優化與擴充：

雙重輸入模式

除了表單輸入外，新增了 自然語言輸入 (NLP) 模式。

使用者可以用一句話輸入退貨需求，系統會呼叫 Google Gemini API 自動解析成結構化資料，並寫入資料庫。

NLP 資料落地策略

缺漏欄位會自動補上預設值（數字 → 0.0，文字 → "Unknown"）。

NLP 新增的紀錄預設為 未批准 (approved_flag = No)，確保業務流程一致性。

非同步請求 (async/await)

使用 httpx.AsyncClient 搭配 async/await 呼叫 LLM API，避免阻塞 UI。

即時回饋機制

在 NLP 模式下，會先顯示 spinner「AI 正在解析中…」，完成後直接展示 AI 產生的 JSON 結果，讓使用者確認。

2. 報告代理 (Report Agent) - 商業洞察的窗口

這個代理的目標是提供快速的數據洞察。它會生成一份包含兩個工作表的 Excel 報告：

Summary (摘要)：提供高層次的關鍵指標 (KPIs)，例如總退貨成本、已批准的退貨比例等，讓管理者能快速掌握整體狀況。

Findings (詳細資料)：包含資料庫中完整的原始數據，供需要深入分析的使用者使用。

我認為這種雙層式的報告設計，能同時滿足快速瀏覽和深度挖掘兩種不同的需求。

🏗️ 系統架構圖
flowchart TD
    subgraph User["使用者"]
        A1["表單輸入"] --> C
        A2["自然語言輸入 (NLP)"] --> C
        A3["下載報告"] --> E
    end

    subgraph Coordinator["協調器 (Streamlit 前端)"]
        C["分派請求"]
    end

    subgraph RetrievalAgent["檢索代理 (Retrieval Agent)"]
        C --> B1["驗證 / NLP 解析"]
        B1 --> B2["SQLite 資料庫"]
        B2 --> B3["更新紀錄 / 回傳清單"]
    end

    subgraph ReportAgent["報告代理 (Report Agent)"]
        C --> D1["取得資料"]
        D1 --> D2["生成 Excel 報告"]
        D2 --> E["回傳下載連結"]
    end

🛠️ 我選擇的技術棧 (Tech Stack)

Streamlit：快速開發互動式前端。

Pandas：核心數據處理工具。

SQLite：輕量級檔案型資料庫，免安裝、內建於 Python。

📄 資料治理的思考

我另外撰寫了一份關於 資料治理與資料血緣 的文件，內容包含：

資料驗證規則

安全性考量

整個數據生命週期：從 Google Sheet → SQLite → Excel 報告

👉 文件位置：DATA_GOVERNANCE.md

⚙️ 在本地端執行

複製儲存庫

git clone https://github.com/Chuan-JenChen/python-agent-app.git
cd python-agent-app


安裝依賴套件

pip install -r requirements.txt


執行應用程式

streamlit run app.py

📤 推送到 GitHub

加入變更

git add .


建立 commit

git commit -m "Docs: Update README.md with NLP logic and system diagram"


推送到 GitHub

git push
