import pandas as pd
from dotenv import load_dotenv
load_dotenv()
import os
import requests
import time
import sys
from datetime import datetime, timedelta

# ==========================================
# ⚙️ 設定區
# ==========================================
tg_token = os.getenv("TELEGRAM_TOKEN", "")
tg_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

# 設定路徑
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_FOLDER = os.path.join(BASE_DIR, "data_core")
trend_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fund_trend_log.csv') 
holdings_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fund_holdings_history.csv')

# 族群整合模組
sys.path.insert(0, os.path.join(BASE_DIR, "tools", "tag_generator"))
from group_mapping import (
    calculate_group_weights, 
    calculate_group_stock_changes
)

# 圖片報告生成器
from report_weekly_html import generate_weekly_report_image

# ==========================================
# 🛠️ 工具函式
# ==========================================
def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
        payload = {"chat_id": tg_chat_id, "text": message}
        resp = requests.post(url, json=payload)
        if resp.status_code == 200: print("✅ TG 發送成功")
        else: print(f"❌ TG 發送失敗: {resp.text}")
    except Exception as e: print(f"❌ TG 錯誤: {e}")

def send_telegram_photo(photo_path, caption=""):
    """Telegram 發送圖片"""
    try:
        url = f"https://api.telegram.org/bot{tg_token}/sendPhoto"
        with open(photo_path, 'rb') as photo:
            files = {'photo': photo}
            data = {'chat_id': tg_chat_id, 'caption': caption}
            resp = requests.post(url, files=files, data=data)
        if resp.status_code == 200: 
            print("✅ TG 圖片發送成功")
        else: 
            print(f"❌ TG 圖片發送失敗: {resp.text}")
    except Exception as e: 
        print(f"❌ TG 圖片錯誤: {e}")

def clean_float(val):
    try:
        return float(str(val).replace(',', '').replace('%', '').strip())
    except:
        return 0.0

def check_trading_day():
    """檢查今日是否為交易日 (FinMind TaiwanStockTradingDate)"""
    today_str = datetime.now().strftime('%Y-%m-%d')
    token = os.getenv("FINMIND_TOKEN", "")
    
    if not token:
        print("⚠️ 未設定 FINMIND_TOKEN，改用平日判斷")
        return datetime.now().weekday() < 5
    
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockTradingDate",
            "start_date": today_str,
            "end_date": today_str,
            "token": token
        }
        resp = requests.get(url, params=params, timeout=20)
        data = resp.json()
        dates = [d['date'] for d in data.get('data', [])]
        if today_str in dates:
            print(f"✅ 是交易日: {today_str}")
            return True
        else:
            print(f"💤 非交易日: {today_str}")
            return False
    except Exception as e:
        print(f"⚠️ API 查詢失敗: {e}")
        return datetime.now().weekday() < 5

# ==========================================
# 🧠 模組一：持股結構變動分析
# ==========================================
def analyze_holdings_weekly(df_holdings, t_curr, t_prev):
    """
    分析本周 vs 上周的持股變化
    """
    df_curr = df_holdings[df_holdings['日期'] == t_curr].copy()
    df_prev = df_holdings[df_holdings['日期'] == t_prev].copy()
    
    # 股數清理
    df_curr['Shares'] = df_curr['股數'].apply(clean_float)
    df_prev['Shares'] = df_prev['股數'].apply(clean_float)
    df_curr['Weight'] = df_curr['持股權重'].apply(clean_float)
    
    map_id = dict(zip(df_curr['股票名稱'], df_curr['股票代號']))
    map_id.update(dict(zip(df_prev['股票名稱'], df_prev['股票代號'])))

    dict_curr = dict(zip(df_curr['股票名稱'], df_curr['Shares']))
    dict_prev = dict(zip(df_prev['股票名稱'], df_prev['Shares']))
    
    set_curr = set(dict_curr.keys())
    set_prev = set(dict_prev.keys())

    # A. 新進名單
    new_entrants_names = set_curr - set_prev
    new_entrants = []
    for name in new_entrants_names:
        code = map_id.get(name, "")
        weight = df_curr[df_curr['股票名稱'] == name]['Weight'].values[0]
        new_entrants.append({'name': name, 'code': code, 'weight': weight})
    
    new_entrants.sort(key=lambda x: x['weight'], reverse=True)

    # B. 買賣超計算（含權重變化）
    common_names = set_curr | set_prev
    diff_list = []
    
    # 建立上週權重對照表
    prev_weight_map = {}
    for _, row in df_prev.iterrows():
        try:
            wt = float(str(row['持股權重']).replace('%', '').replace(',', ''))
        except:
            wt = 0.0
        prev_weight_map[row['股票名稱']] = wt
    
    for name in common_names:
        s_curr = dict_curr.get(name, 0)
        s_prev = dict_prev.get(name, 0)
        diff = s_curr - s_prev
        
        current_weight = 0.0
        if name in set_curr:
            try:
                current_weight = df_curr[df_curr['股票名稱'] == name]['Weight'].values[0]
            except:
                current_weight = 0.0
        
        prev_weight = prev_weight_map.get(name, 0.0)
        weight_change = current_weight - prev_weight

        if diff != 0:
            code = map_id.get(name, "")
            diff_list.append({
                'name': name, 
                'code': code, 
                'diff': diff, 
                'weight': current_weight,
                'weight_change': weight_change
            })
            
    # 以權重變化排序
    buys = sorted([x for x in diff_list if x['diff'] > 0], key=lambda x: abs(x['weight_change']), reverse=True)[:5]
    sells = sorted([x for x in diff_list if x['diff'] < 0], key=lambda x: abs(x['weight_change']), reverse=True)[:5]

    return new_entrants, buys, sells

