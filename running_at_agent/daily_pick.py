#!/usr/bin/env python3
"""
每日選股評分系統（策略 I - 動能強勢股）
多頭50% + RSI在50-70強勢區30% + 成交量突破20%
"""
import sys
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from strategy import calculate_dmpi, calculate_rsi, calculate_macd, generate_signals

def calculate_score(stock_code: str) -> dict:
    """計算單一股票的評分（策略 I - 動能強勢股）"""
    try:
        ticker = yf.Ticker(stock_code)
        df = ticker.history(start=(datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d'))
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        if df.empty or len(df) < 60:
            return None
        
        df = calculate_dmpi(df)
        df = calculate_rsi(df)
        df = calculate_macd(df)
        df = generate_signals(df, indicator='綜合共振')
        
        last = df.iloc[-1]
        signal = int(last.get('Signal', 0))
        position = int(last.get('Position', 0))
        
        if signal != 1:
            return None
        
        dmpi = last['DMPI']
        macd = last['MACD']
        macd_hist = last.get('MACD_Hist', 0)
        rsi = last['RSI']
        volume_20_avg = df['Volume'].rolling(20).mean().iloc[-1]
        volume_ratio = last['Volume'] / volume_20_avg if volume_20_avg > 0 else 1

        if macd > 0 and macd_hist >= 0:
            regime = 'LARGE'
        elif macd < 0 and macd_hist <= 0:
            regime = 'SMALL'
        else:
            regime = 'FLAT'

        # ===== 策略 I 評分邏輯 =====
        # Regime 分數（多頭最高）
        if regime == 'LARGE':
            regime_score = 100
        elif regime == 'FLAT':
            regime_score = 40
        else:
            regime_score = 0
        
        # RSI 分數（50-70 強勢區最高）
        if 50 <= rsi <= 70:
            rsi_score = 100
        elif rsi < 50:
            rsi_score = 50 + 50 * rsi / 50
        else:
            rsi_score = max(0, 100 - (rsi - 70) * 3)
        
        # 成交量分數
        vol_score = min(100, volume_ratio * 100)
        
        # 總分：Regime(50%) + RSI(30%) + Vol(20%)
        total_score = regime_score * 0.50 + rsi_score * 0.30 + vol_score * 0.20
        
        return {
            'stock': stock_code,
            'signal': 'BUY',
            'regime': regime,
            'dmpi': dmpi,
            'rsi': rsi,
            'volume_ratio': volume_ratio,
            'regime_score': regime_score,
            'rsi_score': rsi_score,
            'vol_score': vol_score,
            'total_score': total_score,
            'close': last['Close']
        }
        
    except Exception as e:
        return None

def main():
    if len(sys.argv) < 2:
        print("用法: python daily_pick.py <股票代碼1> <股票代碼2> ...")
        print("例如: python daily_pick.py 2330.TW 2317.TW 2308.TW")
        sys.exit(1)
    
    stocks = sys.argv[1:]
    
    print("📊 每日選股評分系統（策略 I - 動能強勢股）", flush=True)
    print("=" * 70, flush=True)
    print(f"評分股票: {', '.join(stocks)}", flush=True)
    print("=" * 70, flush=True)
    
    results = []
    for stock in stocks:
        print(f"🔍 分析 {stock}...", end=" ", flush=True)
        result = calculate_score(stock)
        if result:
            print(f"✅ Reg:{result['regime']} RSI:{result['rsi']:.1f} 量比:{result['volume_ratio']:.2f}x", flush=True)
            results.append(result)
        else:
            print("❌ 無買訊號", flush=True)
    
    if not results:
        print("沒有合格的買訊號股票")
        return
    
    # 按總分排序
    results.sort(key=lambda x: x['total_score'], reverse=True)
    
    print()
    print("🏆 評分排名", flush=True)
    print("-" * 70, flush=True)
    
    for i, r in enumerate(results):
        regime_icon = '📈' if r['regime'] == 'LARGE' else ('➡️' if r['regime'] == 'FLAT' else '📉')
        
        # 甜區判斷（根據8年回測，80-89最佳，90+報酬遞減）
        score = r['total_score']
        if 50 <= score <= 89:
            zone = '✅甜區'
        elif 90 <= score <= 99:
            zone = '⚠️過熱'
        elif score >= 100:
            zone = '🔴極熱'
        else:
            zone = '🔸普通'
        
        print(f"{i+1}. {r['stock']:<12} | 總分:{r['total_score']:5.1f} {zone}", flush=True)
        print(f"   Reg:{regime_icon}{r['regime']:<5} Reg分:{r['regime_score']:5.1f} RSI分:{r['rsi_score']:5.1f} Vol分:{r['vol_score']:5.1f}", flush=True)
        print(f"   RSI={r['rsi']:.1f} 量比={r['volume_ratio']:.2f}x 現價={r['close']:.2f}", flush=True)
        print(flush=True)
    
    print("-" * 70, flush=True)
    print("💡 策略 I 邏輯：", flush=True)
    print("   多頭(Regime) 50% + RSI強勢區(50-70) 30% + 成交量 20%", flush=True)
    print("   Regime優先：多頭 > 盤整 > 空頭", flush=True)
    print("-" * 70, flush=True)

if __name__ == "__main__":
    main()
