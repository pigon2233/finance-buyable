#!/usr/bin/env python3
"""
美股回測 - 多策略對比
測試 NYFANG (FANG+) 10支 + NU, IONQ, CMPS, SCHD
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

# FANG+ 成分股 + 其他
US_STOCKS = [
    'AAPL', 'AMZN', 'META', 'NFLX', 'GOOGL',
    'MSFT', 'NVDA', 'TSLA', 'BIDU', 'SNAP',
    'NU', 'IONQ', 'CMPS', 'SCHD'
]

START = '2020-01-01'
END = '2026-03-25'

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    epsilon = 1e-8
    high_low_range = df['High'] - df['Low'] + epsilon
    df['Net_Pressure'] = (df['Close'] - df['Low']) / high_low_range - (df['High'] - df['Close']) / high_low_range
    df['Volume_Factor'] = df['Volume'] / (df['Volume'].rolling(20).mean() + epsilon)
    df['Prev_Close'] = df['Close'].shift(1)
    df['TR'] = df[['High', 'Prev_Close']].max(axis=1) - df[['Low', 'Prev_Close']].min(axis=1)
    df['ATR'] = df['TR'].rolling(14).mean()
    df['VP'] = (df['ATR'] / (df['Close'] + epsilon)).clip(lower=0.01)
    df['DMPI'] = ((df['Net_Pressure'] * df['Volume_Factor']) / df['VP']).rolling(2).mean()
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + gain / (loss + epsilon)))
    df['EMA_Fast'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_Slow'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA_Fast'] - df['EMA_Slow']
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    return df

def generate_signal(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['Signal'] = 0
    df['Position'] = 0
    LARGE_UPPER, LARGE_LOWER = 27, -15
    SMALL_UPPER, SMALL_LOWER = 3, -40
    current_pos = 0
    signals, positions = [], []
    for i in range(len(df)):
        dmpi = df['DMPI'].iloc[i] if not pd.isna(df['DMPI'].iloc[i]) else 0
        rsi = df['RSI'].iloc[i] if not pd.isna(df['RSI'].iloc[i]) else 50
        macd = df['MACD'].iloc[i] if not pd.isna(df['MACD'].iloc[i]) else 0
        macd_hist = df['MACD_Hist'].iloc[i] if not pd.isna(df['MACD_Hist'].iloc[i]) else 0
        regime = 'LARGE' if (macd > 0 and macd_hist >= 0) else ('SMALL' if (macd < 0 and macd_hist <= 0) else 'FLAT')
        next_pos = current_pos
        if regime == 'LARGE':
            next_pos = 0 if (dmpi >= LARGE_UPPER or dmpi <= LARGE_LOWER) else 1
        elif regime == 'SMALL':
            next_pos = 0 if (dmpi >= SMALL_UPPER or dmpi <= SMALL_LOWER) else 1
        else:
            next_pos = 1 if rsi < 50 else (0 if rsi > 80 else current_pos)
        signal = 1 if (next_pos == 1 and current_pos == 0) else (-1 if (next_pos == 0 and current_pos == 1) else 0)
        signals.append(signal)
        positions.append(current_pos)
        current_pos = next_pos
    df['Signal'] = signals
    df['Position'] = positions
    return df

# ===== 下載資料 =====
print("=" * 70)
print("📊 美股回測 - 多策略對比")
print("=" * 70)
print(f"回測區間: {START} ~ {END} | 股票: {len(US_STOCKS)} 支")
print("\n🔍 下載歷史資料...", flush=True)

processed = {}
for stock in US_STOCKS:
    try:
        df = yf.Ticker(stock).history(start=START, end=END)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if len(df) < 60:
            print(f"  {stock}: 資料不足", flush=True)
            continue
        df = calculate_indicators(df)
        df = generate_signal(df)
        processed[stock] = df
        print(f"  {stock}: OK ({len(df)} 筆)", flush=True)
    except Exception as e:
        print(f"  {stock}: Error - {e}", flush=True)

print(f"\n成功處理 {len(processed)}/{len(US_STOCKS)} 支")

# ===== 收集訊號 =====
buy_signals = []
for stock, df in processed.items():
    for i in range(60, len(df)):
        if int(df['Signal'].iloc[i]) != 1:
            continue
        date = df.index[i].date()
        row = df.iloc[i]
        dmpi = row['DMPI'] if not pd.isna(row['DMPI']) else 0
        macd = row['MACD'] if not pd.isna(row['MACD']) else 0
        macd_hist = row['MACD_Hist'] if not pd.isna(row['MACD_Hist']) else 0
        rsi = row['RSI'] if not pd.isna(row['RSI']) else 50
        vol_ratio = df['Volume'].iloc[i] / (df['Volume'].iloc[:i+1].rolling(20).mean().iloc[-1] + 1e-8)
        regime = 'LARGE' if (macd > 0 and macd_hist >= 0) else ('SMALL' if (macd < 0 and macd_hist <= 0) else 'FLAT')
        buy_signals.append({
            'date': date, 'stock': stock, 'dmpi': dmpi, 'volume_ratio': max(vol_ratio, 0.01),
            'rsi': rsi, 'regime': regime, 'entry_price': df['Close'].iloc[i],
            'entry_idx': i, 'df': df
        })

print(f"總共 {len(buy_signals)} 個買進訊號\n")

signals_by_date = defaultdict(list)
for s in buy_signals:
    signals_by_date[s['date']].append(s)

# ===== 評分策略 =====
def score_A(candidates):
    if len(candidates) < 2: return candidates
    max_vol = max(c['volume_ratio'] for c in candidates)
    for c in candidates:
        dmpi_score = 100 * max(0, 1 - abs(c['dmpi'] - 5) / 30)
        vol_score = 100 * c['volume_ratio'] / max_vol if max_vol > 0 else 50
        c['score'] = dmpi_score * 0.7 + vol_score * 0.3
    return candidates

def score_B(candidates):
    if len(candidates) < 2: return candidates
    max_vol = max(c['volume_ratio'] for c in candidates)
    for c in candidates:
        dmpi_score = 100 * max(0, 1 - abs(c['dmpi'] - 5) / 30)
        vol_score = 100 * c['volume_ratio'] / max_vol if max_vol > 0 else 50
        regime_score = 100 if c['regime'] == 'LARGE' else (50 if c['regime'] == 'FLAT' else 0)
        c['score'] = dmpi_score * 0.4 + vol_score * 0.2 + regime_score * 0.4
    return candidates

def score_C(candidates):
    if len(candidates) < 2: return candidates
    max_vol = max(c['volume_ratio'] for c in candidates)
    for c in candidates:
        regime_score = 100 if c['regime'] == 'LARGE' else (40 if c['regime'] == 'FLAT' else 0)
        if 50 <= c['rsi'] <= 70: rsi_score = 100
        elif c['rsi'] < 50: rsi_score = 50 + 50 * c['rsi'] / 50
        else: rsi_score = max(0, 100 - (c['rsi'] - 70) * 3)
        vol_score = 100 * c['volume_ratio'] / max_vol if max_vol > 0 else 50
        c['score'] = regime_score * 0.50 + rsi_score * 0.30 + vol_score * 0.20
    return candidates

strategies = {
    'A - 基準(DMPI+Vol)': score_A,
    'B - Regime優先權': score_B,
    'C - 動能策略I': score_C,
}

results = {}
for name, scoring_func in strategies.items():
    high_trades, low_trades = [], []
    for date, candidates in sorted(signals_by_date.items()):
        if len(candidates) < 2: continue
        scored = scoring_func([c.copy() for c in candidates])
        scored.sort(key=lambda x: x['score'], reverse=True)
        best, worst = scored[0], scored[-1]
        # 高分
        df = best['df']
        for j in range(best['entry_idx'] + 1, len(df)):
            if int(df['Signal'].iloc[j]) == -1:
                ret = (df['Close'].iloc[j] - best['entry_price']) / best['entry_price'] * 100
                high_trades.append({'stock': best['stock'], 'return': ret, 'regime': best['regime']})
                break
        # 低分
        df = worst['df']
        for j in range(worst['entry_idx'] + 1, len(df)):
            if int(df['Signal'].iloc[j]) == -1:
                ret = (df['Close'].iloc[j] - worst['entry_price']) / worst['entry_price'] * 100
                low_trades.append({'stock': worst['stock'], 'return': ret, 'regime': worst['regime']})
                break

    if high_trades and low_trades:
        hr = [t['return'] for t in high_trades]
        lr = [t['return'] for t in low_trades]
        results[name] = {
            'high_avg': np.mean(hr), 'high_wr': len([r for r in hr if r > 0]) / len(hr) * 100, 'high_n': len(hr),
            'low_avg': np.mean(lr), 'low_wr': len([r for r in lr if r > 0]) / len(lr) * 100, 'low_n': len(lr),
            'diff': np.mean(hr) - np.mean(lr)
        }

print("=" * 80)
print("🏆 美股評分策略回測結果（14支股票）")
print("=" * 80)
print(f"{'策略':<25} {'高分均酬':>10} {'高分勝率':>8} {'低分均酬':>10} {'低分勝率':>8} {'差異':>8} {'有用':>5}")
print("-" * 80)
for name, r in sorted(results.items(), key=lambda x: x[1]['diff'], reverse=True):
    v = "✅" if r['diff'] > 0 else "❌"
    print(f"{name:<25} {r['high_avg']:>+10.2f}% {r['high_wr']:>7.1f}% {r['low_avg']:>+10.2f}% {r['low_wr']:>7.1f}% {r['diff']:>+8.2f}% {v:>5}")
if results:
    best = sorted(results.items(), key=lambda x: x[1]['diff'], reverse=True)[0]
    print(f"\n💡 美股最佳策略：{best[0]}")
    print(f"   高分組：+{best[1]['high_avg']:.2f}% 勝率{best[1]['high_wr']:.1f}% ({best[1]['high_n']}筆)")
