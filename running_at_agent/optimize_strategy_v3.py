#!/usr/bin/env python3
"""
綜合共振策略參數優化 v3 - 最大化正報酬股票比例 (高效並行程式)
- 基於150支台股近1年數據
- 使用 multiprocessing 並行計算
- 評分標準：
  1. 正報酬股票比例 (權重50%) - 核心目標
  2. 平均年化報酬 (權重30%) - 需 > 8%
  3. 平均勝率 (權重20%)
"""

import pandas as pd
import numpy as np
import itertools
import json
import time
import sys
import os
from datetime import datetime, timedelta
from multiprocessing import Pool, cpu_count, Manager

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

# ============ PARAMETER GRID ============
PARAM_GRID = {
    'large_lower': [-10, -15, -20, -25, -30],   # 多頭通道下軌
    'large_upper': [25, 30, 35, 40, 45],          # 多頭通道上軌
    'small_lower': [-30, -35, -40, -45, -50],     # 空頭通道下軌
    'small_upper': [3, 5, 7, 10, 15],             # 空頭通道上軌
    'rsi_oversold': [30, 35, 40, 45, 50],         # RSI 超賣
    'rsi_overbought': [60, 65, 70, 75, 80],      # RSI 超買
    'small_behavior': ['short', 'flat'],          # 空頭市場行為
}

ALL_KEYS = list(PARAM_GRID.keys())
ALL_VALUES = list(PARAM_GRID.values())


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """一次性計算所有指標"""
    df = df.copy()
    epsilon = 1e-8
    
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
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + epsilon)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['EMA_Fast'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_Slow'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA_Fast'] - df['EMA_Slow']
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    return df


def evaluate_params_for_worker(args):
    """Worker function for multiprocessing - evaluates one param set"""
    params, stock_data = args
    
    results = []
    
    for stock_code, df in stock_data.items():
        if df is None or len(df) < 60:
            continue
        
        # Generate signals
        n = len(df)
        signals = np.zeros(n)
        
        large_lower = params['large_lower']
        large_upper = params['large_upper']
        small_lower = params['small_lower']
        small_upper = params['small_upper']
        rsi_oversold = params['rsi_oversold']
        rsi_overbought = params['rsi_overbought']
        small_behavior = params['small_behavior']
        
        dmpi = df['DMPI'].values
        rsi = df['RSI'].values
        macd = df['MACD'].values
        hist = df['MACD_Hist'].values
        
        current_pos = 0
        
        for i in range(1, n):
            macd_val = macd[i]
            hist_val = hist[i]
            
            if macd_val > 0 and hist_val >= 0:
                regime = 'LARGE'
            elif macd_val < 0 and hist_val <= 0:
                regime = 'SMALL'
            else:
                regime = 'FLAT'
                
            next_pos = current_pos
            
            if regime == 'LARGE':
                dmpi_val = dmpi[i]
                if dmpi_val >= large_upper:
                    next_pos = 0
                elif dmpi_val <= large_lower:
                    next_pos = 0
                else:
                    next_pos = 1
            elif regime == 'SMALL':
                dmpi_val = dmpi[i]
                if small_behavior == 'short':
                    if dmpi_val >= small_upper:
                        next_pos = 0
                    elif dmpi_val <= small_lower:
                        next_pos = 0
                    else:
                        next_pos = 1
                else:
                    next_pos = 0
            else:
                rsi_val = rsi[i]
                if rsi_val < rsi_oversold:
                    next_pos = 1
                elif rsi_val > rsi_overbought:
                    next_pos = 0
            
            if next_pos == 1 and current_pos == 0:
                signals[i] = 1
            elif next_pos == 0 and current_pos == 1:
                signals[i] = -1
                
            current_pos = next_pos
        
        # Backtest
        capital = 100000.0
        shares = 0
        buy_price = 0
        trades = []
        close_prices = df['Close'].values
        
        for i in range(len(df)):
            signal = signals[i]
            close_price = close_prices[i]
            
            if signal == 1 and shares == 0:
                shares = capital / close_price
                capital = 0
                buy_price = close_price
            elif signal == -1 and shares > 0:
                capital = shares * close_price
                shares = 0
                profit_pct = (close_price - buy_price) / buy_price * 100
                trades.append(profit_pct)
        
        final_value = capital + (shares * close_prices[-1])
        
        if shares > 0:
            profit_pct = (close_prices[-1] - buy_price) / buy_price * 100
            trades.append(profit_pct)
        
        days = (df.index[-1] - df.index[0]).days
        years = days / 365.0
        annualized_return = ((final_value / 100000.0) ** (1 / years) - 1) * 100 if years > 0 else 0
        
        winning_trades = sum(1 for t in trades if t > 0)
        win_rate = winning_trades / len(trades) * 100 if trades else 0
        
        results.append({
            'annualized_return': annualized_return,
            'win_rate': win_rate,
        })
    
    if not results:
        return None
    
    total_stocks = len(results)
    positive_return_stocks = sum(1 for r in results if r['annualized_return'] > 0)
    positive_ratio = positive_return_stocks / total_stocks * 100
    
    avg_annualized = np.mean([r['annualized_return'] for r in results])
    avg_win_rate = np.mean([r['win_rate'] for r in results])
    
    return {
        'positive_ratio': positive_ratio,
        'positive_count': positive_return_stocks,
        'total_stocks': total_stocks,
        'avg_annualized_return': avg_annualized,
        'avg_win_rate': avg_win_rate,
        'params': params
    }


