# 專案資料治理與資料血緣說明

本文件旨在說明此「退貨與保固洞察 AI 代理系統」專案中的資料治理 (Data Governance) 策略與資料血緣 (Data Lineage) 追蹤，以確保數據的品質、一致性、安全性與可追溯性。

---

## 1. 資料治理 (Data Governance)

資料治理是確保數據資產得到妥善管理的框架。在本專案中，我們透過以下幾個方面來實踐：

### a. 資料品質 (Data Quality)

我們透過在應用程式前端進行嚴格的**資料驗證 (Validation)** 來確保寫入資料庫的數據品質。

* **必填欄位檢查**：在 `app.py` 中，所有表單欄位都被視為必填，程式會檢查 `product`, `store_name`, `return_reason` 是否為空。
* **格式與 logique 驗證**：
    * `product` 和 `store_name` 必須至少包含 2 個字元。
    * `cost` 必須是大於 0 的數值。
* **錯誤提示**：任何不符合驗證規則的提交都會被阻擋，並在介面上向使用者顯示清晰的錯誤訊息，引導其修正。

### b. 資料一致性 (Data Consistency)

為了確保數據在整個系統中的一致性，我們採取了以下措施：

* **標準化輸入**：對於「產品類別 (Category)」和「是否批准 (Approved)」等欄位，我們使用 `st.selectbox` 下拉選單，限制使用者只能從預設的選項中選擇，避免了因手動輸入錯誤（如 "electronic" vs "Electronics"）造成的資料不一致。
* **主鍵 (Primary Key) 管理**：`order_id` 作為關鍵的業務主鍵，由系統**自動生成** (`MAX(order_id) + 1`)，使用者無法手動輸入。這從根本上杜絕了主鍵重複或亂填的風險。資料庫層級也為此欄位加上了 `UNIQUE` 限制，提供雙重保障。

### c. 資料安全與存取控制 (Data Security & Access)

* **最小權限原則**：
    * **資料來源**：應用程式連接的 Google Sheet 被設定為**公開檢視者 (Read-only)**。這意味著應用程式只有讀取初始資料的權限，絕無可能意外修改或刪除源頭數據。
    * **應用程式**：使用者透過介面只能執行兩種操作：**新增 (INSERT)** 和**讀取 (SELECT)**。沒有提供任何刪除 (DELETE) 或修改 (UPDATE) 現有紀錄的功能，確保了歷史數據的不可變性。

---

## 2. 資料血緣 (Data Lineage)

資料血緣追蹤了數據從來源到最終輸出的完整生命週期。本專案的資料流動路徑清晰明確，如下所示：

### a. 資料流動路徑

1.  **資料來源 (Source)**
    * **類型**：Google Sheet
    * **說明**：作為系統的初始資料集，定義了數據的基本結構和範例內容。

2.  **資料擷取 (Ingestion)**
    * **工具**：Python `pandas` 函式庫
    * **流程**：當應用程式首次啟動時，`database.py` 中的 `ingest_from_google_sheet()` 函數會被觸發，透過一個特殊的 `export?format=csv` 連結，將 Google Sheet 的內容讀取為一個 DataFrame。

3.  **資料儲存 (Storage)**
    * **工具**：SQLite 資料庫 (`returns.db`)
    * **流程**：擷取到的初始資料被寫入本地的 SQLite 資料庫中。後續所有由使用者透過表單新增的資料，也都會直接寫入此資料庫。

4.  **資料處理與轉換 (Processing & Transformation)**
    * **使用者輸入**：`app.py` 中的 Streamlit 表單提供了結構化的介面，讓使用者輸入新的退貨紀錄。
    * **代理處理**：`RetrievalAgent` 接收表單資料，並呼叫資料庫函數將其寫入 `returns` 表格。
    * **報告生成**：`ReportAgent` 從資料庫中讀取所有紀錄，使用 `pandas` 進行彙總計算（如計算總成本、已批准數量等），並將結果整理成兩個不同的 DataFrame（一個用於摘要，一個用於詳細資料）。

5.  **資料輸出 (Output)**
    * **類型**：Excel 報告 (`.xlsx`)
    * **流程**：`ReportAgent` 將處理好的兩個 DataFrame 寫入一個名為 `returns_summary.xlsx` 的 Excel 檔案的不同工作表 (Sheet) 中，作為最終的分析產出。

### b. 資料血緣視覺化圖

以下流程圖簡潔地展示了本專案的資料血緣：

```mermaid
graph TD
    A[來源: Google Sheet] -->|1. 擷取 (pandas.read_csv)| B(儲存: SQLite 資料庫 `returns.db`);
    C[使用者輸入: Streamlit 表單] -->|2. 新增 (RetrievalAgent)| B;
    B -->|3. 讀取 (ReportAgent)| D{處理: pandas 彙總計算};
    D -->|4. 輸出 (pandas.to_excel)| E[產出: Excel 報告 `returns_summary.xlsx`];