# ==========================================
# 🧠 模組二：周級別總判斷
# ==========================================
def analyze_trend_strategy(df_trend, t_curr, t_prev):
    row_curr = df_trend[df_trend['日期'] == t_curr].iloc[0]
    row_prev = df_trend[df_trend['日期'] == t_prev].iloc[0]

    # 1. 曝險趨勢
    exp_curr = clean_float(row_curr.get('總曝險', 0))
    exp_prev = clean_float(row_prev.get('總曝險', 0))
    exp_diff = exp_curr - exp_prev

    # 2. 周均動作流
    last_5 = df_trend[df_trend['日期'] <= t_curr].tail(5)
    if 'SP值' in last_5.columns:
        avg_sp = last_5['SP值'].apply(clean_float).mean()
    else:
        avg_sp = 0.0

    # 3. 資金源頭
    raw_subs = clean_float(row_curr.get('申贖應付款', 0))
    
    has_inflow = raw_subs < -1000000
    
    is_party = False
    last_5_subs = last_5['申贖應付款'].apply(clean_float)
    if raw_subs < 0 and raw_subs == last_5_subs.min():
        is_party = True

    # 判斷邏輯矩陣
    signal = "⚪"
    strategy = "區間震盪 (Consolidation)"
    reason = "操作方向不明"

    if is_party and avg_sp < 0:
        signal = "🚀"
        strategy = "資金派對 (Liquidity Party)"
        reason = "申購款暴增且持續買進，新資金潮湧入。"

    elif exp_diff > 2.0 and avg_sp < -0.2:
        signal = "🔴"
        strategy = "攻擊型建倉 (Accumulation)"
        reason = f"本周曝險顯著增加 (+{exp_diff:.1f}%)，且連續淨買入。"

    elif exp_diff < -3.0 and avg_sp > 0:
        signal = "🔵"
        strategy = "防禦撤退 (Defensive)"
        reason = f"本周曝險大幅下降 ({exp_diff:.1f}%)，經理人正在逃命。"

    elif exp_diff > -1.0 and exp_diff < 1.0:
        if avg_sp < -0.5 and exp_curr < 90:
            signal = "🟢"
            strategy = "低檔回補/抄底 (Bottom Fishing)"
            reason = "水位雖低但買盤強勁，主力正在低檔吸籌。"

    elif avg_sp > 0.2:
        if exp_diff > -2.0 and exp_diff < 1.0:
            signal = "🟠"
            strategy = "高檔出貨/調節 (Distribution)"
            reason = "水位維持高檔但持續賣出，利用申購款倒貨。"

    return {
        "signal": signal,
        "strategy": strategy,
        "reason": reason,
        "exp_diff": exp_diff,
        "avg_sp": avg_sp,
        "has_inflow": raw_subs < 0,
        "total_exposure": exp_curr  # 新增總曝險
    }

