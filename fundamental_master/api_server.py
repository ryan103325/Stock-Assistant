"""
Flask API Server for Fundamental Analysis
提供 REST API 讓前端觸發基本面分析
"""
import json
from flask import Flask, jsonify, request
from flask_cors import CORS
from pathlib import Path

from fundamental_master.main import analyze_stock
from fundamental_master.utils.logger import setup_logger
from fundamental_master.utils.exceptions import DataCollectionError

logger = setup_logger('api_server')

app = Flask(__name__)
CORS(app)  # 允許跨域請求

@app.route('/api/analyze/<stock_id>', methods=['GET'])
def analyze(stock_id):
    """
    基本面分析 API
    
    Args:
        stock_id: 股票代號 (URL 參數)
    
    Returns:
        JSON: 分析結果
    """
    try:
        logger.info(f"📡 收到分析請求: {stock_id}")
        
        # 執行分析 (不發送 Telegram)
        result = analyze_stock(stock_id, send_telegram=False)
        
        # 提取關鍵資訊
        response = {
            'success': True,
            'stock_id': stock_id,
            'stock_name': result['stock_info'].get('股票名稱', ''),
            'timestamp': result['timestamp'],
            'scores': {
                'z_score': {
                    'value': result['scores']['z_score'].get('score'),
                    'rating': result['scores']['z_score'].get('judgment'),
                },
                'f_score': {
                    'value': result['scores']['f_score'].get('score'),
                    'max': 9,
                },
                'm_score': {
                    'value': result['scores']['m_score'].get('score'),
                    'probability': result['scores']['m_score'].get('judgment'),
                },
                'roic': result['scores']['magic_formula'].get('roic'),
                'earnings_yield': result['scores']['magic_formula'].get('earnings_yield'),
                'lynch': result['scores']['lynch'].get('category'),
            },
            'ratios': {
                'pe': result['ratios'].get('本益比'),
                'pb': result['ratios'].get('股價淨值比'),
                'roe': result['ratios'].get('ROE'),
                'dividend_yield': result['stock_info'].get('殖利率'),
            },
            'ai_analysis': {
                'summary': result['ai_analysis'].get('summary', ''),
                'overall_score': result['ai_analysis'].get('overall_score'),
                'recommendation': result['ai_analysis'].get('recommendation', ''),
            },
            'report_image': result.get('report_image'),
        }
        
        logger.info(f"✅ 分析完成: {stock_id}")
        return jsonify(response)
        
    except DataCollectionError as e:
        logger.error(f"❌ 資料採集錯誤: {e}")
        return jsonify({
            'success': False,
            'error': '資料採集失敗',
            'message': str(e)
        }), 500
        
    except Exception as e:
        logger.error(f"❌ 分析失敗: {e}")
        return jsonify({
            'success': False,
            'error': '分析失敗',
            'message': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health():
    """健康檢查端點"""
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    logger.info("🚀 啟動 Flask API Server...")
    logger.info("📡 API 端點: http://localhost:5000/api/analyze/<stock_id>")
    app.run(host='0.0.0.0', port=5000, debug=True)
