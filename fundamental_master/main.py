"""
基本面評分大師 - 主程式
端到端分析流程: 數據採集 → 處理 → 評分 → AI 分析 → 報告生成 → TG 發送
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 確保上層目錄在 path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from fundamental_master.utils.config import Config
from fundamental_master.utils.logger import setup_logger
from fundamental_master.utils.exceptions import FundamentalMasterError
from fundamental_master.data_collection.goodinfo_scraper import GoodinfoScraper
from fundamental_master.data_collection.macromicro_scraper import fetch_risk_free_rate
from fundamental_master.data_collection.data_validator import DataValidator
from fundamental_master.data_processing.ttm_calculator import build_ttm_dataset
from fundamental_master.data_processing.ratio_calculator import calculate_all_ratios
from fundamental_master.scoring_engines.m_score import calculate_m_score
from fundamental_master.scoring_engines.z_score import calculate_z_score
from fundamental_master.scoring_engines.f_score import calculate_f_score
from fundamental_master.scoring_engines.magic_formula import calculate_magic_formula
from fundamental_master.scoring_engines.lynch_classifier import classify_lynch
from fundamental_master.ai_analysis.qualitative_analyzer import QualitativeAnalyzer
from fundamental_master.report_output.html_generator import generate_html_report
from fundamental_master.report_output.image_generator import html_to_image
from fundamental_master.telegram_bot.image_sender import send_report_image, send_progress_message

logger = setup_logger('main')


def analyze_stock(stock_id: str, send_telegram: bool = True, qualitative_info: str = '') -> dict:
    """
    完整的股票基本面分析流程

    Args:
        stock_id: 股票代號 (例如 '2330')
        send_telegram: 是否發送至 Telegram
        qualitative_info: 質化資訊 (法說會摘要等)

    Returns:
        dict: 完整分析結果
    """
    logger.info(f"{'='*60}")
    logger.info(f"🚀 開始基本面分析: {stock_id}")
    logger.info(f"{'='*60}")

    # 建立資料夾
    Config.create_directories()

    # 通知開始分析
    if send_telegram:
        send_progress_message(f"🔄 正在分析 <b>{stock_id}</b> 的基本面...")

    result = {
        'stock_id': stock_id,
        'timestamp': datetime.now().isoformat(),
        'stock_info': {},
        'scores': {},
        'ratios': {},
        'ai_analysis': {},
        'report_image': None,
    }

    try:
        # ==================== 階段 1: 資料採集 ====================
        logger.info("\n📡 階段 1/5: 資料採集")

        with GoodinfoScraper(headless=True) as scraper:
            raw_data = scraper.fetch_all_financial_data(stock_id)

        risk_free_rate = fetch_risk_free_rate()

        # 驗證數據
        validation = DataValidator.validate_all(raw_data)
        if not validation['valid']:
            logger.warning(f"⚠️ 數據不完整: {validation['missing']}")

        result['stock_info'] = raw_data['stock_info']
        result['stock_info']['無風險利率'] = risk_free_rate

        # ==================== 階段 2: 資料處理 ====================
        logger.info("\n⚙️ 階段 2/5: 資料處理")

        # TTM 計算
        ttm_data = build_ttm_dataset(
            raw_data['income_statement'],
            raw_data['cashflow']
        )

        # 財務比率計算
        ratios = calculate_all_ratios(
            raw_data['stock_info'],
            raw_data['balance_sheet'],
            ttm_data
        )
        result['ratios'] = ratios

        # ==================== 階段 3: 模型評分 ====================
        logger.info("\n📊 階段 3/5: 模型評分")

        # 準備資產負債表當期/前期數據
        bs_data = raw_data['balance_sheet'].get('data', {})
        balance_current = {k: v[0] if v else None for k, v in bs_data.items()}
        balance_previous = {k: v[4] if len(v) > 4 else None for k, v in bs_data.items()}

        # M-Score
        m_score_result = calculate_m_score({
            'ttm': ttm_data,
            'balance_current': balance_current,
            'balance_previous': balance_previous,
            'depreciation_current': ttm_data.get('折舊費用', {}).get('current'),
            'depreciation_previous': ttm_data.get('折舊費用', {}).get('previous'),
            'cfo_current': ttm_data.get('營運現金流', {}).get('current'),
        })
        result['scores']['m_score'] = m_score_result

        # Z-Score
        z_score_result = calculate_z_score({
            'balance': balance_current,
            'ttm': ttm_data,
            'market_cap_billion': raw_data['stock_info'].get('市值_億'),
        })
        result['scores']['z_score'] = z_score_result

        # F-Score
        f_score_result = calculate_f_score({
            'ttm': ttm_data,
            'balance_current': balance_current,
            'balance_previous': balance_previous,
            'shares_current': raw_data['stock_info'].get('發行股數_千股'),
            'shares_previous': None,
        })
        result['scores']['f_score'] = f_score_result

        # Magic Formula
        mf_result = calculate_magic_formula({
            'ttm': ttm_data,
            'balance': balance_current,
            'market_cap_billion': raw_data['stock_info'].get('市值_億'),
        })
        result['scores']['magic_formula'] = mf_result

        # Lynch Classification
        lynch_result = classify_lynch({
            'historical_eps': raw_data.get('historical_eps', {}),
            'stock_info': raw_data['stock_info'],
            'ttm': ttm_data,
        })
        result['scores']['lynch'] = lynch_result

        # ==================== 階段 4: AI 分析 ====================
        logger.info("\n🤖 階段 4/5: AI 質化分析")

        analyzer = QualitativeAnalyzer()
        ai_input = {
            'stock_info': raw_data['stock_info'],
            'scores': result['scores'],
            'ratios': ratios,
            'qualitative_info': qualitative_info,
        }
        ai_result = analyzer.analyze(ai_input)
        result['ai_analysis'] = ai_result

        # ==================== 階段 5: 報告生成 ====================
        logger.info("\n📄 階段 5/5: 報告生成")

        analysis_data = {
            'stock_info': raw_data['stock_info'],
            'scores': result['scores'],
            'ratios': ratios,
            'ai_analysis': ai_result,
        }

        # 生成 HTML
        html_content = generate_html_report(analysis_data)

        # 生成圖片
        image_path = html_to_image(html_content, stock_id)
        result['report_image'] = image_path

        # 發送至 Telegram
        if send_telegram and image_path:
            stock_name = raw_data['stock_info'].get('股票名稱', '')
            send_report_image(image_path, stock_id, stock_name)

        # 儲存結果 JSON
        _save_result(result, stock_id)

        # 儲存前端用精簡 JSON (供 GitHub Pages 讀取)
        _save_web_result(result, stock_id)

        logger.info(f"\n{'='*60}")
        logger.info(f"🎉 {stock_id} 基本面分析完成!")
        logger.info(f"{'='*60}")

    except FundamentalMasterError as e:
        logger.error(f"❌ 分析失敗: {e}")
        if send_telegram:
            send_progress_message(f"❌ {stock_id} 分析失敗: {str(e)[:200]}")
        raise

    except Exception as e:
        logger.error(f"❌ 未預期的錯誤: {e}", exc_info=True)
        if send_telegram:
            send_progress_message(f"❌ {stock_id} 分析發生未預期錯誤")
        raise

    return result


def _save_result(result: dict, stock_id: str):
    """儲存分析結果為 JSON"""
    output_dir = Config.PROCESSED_DATA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'analysis_{stock_id}_{timestamp}.json'
    filepath = output_dir / filename

    # 移除不可序列化的項目
    save_data = {}
    for key, value in result.items():
        try:
            json.dumps(value)
            save_data[key] = value
        except (TypeError, ValueError):
            save_data[key] = str(value)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

    logger.info(f"💾 分析結果已儲存: {filepath}")


def _save_web_result(result: dict, stock_id: str):
    """儲存精簡的分析結果 JSON 到 docs/data/fundamental/ 供前端讀取"""
    web_dir = Path(__file__).parent.parent / 'docs' / 'data' / 'fundamental'
    web_dir.mkdir(parents=True, exist_ok=True)

    # 用固定檔名 (覆蓋舊結果)
    filepath = web_dir / f'{stock_id}.json'

    web_data = {
        'success': True,
        'stock_id': stock_id,
        'stock_name': result.get('stock_info', {}).get('股票名稱', ''),
        'timestamp': result.get('timestamp', ''),
        'scores': {},
        'ratios': {},
        'ai_analysis': {},
    }

    # Z-Score
    z = result.get('scores', {}).get('z_score', {})
    web_data['scores']['z_score'] = {
        'value': z.get('score'),
        'rating': z.get('judgment'),
        'description': z.get('description'),
    }

    # F-Score
    f = result.get('scores', {}).get('f_score', {})
    web_data['scores']['f_score'] = {
        'value': f.get('score'),
        'max': 9,
        'judgment': f.get('judgment'),
        'description': f.get('description'),
    }

    # M-Score
    m = result.get('scores', {}).get('m_score', {})
    web_data['scores']['m_score'] = {
        'value': m.get('score'),
        'probability': m.get('judgment'),
        'description': m.get('description'),
    }

    # Magic Formula
    mf = result.get('scores', {}).get('magic_formula', {})
    web_data['scores']['roic'] = mf.get('roic')
    web_data['scores']['earnings_yield'] = mf.get('earnings_yield')

    # Lynch
    ly = result.get('scores', {}).get('lynch', {})
    web_data['scores']['lynch'] = ly.get('category')
    web_data['scores']['lynch_detail'] = {
        'eps_cagr': ly.get('eps_cagr'),
        'fair_pe_range': ly.get('fair_pe_range'),
        'valuation': ly.get('valuation'),
        'description': ly.get('description'),
        'strategy': ly.get('strategy'),
    }

    # 財務比率
    ratios = result.get('ratios', {})
    web_data['ratios'] = {
        'pe': result.get('stock_info', {}).get('本益比'),
        'pb': None,  # 需要從 stock_info 計算
        'roe': ratios.get('ROE'),
        'roa': ratios.get('ROA'),
        'gross_margin': ratios.get('毛利率'),
        'operating_margin': ratios.get('營業利益率'),
        'net_margin': ratios.get('稅後淨利率'),
        'current_ratio': ratios.get('流動比率'),
        'debt_ratio': ratios.get('負債比率'),
        'dividend_yield': result.get('stock_info', {}).get('殖利率'),
        'revenue_growth': ratios.get('營收成長率'),
    }

    # PB 計算
    price = result.get('stock_info', {}).get('收盤價')
    nav = result.get('stock_info', {}).get('每股淨值')
    if price and nav and nav > 0:
        web_data['ratios']['pb'] = round(price / nav, 2)

    # AI 分析
    ai = result.get('ai_analysis', {})
    web_data['ai_analysis'] = {
        'summary': ai.get('summary', ''),
        'overall_score': ai.get('overall_score'),
        'recommendation': ai.get('recommendation', ''),
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(web_data, f, ensure_ascii=False, indent=2)

    logger.info(f"🌐 前端 JSON 已儲存: {filepath}")


# ==================== CLI 入口 ====================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='基本面評分大師 - 股票基本面分析')
    parser.add_argument('stock_id', help='股票代號 (例如: 2330)')
    parser.add_argument('--no-telegram', action='store_true', help='不發送至 Telegram')
    parser.add_argument('--info', type=str, default='', help='補充的質化資訊')

    args = parser.parse_args()

    try:
        result = analyze_stock(
            stock_id=args.stock_id,
            send_telegram=not args.no_telegram,
            qualitative_info=args.info,
        )

        # 印出摘要
        scores = result.get('scores', {})
        ai = result.get('ai_analysis', {})

        print(f"\n{'='*50}")
        print(f"📊 {args.stock_id} 基本面分析摘要")
        print(f"{'='*50}")
        print(f"M-Score: {scores.get('m_score', {}).get('judgment', 'N/A')}")
        print(f"Z-Score: {scores.get('z_score', {}).get('judgment', 'N/A')}")
        print(f"F-Score: {scores.get('f_score', {}).get('score', 'N/A')}/9")
        print(f"ROIC: {scores.get('magic_formula', {}).get('roic', 'N/A')}")
        print(f"Lynch: {scores.get('lynch', {}).get('category', 'N/A')}")
        print(f"綜合評分: {ai.get('overall_score', 'N/A')}/10")
        print(f"建議: {ai.get('target_action', 'N/A')}")
        print(f"{'='*50}")

    except Exception as e:
        print(f"❌ 分析失敗: {e}")
        sys.exit(1)