# ==========================================
# 🚀 主程式
# ==========================================
def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"🚀 啟動 AI 基金週報分析系統... ({today})")
    
    # 交易日檢查
    force_mode = "--force" in sys.argv
    if not force_mode:
        if not check_trading_day():
            print("😴 非交易日，跳過執行。")
            return
    else:
        print("⚠️ [Force Mode] 強制執行，跳過交易日檢查。")

    if not os.path.exists(holdings_filename) or not os.path.exists(trend_filename):
        print("❌ 找不到資料檔，請確認 fund_trend_log.csv 與 fund_holdings_history.csv 存在。")
        return

    # 讀取資料
    df_holdings = pd.read_csv(holdings_filename)
    df_trend = pd.read_csv(trend_filename)
    
    # 確保日期排序
    df_holdings['日期'] = df_holdings['日期'].astype(str)
    df_trend['日期'] = df_trend['日期'].astype(str)
    df_holdings = df_holdings.sort_values('日期').reset_index(drop=True)
    df_trend = df_trend.sort_values('日期').reset_index(drop=True)

    # 1. 定義時間錨點
    dates_trend = sorted(df_trend['日期'].unique())
    if len(dates_trend) < 5:
        print("⚠️ 資料不足 5 天，無法製作週報。")
        return

    t_curr = dates_trend[-1]
    
    # 找上周日期 (回推 5 筆)
    if len(dates_trend) >= 6:
        t_prev = dates_trend[-6]
    else:
        t_prev = dates_trend[0]
        
    print(f"📅 統計區間: {t_prev} ~ {t_curr}")

    # 2. 執行分析
    try:
        report = analyze_trend_strategy(df_trend, t_curr, t_prev)
        new_in, buys, sells = analyze_holdings_weekly(df_holdings, t_curr, t_prev)
        
        # 3. 概念股配置分析
        concept_data = {'increases': [], 'decreases': [], 'group_stock_changes': {}}
        try:
            df_curr = df_holdings[df_holdings['日期'] == t_curr]
            df_prev_h = df_holdings[df_holdings['日期'] == t_prev]
            
            if not df_curr.empty and not df_prev_h.empty:
                group_weights_curr = calculate_group_weights(df_curr, code_col='股票代號', weight_col='持股權重')
                group_weights_prev = calculate_group_weights(df_prev_h, code_col='股票代號', weight_col='持股權重')
                
                group_changes = {}
                all_groups = set(group_weights_curr.keys()) | set(group_weights_prev.keys())
                for g in all_groups:
                    w_curr = group_weights_curr.get(g, 0)
                    w_prev = group_weights_prev.get(g, 0)
                    change = w_curr - w_prev
                    group_changes[g] = (w_curr, change)
                
                sorted_groups = sorted(group_changes.items(), key=lambda x: x[1][1], reverse=True)
                concept_data['increases'] = [(g, w, c) for g, (w, c) in sorted_groups if c > 0][:3]
                concept_data['decreases'] = sorted([(g, w, c) for g, (w, c) in sorted_groups if c < 0], key=lambda x: x[2])[:3]
                
                group_stock_changes = calculate_group_stock_changes(
                    df_curr, df_prev_h,
                    code_col='股票代號', name_col='股票名稱', shares_col='股數'
                )
                concept_data['group_stock_changes'] = group_stock_changes
                print("✅ 概念股配置分析完成")
        except Exception as e:
            print(f"⚠️ 概念股分析失敗: {e}")
        
        # 4. 簡易 AI 總結生成
        buy_names = [x['name'] for x in buys[:2]]
        sell_names = [x['name'] for x in sells[:2]]
        
        ai_summary = ""
        if report['signal'] == "🔴" or report['signal'] == "🚀":
            ai_summary = f"經理人本周轉趨積極，重點加碼{'、'.join(buy_names)}。"
        elif report['signal'] == "🔵" or report['signal'] == "🟠":
            ai_summary = f"經理人本周偏向調節，主要減碼{'、'.join(sell_names)}。"
        else:
            ai_summary = "經理人操作相對保守，多空互見。"

        # 5. 生成圖片報告
        print("🖼️ 正在生成週報圖片...")
        report_data = {
            'date_range': {
                'start': t_prev,
                'end': t_curr
            },
            'signal': {
                'emoji': report['signal'],
                'strategy': report['strategy'],
                'reason': report['reason']
            },
            'exp_diff': report['exp_diff'],
            'avg_sp': report['avg_sp'],
            'has_inflow': report['has_inflow'],
            'total_exposure': report['total_exposure'],
            'new_entries': new_in,
            'buys': buys,
            'sells': sells,
            'concept': concept_data,
            'ai_summary': ai_summary
        }
        
        image_path = generate_weekly_report_image(report_data)
        
        if image_path:
            send_telegram_photo(image_path, f"00981A 經理人週報 - {t_prev} ~ {t_curr}")
            
            try:
                os.remove(image_path)
                print(f"🗑️ 已刪除暫存圖片: {image_path}")
            except:
                pass
        else:
            # Fallback: 純文字報告
            print("⚠️ 圖片生成失敗，改用文字報告")
            msg = f"📅 【AI 經理人周戰報】 (統計區間: {t_prev} ~ {t_curr})\n"
            msg += "==========================================\n"
            msg += f"🏆 【周級別總判斷】：{report['signal']} {report['strategy']}\n"
            msg += f"• 戰略解讀：{report['reason']}\n"
            msg += f"• 數據細節：曝險變動 {report['exp_diff']:+.1f}% | 動作流 SP {report['avg_sp']:.2f}\n"
            msg += "==========================================\n"
            msg += f"💡 AI 總結：{ai_summary}\n"
            send_telegram_message(msg)

    except Exception as e:
        print(f"❌ 週報產生失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
