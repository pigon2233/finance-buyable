#!/usr/bin/env python3
"""
評分系統回測（快速版）：驗證高分組是否戰勝低分組
"""
import yfinance as yf
import pandas as pd
import numpy as np
from strategy import calculate_dmpi, calculate_rsi, calculate_macd, generate_signals

LARGE_UPPER, LARGE_LOWER = 30, -20
SMALL_UPPER, SMALL_LOWER = 5, -35

START = '2020-01-01'
END = '2026-03-25'
TEST_STOCKS = [
    '2330.TW', '2317.TW', '2454.TW', '2308.TW', '2382.TW', '2412.TW',
    '2881.TW', '2882.TW', '2303.TW', '2886.TW', '2891.TW', '1301.TW',
    '1216.TW', '2884.TW', '2357.TW', '2892.TW', '3008.TW', '2603.TW',
    '2327.TW', '3034.TW', '2379.TW', '2912.TW', '1326.TW', '2409.TW',
    '6669.TW', '3037.TW', '1605.TW', '9904.TW', '3661.TW', '3443.TW'
]

print("=" * 70)
print("📊 評分系統回測（快速版）")
print("=" * 70)
print(f"回測區間: {START} ~ {END}")
print(f"測試股票: {len(TEST_STOCKS)} 支")
print("\n🔍 預先計算所有指標...", flush=True)

# STEP 1: 預先計算所有股票的指標
processed = {}
for stock in TEST_STOCKS:
    try:
        df = yf.Ticker(stock).history(start=START, end=END)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if len(df) < 60:
            continue
        df = calculate_dmpi(df)
        df = calculate_rsi(df)
        df = calculate_macd(df)
        df = generate_signals(df, indicator='綜合共振')
        processed[stock] = df
        print(f"  {stock}: OK ({len(df)} 筆)", flush=True)
    except Exception as e:
        print(f"  {stock}: Error - {e}", flush=True)

print(f"\n成功處理 {len(processed)}/{len(TEST_STOCKS)} 支股票\n")

# STEP 2: 收集所有 BUY 訊號 (date, stock, score_data)
buy_signals = []
for stock, df in processed.items():
    for i in range(60, len(df)):
        signal = int(df['Signal'].iloc[i])
        if signal != 1:
            continue
        date = df.index[i].date()
        row = df.iloc[i]
        macd = row['MACD']
        macd_hist = row.get('MACD_Hist', 0)
        dmpi = row['DMPI']
        volume_20_avg = df['Volume'].iloc[:i+1].rolling(20).mean().iloc[-1]
        volume_ratio = row['Volume'] / volume_20_avg if volume_20_avg > 0 else 1
        rsi = row['RSI']

        if macd > 0 and macd_hist >= 0:
            regime = 'LARGE'
            channel_middle = (LARGE_UPPER + LARGE_LOWER) / 2
        elif macd < 0 and macd_hist <= 0:
            regime = 'SMALL'
            channel_middle = (SMALL_UPPER + SMALL_LOWER) / 2
        else:
            regime = 'FLAT'
            channel_middle = 0

        dmpi_distance = abs(dmpi - channel_middle) if regime in ['LARGE', 'SMALL'] else abs(dmpi)
        buy_signals.append({
            'date': date,
            'stock': stock,
            'dmpi': dmpi,
            'dmpi_distance': dmpi_distance,
            'volume_ratio': max(volume_ratio, 0.01),
            'rsi': rsi,
            'regime': regime,
            'entry_price': df['Close'].iloc[i],
            'entry_idx': i
        })

print(f"總共 {len(buy_signals)} 個買進訊號\n")

# STEP 3: 按日期分組，計算相對排名
from collections import defaultdict
signals_by_date = defaultdict(list)
for s in buy_signals:
    signals_by_date[s['date']].append(s)

# 對每天的候選股做標準化和排名
high_trades = []  # (stock, entry_date, exit_date, entry_price, exit_price, regime, score)
low_trades = []

for date, candidates in sorted(signals_by_date.items()):
    if len(candidates) < 2:
        continue

    # 標準化評分
    max_dist = max(c['dmpi_distance'] for c in candidates)
    max_vol = max(c['volume_ratio'] for c in candidates)
    for c in candidates:
        c['dmpi_score'] = 100 * (1 - c['dmpi_distance'] / max_dist) if max_dist > 0 else 50
        c['volume_score'] = 100 * (c['volume_ratio'] / max_vol) if max_vol > 0 else 50
        c['total_score'] = c['dmpi_score'] * 0.7 + c['volume_score'] * 0.3

    candidates.sort(key=lambda x: x['total_score'], reverse=True)
    best = candidates[0]
    worst = candidates[-1]

    # 找離場日
    for pick in [best, worst]:
        stock = pick['stock']
        df = processed[stock]
        entry_idx = pick['entry_idx']
        exit_price = None
        exit_date = None

        for j in range(entry_idx + 1, len(df)):
            if int(df['Signal'].iloc[j]) == -1:
                exit_date = df.index[j].date()
                exit_price = df['Close'].iloc[j]
                break

        if exit_date is None:
            continue

        ret = (exit_price - pick['entry_price']) / pick['entry_price'] * 100
        trade = {
            'stock': stock,
            'entry_date': date,
            'exit_date': exit_date,
            'entry_price': pick['entry_price'],
            'exit_price': exit_price,
            'return': ret,
            'regime': pick['regime'],
            'score': pick['total_score']
        }
        if pick == best:
            high_trades.append(trade)
        else:
            low_trades.append(trade)

# 輸出結果
print("=" * 70)
print("🏆 高分組（當天評分最高的股票）")
print("-" * 70)
for t in sorted(high_trades, key=lambda x: x['entry_date']):
    print(f"  {t['entry_date']} {t['stock']:<8} 進{t['entry_price']:.2f} 出{t['exit_price']:.2f} 報酬:{t['return']:>+6.1f}% Reg:{t['regime']}")

print("\n" + "=" * 70)
print("🥺 低分組（當天評分最低的股票）")
print("-" * 70)
for t in sorted(low_trades, key=lambda x: x['entry_date']):
    print(f"  {t['entry_date']} {t['stock']:<8} 進{t['entry_price']:.2f} 出{t['exit_price']:.2f} 報酬:{t['return']:>+6.1f}% Reg:{t['regime']}")

if high_trades:
    high_returns = [t['return'] for t in high_trades]
    high_wr = len([r for r in high_returns if r > 0]) / len(high_returns) * 100
    print(f"\n📈 高分組：平均報酬 {np.mean(high_returns):>+.2f}%  勝率 {high_wr:.1f}%  ({len(high_returns)} 筆)")

if low_trades:
    low_returns = [t['return'] for t in low_trades]
    low_wr = len([r for r in low_returns if r > 0]) / len(low_returns) * 100
    print(f"📉 低分組：平均報酬 {np.mean(low_returns):>+.2f}%  勝率 {low_wr:.1f}%  ({len(low_returns)} 筆)")

if high_trades and low_trades:
    diff = np.mean(high_returns) - np.mean(low_returns)
    verdict = "有效✅" if diff > 0 else "無效❌"
    print(f"\n💡 結論：評分系統 {verdict}")
    print(f"   高分組平均報酬比低分組 {'高' if diff > 0 else '低'} {abs(diff):.2f}%")
