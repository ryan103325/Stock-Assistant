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
# 設定路徑
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # src/策略庫/00981a_基金 -> src/策略庫 -> src
DATA_FOLDER = os.path.join(BASE_DIR, "data_core")
trend_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fund_trend_log.csv') 
holdings_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fund_holdings_history.csv')

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

def clean_float(val):
    try:
        return float(str(val).replace(',', '').replace('%', '').strip())
    except:
        return 0.0

# ==========================================
# 🧠 模組一：持股結構變動分析
# ==========================================
def analyze_holdings_weekly(df_holdings, t_curr, t_prev):
    """
    分析本周 vs 上周的持股變化
    """
    df_curr = df_holdings[df_holdings['日期'] == t_curr].copy()
    df_prev = df_holdings[df_holdings['日期'] == t_prev].copy()
    
    # 建立映射: Name -> ID, Name -> Shares, Name -> Weight
    # 假設 CSV 欄位: 日期, 股票代號, 股票名稱, 股數, 持股權重
    
    # 股數清理
    df_curr['Shares'] = df_curr['股數'].apply(clean_float)
    df_prev['Shares'] = df_prev['股數'].apply(clean_float)
    df_curr['Weight'] = df_curr['持股權重'].apply(clean_float)
    
    map_id = dict(zip(df_curr['股票名稱'], df_curr['股票代號']))
    # 對於不在本周名單但上周有的，也要記錄代號
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
        new_entrants.append((name, code, weight))
    
    # Sort by weight desc
    new_entrants.sort(key=lambda x: x[2], reverse=True)

    # B. 買賣超計算 (針對交集)
    common_names = set_curr | set_prev # 改為聯集，涵蓋新進與退出，視為0
    diff_list = []
    
    for name in common_names:
        s_curr = dict_curr.get(name, 0)
        s_prev = dict_prev.get(name, 0)
        diff = s_curr - s_prev
        if diff != 0:
            code = map_id.get(name, "")
            diff_list.append((name, code, diff))
            
    # Top 5 Buys
    buys = sorted([x for x in diff_list if x[2] > 0], key=lambda x: x[2], reverse=True)[:5]
    # Top 5 Sells
    sells = sorted([x for x in diff_list if x[2] < 0], key=lambda x: x[2])[:5] # 負最大排前面

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

    # 2. 周均動作流 (抓取 t_curr 往前推 5 筆資料的 SP值 平均)
    # 找出 t_curr 的 index
    idx_curr = df_trend[df_trend['日期'] == t_curr].index[0]
    # 取 slice: idx_curr - 4 到 idx_curr + 1 (因為 iloc 不包含 end) -> 但 DataFrame index 可能不是連續整數
    # 簡單做法: 取日期 <= t_curr 的最後 5 筆
    last_5 = df_trend[df_trend['日期'] <= t_curr].tail(5)
    if 'SP值' in last_5.columns:
        avg_sp = last_5['SP值'].apply(clean_float).mean()
    else:
        avg_sp = 0.0

    # 3. 資金源頭 (本周)
    # 假設 CSV 有 '申贖應付款' 或 'sub_payable'/'red_payable'
    # 根據 00981a.py 邏輯，存的是 '申贖應付款' (raw value)
    raw_subs = clean_float(row_curr.get('申贖應付款', 0))
    
    # 判斷資金方向
    has_inflow = raw_subs < -1000000 # 假設單位，或直接判斷負值 (申購)
    # 其實邏輯書上寫: "資金: 有申購" -> 申購應付款為負
    # 這裡我們用 raw_subs < 0 代表有申購款 (欠憑證)
    
    # Liquidity Party Check (Week High)
    # 檢查是否為近 5 日最大量 (負最多)
    is_party = False
    last_5_subs = last_5['申贖應付款'].apply(clean_float)
    if raw_subs < 0 and raw_subs == last_5_subs.min():
        # 且金額夠大 (例如 > 0.8% 淨資產? 這裡先簡化用絕對比較或趨勢)
        is_party = True

    # 判斷邏輯矩陣
    signal = "⚪"
    strategy = "區間震盪 (Consolidation)"
    reason = "操作方向不明"

    # 🚀 資金派對
    if is_party and avg_sp < 0: # 申購暴增 + 買進
        signal = "🚀"
        strategy = "資金派對 (Liquidity Party)"
        reason = "申購款暴增且持續買進，新資金潮湧入。"

    # 🔴 攻擊型建倉
    elif exp_diff > 2.0 and avg_sp < -0.2:
        signal = "🔴"
        strategy = "攻擊型建倉 (Accumulation)"
        reason = f"本周曝險顯著增加 (+{exp_diff:.1f}%)，且連續淨買入。"

    # 🔵 防禦撤退
    elif exp_diff < -3.0 and avg_sp > 0: # 淨賣出
        signal = "🔵"
        strategy = "防禦撤退 (Defensive)"
        reason = f"本周曝險大幅下降 ({exp_diff:.1f}%)，經理人正在逃命。"

    # 🟢 低檔回補
    elif exp_diff > -1.0 and exp_diff < 1.0: # 微變
        if avg_sp < -0.5 and exp_curr < 90:
            signal = "🟢"
            strategy = "低檔回補/抄底 (Bottom Fishing)"
            reason = "水位雖低但買盤強勁，主力正在低檔吸籌。"

    # 🟠 高檔出貨
    elif avg_sp > 0.2: # 淨賣出
        # 曝險持平或微降 (上面的防禦已經抓過大幅下降，這裡抓微降或持平)
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
        "has_inflow": raw_subs < 0
    }

