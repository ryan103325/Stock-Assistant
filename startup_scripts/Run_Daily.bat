@echo off
chcp 65001 > nul
echo ==========================================
echo 🚀 啟動每日自動化分析流程 (Daily Analysis)
echo ==========================================

echo [Step 1] 更新股價數據 (Pipeline Data)...
python src/data_core/maintenance/Pipeline_data.py
if %errorlevel% neq 0 (
    echo ❌ 股價更新失敗！
    pause
    exit /b %errorlevel%
)

echo [Step 2] 計算技術指標矩陣 (Matrix)...
python src/data_core/maintenance/optimize_matrix.py
if %errorlevel% neq 0 (
    echo ❌ 矩陣計算失敗！
    pause
    exit /b %errorlevel%
)

echo [Step 3] 執行統一動能策略 (Unified Momentum)...
python src/strategies/unified_momentum/run_unified_momentum.py
if %errorlevel% neq 0 (
    echo ❌ 篩選器執行失敗！
    pause
    exit /b %errorlevel%
)

echo ==========================================
echo ✅ 每日流程執行完畢！報告已發送。
echo ==========================================
pause
