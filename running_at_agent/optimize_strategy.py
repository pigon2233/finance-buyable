#!/usr/bin/env python3
"""
綜合共振策略參數優化腳本
Grid search across parameter combinations for Taiwan Top 10 weighted stocks
"""

import pandas as pd
import numpy as np
import yfinance as yf
from itertools import product
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ---- Constants ----
STOCKS = [
    "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2412.TW",
    "2881.TW", "2886.TW", "2891.TW", "2882.TW", "1301.TW"
]
STOCK_NAMES = {
    "2330.TW": "台積電", "2317.TW": "鴻海", "2454.TW": "聯發科",
    "2308.TW": "台達電", "2412.TW": "中華電", "2881.TW": "國泰金",
    "2886.TW": "兆豐金", "2891.TW": "中信金", "2882.TW": "富邦金",
    "1301.TW": "台塑"
}

# Parameter grid
PARAM_GRID = {
    'large_lower':   [-10, -15, -20],    # 多頭通道下軌
    'large_upper':   [20, 25, 27, 30],   # 多頭通道上軌
    'small_lower':   [-30, -35, -40],    # 空頭通道下軌
    'small_upper':   [3, 5, 7],          # 空頭通道上軌
    'rsi_oversold':  [25, 30, 35],        # RSI 超賣
    'rsi_overbought':[65, 70, 75],        # RSI 超買
    'rsi_period':    [10, 14, 20],        # RSI 期間
}

INITIAL_CAPITAL = 100000.0

# ---- Indicator Calculations ----

def calculate_dmpi(df: pd.DataFrame, window=5, vol_window=20, atr_window=14) -> pd.DataFrame:
    df = df.copy()
    epsilon = 1e-8
    high_low_range = df['High'] - df['Low'] + epsilon
    buy_pressure = (df['Close'] - df['Low']) / high_low_range
    sell_pressure = (df['High'] - df['Close']) / high_low_range
    df['Net_Pressure'] = buy_pressure - sell_pressure
    avg_volume = df['Volume'].rolling(window=vol_window).mean()
    df['Volume_Factor'] = df['Volume'] / (avg_volume + epsilon)
    df['Prev_Close'] = df['Close'].shift(1)
    df['TR'] = df[['High', 'Prev_Close']].max(axis=1) - df[['Low', 'Prev_Close']].min(axis=1)
    df['ATR'] = df['TR'].rolling(window=atr_window).mean()
    df['VP'] = df['ATR'] / (df['Close'] + epsilon)
    df['VP'] = df['VP'].clip(lower=0.01)
    df['Raw_DMPI'] = (df['Net_Pressure'] * df['Volume_Factor']) / df['VP']
    df['DMPI'] = df['Raw_DMPI'].rolling(window=2).mean()
    return df

