@echo off
chcp 65001 > nul
echo ==========================================
echo 🗓️ 啟動每週資料維護 (Weekly Maintenance)
echo ==========================================

echo [Step 1] 爬取 TPEx 供應鏈結構 (Scrape)...
python src/data_core/crawlers/scrape_tpex.py
if %errorlevel% neq 0 (
    echo ❌ TPEx 爬蟲失敗！
    pause
    exit /b %errorlevel%
)

echo [Step 2] AI 標籤清洗與標準化 (AI Cleaner)...
python src/data_core/ai_tag_cleaning/flow_strategy/ai_tag_cleaner.py
if %errorlevel% neq 0 (
    echo ❌ AI 清洗失敗！
    pause
    exit /b %errorlevel%
)

echo [Step 3] 整合標籤清單 (Apply Tags)...
python src/data_core/ai_tag_cleaning/flow_strategy/apply_ai_tags.py
if %errorlevel% neq 0 (
    echo ❌ 標籤整合失敗！
    pause
    exit /b %errorlevel%
)

echo ==========================================
echo ✅ 每週維護完成！您的 AI 標籤庫已更新。
echo 💡 建議接著執行 Run_Daily.bat 查看最新分析結果。
echo ==========================================
pause
