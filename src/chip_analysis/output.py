"""
籌碼面分析結果輸出模組
將 ChipScore 序列化為 JSON 並存到 docs/data/chip/{stock_id}.json
"""

import json
import os
from datetime import datetime
from dataclasses import asdict

from .scorer import ChipScore


def build_output(stock_id: str, stock_name: str, raw_data: dict, score: ChipScore) -> dict:
    """組裝最終輸出 JSON 結構"""
    return {
        'stock_id': stock_id,
        'stock_name': stock_name,
        'analysis_date': datetime.now().strftime('%Y-%m-%d'),
        'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
            'trust_buy_5d': raw_data.get('trust_buy_5d'),
            'trust_consecutive_days': raw_data.get('trust_consecutive_days'),
            'foreign_buy_5d': raw_data.get('foreign_buy_5d'),
            'whale_pct_this': raw_data.get('whale_pct_this'),
            'whale_pct_last': raw_data.get('whale_pct_last'),
            'retail_pct_this': raw_data.get('retail_pct_this'),
            'retail_pct_last': raw_data.get('retail_pct_last'),
            'broker_name_1d': raw_data.get('broker_name_1d'),
            'broker_buy_1d': raw_data.get('broker_buy_1d'),
            'broker_name_5d': raw_data.get('broker_name_5d'),
            'broker_buy_5d': raw_data.get('broker_buy_5d'),
            'broker_name_10d': raw_data.get('broker_name_10d'),
            'broker_buy_10d': raw_data.get('broker_buy_10d'),
            'broker_name_20d': raw_data.get('broker_name_20d'),
            'broker_buy_20d': raw_data.get('broker_buy_20d'),
            'total_volume_1d': raw_data.get('total_volume_1d'),
            'is_geo_broker': raw_data.get('is_geo_broker', False),
            'margin_change': raw_data.get('margin_change'),
            'short_ratio': raw_data.get('short_ratio'),
            'price_above_ma': raw_data.get('price_above_ma'),
            'current_price': raw_data.get('current_price'),
            'data_date': raw_data.get('data_date'),
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
