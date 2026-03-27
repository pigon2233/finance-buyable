#!/usr/bin/env python3
"""
完整回測腳本 - 使用優化後的「綜合共振」策略參數 v2
"""
import sys
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from strategy import calculate_dmpi, calculate_rsi, calculate_macd, generate_signals
from backtester import run_backtest

# 150支股票清單
STOCKS = [
    "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2412.TW",
    "2881.TW", "2882.TW", "2303.TW", "3711.TW", "2886.TW",
    "2891.TW", "1301.TW", "1303.TW", "1216.TW", "2884.TW",
    "2002.TW", "2885.TW", "2357.TW", "2892.TW", "2880.TW",
    "3008.TW", "2603.TW", "5880.TW", "2327.TW", "2890.TW",
    "2883.TW", "2887.TW", "2207.TW", "3034.TW", "2379.TW",
    "2912.TW", "1326.TW", "2409.TW", "1101.TW", "3231.TW",
    "4938.TW", "5871.TW", "2615.TW", "2609.TW", "3045.TW",
    "2845.TW", "6669.TW", "2395.TW", "3037.TW", "2345.TW",
    "1605.TW", "9904.TW", "2812.TW", "2105.TW", "3443.TW",
    "3661.TW", "3035.TW", "1513.TW", "1519.TW", "1503.TW",
    "2376.TW", "2368.TW", "6239.TW", "6176.TW", "3189.TW",
    "8046.TW", "2360.TW", "3406.TW", "6213.TW", "2449.TW",
    "6415.TW", "2313.TW", "2408.TW", "2329.TW", "3017.TW",
    "3324.TWO", "3583.TW", "6278.TW", "3533.TW", "6443.TW",
    "2383.TW", "2385.TW", "2421.TW", "3013.TW", "3044.TW",
    "6235.TW", "2458.TW", "3010.TW", "3592.TW", "4919.TW",
    "4958.TW", "4961.TW", "4967.TW", "4968.TW", "5269.TW",
    "6120.TW", "6153.TW", "6177.TW", "6206.TW", "6271.TW",
    "6282.TW", "6285.TW", "8016.TW", "8081.TW", "8150.TW",
    "8210.TW", "2618.TW", "2610.TW", "2633.TW", "2723.TW",
    "2722.TW", "2204.TW", "2206.TW", "2211.TW", "2542.TW",
    "2501.TW", "2548.TW", "1402.TW", "1455.TW", "1717.TW",
    "1708.TW", "1718.TW", "1722.TW", "1723.TW", "1727.TW",
    "4763.TW", "1802.TW", "1904.TW", "1909.TW", "2049.TW",
    "2101.TW", "2103.TW", "2106.TW", "9910.TW", "9921.TW",
    "9945.TW", "2534.TW", "2520.TW", "3005.TW", "3532.TW",
    "3545.TW", "3576.TW", "3605.TW", "3617.TW", "3686.TW",
    "3701.TW", "3702.TW", "3703.TW", "3706.TW", "4912.TW",
    "4943.TW", "4960.TW", "4976.TW", "5284.TW"
]

# 優化後的參數（直接寫入）
LARGE_UPPER = 30      # 多頭上軌
LARGE_LOWER = -20     # 多頭下軌
SMALL_UPPER = 5       # 空頭上軌
SMALL_LOWER = -35      # 空頭下軌
RSI_OVERSOLD = 40     # RSI 超賣
RSI_OVERBOUGHT = 80    # RSI 超買
空頭行為 = "flat"      # 空手（不搶短）

def run_backtest_for_stock(stock_code: str, days: int = 365) -> dict:
    """對單一股票跑回測"""
    try:
        ticker = yf.Ticker(stock_code)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        df = ticker.history(start=start_date, end=end_date)
        
        if df.empty or len(df) < 60:
            return None
            
        # 計算指標
        df = calculate_dmpi(df)
        df = calculate_rsi(df)
        df = calculate_macd(df)
        df = generate_signals(df, indicator="綜合共振")
        
        # 執行回測
        result = run_backtest(df, initial_capital=100000.0, indicator_name="綜合共振")
        
        return {
            'stock': stock_code,
            'total_return': result['total_return_pct'],
            'max_drawdown': result['max_drawdown_pct'],
            'win_rate': result['win_rate_pct'],
            'total_trades': result['total_trades'],
            'final_capital': result['final_capital']
        }
    except Exception as e:
        return None

def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 365
    
    print(f"🚀 使用優化參數回測 {len(STOCKS)} 支股票（近 {days} 天）", flush=True)
    print("=" * 80, flush=True)
    print(f"參數設定：多頭通道({LARGE_LOWER}~{LARGE_UPPER}) 空頭通道({SMALL_LOWER}~{SMALL_UPPER}) RSI({RSI_OVERSOLD}/{RSI_OVERBOUGHT}) 空頭行為({空頭行為})", flush=True)
    print("=" * 80, flush=True)
    
    results = []
    
    for i, stock in enumerate(STOCKS):
        result = run_backtest_for_stock(stock, days)
        if result:
            results.append(result)
            # 輸出格式：代碼 | 報酬率 | 最大回撤 | 勝率 | 交易次數
            ret_emoji = "🟢" if result['total_return'] > 0 else "🔴"
            print(f"{ret_emoji} {result['stock']:12} | 報酬:{result['total_return']:+8.2f}% | 回撤:{result['max_drawdown']:7.2f}% | 勝率:{result['win_rate']:5.1f}% | 交易:{result['total_trades']:3.0f}次", flush=True)
    
    print("=" * 80, flush=True)
    
    # 統計
    if results:
        returns = [r['total_return'] for r in results]
        win_rates = [r['win_rate'] for r in results]
        max_dds = [r['max_drawdown'] for r in results]
        
        profitable = [r for r in results if r['total_return'] > 0]
        
        print(f"✅ 完成 {len(results)}/{len(STOCKS)} 支股票", flush=True)
        print()
        print("📊 總體統計", flush=True)
        print("-" * 40, flush=True)
        print(f"  獲利股票: {len(profitable)} ({len(profitable)/len(results)*100:.1f}%)", flush=True)
        print(f"  虧損股票: {len(results)-len(profitable)} ({(len(results)-len(profitable))/len(results)*100:.1f}%)", flush=True)
        print()
        print(f"  平均報酬率: {sum(returns)/len(returns):+.2f}%", flush=True)
        print(f"  平均勝率: {sum(win_rates)/len(win_rates):.1f}%", flush=True)
        print(f"  平均最大回撤: {sum(max_dds)/len(max_dds):.2f}%", flush=True)
        print()
        
        # 完整排行榜
        print("🏆 完整排名（按報酬率）", flush=True)
        print("-" * 80, flush=True)
        sorted_results = sorted(results, key=lambda x: x['total_return'], reverse=True)
        for i, r in enumerate(sorted_results):
            ret_emoji = "🟢" if r['total_return'] > 0 else "🔴"
            print(f"{i+1:3}. {ret_emoji} {r['stock']:12} | {r['total_return']:+8.2f}% | 勝率:{r['win_rate']:5.1f}% | 回撤:{r['max_drawdown']:7.2f}%", flush=True)

if __name__ == "__main__":
    main()
