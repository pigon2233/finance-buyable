#!/usr/bin/env python3
"""
綜合共振策略參數優化 v2 (高效版)
- 基於150支台股近1年數據
- 預先計算指標，大量減少重複計算
- 網格搜索最優參數
- 避免過擬合：只保留正報酬組合，按夏普比率排序
"""

import pandas as pd
import numpy as np
import itertools
import json
import time
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, '/home/pigon/.openclaw/workspace/skills/finance_buyable')

# ============ STOCK LIST (150 stocks) ============
STOCKS = [
    "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW", "2412.TW",
    "2881.TW", "2882.TW", "2303.TW", "3711.TW", "2886.TW", "2891.TW",
    "1301.TW", "1303.TW", "1216.TW", "2884.TW", "2002.TW", "2885.TW",
    "2357.TW", "2892.TW", "2880.TW", "3008.TW", "2603.TW", "5880.TW",
    "2327.TW", "2890.TW", "2883.TW", "2887.TW", "2207.TW", "3034.TW",
    "2379.TW", "2912.TW", "1326.TW", "2409.TW", "1101.TW", "3231.TW",
    "4938.TW", "5871.TW", "2615.TW", "2609.TW", "3045.TW", "2845.TW",
    "6669.TW", "2395.TW", "3037.TW", "2345.TW", "1605.TW", "9904.TW",
    "2812.TW", "2105.TW", "3661.TW", "3443.TW", "3035.TW", "1513.TW",
    "1519.TW", "1503.TW", "2376.TW", "2368.TW", "6239.TW", "6176.TW",
    "3189.TW", "8046.TW", "2360.TW", "3406.TW", "6213.TW", "2449.TW",
    "6415.TW", "2313.TW", "2408.TW", "2329.TW", "3017.TW", "3324.TWO",
    "3583.TW", "6278.TW", "3533.TW", "6443.TW", "2383.TW", "2385.TW",
    "2421.TW", "3013.TW", "3044.TW", "6235.TW", "2458.TW", "3010.TW",
    "3592.TW", "4919.TW", "4958.TW", "4961.TW", "4967.TW", "4968.TW",
    "5269.TW", "6120.TW", "6153.TW", "6177.TW", "6206.TW", "6271.TW",
    "6282.TW", "6285.TW", "8016.TW", "8081.TW", "8150.TW", "8210.TW",
    "2618.TW", "2610.TW", "2633.TW", "2723.TW", "2722.TW", "2204.TW",
    "2206.TW", "2211.TW", "2542.TW", "2501.TW", "2548.TW", "1402.TW",
    "1455.TW", "1717.TW", "1708.TW", "1718.TW", "1722.TW", "1723.TW",
    "1727.TW", "4763.TW", "1802.TW", "1904.TW", "1909.TW", "2049.TW",
    "2101.TW", "2103.TW", "2106.TW", "9910.TW", "9921.TW", "9945.TW",
    "2534.TW", "2520.TW", "3005.TW", "3532.TW", "3545.TW", "3576.TW",
    "3605.TW", "3617.TW", "3686.TW", "3701.TW", "3702.TW", "3703.TW",
    "3706.TW", "4912.TW", "4943.TW", "4960.TW", "4976.TW", "5284.TW"
]

# Reduced parameter grid for faster optimization
PARAM_GRID = {
    'large_lower': [-10, -20],         # 2 values (多頭通道下軌)
    'large_upper': [30, 40],            # 2 values (多頭通道上軌)
    'small_lower': [-35, -45],          # 2 values (空頭通道下軌)
    'small_upper': [5, 10],             # 2 values (空頭通道上軌)
    'rsi_oversold': [30, 40],           # 2 values (RSI 超賣)
    'rsi_overbought': [70, 80],         # 2 values (RSI 超買)
    'small_behavior': ['short', 'flat'], # 2 values
}
# Total: 2^6 * 2 = 128 combinations

# ============ INDICATOR CALCULATIONS ============

def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """一次性計算所有指標"""
    df = df.copy()
    epsilon = 1e-8
    
    # DMPI
    high_low_range = df['High'] - df['Low'] + epsilon
    buy_pressure = (df['Close'] - df['Low']) / high_low_range
    sell_pressure = (df['High'] - df['Close']) / high_low_range
    df['Net_Pressure'] = buy_pressure - sell_pressure
    
    avg_volume = df['Volume'].rolling(window=20).mean()
    df['Volume_Factor'] = df['Volume'] / (avg_volume + epsilon)
    
    df['Prev_Close'] = df['Close'].shift(1)
    df['TR'] = df[['High', 'Prev_Close']].max(axis=1) - df[['Low', 'Prev_Close']].min(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()
    
    df['VP'] = df['ATR'] / (df['Close'] + epsilon)
    df['VP'] = df['VP'].clip(lower=0.01)
    
    df['Raw_DMPI'] = (df['Net_Pressure'] * df['Volume_Factor']) / df['VP']
    df['DMPI'] = df['Raw_DMPI'].rolling(window=2).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-8)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    df['EMA_Fast'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_Slow'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA_Fast'] - df['EMA_Slow']
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    return df