def calculate_rsi(df: pd.DataFrame, window=14) -> pd.DataFrame:
    df = df.copy()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / (loss + 1e-8)
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def calculate_macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> pd.DataFrame:
    df = df.copy()
    df['EMA_Fast'] = df['Close'].ewm(span=fast, adjust=False).mean()
    df['EMA_Slow'] = df['Close'].ewm(span=slow, adjust=False).mean()
    df['MACD'] = df['EMA_Fast'] - df['EMA_Slow']
    df['MACD_Signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    return df

def generate_signals_param(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """
    參數化的綜合共振策略信號生成
    """
    df = df.copy()
    df['Signal'] = 0
    df['Position'] = 0
    
    large_lower  = params['large_lower']
    large_upper  = params['large_upper']
    small_lower  = params['small_lower']
    small_upper  = params['small_upper']
    rsi_oversold  = params['rsi_oversold']
    rsi_overbought = params['rsi_overbought']
    rsi_period  = params['rsi_period']
    
    # Recalculate RSI with given period
    df = calculate_rsi(df, window=rsi_period)
    
    buy_sig = pd.Series(False, index=df.index)
    sell_sig = pd.Series(False, index=df.index)
    
    current_pos = 0
    for i in range(1, len(df)):
        dmpi = df['DMPI'].iloc[i]
        rsi = df['RSI'].iloc[i]
        macd = df['MACD'].iloc[i]
        hist = df['MACD_Hist'].iloc[i]
        
        if macd > 0 and hist >= 0:
            regime = 'LARGE'
        elif macd < 0 and hist <= 0:
            regime = 'SMALL'
        else:
            regime = 'FLAT'
            
        next_pos = current_pos
        
        if regime == 'LARGE':
            if dmpi >= large_upper: next_pos = 0
            elif dmpi <= large_lower: next_pos = 0
            else: next_pos = 1
        elif regime == 'SMALL':
            if dmpi >= small_upper: next_pos = 0
            elif dmpi <= small_lower: next_pos = 0
            else: next_pos = 1
        else:
            if rsi < rsi_oversold: next_pos = 1
            elif rsi > rsi_overbought: next_pos = 0
            
        if next_pos == 1 and current_pos == 0:
            buy_sig.iloc[i] = True
        elif next_pos == 0 and current_pos == 1:
            sell_sig.iloc[i] = True
            
        current_pos = next_pos
        
    df.loc[buy_sig, 'Signal'] = 1
    df.loc[sell_sig, 'Signal'] = -1
    
    positions = []
    current_position = 0
    for signal in df['Signal']:
        if signal == 1:
            current_position = 1
        elif signal == -1:
            current_position = 0
        positions.append(current_position)
    df['Position'] = positions
    return df

def run_backtest(df: pd.DataFrame, initial_capital=100000.0) -> dict:
    """Run backtest on a dataframe with Signal and Position columns."""
    capital = initial_capital
    shares = 0
    buy_price = 0
    trades = []
    history = []
    
    for date, row in df.iterrows():
        signal = row.get('Signal', 0)
        close_price = float(row['Close'])
        
        if signal == 1 and shares == 0:
            shares = capital / close_price
            capital = 0
            buy_price = close_price
            trades.append({'Date': date, 'Type': 'Buy', 'Price': close_price})
            
        elif signal == -1 and shares > 0:
            capital = shares * close_price
            shares = 0
            profit_pct = (close_price - buy_price) / buy_price * 100
            trades.append({'Date': date, 'Type': 'Sell', 'Price': close_price, 'Profit_%': profit_pct})
            
        current_value = capital + (shares * close_price)
        history.append({'Date': date, 'Total_Value': current_value})
    
    if shares > 0:
        capital = shares * float(df.iloc[-1]['Close'])
        shares = 0
        profit_pct = (float(df.iloc[-1]['Close']) - buy_price) / buy_price * 100
        trades.append({'Date': df.index[-1], 'Type': 'Sell (Auto Close)', 'Price': float(df.iloc[-1]['Close']), 'Profit_%': profit_pct})
        
    final_capital = capital
    total_return = (final_capital - initial_capital) / initial_capital * 100
    
    # Max drawdown
    history_df = pd.DataFrame(history)
    max_drawdown = 0
    if not history_df.empty and len(history_df) > 1:
        history_df['Peak'] = history_df['Total_Value'].cummax()
        history_df['Drawdown'] = (history_df['Total_Value'] - history_df['Peak']) / history_df['Peak']
        min_dd = history_df['Drawdown'].min()
        if pd.notna(min_dd):
            max_drawdown = min_dd * 100

    # Win rate
    sell_trades = [t for t in trades if 'Sell' in t['Type']]
    winning_trades = [t for t in sell_trades if t.get('Profit_%', 0) > 0]
    win_rate = (len(winning_trades) / len(sell_trades) * 100) if len(sell_trades) > 0 else 0
    
    return {
        'total_return_pct': total_return,
        'max_drawdown_pct': max_drawdown,
        'total_trades': len(sell_trades),
        'win_rate_pct': win_rate,
        'final_capital': final_capital,
        'history': history_df
    }

def score_portfolio(results: list) -> dict:
    """
    根據新評分標準計算投資組合分數
    - 總報酬率: 40%
    - 最大回撤控制: 30%
    - 勝率: 15%
    - 報酬/回撤比: 15%
    """
    total_return = np.mean([r['total_return_pct'] for r in results])
    avg_max_dd = np.mean([r['max_drawdown_pct'] for r in results])  # 負值
    avg_win_rate = np.mean([r['win_rate_pct'] for r in results])
    total_trades = sum([r['total_trades'] for r in results])
    
    # 勝率目標區間: 55-60%，偏離則扣分
    # 勝率 < 55 或 > 60 都會被懲罰（額外扣分，不進入 win_rate_score）
    win_rate_penalty = 0
    if avg_win_rate < 45:
        win_rate_penalty = (45 - avg_win_rate) * 3  # 45%以下重罰
    elif avg_win_rate < 55:
        win_rate_penalty = (55 - avg_win_rate) * 1.5  # 55%以下線性懲罰
    elif avg_win_rate > 65:
        win_rate_penalty = (avg_win_rate - 65) * 1.5  # 65%以上也輕罰（過度擬合風險）
    
    # 標準化各指標 (0-100 分制)
    # 報酬率: 0% = 0分, 100%+ = 100分
    return_score = min(100, max(0, total_return))
    
    # 最大回撤: 0% = 100分, -50% = 0分
    drawdown_score = min(100, max(0, (50 + avg_max_dd) * 2))
    
    # 勝率: 55-60% = 100分，其他區間遞減
    # 45% = ~15分, 50% = ~60分, 55% = 100分, 60% = 100分, 65% = ~75分
    if 55 <= avg_win_rate <= 60:
        win_rate_score = 100
    elif avg_win_rate < 55:
        # 從 45% 的 0 分線性插值到 55% 的 100 分
        win_rate_score = max(0, (avg_win_rate - 45) / 10 * 100)
    else:
        # 從 60% 的 100 分降到 75% 的 0 分
        win_rate_score = max(0, 100 - (avg_win_rate - 60) * 20)
    
    # 報酬/回撤比: >3 = 100分, <0 = 0分
    ret_dd_ratio = total_return / abs(avg_max_dd) if avg_max_dd != 0 else 0
    ratio_score = min(100, max(0, ret_dd_ratio * 33.33))  # 3 => 100分
    
    # 最終加權分數（扣除勝率懲罰）
    score = (return_score * 0.40 +
             drawdown_score * 0.30 +
             win_rate_score * 0.15 +
             ratio_score * 0.15 -
             win_rate_penalty)
    
    return {
        'avg_return': total_return,
        'avg_max_drawdown': avg_max_dd,
        'avg_win_rate': avg_win_rate,
        'total_trades': total_trades,
        'score': score,
        'return_score': return_score,
        'drawdown_score': drawdown_score,
        'win_rate_score': win_rate_score,
        'ratio_score': ratio_score,
        'ret_dd_ratio': ret_dd_ratio,
        'win_rate_penalty': win_rate_penalty
    }

# ---- Data Loading ----

def load_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Download and prepare stock data."""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(start=start_date, end=end_date)
        if df.empty:
            print(f"  [WARN] No data for {ticker}")
            return pd.DataFrame()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        df = df[df['Volume'] > 0]  # Remove zero-volume rows
        return df
    except Exception as e:
        print(f"  [ERROR] {ticker}: {e}")
        return pd.DataFrame()

def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate all indicators for a dataframe."""
    df = calculate_dmpi(df)
    df = calculate_rsi(df)  # default period, will be recalculated in signal gen
    df = calculate_macd(df)
    df = df.dropna()
    return df

# ---- Main Optimization ----

def main():
    print("=" * 60)
    print("綜合共振策略參數優化")
    print("=" * 60)
    
    # Date range: try 5 years
    end_date = "2026-03-25"
    start_date = "2021-03-25"
    print(f"\n數據期間: {start_date} ~ {end_date}")
    print(f"標的股票: {len(STOCKS)} 檔")
    
    # Load all stock data
    print("\n📥 正在下載歷史數據...")
    stock_data = {}
    for ticker in STOCKS:
        print(f"  下載 {ticker} ({STOCK_NAMES[ticker]})...", end=" ")
        df = load_data(ticker, start_date, end_date)
        if not df.empty:
            df = prepare_data(df)
            stock_data[ticker] = df
            print(f"OK ({len(df)} rows)")
        else:
            print(f"FAIL")
    
    print(f"\n成功載入 {len(stock_data)}/{len(STOCKS)} 檔股票")
    
    if len(stock_data) == 0:
        print("沒有可用的股票數據，終止。")
        return
    
    # Generate all parameter combinations
    param_keys = list(PARAM_GRID.keys())
    param_values = list(PARAM_GRID.values())
    total_combinations = 1
    for v in param_values:
        total_combinations *= len(v)
    
    print(f"\n🔍 總共 {total_combinations} 組參數組合")
    print(f"   每檔股票需回測 {total_combinations} 次")
    print(f"   總回測次數: {total_combinations * len(stock_data)}")
    print()
    
    best_score = -999
    best_params = None
    best_portfolio = None
    all_results = []
    
    combo_idx = 0
    start_time = datetime.now()
    
    for combo in product(*param_values):
        combo_idx += 1
        params = dict(zip(param_keys, combo))
        
        # Progress every 50 combinations
        if combo_idx % 50 == 1:
            elapsed = (datetime.now() - start_time).total_seconds()
            eta = (elapsed / (combo_idx - 1)) * (total_combinations - combo_idx + 1) if combo_idx > 1 else 0
            print(f"\n  進度 {combo_idx}/{total_combinations} ({combo_idx/total_combinations*100:.1f}%) | "
                  f"已用時 {elapsed:.0f}s | 預估剩餘 {eta:.0f}s")
            if best_portfolio:
                print(f"  目前最佳: score={best_score:.1f}, return={best_portfolio['avg_return']:.1f}%, dd={best_portfolio['avg_max_drawdown']:.1f}%, win={best_portfolio['avg_win_rate']:.1f}% (penalty={best_portfolio['win_rate_penalty']:.1f})")
        
        stock_results = []
        for ticker, df in stock_data.items():
            try:
                df_sig = generate_signals_param(df.copy(), params)
                result = run_backtest(df_sig, initial_capital=INITIAL_CAPITAL)
                stock_results.append(result)
            except Exception as e:
                pass  # Skip failed stocks
        
        if len(stock_results) == 0:
            continue
        
        portfolio = score_portfolio(stock_results)
        portfolio['params'] = params
        portfolio['stock_results'] = {
            ticker: {
                'return': r['total_return_pct'],
                'drawdown': r['max_drawdown_pct'],
                'trades': r['total_trades'],
                'win_rate': r['win_rate_pct']
            }
            for ticker, r in zip(stock_data.keys(), stock_results)
        }
        all_results.append(portfolio)
        
        if portfolio['score'] > best_score:
            best_score = portfolio['score']
            best_params = params.copy()
            best_portfolio = portfolio.copy()
            print(f"\n  ⭐ NEW BEST! score={portfolio['score']:.1f} | return={portfolio['avg_return']:.1f}% | dd={portfolio['avg_max_drawdown']:.1f}% | win={portfolio['avg_win_rate']:.1f}% | penalty={portfolio['win_rate_penalty']:.1f}")
            print(f"     params: large=[{params['large_lower']},{params['large_upper']}], "
                  f"small=[{params['small_lower']},{params['small_upper']}], "
                  f"rsi=[{params['rsi_oversold']},{params['rsi_overbought']}], period={params['rsi_period']}")
    
    # ---- Print Final Results ----
    print("\n" + "=" * 60)
    print("🏆 優化結果")
    print("=" * 60)
    
    print(f"\n最佳參數組合:")
    print(f"  多頭通道下軌 (large_lower):  {best_params['large_lower']}")
    print(f"  多頭通道上軌 (large_upper):  {best_params['large_upper']}")
    print(f"  空頭通道下軌 (small_lower):  {best_params['small_lower']}")
    print(f"  空頭通道上軌 (small_upper):  {best_params['small_upper']}")
    print(f"  RSI 超賣閾值 (rsi_oversold): {best_params['rsi_oversold']}")
    print(f"  RSI 超買閾值 (rsi_overbought): {best_params['rsi_overbought']}")
    print(f"  RSI 期間 (rsi_period):       {best_params['rsi_period']}")
    
    print(f"\n最佳組合平均表現 (10檔股票):")
    print(f"  平均總報酬率:   {best_portfolio['avg_return']:.2f}%")
    print(f"  平均最大回撤:   {best_portfolio['avg_max_drawdown']:.2f}%")
    print(f"  平均勝率:       {best_portfolio['avg_win_rate']:.2f}%")
    print(f"  總交易次數:     {best_portfolio['total_trades']}")
    print(f"  報酬/回撤比:    {best_portfolio['ret_dd_ratio']:.2f}")
    print(f"  综合评分:       {best_portfolio['score']:.1f}")
    print(f"  分項得分: 報酬={best_portfolio['return_score']:.0f} | 回撤={best_portfolio['drawdown_score']:.0f} | 勝率={best_portfolio['win_rate_score']:.0f} | 比值={best_portfolio['ratio_score']:.0f} | 勝率懲罰={best_portfolio['win_rate_penalty']:.1f}")
    
    print(f"\n各檔股票個別表現:")
    print(f"{'股票':<8} {'名稱':<6} {'報酬率':>10} {'最大回撤':>10} {'交易次數':>8} {'勝率':>8}")
    print("-" * 56)
    for ticker, res in best_portfolio['stock_results'].items():
        name = STOCK_NAMES.get(ticker, ticker)
        print(f"{ticker:<8} {name:<6} {res['return']:>9.2f}% {res['drawdown']:>9.2f}% {res['trades']:>8} {res['win_rate']:>7.1f}%")
    
    # Top 5 parameter combinations
    print(f"\n\n🏅 前5名參數組合:")
    sorted_results = sorted(all_results, key=lambda x: x['score'], reverse=True)[:5]
    for i, r in enumerate(sorted_results, 1):
        p = r['params']
        print(f"\n  #{i} 總分={r['score']:.1f} | 報酬={r['avg_return']:.1f}% | 回撤={r['avg_max_drawdown']:.1f}% | 勝率={r['avg_win_rate']:.1f}% | 比值={r['ret_dd_ratio']:.2f}")
        print(f"     分項: 報酬{r['return_score']:.0f} | 回撤{r['drawdown_score']:.0f} | 勝率{r['win_rate_score']:.0f} | 比值{r['ratio_score']:.0f} | 懲罰={r['win_rate_penalty']:.1f}")
        print(f"     large=[{p['large_lower']},{p['large_upper']}] small=[{p['small_lower']},{p['small_upper']}] "
              f"rsi=[{p['rsi_oversold']},{p['rsi_overbought']}] period={p['rsi_period']}")
    
    total_time = (datetime.now() - start_time).total_seconds()
    print(f"\n\n總耗時: {total_time:.0f} 秒 ({total_time/60:.1f} 分鐘)")
    print("=" * 60)

if __name__ == "__main__":
    main()
