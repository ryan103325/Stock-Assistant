"""
籌碼面分析系統入口點
用法：python -m src.chip_analysis.main <stock_id> [--no-telegram]
"""

import argparse
import sys

from .fetcher import fetch_all
from .scorer import calculate
from .output import build_output, save_json


def main():
    parser = argparse.ArgumentParser(description='台股籌碼面評分系統')
    parser.add_argument('stock_id', help='股票代號（例如：2330）')
    parser.add_argument('--no-telegram', action='store_true', help='不發送 Telegram 通知')
    parser.add_argument('--output-dir', default=None, help='自訂輸出目錄')
    args = parser.parse_args()

    stock_id = args.stock_id.strip()
    print(f"[main] 開始分析股票：{stock_id}")

    # 1. 抓取資料
    raw_data = fetch_all(stock_id)

    # 2. 評分
    score = calculate(raw_data)
    print(f"[main] 評分完成：{score.total} 分 / {score.rating}")

    # 3. 組裝輸出
    output = build_output(
        stock_id=stock_id,
        stock_name=raw_data.get('stock_name', stock_id),
        raw_data=raw_data,
        score=score,
    )

    # 4. 儲存 JSON
    path = save_json(output, base_dir=args.output_dir)
    print(f"[main] 完成！結果已儲存至 {path}")

    # 5. 印出摘要
    print(f"\n{'='*40}")
    print(f"股票：{output['stock_name']} ({stock_id})")
    print(f"總分：{output['total_score']} / 100")
    print(f"評級：{output['rating']}")
    if output['highlights']:
        print(f"\n✅ 亮點：")
        for h in output['highlights']:
            print(f"  • {h}")
    if output['risks']:
        print(f"\n⚠️ 風險：")
        for r in output['risks']:
            print(f"  • {r}")
    print(f"\n💡 策略：{output['strategy']}")
    print(f"{'='*40}")


if __name__ == '__main__':
    main()