def score_params(eval_result):
    """根據評分標準計算綜合分數"""
    if eval_result is None:
        return -999
    
    positive_ratio = eval_result['positive_ratio']
    if positive_ratio < 60:
        return -999
    
    avg_annualized = eval_result['avg_annualized_return']
    avg_win_rate = eval_result['avg_win_rate']
    
    score_ratio = positive_ratio
    score_annualized = min(100, max(0, (avg_annualized / 20) * 100))
    score_win_rate = avg_win_rate
    
    total_score = (score_ratio * 0.5) + (score_annualized * 0.3) + (score_win_rate * 0.2)
    
    return total_score


def main():
    print("=" * 70)
    print("📊 綜合共振策略參數優化 v3 - 最大化正報酬股票比例")
    print("=" * 70)
    print(f"股票數量: {len(STOCKS)}")
    
    total_combinations = 1
    for v in PARAM_GRID.values():
        total_combinations *= len(v)
    print(f"參數組合數: {total_combinations}")
    print(f"CPU 核心數: {cpu_count()}")
    print()
    
    # Step 1: 下載股票數據
    print("📥 Step 1: 下載股票數據...")
    import yfinance as yf
    
    stock_data = {}
    failed_stocks = []
    
    for i, stock in enumerate(STOCKS):
        if (i + 1) % 20 == 0:
            print(f"  進度: {i + 1}/{len(STOCKS)}")
        try:
            ticker = yf.Ticker(stock)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=400)
            df = ticker.history(start=start_date, end=end_date)
            if len(df) > 60:
                df = calculate_all_indicators(df)
                stock_data[stock] = df
            else:
                failed_stocks.append(stock)
        except Exception as e:
            failed_stocks.append(stock)
    
    print(f"✅ 成功下載: {len(stock_data)} 支股票")
    if failed_stocks:
        print(f"⚠️ 失敗: {len(failed_stocks)} 支")
    
    # Step 2: 準備參數組合
    print()
    print("🔍 Step 2: 網格搜索參數組合...")
    
    all_param_combos = list(itertools.product(*ALL_VALUES))
    all_param_combos = [dict(zip(ALL_KEYS, combo)) for combo in all_param_combos]
    
    # 準備 worker 任務
    worker_args = [(params, stock_data) for params in all_param_combos]
    
    print(f"共 {len(worker_args)} 組參數待測試")
    start_time = time.time()
    
    # 使用 Pool 進行並行計算
    num_workers = min(cpu_count(), 8)
    
    results = []
    with Pool(num_workers) as pool:
        for i, result in enumerate(pool.imap(evaluate_params_for_worker, worker_args, chunksize=50)):
            results.append(result)
            
            if (i + 1) % 2000 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                remaining = (len(worker_args) - i - 1) / rate if rate > 0 else 0
                print(f"  進度: {i+1}/{len(worker_args)} ({rate:.1f} 組/秒, 預估剩餘: {remaining/60:.1f} 分)")
    
    elapsed_total = time.time() - start_time
    print(f"✅ 所有計算完成！耗時 {elapsed_total:.1f} 秒")
    
    # 評分並排序
    scored_results = []
    for eval_result in results:
        if eval_result is not None:
            score = score_params(eval_result)
            if score > -999:
                scored_results.append({
                    'params': eval_result['params'],
                    'score': score,
                    'eval': eval_result
                })
    
    scored_results.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"   符合條件（正報酬比例 > 60%）: {len(scored_results)} 組")
    
    # Step 3: 輸出結果
    print()
    print("=" * 70)
    print("🏆 Top 10 最佳參數組合")
    print("=" * 70)
    
    for i, result in enumerate(scored_results[:10]):
        p = result['params']
        e = result['eval']
        print()
        print(f"#{i+1} (分數: {result['score']:.2f})")
        print(f"  多頭通道: [{p['large_lower']}, {p['large_upper']}]")
        print(f"  空頭通道: [{p['small_lower']}, {p['small_upper']}]")
        print(f"  RSI: 超賣 < {p['rsi_oversold']}, 超買 > {p['rsi_overbought']}")
        print(f"  空頭行為: {p['small_behavior']}")
        print(f"  正報酬股票比例: {e['positive_ratio']:.1f}% ({e['positive_count']}/{e['total_stocks']})")
        print(f"  平均年化報酬: {e['avg_annualized_return']:.2f}%")
        print(f"  平均勝率: {e['avg_win_rate']:.1f}%")
    
    best_result = scored_results[0] if scored_results else None
    
    if best_result:
        p = best_result['params']
        e = best_result['eval']
        
        print()
        print("=" * 70)
        print("🥇 最佳參數組合")
        print("=" * 70)
        print(f"""
🎯 最佳參數:
  - 多頭通道下軌: {p['large_lower']}
  - 多頭通道上軌: {p['large_upper']}
  - 空頭通道下軌: {p['small_lower']}
  - 空頭通道上軌: {p['small_upper']}
  - RSI 超賣: {p['rsi_oversold']}
  - RSI 超買: {p['rsi_overbought']}
  - 空頭市場行為: {p['small_behavior']}

📊 績效指標:
  - 正報酬股票比例: {e['positive_ratio']:.1f}% ({e['positive_count']}/{e['total_stocks']})
  - 平均年化報酬: {e['avg_annualized_return']:.2f}%
  - 平均勝率: {e['avg_win_rate']:.1f}%
  - 評分: {best_result['score']:.2f}
""")
        
        # 空頭行為對比
        short_results = [r for r in scored_results if r['params']['small_behavior'] == 'short']
        flat_results = [r for r in scored_results if r['params']['small_behavior'] == 'flat']
        
        print()
        print("=" * 70)
        print("📊 空頭行為對比")
        print("=" * 70)
        
        if short_results:
            best_short = max(short_results, key=lambda x: x['score'])
            print(f"\n🔴 short (搶短) 最佳:")
            print(f"   正報酬比例: {best_short['eval']['positive_ratio']:.1f}%")
            print(f"   平均年化: {best_short['eval']['avg_annualized_return']:.2f}%")
            print(f"   平均勝率: {best_short['eval']['avg_win_rate']:.1f}%")
        
        if flat_results:
            best_flat = max(flat_results, key=lambda x: x['score'])
            print(f"\n⚪ flat (空手) 最佳:")
            print(f"   正報酬比例: {best_flat['eval']['positive_ratio']:.1f}%")
            print(f"   平均年化: {best_flat['eval']['avg_annualized_return']:.2f}%")
            print(f"   平均勝率: {best_flat['eval']['avg_win_rate']:.1f}%")
    
    # 保存結果
    output_file = f"optimization_results_v3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_data = {
        'best_params': best_result['params'] if best_result else None,
        'best_score': best_result['score'] if best_result else None,
        'best_eval': {k: v for k, v in best_result['eval'].items()} if best_result else None,
        'top_10': [
            {
                'rank': i+1,
                'params': r['params'],
                'score': r['score'],
                'positive_ratio': r['eval']['positive_ratio'],
                'avg_annualized_return': r['eval']['avg_annualized_return'],
                'avg_win_rate': r['eval']['avg_win_rate']
            }
            for i, r in enumerate(scored_results[:10])
        ],
        'total_combinations': total_combinations,
        'qualifying_combinations': len(scored_results),
        'stocks_tested': len(stock_data),
        'elapsed_seconds': elapsed_total
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)
    
    print()
    print(f"💾 結果已保存至: {output_file}")
    
    # Discord 訊息
    if best_result:
        p = best_result['params']
        e = best_result['eval']
        
        discord_msg = f"""🏆 **綜合共振策略參數優化 v3 結果**

🎯 **最佳參數組合:**
- 多頭通道: [{p['large_lower']}, {p['large_upper']}]
- 空頭通道: [{p['small_lower']}, {p['small_upper']}]
- RSI: 超賣 < {p['rsi_oversold']}, 超買 > {p['rsi_overbought']}
- 空頭行為: {p['small_behavior']}

📊 **績效指標:**
- ✅ 正報酬股票比例: {e['positive_ratio']:.1f}% ({e['positive_count']}/{e['total_stocks']})
- 📈 平均年化報酬: {e['avg_annualized_return']:.2f}%
- 🎯 平均勝率: {e['avg_win_rate']:.1f}%
- ⭐ 評分: {best_result['score']:.2f}

📋 **Top 3:**
"""
        
        for i, r in enumerate(scored_results[:3]):
            pp = r['params']
            discord_msg += f"\n#{i+1} [{pp['large_lower']},{pp['large_upper']}]/[{pp['small_lower']},{pp['small_upper']}] RSI({pp['rsi_oversold']},{pp['rsi_overbought']}) {pp['small_behavior']} → 正報酬{r['eval']['positive_ratio']:.1f}% 年化{r['eval']['avg_annualized_return']:.1f}%"

        discord_msg += f"\n\n__{len(scored_results)} 組合格過篩選（正報酬>60%）共 {total_combinations} 組__"
        
        with open("discord_msg_v3.txt", 'w', encoding='utf-8') as f:
            f.write(discord_msg)
        
        print()
        print("📨 Discord 訊息已保存至 discord_msg_v3.txt")
        print()
        print("-" * 50)
        print(discord_msg)
    
    print("=" * 70)
    
    return output_data


if __name__ == "__main__":
    main()
