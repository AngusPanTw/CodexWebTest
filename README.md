# 台股資料擷取專案

本專案示範如何從台灣證券交易所下載每日交易資料並進行比較分析。
程式會以 Big5/CP950 編碼處理 CSV 檔案並過濾無效資料，亦考量個股在特定日期可能無交易的情況。

## 專案需求
- 下載台灣證券交易所每日股票資料
- 擷取兩個時間區間的資料：
  1. 2025 年 4 月 7 日起（川普宣布關稅執行後）至 6 月 5 日的所有交易日
- 找出 5 月 26 日至 6 月 5 日期間仍然跌破先前低點的股票
- 處理中文編碼 (Big5/CP950)，並過濾無效資料

## 資料來源
- 下載網址: `https://www.twse.com.tw/exchangeReport/MI_INDEX?response=csv&date=YYYYMMDD&type=ALL`
- 檔案格式: CSV
- 預設編碼: Big5/CP950

## 處理流程
1. 下載指定日期的 CSV 檔
2. 以正確編碼讀取資料
3. 擷取日期、證券代號、名稱、收盤價及最低價
4. 記錄 4 月 7 日至 5 月 25 日期間的最低價
5. 比對 5 月 26 日至 6 月 5 日是否跌破上述低點
6. 產生報表

## 輸出檔案
- `output/TSE_stock_records_20250407_20250605.xlsx`
- `output/TSE_stock_price_comparison_20250526_20250605.xlsx`
- `output/stock_price_analyzer.log`

以上檔案儲存在本儲存庫的 `output/` 目錄下，方便在雲端或不同環境使用。
程式執行過程會寫入 `stock_price_analyzer.log` 以便追蹤下載與比對狀態。

## 執行方式
```bash
python stock_price_analyzer.py
```

程式會輸出範例格式：
```
1101,台泥,2025-06-02創新低,收盤價27.70,(基準低點:28.50),新低價25.50
```

## 上櫃資料分析
~~若需擷取上櫃 (OTC) 的每日行情並進行相同比較，可執行：~~
~~```bash~~
~~python otc_stock_price_analyzer.py~~
~~```~~

**注意：經測試後發現櫃買 API 無法正常擷取指定日期的資料，加入日期參數後仍顯示為最新一天的資料，因此暫時無法提供上櫃股票的歷史比較分析。**

~~對應產出檔案如下：~~
~~- `output/OTC_stock_records_20250407_20250605.xlsx`~~
~~- `output/OTC_stock_price_comparison_20250526_20250605.xlsx`~~
~~- `output/otc_stock_price_analyzer.log`~~
