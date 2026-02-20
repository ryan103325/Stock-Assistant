"""
籌碼面分析結果輸出模組
將 ChipScore 序列化為 JSON 並存到 docs/data/chip/{stock_id}.json
"""

import json
import os
from datetime import datetime

from .scorer import ChipScore


def build_output(stock_id: str, stock_name: str, raw_data: dict, score: ChipScore) -> dict:
    """組裝最終輸出 JSON 結構"""

    # 分類 rawData
    raw_institutional = {
        'trust_buy_5d': raw_data.get('trust_buy_5d'),
        'trust_consecutive_days': raw_data.get('trust_consecutive_days'),
        'foreign_buy_5d': raw_data.get('foreign_buy_5d'),
        'foreign_consecutive_days': raw_data.get('foreign_consecutive_days'),
        'dealer_buy_5d': raw_data.get('dealer_buy_5d'),
        'dealer_consecutive_days': raw_data.get('dealer_consecutive_days'),
        'institutional_daily': raw_data.get('institutional_daily', [])[:20],
    }

    raw_ownership = {
        'whale_pct_this': raw_data.get('whale_pct_this'),
        'whale_pct_last': raw_data.get('whale_pct_last'),
        'total_holders_this': raw_data.get('total_holders_this'),
        'avg_shares_this': raw_data.get('avg_shares_this'),
        'data_date': raw_data.get('data_date'),
        'ownership_weekly': raw_data.get('ownership_weekly', [])[:50],
    }

    raw_broker = {
        'main_force_net_5d': raw_data.get('main_force_net_5d'),
        'main_force_consecutive': raw_data.get('main_force_consecutive'),
        'main_force_trend': raw_data.get('main_force_trend', [])[-20:],
    }
    # 各期間分點資料
    for period in ['1d', '5d', '10d', '20d', '60d']:
        key = f'broker_{period}'
        pd = raw_data.get(key) or {}
        raw_broker[key] = {
            'top_buy_broker': pd.get('top_buy_broker'),
            'top_buy_net': pd.get('top_buy_net'),
            'top_sell_broker': pd.get('top_sell_broker'),
            'top_sell_net': pd.get('top_sell_net'),
            'buy_brokers': pd.get('buy_brokers', [])[:15],
            'sell_brokers': pd.get('sell_brokers', [])[:15],
        }

    raw_sentiment = {
        'margin_change': raw_data.get('margin_change'),
        'short_change': raw_data.get('short_change'),
        'short_ratio': raw_data.get('short_ratio'),
        'margin_daily': raw_data.get('margin_daily', []),
    }

    return {
        'stock_id': stock_id,
        'stock_name': stock_name,
        'analysis_date': datetime.now().strftime('%Y-%m-%d'),
        'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'current_price': raw_data.get('current_price'),
        'total_volume_1d': raw_data.get('total_volume_1d'),
        'total_score': score.total,
        'rating': score.rating,
        'rating_en': score.rating_en,
        'low_volume_penalty': score.low_volume_penalty,
        'dimensions': {
            'institutional': {
                'score': round(score.institutional.score, 1),
                'max': score.institutional.max_score,
                **score.institutional.breakdown,
            },
            'ownership': {
                'score': round(score.ownership.score, 1),
                'max': score.ownership.max_score,
                **score.ownership.breakdown,
            },
            'broker': {
                'score': round(score.broker.score, 1),
                'max': score.broker.max_score,
                **score.broker.breakdown,
            },
            'sentiment': {
                'score': round(score.sentiment.score, 1),
                'max': score.sentiment.max_score,
                **score.sentiment.breakdown,
            },
        },
        'highlights': score.highlights,
        'risks': score.risks,
        'strategy': score.strategy,
        'raw_data': {
            'institutional': raw_institutional,
            'ownership': raw_ownership,
            'broker': raw_broker,
            'sentiment': raw_sentiment,
        },
    }


def save_json(output: dict, base_dir: str = None) -> str:
    """儲存 JSON 到 docs/data/chip/{stock_id}.json，回傳儲存路徑"""
    if base_dir is None:
        # 自動找專案根目錄
        here = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.join(here, '..', '..', 'docs', 'data', 'chip')

    os.makedirs(base_dir, exist_ok=True)
    path = os.path.join(base_dir, f"{output['stock_id']}.json")

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[output] 已儲存: {path}")
    return path
