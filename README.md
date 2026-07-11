# Telegram Stock Assistant Bot

個人專屬的台股投資助手。每天自動抓資料、跑分析、發報表到 Telegram，不用自己盯盤。

## 能做什麼

- **每日自動排程**：收盤後自動更新資料、產生分析、推播報表，全程不用手動觸發
- **即時技術分析**：在 Telegram 輸入股票代號（如 `2330`）就能拿到 K 線圖，含 Mansfield / IBD 相對強度
- **資金水位監控**：追蹤特定 ETF（目前是 00981A）的持股與資金流向變化
- **省資源**：資料有快取、機器可以定時開關機，不用整天掛著跑

## 開始使用

需要 Python 3.9+（Node.js 可選，只是用來跑 `npm` 指令捷徑）。

```bash
pip install -r requirements.txt
```

打開 `scheduler.py` 和 `00981a.py`，填入你的 Telegram Token 與 Chat ID。要調整排程時間就改 `scheduler.py` 裡的：

| 變數 | 用途 | 預設 |
|---|---|---|
| `UPDATE_TIME` | 資料更新時間 | 15:00 |
| `REPORT_TIME` | 報表發送時間 | 18:00 |
| `STOP_TIME` | 自動關機時間 | 00:00 |

啟動（保持終端機開啟）：

```bash
npm start     # 排程器（scheduler.py）
npm run day   # 手動跑一次下午場
npm run night # 手動跑一次晚場

# 不想用 npm 也可以直接
python scheduler.py
```

## 雲端排程（GitHub Actions）

Push 上去之後，在 Repository → Settings → Secrets and variables → Actions 新增：

- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`
- `FINMIND_TOKEN`

排程邏輯：

- **15:00** 跑 `run_day.py`（價量更新 → VCP / RSI 篩選）
- **18:00** 跑 `run_night.py`（00981A 報告）
- **週五晚場**額外跑 `00981aW.py`（週報）
- 雲端執行會自動跳過互動式圖表 Bot，避免報錯

## 專案結構

```
scheduler.py       排程橋接器（本機 CLI 與 GitHub Actions 通用）
run_day.py         下午場：交易日檢查 → 更新 → 篩選
run_night.py       晚場：交易日檢查 → 報告
run_periodic.py    維護：每週/每季更新代碼與分類，不受交易日限制

src/core/
  Pipeline_data.py     下載最新股價
  optimize_matrix.py   計算指標快取（market_matrix.pkl）
  VCP_screener.py      VCP 強勢股篩選
  RSI_screener.py      RSI 底背離篩選

src/reports/
  00981a.py    00981A 資金流向日報
  00981aW.py   00981A 資金流向週報

src/vis/
  技術分析圖.py   Telegram Bot 互動圖表
```