def run_backtest_simple(df: pd.DataFrame, initial_capital=100000.0) -> dict:
    """簡單但正確的回測"""
    signals = df['Signal'].values
    closes = df['Close'].values
    n = len(signals)
    
    capital = initial_capital
    shares = 0
    buy_price = 0
    trade_returns = []
    values = []
    peak = initial_capital
    
    for i in range(n):
        sig = signals[i]
        close = closes[i]
        
        if sig == 1 and shares == 0:
            shares = capital / close
            buy_price = close
            capital = 0
        elif sig == -1 and shares > 0:
            capital = shares * close
            ret = (close - buy_price) / buy_price * 100
            trade_returns.append(ret)
            shares = 0
        
        current_value = capital + shares * close
        values.append(current_value)
        if current_value > peak:
            peak = current_value
    
    # Force close at end
    if shares > 0:
        capital = shares * closes[-1]
        trade_returns.append((closes[-1] - buy_price) / buy_price * 100)
        shares = 0
    
    final_capital = capital
    total_return = (final_capital - initial_capital) / initial_capital * 100
    
    values = np.array(values)
    peaks = np.maximum.accumulate(values)
    drawdowns = (values - peaks) / peaks
    max_drawdown = abs(np.min(drawdowns)) * 100 if len(drawdowns) > 0 else 0
    
    winning_trades = [r for r in trade_returns if r > 0]
    win_rate = len(winning_trades) / len(trade_returns) * 100 if trade_returns else 0
    sharpe_proxy = abs(total_return / max_drawdown) if max_drawdown > 0.1 else 0
    
    return {
        'total_return_pct': total_return,
        'max_drawdown_pct': max_drawdown,
        'win_rate_pct': win_rate,
        'total_trades': len(trade_returns),
        'sharpe_proxy': sharpe_proxy,
    }

def generate_signals_fast(df: pd.DataFrame, params: dict) -> pd.Series:
    """快速向量化信號生成"""
    dmpi = df['DMPI'].values
    rsi = df['RSI'].values
    macd = df['MACD'].values
    macd_hist = df['MACD_Hist'].values
    n = len(dmpi)
    
    # Regime
    large_mask = (macd > 0) & (macd_hist >= 0)
    small_mask = (macd < 0) & (macd_hist <= 0)
    flat_mask = ~(large_mask | small_mask)
    
    # Initialize
    signals = np.zeros(n)
    positions = np.zeros(n)
    current_pos = 0
    
    large_lower = params['large_lower']
    large_upper = params['large_upper']
    small_lower = params['small_lower']
    small_upper = params['small_upper']
    rsi_oversold = params['rsi_oversold']
    rsi_overbought = params['rsi_overbought']
    small_behavior = params['small_behavior']
    
    for i in range(1, n):
        if large_mask[i]:
            if dmpi[i] >= large_upper:
                next_pos = 0
            elif dmpi[i] <= large_lower:
                next_pos = 0
            else:
                next_pos = 1
        elif small_mask[i]:
            if small_behavior == 'flat':
                next_pos = 0
            else:
                if dmpi[i] >= small_upper:
                    next_pos = 0
                elif dmpi[i] <= small_lower:
                    next_pos = 0
                else:
                    next_pos = 1
        else:  # FLAT
            if rsi[i] < rsi_oversold:
                next_pos = 1
            elif rsi[i] > rsi_overbought:
                next_pos = 0
            else:
                next_pos = current_pos
        
        # Signal
        if next_pos == 1 and current_pos == 0:
            signals[i] = 1
        elif next_pos == 0 and current_pos == 1:
            signals[i] = -1
        
        positions[i] = next_pos
        current_pos = next_pos
    
    df_out = df.copy()
    df_out['Signal'] = signals
    df_out['Position'] = positions
    return df_out

# ============ DATA DOWNLOAD ============

def download_stock_data(stock_id: str, days=365) -> pd.DataFrame:
    """下載股票數據"""
    try:
        import yfinance as yf
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        ticker = yf.Ticker(stock_id)
        df = ticker.history(start=start_date, end=end_date)
        
        if df is None or df.empty or len(df) < 60:
            return None
        
        # Ensure columns are named correctly
        df.columns = [c.capitalize() for c in df.columns]
        
        return df
    except Exception as e:
        return None

# ============ OPTIMIZATION ============

