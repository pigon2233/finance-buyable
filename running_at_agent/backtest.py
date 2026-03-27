#!/usr/bin/env python3
"""
股票策略回測工具
使用「綜合共振」策略進行歷史回測
"""
import sys
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# 載入策略和回測引擎
from strategy import calculate_dmpi, calculate_rsi, calculate_macd, generate_signals
from backtester import run_backtest

def load_stock_data(stock_code: str, days: int = 365) -> pd.DataFrame:
    """載入股票歷史資料"""
    ticker = yf.Ticker(stock_code)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    df = ticker.history(start=start_date, end=end_date)
    return df

def main():
    if len(sys.argv) < 2:
        print("用法: python backtest.py <股票代碼> [回測天數]")
        print("例如: python backtest.py 2317.TW 365")
        sys.exit(1)
    
    stock_code = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 365
    
    print(f"📊 正在載入 {stock_code} 近 {days} 天的歷史資料...")
    
    # 載入資料
    df = load_stock_data(stock_code, days)
    
    if df.empty:
        print(f"❌ 無法載入 {stock_code} 的資料")
        sys.exit(1)
    
    print(f"✅ 成功載入 {len(df)} 筆資料")
    print(f"   時間範圍: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}")
    print()
    
    # 計算技術指標
    print("🔧 計算技術指標...")
    df = calculate_dmpi(df)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    print("✅ 指標計算完成")
    print()
    
    # 產生綜合共振訊號
    print("📡 產生綜合共振買賣訊號...")
    df = generate_signals(df, indicator="綜合共振")
    buy_signals = (df['Signal'] == 1).sum()
    sell_signals = (df['Signal'] == -1).sum()
    print(f"✅ 訊號產生完成 - 買進: {buy_signals} 次, 賣出: {sell_signals} 次")
    print()
    
    # 執行回測
    print("🚀 執行回測...")
    result = run_backtest(df, initial_capital=100000.0, indicator_name="綜合共振")
    
    # 輸出結果
    print()
    print("=" * 60)
    print(f"📈 {stock_code} 綜合共振策略回測報告")
    print("=" * 60)
    print(f"回測期間: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"初始資金: ${result['initial_capital']:,.2f}")
    print(f"最終資金: ${result['final_capital']:,.2f}")
    print(f"總報酬率: {result['total_return_pct']:+.2f}%")
    print(f"最大回撤: {result['max_drawdown_pct']:.2f}%")
    print(f"總交易次數: {result['total_trades']}")
    print(f"勝率: {result['win_rate_pct']:.1f}%")
    print()
    
    # 顯示交易明細
    if result['trades']:
        print("📋 交易明細:")
        print("-" * 60)
        for trade in result['trades']:
            if trade['Type'] == 'Buy':
                print(f"  🟢 {trade['Date'].strftime('%Y-%m-%d')} 買進 @ ${trade['Price']:.2f}")
                print(f"     原因: {trade['Reason']}")
            else:
                profit = trade.get('Profit_%', 0)
                emoji = "🔴" if profit < 0 else "🟢"
                print(f"  {emoji} {trade['Date'].strftime('%Y-%m-%d')} 賣出 @ ${trade['Price']:.2f} ({profit:+.2f}%)")
                print(f"     原因: {trade['Reason']}")
            print()
    
    print("=" * 60)
    print("⚠️  以上為歷史回測結果，不代表未來投資績效")
    print("=" * 60)

if __name__ == "__main__":
    main()
