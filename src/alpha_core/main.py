"""
台股新聞情緒分析 - CLI 入口
"""

import sys
import asyncio

from .pipeline import run_fetch, run_analyze, run_stats


def main():
    if len(sys.argv) < 2:
        print_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == "fetch":
        run_fetch()
    
    elif command == "analyze":
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
        run_stats()
    
    elif command == "run":
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
    reflect     收盤後反省 (尚未實作)
""")


if __name__ == "__main__":
    main()
