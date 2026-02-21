"""
台股新聞情緒分析 - CLI 入口
"""

import sys
import asyncio


def main():
    if len(sys.argv) < 2:
        print_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == "fetch":
        from .pipeline import run_fetch
        run_fetch()
    
    elif command == "analyze":
        from .pipeline import run_analyze
        limit = 100
        if len(sys.argv) > 2:
            try:
                limit = int(sys.argv[2])
            except ValueError:
                pass
        
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(run_analyze(limit))
    
    elif command == "stats":
        from .pipeline import run_stats
        run_stats()
    
    elif command == "run":
        from .pipeline import run_fetch, run_analyze
        # 完整流程: fetch + analyze
        run_fetch()
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(run_analyze())
    
    elif command == "reflect":
        from .reflection import reflect_daily
        date_arg = None
        if len(sys.argv) > 2:
            date_arg = sys.argv[2]  # 可指定日期
        
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(reflect_daily(date_arg))
    
    elif command == "export":
        from .export_sentiment import main as export_main
        export_main()
    
    elif command == "search":
        # Tavily 搜尋個股新聞 → 分析 → 匯出
        if len(sys.argv) < 3:
            print("❌ 請指定股票代碼, e.g., search 2330")
            return
        ticker = sys.argv[2]
        
        # Step 1: Tavily 搜尋並存入 DB
        from .tavily_fetcher import fetch_and_store
        inserted = fetch_and_store(ticker)
        
        if inserted > 0:
            # Step 2: 分析新增的新聞
            from .pipeline import run_analyze
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            asyncio.run(run_analyze(limit=inserted + 5))
        
        # Step 3: 匯出 JSON
        from .export_sentiment import main as export_main
        export_main()
    
    else:
        print(f"❌ Unknown command: {command}")
        print_help()


def print_help():
    print("""
台股新聞情緒分析系統

Usage:
    python -m src.alpha_core.main <command>

Commands:
    fetch       抓取 RSS 新聞
    analyze     AI 情緒分析 (可指定數量, e.g., analyze 50)
    stats       顯示統計資訊
    run         完整流程 (fetch + analyze)
    reflect     收盤後反省
    export      匯出情緒排名 JSON 到 docs/data/news/
    search      Tavily 搜尋個股新聞 (e.g., search 2330)
""")


if __name__ == "__main__":
    main()