# ==========================================
# 🚀 主程式
# ==========================================
def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"🚀 啟動 AI 基金週報分析系統... ({today})")
    
    # 策略 1: 檢查 TAIEX.csv 是否有今天的資料 (最準確)
    taiex_path = os.path.join(DATA_FOLDER, "TAIEX.csv")
    is_trading_day = False
    
    if os.path.exists(taiex_path):
        try:
            with open(taiex_path, "r") as f:
                last_line = f.readlines()[-1]
                last_date = last_line.split(",")[0].strip()
                last_date = last_date.replace("/", "-")
                
                if last_date == today:
                    is_trading_day = True
                    print(f"✅ TAIEX 資料日期 ({last_date}) 與今日相符，確認為交易日。")
                else:
                    print(f"📅 TAIEX 最新日期 ({last_date}) 與今日 ({today}) 不符。")
        except Exception as e:
            print(f"⚠️ 無法讀取 TAIEX 驗證日期: {e}")
            
    force_mode = "--force" in sys.argv
    if not is_trading_day:
        if force_mode:
            print(f"⚠️ [Force Mode] TAIEX 日期不符，但強制繼續執行。")
        else:
            print("😴 非交易日或資料尚未更新 (TAIEX Check Failed)，跳過執行。")
            return

    if not os.path.exists(holdings_filename) or not os.path.exists(trend_filename):
        print("❌ 找不到資料檔，請確認 fund_trend_log.csv 與 fund_holdings_history.csv 存在。")
        return

    # 讀取資料
    df_holdings = pd.read_csv(holdings_filename)
    df_trend = pd.read_csv(trend_filename)
    
    # 確保日期排序
    df_holdings['日期'] = sorted(df_holdings['日期']) # 字串排序即可 (YYYY-MM-DD)
    df_trend['日期'] = sorted(df_trend['日期'])

    # 1. 定義時間錨點
    # 取得最新日期
    dates_trend = sorted(df_trend['日期'].unique())
    if len(dates_trend) < 5:
        print("⚠️ 資料不足 5 天，無法製作週報。")
        return

    t_curr = dates_trend[-1]
    
    # 找上周日期 (回推 5 筆)
    # 因為是交易日，直接取 index -5
    if len(dates_trend) >= 6:
        t_prev = dates_trend[-6] # -1 is current, -6 is 5 days ago diff
    else:
        t_prev = dates_trend[0]
        
    print(f"📅 統計區間: {t_prev} ~ {t_curr}")

    # 2. 執行分析
    try:
        report = analyze_trend_strategy(df_trend, t_curr, t_prev)
        new_in, buys, sells = analyze_holdings_weekly(df_holdings, t_curr, t_prev)
        
        # 3. 產生報告
        msg = f"📅 【AI 經理人周戰報】 (統計區間: {t_prev} ~ {t_curr})\n"
        msg += "=========================================\n"
        msg += f"🏆 【周級別總判斷】：{report['signal']} {report['strategy']}\n"
        msg += f"• 戰略解讀：{report['reason']}\n"
        msg += f"• 數據細節：曝險變動 {report['exp_diff']:+.1f}% | 動作流 SP {report['avg_sp']:.2f}\n"
        
        msg += "=========================================\n"
        msg += "🆕 【新進名單 (潛力股)】\n"
        if new_in:
            for n, c, w in new_in[:5]: # 只列前5
                msg += f"{n} ({c}) | 權重 {w}%\n"
        else:
            msg += "無新進個股。\n"

        msg += "\n📈 【本周加碼 (買超前五)】\n"
        if buys:
            for n, c, d in buys:
                msg += f"{n} ({c}) | +{int(d/1000):,} 張\n"
        else:
            msg += "無顯著買盤。\n"

        msg += "\n📉 【本周減碼 (賣超前五)】\n"
        if sells:
            for n, c, d in sells:
                msg += f"{n} ({c}) | {int(d/1000):,} 張\n" # diff is negative
        else:
            msg += "無顯著賣盤。\n"

        msg += "=========================================\n"
        
        # 簡易 AI 總結生成
        buy_names = [x[0] for x in buys[:2]]
        sell_names = [x[0] for x in sells[:2]]
        
        ai_summary = "💡 AI 總結："
        if report['signal'] == "🔴" or report['signal'] == "🚀":
            ai_summary += f"經理人本周轉趨積極，重點加碼{','.join(buy_names)}。"
        elif report['signal'] == "🔵" or report['signal'] == "🟠":
            ai_summary += f"經理人本周偏向調節，主要減碼{','.join(sell_names)}。"
        else:
            ai_summary += "經理人操作相對保守，多空互見。"
            
        msg += ai_summary
        
        print("\n" + msg)
        send_telegram_message(msg)

    except Exception as e:
        print(f"❌ 週報產生失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