def score_combination(result: dict) -> float:
    """計算參數組合的綜合得分"""
    if result is None or result['avg_return'] <= 0:
        return -9999
    
    sharpe_norm = result['avg_sharpe'] / 10
    drawdown_norm = 1 - (result['avg_drawdown'] / 50)
    win_rate_norm = result['avg_win_rate'] / 100
    rtdd = abs(result['avg_return'] / result['avg_drawdown']) if result['avg_drawdown'] > 0.1 else 0
    rtdd_norm = rtdd / 10
    
    score = (
        0.40 * sharpe_norm +
        0.30 * drawdown_norm +
        0.15 * win_rate_norm +
        0.15 * rtdd_norm
    )
    return score

def main():
    print("=" * 60, flush=True)
    print("綜合共振策略參數優化 v2 (高效版)", flush=True)
    print("=" * 60, flush=True)
    print(f"開始時間: {datetime.now()}", flush=True)
    
    # Step 1: 下載數據
    print("\n📥 步驟1: 下載150支股票數據...", flush=True)
    stocks_data = {}
    
    for i, stock in enumerate(STOCKS):
        if (i + 1) % 20 == 0:
            print(f"  已下載 {i+1}/{len(STOCKS)}...", flush=True)
        df = download_stock_data(stock, days=365)
        if df is not None:
            df_ind = calculate_all_indicators(df)
            stocks_data[stock] = df_ind
    
    print(f"  ✅ 成功處理 {len(stocks_data)}/{len(STOCKS)} 支股票", flush=True)
    
    if len(stocks_data) < 50:
        print("  ❌ 數據不足，放棄優化", flush=True)
        return
    
    # Step 2: 生成參數組合
    print("\n⚙️ 步驟2: 生成參數組合...", flush=True)
    param_names = list(PARAM_GRID.keys())
    param_values = list(PARAM_GRID.values())
    all_combinations = list(itertools.product(*param_values))
    
    print(f"  總共 {len(all_combinations)} 組參數組合", flush=True)
    
    # Step 3: 網格搜索
    print("\n🔍 步驟3: 網格搜索...", flush=True)
    
    all_results = []
    positive_return_count = 0
    start_time = time.time()
    
    for combo_idx, combo in enumerate(all_combinations):
        params = dict(zip(param_names, combo))
        
        stock_results = []
        for stock_id, df_ind in stocks_data.items():
            try:
                df_sig = generate_signals_fast(df_ind.copy(), params)
                bt = run_backtest_simple(df_sig)
                stock_results.append(bt)
            except Exception as e:
                continue
        
        if not stock_results:
            continue
        
        avg_return = np.mean([r['total_return_pct'] for r in stock_results])
        avg_sharpe = np.mean([r['sharpe_proxy'] for r in stock_results])
        avg_drawdown = np.mean([r['max_drawdown_pct'] for r in stock_results])
        avg_win_rate = np.mean([r['win_rate_pct'] for r in stock_results])
        
        result = {
            'params': params,
            'avg_return': avg_return,
            'avg_sharpe': avg_sharpe,
            'avg_drawdown': avg_drawdown,
            'avg_win_rate': avg_win_rate,
            'num_stocks': len(stock_results),
        }
        
        if avg_return > 0:
            positive_return_count += 1
            result['score'] = score_combination(result)
            all_results.append(result)
        
        if (combo_idx + 1) % 20 == 0:
            elapsed = time.time() - start_time
            eta = elapsed / (combo_idx + 1) * len(all_combinations)
            print(f"  進度: {combo_idx+1}/{len(all_combinations)} | 正報酬: {positive_return_count} | "
                  f"已耗時: {elapsed:.1f}s | 預估剩餘: {eta-elapsed:.1f}s", flush=True)
    
    # Step 4: 分析結果
    print("\n📊 步驟4: 分析結果...", flush=True)
    
    if not all_results:
        print("  ❌ 沒有找到正報酬的參數組合", flush=True)
        return
    
    all_results.sort(key=lambda x: x['score'], reverse=True)
    
    # Top 10
    print("\n" + "=" * 60, flush=True)
    print("🏆 TOP 10 最佳參數組合", flush=True)
    print("=" * 60, flush=True)
    
    for i, result in enumerate(all_results[:10]):
        p = result['params']
        print(f"\n#{i+1} (分數: {result['score']:.3f})", flush=True)
        print(f"  多頭通道: [{p['large_lower']}, {p['large_upper']}]", flush=True)
        print(f"  空頭通道: [{p['small_lower']}, {p['small_upper']}]", flush=True)
        print(f"  RSI: [{p['rsi_oversold']}, {p['rsi_overbought']}]", flush=True)
        print(f"  空頭行為: {p['small_behavior']}", flush=True)
        print(f"  平均報酬: {result['avg_return']:.2f}%", flush=True)
        print(f"  平均夏普: {result['avg_sharpe']:.3f}", flush=True)
        print(f"  平均回撤: {result['avg_drawdown']:.2f}%", flush=True)
        print(f"  平均勝率: {result['avg_win_rate']:.1f}%", flush=True)
    
    best = all_results[0]
    best_params = best['params']
    
    # 空頭行為對比
    print("\n" + "=" * 60, flush=True)
    print("📈 空頭行為對比 (short vs flat)", flush=True)
    print("=" * 60, flush=True)
    
    short_results = [r for r in all_results if r['params']['small_behavior'] == 'short']
    flat_results = [r for r in all_results if r['params']['small_behavior'] == 'flat']
    
    if short_results:
        print(f"\n【空頭搶短 (short)】({len(short_results)} 組合)", flush=True)
        print(f"  平均報酬: {np.mean([r['avg_return'] for r in short_results]):.2f}%", flush=True)
        print(f"  平均夏普: {np.mean([r['avg_sharpe'] for r in short_results]):.3f}", flush=True)
        print(f"  平均回撤: {np.mean([r['avg_drawdown'] for r in short_results]):.2f}%", flush=True)
    
    if flat_results:
        print(f"\n【空頭空手 (flat)】({len(flat_results)} 組合)", flush=True)
        print(f"  平均報酬: {np.mean([r['avg_return'] for r in flat_results]):.2f}%", flush=True)
        print(f"  平均夏普: {np.mean([r['avg_sharpe'] for r in flat_results]):.3f}", flush=True)
        print(f"  平均回撤: {np.mean([r['avg_drawdown'] for r in flat_results]):.2f}%", flush=True)
    
    # 敏感度分析
    print("\n" + "=" * 60, flush=True)
    print("📉 參數敏感度分析", flush=True)
    print("=" * 60, flush=True)
    
    for param in param_names:
        param_values_dict = {}
        for r in all_results:
            val = r['params'][param]
            if val not in param_values_dict:
                param_values_dict[val] = {'returns': [], 'sharpes': []}
            param_values_dict[val]['returns'].append(r['avg_return'])
            param_values_dict[val]['sharpes'].append(r['avg_sharpe'])
        
        print(f"\n{param}:", flush=True)
        for val, data in sorted(param_values_dict.items()):
            avg_ret = np.mean(data['returns'])
            avg_sha = np.mean(data['sharpes'])
            print(f"  = {val}: 平均報酬={avg_ret:.2f}%, 平均夏普={avg_sha:.3f}", flush=True)
    
    # 儲存結果
    elapsed_total = time.time() - start_time
    
    output_data = {
        'best_params': best_params,
        'best_score': best['score'],
        'best_metrics': {
            'avg_return': float(best['avg_return']),
            'avg_sharpe': float(best['avg_sharpe']),
            'avg_drawdown': float(best['avg_drawdown']),
            'avg_win_rate': float(best['avg_win_rate']),
        },
        'top_10': [
            {
                'params': r['params'],
                'score': float(r['score']),
                'metrics': {
                    'avg_return': float(r['avg_return']),
                    'avg_sharpe': float(r['avg_sharpe']),
                    'avg_drawdown': float(r['avg_drawdown']),
                    'avg_win_rate': float(r['avg_win_rate']),
                }
            }
            for r in all_results[:10]
        ],
        'small_behavior_comparison': {
            'short': {
                'count': len(short_results),
                'avg_return': float(np.mean([r['avg_return'] for r in short_results])) if short_results else 0,
                'avg_sharpe': float(np.mean([r['avg_sharpe'] for r in short_results])) if short_results else 0,
                'avg_drawdown': float(np.mean([r['avg_drawdown'] for r in short_results])) if short_results else 0,
            },
            'flat': {
                'count': len(flat_results),
                'avg_return': float(np.mean([r['avg_return'] for r in flat_results])) if flat_results else 0,
                'avg_sharpe': float(np.mean([r['avg_sharpe'] for r in flat_results])) if flat_results else 0,
                'avg_drawdown': float(np.mean([r['avg_drawdown'] for r in flat_results])) if flat_results else 0,
            }
        },
        'total_combinations': len(all_combinations),
        'positive_return_combinations': positive_return_count,
        'stocks_analyzed': len(stocks_data),
        'elapsed_time_seconds': elapsed_total,
    }
    
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"optimization_results_v2_{ts}.json"
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2, default=str)
    
    print(f"\n✅ 結果已儲存至: {output_file}", flush=True)
    print(f"總耗時: {elapsed_total:.1f} 秒 ({elapsed_total/60:.1f} 分鐘)", flush=True)
    
    return output_data

if __name__ == "__main__":
    main()
