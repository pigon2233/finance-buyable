#!/usr/bin/env python3
"""
美股參數對比回測
測試 scan.py參數 vs strategy.py參數 哪個用在美股較好
"""
import yfinance as yf
import pandas as pd
import numpy as np
from collections import defaultdict

US_STOCKS = [
    'AAPL', 'AMZN', 'META', 'NFLX', 'GOOGL',
    'MSFT', 'NVDA', 'TSLA', 'BIDU', 'SNAP',
    'NU', 'IONQ', 'CMPS', 'SCHD'
]

START = '2020-01-01'
END = '2026-03-25'

def calculate_indicators(df):
    df = df.copy()
    e = 1e-8
    df['NP'] = (df['Close']-df['Low'])/(df['High']-df['Low']+e) - (df['High']-df['Close'])/(df['High']-df['Low']+e)
    df['VF'] = df['Volume']/(df['Volume'].rolling(20).mean()+e)
    df['PC'] = df['Close'].shift(1)
    df['TR'] = df[['High','PC']].max(1) - df[['Low','PC']].min(1)
    df['ATR'] = df['TR'].rolling(14).mean()
    df['VP'] = (df['ATR']/(df['Close']+e)).clip(lower=0.01)
    df['DMPI'] = ((df['NP']*df['VF'])/df['VP']).rolling(2).mean()
    d = df['Close'].diff()
    g = d.where(d>0,0).rolling(14).mean()
    l = (-d.where(d<0,0)).rolling(14).mean()
    df['RSI'] = 100-(100/(1+g/(l+e)))
    df['EMAF'] = df['Close'].ewm(span=12,adjust=False).mean()
    df['EMAS'] = df['Close'].ewm(span=26,adjust=False).mean()
    df['MACD'] = df['EMAF']-df['EMAS']
    df['MACDS'] = df['MACD'].ewm(span=9,adjust=False).mean()
    df['MACDH'] = df['MACD']-df['MACDS']
    return df

def backtest_params(df, params, label):
    """用指定參數跑回測"""
    LARGE_UPPER = params['LARGE_UPPER']
    LARGE_LOWER = params['LARGE_LOWER']
    SMALL_UPPER = params['SMALL_UPPER']
    SMALL_LOWER = params['SMALL_LOWER']
    
    trades = []
    pos = 0
    entry_price = 0
    entry_date = None
    
    for i in range(60, len(df)):
        dmpi = df['DMPI'].iloc[i] if not pd.isna(df['DMPI'].iloc[i]) else 0
        rsi = df['RSI'].iloc[i] if not pd.isna(df['RSI'].iloc[i]) else 50
        macd = df['MACD'].iloc[i] if not pd.isna(df['MACD'].iloc[i]) else 0
        macdh = df['MACDH'].iloc[i] if not pd.isna(df['MACDH'].iloc[i]) else 0
        
        if macd > 0 and macdh >= 0:
            regime = 'LARGE'
        elif macd < 0 and macdh <= 0:
            regime = 'SMALL'
        else:
            regime = 'FLAT'
        
        next_pos = pos
        if regime == 'LARGE':
            next_pos = 0 if (dmpi >= LARGE_UPPER or dmpi <= LARGE_LOWER) else 1
        elif regime == 'SMALL':
            next_pos = 0 if (dmpi >= SMALL_UPPER or dmpi <= SMALL_LOWER) else 1
        else:
            next_pos = 1 if rsi < 50 else (0 if rsi > 80 else pos)
        
        # 進場
        if next_pos == 1 and pos == 0:
            entry_price = df['Close'].iloc[i]
            entry_date = df.index[i]
        # 出場
        elif next_pos == 0 and pos == 1:
            if entry_date is not None:
                ret = (df['Close'].iloc[i] - entry_price) / entry_price * 100
                trades.append({
                    'entry': entry_date, 'exit': df.index[i],
                    'return': ret, 'regime': regime,
                    'dmpi': dmpi, 'rsi': rsi
                })
            entry_date = None
        
        pos = next_pos
    
    return trades

print("=" * 70)
print("📊 美股參數對比回測")
print("=" * 70)
print(f"股票: {len(US_STOCKS)} 支 | 回測區間: {START} ~ {END}")
print()

# 兩套參數
SCAN_PARAMS = {'LARGE_UPPER': 27, 'LARGE_LOWER': -15, 'SMALL_UPPER': 3, 'SMALL_LOWER': -40}
STRATEGY_PARAMS = {'LARGE_UPPER': 30, 'LARGE_LOWER': -20, 'SMALL_UPPER': 5, 'SMALL_LOWER': -35}

results = {'scan.py參數': [], 'strategy.py參數': []}

for stock in US_STOCKS:
    try:
        df = yf.Ticker(stock).history(start=START, end=END)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if len(df) < 60:
            continue
        df = calculate_indicators(df)
        
        scan_trades = backtest_params(df, SCAN_PARAMS, 'scan')
        strategy_trades = backtest_params(df, STRATEGY_PARAMS, 'strategy')
        
        results['scan.py參數'].extend(scan_trades)
        results['strategy.py參數'].extend(strategy_trades)
        
        print(f"  {stock}: scan={len(scan_trades)}筆, strategy={len(strategy_trades)}筆", flush=True)
    except Exception as e:
        print(f"  {stock}: Error", flush=True)

print()
print("=" * 70)
print("🏆 結果對比")
print("=" * 70)

for name, trades in results.items():
    if not trades:
        continue
    rets = [t['return'] for t in trades]
    wr = len([r for r in rets if r > 0]) / len(rets) * 100
    avg = np.mean(rets)
    pos_rets = [r for r in rets if r > 0]
    neg_rets = [r for r in rets if r < 0]
    avg_win = np.mean(pos_rets) if pos_rets else 0
    avg_loss = np.mean(neg_rets) if neg_rets else 0
    
    print(f"\n{name}:")
    print(f"  總交易: {len(trades)} 筆")
    print(f"  平均報酬: {avg:+.2f}%")
    print(f"  勝率: {wr:.1f}%")
    print(f"  平均獲利: {avg_win:+.2f}% | 平均虧損: {avg_loss:+.2f}%")
    print(f"  期望值: {wr/100*avg_win + (1-wr/100)*avg_loss:.2f}%")

# 總結
s_rets = [t['return'] for t in results['scan.py參數']]
st_rets = [t['return'] for t in results['strategy.py參數']]
if s_rets and st_rets:
    s_avg, st_avg = np.mean(s_rets), np.mean(st_rets)
    s_wr = len([r for r in s_rets if r > 0])/len(s_rets)*100
    st_wr = len([r for r in st_rets if r > 0])/len(st_rets)*100
    print()
    print("=" * 70)
    print("💡 結論:")
    if s_avg > st_avg:
        print(f"  scan.py參數較好：均酬 +{s_avg:.2f}% vs +{st_avg:.2f}%（差 {s_avg-st_avg:.2f}%）")
    else:
        print(f"  strategy.py參數較好：均酬 +{st_avg:.2f}% vs +{s_avg:.2f}%（差 {st_avg-s_avg:.2f}%）")
    print(f"  scan.py勝率: {s_wr:.1f}% | strategy.py勝率: {st_wr:.1f}%")
