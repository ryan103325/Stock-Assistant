# 基本面評分大師 (Fundamental Master)

自動化基本面分析平台,整合 5 大量化評分模型 + AI 質化分析,產出標準化投資報告。

## 🎯 核心功能

### 五大評分模型
1. **Beneish M-Score** - 財報操縱偵測
2. **Altman Z-Score** - 破產風險評估
3. **Piotroski F-Score** - 營運體質變化
4. **Greenblatt Magic Formula** - 價值投資篩選
5. **Peter Lynch Classification** - 企業分類策略

### AI 質化分析
- 整合 OpenAI GPT-4-mini 進行財務數據解讀
- 結合法說會資訊驗證量化結果
- 產出專業投資建議與風險評估

### Telegram 整合
- 透過 TG Bot 輸入股票代號
- 自動生成精美的分析報告圖片
- 即時發送至 Telegram

## 📦 安裝

### 1. 安裝依賴套件
```bash
pip install -r requirements.txt
```

### 2. 安裝 Playwright 瀏覽器
```bash
playwright install chromium
```

### 3. 環境變數設定
專案會自動讀取上層目錄的 `.env` 檔案,確保以下變數已設定:

```env
# OpenAI API (必要)
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini

# Telegram Bot (必要)
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# 其他 API (選用)
GOOGLE_API_KEY=your_google_api_key
FINMIND_TOKEN=your_finmind_token
OPENROUTER_API_KEY=your_openrouter_api_key
```

## 🚀 快速開始

### 初始化專案
```python
from fundamental_master.utils import Config

# 建立必要的資料夾
Config.create_directories()

# 驗證配置
Config.validate()
```

### 分析單一股票
```python
from fundamental_master.main import analyze_stock

# 分析台積電 (2330)
result = analyze_stock('2330')
```

### 透過 Telegram Bot 使用
```bash
# 啟動 Telegram Bot
python -m fundamental_master.telegram_bot.bot_handler
```

然後在 Telegram 中輸入:
```
/analyze 2330
```

## 📁 專案結構

```
fundamental_master/
├── data_collection/          # 資料採集模組
│   ├── goodinfo_scraper.py   # Goodinfo 爬蟲
│   ├── macromicro_scraper.py # MacroMicro 爬蟲
│   └── data_validator.py     # 數據驗證
│
├── data_processing/          # 資料處理模組
│   ├── ttm_calculator.py     # TTM 計算
│   ├── growth_calculator.py  # 成長率計算
│   └── ratio_calculator.py   # 財務比率計算
│
├── scoring_engines/          # 評分引擎模組
│   ├── m_score.py            # Beneish M-Score
│   ├── z_score.py            # Altman Z-Score
│   ├── f_score.py            # Piotroski F-Score
│   ├── magic_formula.py      # Greenblatt Magic Formula
│   └── lynch_classifier.py   # Peter Lynch Classification
│
├── ai_analysis/              # AI 分析模組
│   ├── prompt_templates.py   # GPT-4 Prompt 模板
│   ├── qualitative_analyzer.py  # 質化分析引擎
│   └── report_generator.py   # 報告生成器
│
├── report_output/            # 報告輸出模組
│   ├── html_generator.py     # HTML 報告生成
│   ├── image_generator.py    # Playwright 圖片生成
│   └── templates/            # HTML 模板
│
├── telegram_bot/             # Telegram 整合模組
│   ├── bot_handler.py        # TG Bot 主程式
│   ├── message_formatter.py  # 訊息格式化
│   └── image_sender.py       # 圖片發送功能
│
└── utils/                    # 工具模組
    ├── config.py             # 配置管理
    ├── logger.py             # 日誌系統
    └── exceptions.py         # 異常處理
```

## 📊 資料來源

- **Goodinfo**: 台灣股市資訊網 (財務報表)
- **MacroMicro**: 財經 M 平方 (台灣 10 年期公債殖利率)
- **FinMind**: 備用財務資料源

## 🔧 開發狀態

### Phase 1: MVP (進行中)
- [x] 專案結構建立
- [x] 配置管理系統
- [ ] Goodinfo 爬蟲
- [ ] M-Score & Z-Score 評分引擎
- [ ] AI 分析整合
- [ ] 報告圖片生成
- [ ] Telegram Bot 整合

### Phase 2: 完整功能 (規劃中)
- [ ] F-Score, Magic Formula, Lynch 分類
- [ ] 法說會資訊整合
- [ ] 批量分析功能

### Phase 3: 優化與擴展 (規劃中)
- [ ] 網頁整合
- [ ] 歷史回測
- [ ] 自訂參數

## ⚖️ 免責聲明

本系統之分析結果係經由 AI 模型依據歷史數據運算生成,僅供投資研究參考,不代表任何形式之投資建議或獲利保證。本平台無法保證原始數據之即時性與正確性,投資人應審慎評估並自負風險。

## 📝 授權

MIT License

## 👨‍💻 作者

Ryan - 2026
