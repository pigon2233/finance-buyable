#!/usr/bin/env python3
"""
評分系統回測 - 多策略對比
測試不同的評分邏輯，找出真正有效的
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
print("📊 多策略評分回測")
print("=" * 70)
print(f"回測區間: {START} ~ {END} | 股票: {len(TEST_STOCKS)} 支")
print("\n🔍 下載歷史資料...", flush=True)

# 預先計算所有股票的指標
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
        print(f"  {stock}: Error")

print(f"\n成功處理 {len(processed)}/{len(TEST_STOCKS)} 支\n")

# 收集所有 BUY 訊號
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
        close = df['Close'].iloc[i]

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
            'macd': macd,
            'macd_hist': macd_hist,
            'entry_price': close,
            'entry_idx': i,
            'df': df
        })

print(f"總共 {len(buy_signals)} 個買進訊號\n")

from collections import defaultdict
signals_by_date = defaultdict(list)
for s in buy_signals:
    signals_by_date[s['date']].append(s)

# ========== 評分策略定義 ==========
def score_method_A(candidates):
    """基準：DMPI偏離(70%) + 成交量(30%)"""
    if len(candidates) < 2:
        return candidates
    max_dist = max(c['dmpi_distance'] for c in candidates)
    max_vol = max(c['volume_ratio'] for c in candidates)
    for c in candidates:
        c['score'] = (100 * (1 - c['dmpi_distance'] / max_dist) if max_dist > 0 else 50) * 0.7 + \
                     (100 * c['volume_ratio'] / max_vol if max_vol > 0 else 50) * 0.3
    return candidates

def score_method_B(candidates):
    """Regime 優先權：多頭額外加分"""
    if len(candidates) < 2:
        return candidates
    max_dist = max(c['dmpi_distance'] for c in candidates)
    max_vol = max(c['volume_ratio'] for c in candidates)
    for c in candidates:
        base = (100 * (1 - c['dmpi_distance'] / max_dist) if max_dist > 0 else 50) * 0.6 + \
               (100 * c['volume_ratio'] / max_vol if max_vol > 0 else 50) * 0.2
        if c['regime'] == 'LARGE':
            base += 20  # 多頭額外加分
        elif c['regime'] == 'FLAT':
            base += 10  # 盤整加分
        # SMALL 不加分
        c['score'] = base
    return candidates

def score_method_C(candidates):
    """RSI 逆向評分：RSI 越低分數越高"""
    if len(candidates) < 2:
        return candidates
    max_dist = max(c['dmpi_distance'] for c in candidates)
    max_vol = max(c['volume_ratio'] for c in candidates)
    max_rsi = max(c['rsi'] for c in candidates)
    min_rsi = min(c['rsi'] for c in candidates)
    rsi_range = max_rsi - min_rsi if max_rsi != min_rsi else 1
    for c in candidates:
        # RSI 低 = 超賣 = 較佳買點
        rsi_score = 100 * (1 - (c['rsi'] - min_rsi) / rsi_range)
        c['score'] = (100 * (1 - c['dmpi_distance'] / max_dist) if max_dist > 0 else 50) * 0.5 + \
                     (100 * c['volume_ratio'] / max_vol if max_vol > 0 else 50) * 0.2 + \
                     rsi_score * 0.3
    return candidates

def score_method_D(candidates):
    """Regime + RSI 組合"""
    if len(candidates) < 2:
        return candidates
    max_dist = max(c['dmpi_distance'] for c in candidates)
    max_vol = max(c['volume_ratio'] for c in candidates)
    max_rsi = max(c['rsi'] for c in candidates)
    min_rsi = min(c['rsi'] for c in candidates)
    rsi_range = max_rsi - min_rsi if max_rsi != min_rsi else 1
    for c in candidates:
        rsi_score = 100 * (1 - (c['rsi'] - min_rsi) / rsi_range)
        base = (100 * (1 - c['dmpi_distance'] / max_dist) if max_dist > 0 else 50) * 0.4 + \
               (100 * c['volume_ratio'] / max_vol if max_vol > 0 else 50) * 0.2 + \
               rsi_score * 0.2
        if c['regime'] == 'LARGE':
            base += 20
        elif c['regime'] == 'FLAT':
            base += 8
        c['score'] = base
    return candidates

def score_method_E(candidates):
    """純 Regime 評分：Regime 最重要"""
    if len(candidates) < 2:
        return candidates
    max_dist = max(c['dmpi_distance'] for c in candidates)
    max_vol = max(c['volume_ratio'] for c in candidates)
    for c in candidates:
        regime_bonus = 50 if c['regime'] == 'LARGE' else (20 if c['regime'] == 'FLAT' else 0)
        dmpi_score = 100 * (1 - c['dmpi_distance'] / max_dist) if max_dist > 0 else 50
        vol_score = 100 * c['volume_ratio'] / max_vol if max_vol > 0 else 50
        c['score'] = regime_bonus * 0.5 + dmpi_score * 0.3 + vol_score * 0.2
    return candidates

def score_method_F(candidates):
    """DMPI 甜蜜點：DMPI 在通道中間附近最高分"""
    if len(candidates) < 2:
        return candidates
    for c in candidates:
        if c['regime'] == 'LARGE':
            # 多頭：-15 到 25，中間大約是 5
            ideal = (LARGE_UPPER + LARGE_LOWER) / 2  # = 5
            sweet_spot_score = 100 * max(0, 1 - abs(c['dmpi'] - ideal) / 30)
        elif c['regime'] == 'SMALL':
            # 空頭：-40 到 3，中間大約是 -18.5
            ideal = (SMALL_UPPER + SMALL_LOWER) / 2  # = -17.5
            sweet_spot_score = 100 * max(0, 1 - abs(c['dmpi'] - ideal) / 25)
        else:
            ideal = 0
            sweet_spot_score = 100 * max(0, 1 - abs(c['dmpi']) / 30)
        
        max_vol = max(x['volume_ratio'] for x in candidates)
        vol_score = 100 * c['volume_ratio'] / max_vol if max_vol > 0 else 50
        c['score'] = sweet_spot_score * 0.7 + vol_score * 0.3
    return candidates

def score_method_G(candidates):
    """綜合：Regime(30%) + DMPI甜蜜點(30%) + RSI(20%) + Vol(20%)"""
    if len(candidates) < 2:
        return candidates
    max_dist = max(c['dmpi_distance'] for c in candidates)
    max_vol = max(c['volume_ratio'] for c in candidates)
    max_rsi = max(c['rsi'] for c in candidates)
    min_rsi = min(c['rsi'] for c in candidates)
    rsi_range = max_rsi - min_rsi if max_rsi != min_rsi else 1
    for c in candidates:
        # Regime 分數
        regime_score = 100 if c['regime'] == 'LARGE' else (50 if c['regime'] == 'FLAT' else 0)
        # DMPI 甜蜜點
        if c['regime'] == 'LARGE':
            ideal = (LARGE_UPPER + LARGE_LOWER) / 2
            dmpi_score = 100 * max(0, 1 - abs(c['dmpi'] - ideal) / 30)
        elif c['regime'] == 'SMALL':
            ideal = (SMALL_UPPER + SMALL_LOWER) / 2
            dmpi_score = 100 * max(0, 1 - abs(c['dmpi'] - ideal) / 25)
        else:
            dmpi_score = 100 * max(0, 1 - abs(c['dmpi']) / 30)
        # RSI 分數
        rsi_score = 100 * (1 - (c['rsi'] - min_rsi) / rsi_range)
        # Vol 分數
        vol_score = 100 * c['volume_ratio'] / max_vol if max_vol > 0 else 50
        c['score'] = regime_score * 0.30 + dmpi_score * 0.30 + rsi_score * 0.20 + vol_score * 0.20
    return candidates

def score_method_H(candidates):
    """買在回檔低點：DMPI < 0 的空頭/超賣時進場"""
    if len(candidates) < 2:
        return candidates
    max_dist = max(c['dmpi_distance'] for c in candidates)
    max_vol = max(c['volume_ratio'] for c in candidates)
    max_rsi = max(c['rsi'] for c in candidates)
    min_rsi = min(c['rsi'] for c in candidates)
    rsi_range = max_rsi - min_rsi if max_rsi != min_rsi else 1
    for c in candidates:
        # Regime 分數（多頭最高）
        regime_score = 100 if c['regime'] == 'LARGE' else (50 if c['regime'] == 'FLAT' else 20)
        # RSI 越低越好（超賣反彈）
        rsi_score = 100 * (1 - (c['rsi'] - min_rsi) / rsi_range)
        # DMPI 在低位時進場（dmpi_score 越高代表越在低檔）
        dmpi_score = 100 * max(0, (c['dmpi'] + 50) / 100)  # 標準化到 0-100
        vol_score = 100 * c['volume_ratio'] / max_vol if max_vol > 0 else 50
        c['score'] = regime_score * 0.35 + rsi_score * 0.30 + dmpi_score * 0.20 + vol_score * 0.15
    return candidates

def score_method_I(candidates):
    """動能評分：多頭 + 價格在均線上 + 強勢股"""
    if len(candidates) < 2:
        return candidates
    max_vol = max(c['volume_ratio'] for c in candidates)
    max_rsi = max(c['rsi'] for c in candidates)
    min_rsi = min(c['rsi'] for c in candidates)
    rsi_range = max_rsi - min_rsi if max_rsi != min_rsi else 1
    for c in candidates:
        # Regime 分數（多頭最高）
        regime_score = 100 if c['regime'] == 'LARGE' else (40 if c['regime'] == 'FLAT' else 0)
        # RSI 在強勢區 (50-70)
        if 50 <= c['rsi'] <= 70:
            rsi_score = 100
        elif c['rsi'] < 50:
            rsi_score = 50 + 50 * c['rsi'] / 50
        else:
            rsi_score = max(0, 100 - (c['rsi'] - 70) * 3)
        # 成交量突破
        vol_score = 100 * c['volume_ratio'] / max_vol if max_vol > 0 else 50
        c['score'] = regime_score * 0.50 + rsi_score * 0.30 + vol_score * 0.20
    return candidates

# ========== 跑回測 ==========
strategies = {
    'A - 基準(DMPI偏離+Vol)': score_method_A,
    'B - Regime優先權': score_method_B,
    'C - RSI逆向': score_method_C,
    'D - Regime+RSI': score_method_D,
    'E - 純Regime': score_method_E,
    'F - DMPI甜蜜點': score_method_F,
    'G - 綜合評分': score_method_G,
    'H - 買在回檔低點': score_method_H,
    'I - 動能強勢股': score_method_I,
}

results = {}

for name, scoring_func in strategies.items():
    high_trades = []
    low_trades = []

    for date, candidates in sorted(signals_by_date.items()):
        if len(candidates) < 2:
            continue

        scored = scoring_func([c.copy() for c in candidates])
        scored.sort(key=lambda x: x['score'], reverse=True)
        best = scored[0]
        worst = scored[-1]

        # 高分組交易
        df = best['df']
        entry_idx = best['entry_idx']
        exit_price = None
        exit_date = None
        for j in range(entry_idx + 1, len(df)):
            if int(df['Signal'].iloc[j]) == -1:
                exit_date = df.index[j].date()
                exit_price = df['Close'].iloc[j]
                break
        if exit_date:
            ret = (exit_price - best['entry_price']) / best['entry_price'] * 100
            high_trades.append({'stock': best['stock'], 'return': ret, 'regime': best['regime'], 'score': best['score'], 'date': date})

        # 低分組交易
        df = worst['df']
        entry_idx = worst['entry_idx']
        exit_price = None
        exit_date = None
        for j in range(entry_idx + 1, len(df)):
            if int(df['Signal'].iloc[j]) == -1:
                exit_date = df.index[j].date()
                exit_price = df['Close'].iloc[j]
                break
        if exit_date:
            ret = (exit_price - worst['entry_price']) / worst['entry_price'] * 100
            low_trades.append({'stock': worst['stock'], 'return': ret, 'regime': worst['regime'], 'score': worst['score'], 'date': date})

    if high_trades and low_trades:
        high_returns = [t['return'] for t in high_trades]
        low_returns = [t['return'] for t in low_trades]
        high_wr = len([r for r in high_returns if r > 0]) / len(high_returns) * 100
        low_wr = len([r for r in low_returns if r > 0]) / len(low_returns) * 100
        diff = np.mean(high_returns) - np.mean(low_returns)
        results[name] = {
            'high_avg': np.mean(high_returns),
            'high_wr': high_wr,
            'high_n': len(high_returns),
            'low_avg': np.mean(low_returns),
            'low_wr': low_wr,
            'low_n': len(low_returns),
            'diff': diff,
            'high_trades': high_trades,
            'low_trades': low_trades
        }

# 輸出排名
print("\n" + "=" * 80)
print("🏆 評分策略回測結果排名（按 高分-低分 差異排序）")
print("=" * 80)
print(f"{'策略':<25} {'高分組均酬':>10} {'高分勝率':>8} {'低分組均酬':>10} {'低分勝率':>8} {'差異':>8} {'有用':>5}")
print("-" * 80)

sorted_results = sorted(results.items(), key=lambda x: x[1]['diff'], reverse=True)
for i, (name, r) in enumerate(sorted_results):
    verdict = "✅" if r['diff'] > 0 else "❌"
    print(f"{name:<25} {r['high_avg']:>+10.2f}% {r['high_wr']:>7.1f}% {r['low_avg']:>+10.2f}% {r['low_wr']:>7.1f}% {r['diff']:>+8.2f}% {verdict:>5}")

best_name, best_r = sorted_results[0]
print(f"\n💡 最佳策略：{best_name}")
print(f"   高分組平均報酬：{best_r['high_avg']:+.2f}%  勝率：{best_r['high_wr']:.1f}%")
print(f"   低分組平均報酬：{best_r['low_avg']:+.2f}%  勝率：{best_r['low_wr']:.1f}%")
print(f"   差異：{best_r['diff']:+.2f}%（每筆交易）")
