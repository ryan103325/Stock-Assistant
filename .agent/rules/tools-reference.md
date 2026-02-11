# 專案工具與資源參考指南

> 本文件記錄 `src/tools`、`src/schedulers` 及 `.github/workflows` 中所有可用的工具，供 AI 助手參考以避免建立重複檔案。

---

## 📁 src/tools/data_pipeline — 資料管線工具

| 工具 | 用途 | 使用時機 |
|------|------|----------|
| `Pipeline_data.py` | 每日更新個股歷史資料 (TWSE/TPEx) | 每日 15:00 自動排程 |
| `sync_stock_data.py` | 同步股票清單（處理新上市/下市） | 每日 15:00，Pipeline 前執行 |
| `update_taiex.py` | 更新大盤加權指數 (TAIEX) 資料 | 每日 15:00，Pipeline 後執行 |
| `csv_to_json.py` | 將 CSV 轉為 JSON (含 TAIEX)，供圖表網站使用 | 每日 15:00，TAIEX 更新後 |
| `optimize_matrix.py` | 計算技術指標矩陣 | data_sync 完成後 |
| `update_quarterly.py` | 更新季度財務資料 (EPS/ROE) | 季度更新月份 (1/4/7/10月) |
| `cleanup_delisted.py` | 清理下市股票 CSV | 手動維護時使用 |
| `backfill_finmind.py` | 使用 FinMind API 補齊歷史資料 | 手動補齊資料時使用 |
| `backfill_history.py` | 使用 TWSE/TPEx 官方 API 補齊特定月份資料 | 手動補齊資料時使用 |
| `refetch_all_history.py` | 完整重新抓取所有個股資料 | 緊急重建資料時使用 |

### ⚠️ 重要注意事項
- 如需「補齊歷史資料」，優先使用 `backfill_finmind.py`（FinMind API）
- 如 FinMind 不可用，備選 `backfill_history.py`（TWSE/TPEx 官方 API）
- **不要再建立新的補齊腳本**，上述工具已涵蓋所有情境

---

## 📁 src/tools/crawlers — 爬蟲工具

| 工具 | 用途 | 排程 |
|------|------|------|
| `fetch_cmoney_tags.py` | 爬取 CMoney 股票標籤 | 每週六 |
| `fetch_moneydj_tags.py` | 爬取 MoneyDJ 產業標籤 | 每週六 |
| `sector_momentum_crawler.py` | 爬取族群資金動能資料 | 策略執行時呼叫 |

---

## 📁 src/tools/tag_generator — 標籤生成器

| 工具 | 用途 | 排程 |
|------|------|------|
| `generate_master_tags.py` | 整合 CMoney + MoneyDJ 標籤生成主標籤表 | 每週六，爬蟲後執行 |
| `ai_classifier.py` | AI 輔助分類股票標籤 | 由 generate_master_tags 呼叫 |
| `group_mapping.py` | 標籤群組對照表 | 靜態資料 |

---

## 📁 src/schedulers — 排程器

| 排程器 | 用途 | 觸發方式 |
|--------|------|----------|
| `run_daily.py` | 每日策略排程（Pipeline → 指標 → 並行策略） | GitHub Actions / 本地 |
| `run_morning.py` | 早場新聞抓取與情緒分析 | GitHub Actions / 本地 |
| `run_weekly.py` | 週維護（標籤爬蟲 + 生成） | GitHub Actions / 本地 |
| `run_periodic.py` | 季度維護（EPS/ROE 更新） | 本地手動 |

---

## 📁 src/alpha_core — 新聞情緒分析

**執行方式:** `python -m src.alpha_core.main <command>`（必須用 -m 模式）

| 命令 | 用途 |
|------|------|
| `fetch` | 抓取 RSS 新聞 |
| `analyze` | AI 情緒分析 |
| `stats` | 顯示統計資訊 |
| `run` | 完整流程 (fetch + analyze) |
| `reflect` | 收盤後反省 |

---

## 📁 .github/workflows — GitHub Actions

### 執行流程圖

```
08:00 step_morning_news.yml → 新聞抓取 + 情緒分析
15:00 step_data_sync.yml → 資料同步 + TAIEX + CSV→JSON
        ├─→ daily_analysis.yml → 策略執行 (run_daily.py)
        └─→ deploy_chart_site.yml → GitHub Pages 部署
手動   step_compute.yml → 計算指標
手動   step_strategies_*.yml → 個別策略執行
```

### 各 Workflow 說明

| Workflow | 觸發 | 用途 |
|----------|------|------|
| `step_data_sync.yml` | 15:00 / 手動 | 資料同步核心（sync + Pipeline + TAIEX + JSON） |
| `step_morning_news.yml` | 08:00 / 手動 | 新聞抓取與情緒分析 |
| `daily_analysis.yml` | data_sync 後 / 手動 | 策略執行（RSI、Momentum、00981a） |
| `deploy_chart_site.yml` | data_sync 後 / 手動 | 部署圖表網站到 GitHub Pages |
| `step_compute.yml` | 手動 | 計算技術指標矩陣 |
| `step_strategies_00981a_fund.yml` | 手動 | 00981a 策略（獨立執行） |
| `step_strategies_rsi_screener.yml` | 手動 | RSI Screener（獨立執行） |
| `step_strategies_unified_momentum.yml` | 手動 | Unified Momentum（獨立執行） |

---

## 📁 核心資料路徑

| 路徑 | 內容 |
|------|------|
| `src/data_core/history/*.csv` | 個股歷史資料 |
| `src/data_core/TAIEX.csv` | 大盤加權指數 |
| `src/data_core/market_meta/` | 標籤、產業分類等元資料 |
| `docs/data/*.json` | 圖表網站用 JSON 資料 |
| `logs/` | 執行日誌與快取 |
