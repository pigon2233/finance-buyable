#!/usr/bin/env python3
"""
冰可樂龍蝦：150 支動能標的自動化掃描器
修正點：yfinance 多層索引、AI 模組容錯、輸出格式優化
"""
import pandas as pd
import yfinance as yf
import sys
import warnings

warnings.filterwarnings('ignore')

# ========== 指標計算 (修正邏輯) ==========

def calculate_indicators(df):
    df = df.copy()
    # 統一處理 yfinance 的索引問題
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    epsilon = 1e-8
    
    # 1. DMPI 原始物理數值計算 (無閹割版)
    high_low_range = df['High'] - df['Low'] + epsilon
    buy_pressure = (df['Close'] - df['Low']) / high_low_range
    sell_pressure = (df['High'] - df['Close']) / high_low_range
    df['Net_Pressure'] = buy_pressure - sell_pressure
    
    avg_volume = df['Volume'].rolling(20).mean()
    df['Volume_Factor'] = df['Volume'] / (avg_volume + epsilon)
    
    df['Prev_Close'] = df['Close'].shift(1)
    df['TR'] = df[['High', 'Prev_Close']].max(axis=1) - df[['Low', 'Prev_Close']].min(axis=1)
    df['ATR'] = df['TR'].rolling(14).mean()
    
    # 計算 VP (波動率因子) 並計算 Raw_DMPI
    df['VP'] = (df['ATR'] / (df['Close'] + epsilon)).clip(lower=0.01)
    # 套用長官的公式：(Net_Pressure * Volume_Factor) / VP
    df['DMPI'] = ((df['Net_Pressure'] * df['Volume_Factor']) / df['VP']).rolling(2).mean()

    # 2. RSI 計算
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + gain / (loss + 1e-8)))

    # 3. MACD 計算
    df['EMA_Fast'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_Slow'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA_Fast'] - df['EMA_Slow']
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    return df

def get_signals(df):
    """執行長官的三位一體切換戰術"""
    row = df.iloc[-1]
    dmpi = row['DMPI']
    rsi = row['RSI']
    macd = row['MACD']
    hist = row['MACD_Hist']

    # 判定市場狀態 (Regime)
    if macd > 0 and hist >= 0:
        regime = '多頭'
    elif macd < 0 and hist <= 0:
        regime = '空頭'
    else:
        regime = '盤整'

    # 核心邏輯判斷 + 理由
    reason = ""
    
    if rsi < 25 and dmpi < -20:
        comp = '買'
        regime = '底部反彈'
        reason = f"[底部反彈] RSI={rsi:.1f} <25 且 DMPI={dmpi:.1f} <-20 (超賣反彈)"
    elif regime == '多頭':
        # MACD 大(多頭)：DMPI 保持在 -15 ~ +27 之間持續做多
        if -15 < dmpi < 27:
            comp = '買'
            reason = f"[多頭] DMPI={dmpi:.1f} 在通道內 (-15~27) 持續做多"
        else:
            comp = '賣'
            if dmpi >= 27:
                reason = f"[多頭] DMPI={dmpi:.1f} >27 離開通道(過熱)"
            else:
                reason = f"[多頭] DMPI={dmpi:.1f} <-15 跌破支撐"
    elif regime == '空頭':
        
        comp = '賣'
        
        reason = f"[空頭] 不操作"
    else:
        # MACD 持平(盤整)：切換為 RSI 測定
        if rsi < 30:
            comp = '買'
            reason = f"[盤整] RSI={rsi:.1f} <30 超賣"
        elif rsi > 70:
            comp = '賣'
            reason = f"[盤整] RSI={rsi:.1f} >70 超買"
        else:
            comp = '觀'
            reason = f"[盤整] RSI={rsi:.1f} 在中性區間"

    return {
        'dmpi': round(dmpi, 2),
        'rsi': round(rsi, 1),
        'macd': round(macd, 2),
        'regime': regime,
        'comp': comp,
        'reason': reason
    }

# ========== AI 模型 (防護性加載) ==========
ai_engine = None
try:
    from ml_engine import MLExpertEngine
    ai_engine = MLExpertEngine()
except ImportError:
    pass # 如果沒有 AI 模組則跳過

def get_ai_prediction(df):
    if ai_engine and hasattr(ai_engine, 'predict_action'):
        result = ai_engine.predict_action(df)
        return '買' if '做多' in result.get('action', '') else '觀'
    return '?'

# ========== 主程式執行面 ==========
if __name__ == "__main__":
    if len(sys.argv) > 1:
        tickers = sys.argv[1:]
    else:
        print("請輸入代碼 (例如: 2330.TW 2357.TW IONQ): ", end="")
        tickers = input().strip().split()

    if not tickers: sys.exit(0)

    print(f"\n{'代碼':<8} {'DMPI':>6} {'RSI':>5} {'MACD':>7} {'趨勢':>4} {'綜合':>3} {'結果'}")
    print("=" * 55)

    buy_list = []
    sell_list = []
    
    for ticker in tickers:
        try:
            df = yf.download(ticker, period="1y", progress=False)
            if df.empty or len(df) < 60: continue
            
            df = calculate_indicators(df)
            sig = get_signals(df)
            ai_pred = get_ai_prediction(df)
            
            # 格式化輸出
            color = "🔥" if sig['comp'] == '買' else ("🧹" if sig['comp'] == '賣' else "☕")
            result = f"{color}{sig['comp']}"
            
            # 只在有訊號時顯示理由
            if sig['comp'] != '觀':
                print(f"{ticker:<8} {sig['dmpi']:>6.1f} {sig['rsi']:>5.1f} {sig['macd']:>7.2f} {sig['regime']:>4} {sig['comp']:>3} {result} 📋 {sig['reason']}")
            else:
                print(f"{ticker:<8} {sig['dmpi']:>6.1f} {sig['rsi']:>5.1f} {sig['macd']:>7.2f} {sig['regime']:>4} {sig['comp']:>3} {result}")
            
            if sig['comp'] == '買':
                buy_list.append(ticker)
            elif sig['comp'] == '賣':
                sell_list.append(ticker)
        except Exception as e:
            print(f"{ticker:<8} Error")
    
    print("\n" + "=" * 65)
    print("🔥 強烈買進:", ", ".join(buy_list) if buy_list else "無")
    print("🧹 強烈賣出:", ", ".join(sell_list) if sell_list else "無")