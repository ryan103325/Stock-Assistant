# Telegram Stock Assistant Bot (TG 助手)

個人專屬的台股投資助手，具備自動化資料更新、技術分析與 Telegram 通知功能。

## ✨ 主要功能
- **每日自動排程**：自動下載資料、產生分析、發送報表。
- **即時技術分析**：在 TG 輸入股票代號 (如 `2330`) 即可獲得專業 K 線圖 (含 Mansfield/IBD 強度)。
- **資金水位監控**：定期監控特定基金/投資組合的資金流向與持股變化 (00981a)。
- **低資源消耗**：支援資料快取 (Optimization Cache) 與定時開關機，不佔用電腦資源。

## 🚀 快速開始

### 1. 安裝環境
請確保已安裝 Python (建議 3.9+) 與 Node.js (可選，用於管理腳本)。

```bash
# 安裝 Python 套件
pip install -r requirements.txt
```

### 2. 設定
- 打開 `scheduler.py` 與 `00981a.py`，填入你的 Telegram Token 與 Chat ID。
- 修改 `scheduler.py` 中的時間設定 (如果是 24 小時開機)：
  - `UPDATE_TIME`: 資料更新時間 (預設 15:00)
  - `REPORT_TIME`: 報表發送時間 (預設 18:00)
  - `STOP_TIME`: 自動關機時間 (預設 00:00)

### 3. 啟動系統
使用以下指令啟動 (需保持終端機開啟)：

```bash
# 使用 npm 指令 (推薦)
npm start    # 啟動排程器 (scheduler.py)
npm run day  # 手動執行下午場 (run_day.py)
npm run night # 手動執行晚場 (run_night.py)

# 或直接使用 python
python scheduler.py
```

## 🛠️ GitHub 自動排程
本專案已設定 GitHub Actions，可自動在雲端執行。

### 設定步驟
1. 將專案 Push 到 GitHub。
2. 進入 Repository > **Settings** > **Secrets and variables** > **Actions**。
3. 新增以下 Secrets:
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `FINMIND_TOKEN`

### 雲端執行邏輯
- **每天 15:00**: 執行 `run_day.py` (價量更新 + VCP/RSI 篩選)。
- **每天 18:00**: 執行 `run_night.py` (00981a 報告)。
- **週五晚場**: 自動追加 `00981aW.py` (週報)。
- **雲端優化**: 自動跳過互動式圖表 Bot，避免報錯。

## 📂 專案結構
- `scheduler.py`: 排程橋接器 (相容 CLI 與 GitHub Actions)。
- `run_day.py`: **下午場主程式** (交易日檢查 -> 更新 -> 篩選)。
- `run_night.py`: **晚場主程式** (交易日檢查 -> 報告)。
- `run_periodic.py`: **維護主程式** (每週/每季更新代碼與分類，無交易日限制)。
- `package.json`: 腳本指令管理。

### 核心模組 (`src/core/`)
- `Pipeline_data.py`: 下載最新股價。
- `optimize_matrix.py`: 計算指標快取 (`market_matrix.pkl`)。
- `VCP_screener.py`: VCP 強勢股篩選。
- `RSI_screener.py`: RSI 底背離篩選。

### 報告與視覺化 (`src/`)
- `reports/00981a.py`: 00981a 資金流向日報。
- `reports/00981aW.py`: 00981a 資金流向週報。
- `vis/技術分析圖.py`: Telegram Bot 互動圖表。

