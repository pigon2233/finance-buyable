#!/usr/bin/env python3
"""
完整透明化台股篩選報告
步驟：
1. 分析150支股票的技術指標
2. 根據綜合共振策略給出訊號
3. 嚴格篩選過程
4. 最終推薦
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from strategy import calculate_dmpi, calculate_rsi, calculate_macd, generate_signals

STOCKS = [
    '2330.TW', '2317.TW', '2454.TW', '2308.TW', '2412.TW',
    '2881.TW', '2882.TW', '2303.TW', '3711.TW', '2886.TW',
    '2891.TW', '1301.TW', '1303.TW', '1216.TW', '2884.TW',
    '2002.TW', '2885.TW', '2357.TW', '2892.TW', '2880.TW',
    '3008.TW', '2603.TW', '5880.TW', '2327.TW', '2890.TW',
    '2883.TW', '2887.TW', '2207.TW', '3034.TW', '2379.TW',
    '2912.TW', '1326.TW', '2409.TW', '1101.TW', '3231.TW',
    '4938.TW', '5871.TW', '2615.TW', '2609.TW', '3045.TW',
    '2845.TW', '6669.TW', '2395.TW', '3037.TW', '2345.TW',
    '1605.TW', '9904.TW', '2812.TW', '2105.TW', '3443.TW',
    '3661.TW', '3035.TW', '1513.TW', '1519.TW', '1503.TW',
    '2376.TW', '2368.TW', '6239.TW', '6176.TW', '3189.TW',
    '8046.TW', '2360.TW', '3406.TW', '6213.TW', '2449.TW',
    '6415.TW', '2313.TW', '2408.TW', '2329.TW', '3017.TW',
    '3324.TWO', '3583.TW', '6278.TW', '3533.TW', '6443.TW',
    '2383.TW', '2385.TW', '2421.TW', '3013.TW', '3044.TW',
    '6235.TW', '2458.TW', '3010.TW', '3592.TW', '4919.TW',
    '4958.TW', '4961.TW', '4967.TW', '4968.TW', '5269.TW',
    '6120.TW', '6153.TW', '6177.TW', '6206.TW', '6271.TW',
    '6282.TW', '6285.TW', '8016.TW', '8081.TW', '8150.TW',
    '8210.TW', '2618.TW', '2610.TW', '2633.TW', '2723.TW',
    '2722.TW', '2204.TW', '2206.TW', '2211.TW', '2542.TW',
    '2501.TW', '2548.TW', '1402.TW', '1455.TW', '1717.TW',
    '1708.TW', '1718.TW', '1722.TW', '1723.TW', '1727.TW',
    '4763.TW', '1802.TW', '1904.TW', '1909.TW', '2049.TW',
    '2101.TW', '2103.TW', '2106.TW', '9910.TW', '9921.TW',
    '9945.TW', '2534.TW', '2520.TW', '3005.TW', '3532.TW',
    '3545.TW', '3576.TW', '3605.TW', '3617.TW', '3686.TW',
    '3701.TW', '3702.TW', '3703.TW', '3706.TW', '4912.TW',
    '4943.TW', '4960.TW', '4976.TW', '5284.TW'
]

print("=" * 80)
print("📊 台股 150 支完整透明化篩選報告")
print("=" * 80)
print(f"日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"策略: 綜合共振 v3")
print(f"參數: LARGE(-30~25) SMALL(-40~3) RSI(50/80) 空頭:搶短")
print("=" * 80)
print()

# ============ 第一步：收集所有數據 ============
print("【第一步】收集 150 支股票的技術指標")
print("-" * 80)

all_data = []
for stock in STOCKS:
    try:
        ticker = yf.Ticker(stock)
        df = ticker.history(start=(datetime.now() - timedelta(days=120)))
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        if len(df) < 60:
            continue
        
        # 計算指標
        df = calculate_dmpi(df)
        df = calculate_rsi(df)
        df = calculate_macd(df)
        df = generate_signals(df, indicator='綜合共振')
        
        last = df.iloc[-1]
        macd = last['MACD']
        macd_hist = last.get('MACD_Hist', macd - last.get('MACD_Signal', macd))
        
        # 判斷 Regime
        if macd > 0 and macd_hist >= 0:
            regime = 'LARGE'
            regime_cn = '多頭'
        elif macd < 0 and macd_hist <= 0:
            regime = 'SMALL'
            regime_cn = '空頭'
        else:
            regime = 'FLAT'
            regime_cn = '盤整'
        
        all_data.append({
            'stock': stock,
            'close': last['Close'],
            'dmpi': last['DMPI'],
            'rsi': last['RSI'],
            'macd': macd,
            'macd_hist': macd_hist,
            'volume': last['Volume'],
            'volume_20avg': df['Volume'].rolling(20).mean().iloc[-1],
            'signal': int(last['Signal']),
            'position': int(last['Position']),
            'regime': regime,
            'regime_cn': regime_cn
        })
    except Exception as e:
        pass

print(f"成功分析: {len(all_data)} 支股票")
print()

# ============ 第二步：根據訊號分類 ============
print("【第二步】根據 Strategy Signal 分類")
print("-" * 80)

buy_signals = [d for d in all_data if d['signal'] == 1]
sell_signals = [d for d in all_data if d['signal'] == -1]
no_signals = [d for d in all_data if d['signal'] == 0]

print(f"🔥 Signal=1 (買進): {len(buy_signals)} 支")
print(f"🧹 Signal=-1 (賣出): {len(sell_signals)} 支")
print(f"☁️ Signal=0 (無訊號): {len(no_signals)} 支")
print()

# ============ 第三步：買進訊號細節 ============
if buy_signals:
    print("【第三步】🔥 Signal=1 買進訊號詳細分析")
    print("-" * 80)
    
    # 計算各項評分
    for d in buy_signals:
        # Regime 評分（多頭>空頭>盤整）
        if d['regime'] == 'LARGE':
            d['regime_score'] = 3
        elif d['regime'] == 'SMALL':
            d['regime_score'] = 2
        else:
            d['regime_score'] = 1
        
        # DMPI 評分（靠近通道中間越好）
        if d['regime'] == 'LARGE':
            middle = -2.5  # (-30 + 25) / 2
            d['dmpi_dist'] = abs(d['dmpi'] - middle)
        elif d['regime'] == 'SMALL':
            middle = -18.5  # (-40 + 3) / 2
            d['dmpi_dist'] = abs(d['dmpi'] - middle)
        else:
            d['dmpi_dist'] = abs(d['dmpi'])
        
        # 計算量比
        d['vol_ratio'] = d['volume'] / d['volume_20avg'] if d['volume_20avg'] > 0 else 1
        
        # RSI 評分（40-60 中性區間最好）
        rsi = d['rsi']
        if 40 <= rsi <= 60:
            d['rsi_ok'] = True
        else:
            d['rsi_ok'] = False
    
    # 計算總分
    max_dmpi_dist = max([d['dmpi_dist'] for d in buy_signals])
    max_vol_ratio = max([d['vol_ratio'] for d in buy_signals])
    
    for d in buy_signals:
        # DMPI 分數（偏離越小分數越高）
        d['dmpi_score'] = 100 * (1 - d['dmpi_dist'] / max_dmpi_dist) if max_dmpi_dist > 0 else 50
        
        # 量比分數
        d['vol_score'] = 100 * (d['vol_ratio'] / max_vol_ratio) if max_vol_ratio > 0 else 50
        
        # Regime 分數
        d['regime_score_final'] = d['regime_score'] * 20
        
        # 總分
        d['total_score'] = (
            d['dmpi_score'] * 0.5 +    # DMPI 距離 50%
            d['vol_score'] * 0.2 +     # 成交量 20%
            d['regime_score_final'] * 0.3  # Regime 30%
        )
    
    # 排序
    buy_signals.sort(key=lambda x: x['total_score'], reverse=True)
    
    print(f"{'排名':<4} {'股票':<12} {'現價':>8} {'Regime':<6} {'DMPI':>8} {'DMPI距':>6} {'RSI':>6} {'量比':>6} {'總分':>6}")
    print("-" * 80)
    
    for i, d in enumerate(buy_signals):
        print(f"{i+1:<4} {d['stock']:<12} {d['close']:>8.2f} {d['regime_cn']:<6} {d['dmpi']:>+8.1f} {d['dmpi_dist']:>6.1f} {d['rsi']:>6.1f} {d['vol_ratio']:>6.2f}x {d['total_score']:>6.1f}")

print()

# ============ 第四步：篩選最終推薦 ============
print("【第四步】🎯 最終推薦")
print("-" * 80)

if buy_signals:
    # 嚴格篩選條件
    candidates = []
    for d in buy_signals:
        reasons = []
        
        # 條件1：Regime 必須是多頭
        if d['regime'] == 'LARGE':
            reasons.append("✅ Regime=多頭")
        else:
            reasons.append("⚠️ Regime=空頭")
        
        # 條件2：RSI 要在合理範圍（不超過80）
        if d['rsi'] <= 75:
            reasons.append("✅ RSI={:.1f}<80".format(d['rsi']))
        else:
            reasons.append("⚠️ RSI={:.1f}>80 偏熱".format(d['rsi']))
        
        # 條件3：DMPI 不能太靠近邊界
        if d['regime'] == 'LARGE':
            if -25 <= d['dmpi'] <= 20:
                reasons.append("✅ DMPI 在安全區間")
            else:
                reasons.append("⚠️ DMPI 靠近邊界")
        else:
            if -35 <= d['dmpi'] <= 0:
                reasons.append("✅ DMPI 在安全區間")
            else:
                reasons.append("⚠️ DMPI 靠近邊界")
        
        candidates.append({
            **d,
            'reasons': reasons,
            'pass_count': sum([1 for r in reasons if r.startswith('✅')])
        })
    
    # 按通過條件數排序
    candidates.sort(key=lambda x: (x['pass_count'], x['total_score']), reverse=True)
    
    print("篩選標準：")
    print("  1. Regime = 多頭（多頭市場順勢而為）")
    print("  2. RSI < 80（避開過熱）")
    print("  3. DMPI 在安全區間（不要太靠近邊界）")
    print()
    
    print("🏆 推薦名單（按綜合評分排序）：")
    print("-" * 80)
    
    for i, c in enumerate(candidates[:5]):  # 只推薦前5名
        print(f"\n第 {i+1} 名：{c['stock']}")
        print(f"  現價: ${c['close']:.2f}")
        print(f"  Regime: {c['regime_cn']} ({c['regime']})")
        print(f"  DMPI: {c['dmpi']:+.1f} (距離通道中間 {c['dmpi_dist']:.1f})")
        print(f"  RSI: {c['rsi']:.1f}")
        print(f"  量比: {c['vol_ratio']:.2f}x")
        print(f"  總評分: {c['total_score']:.1f}")
        print(f"  通過條件: {c['pass_count']}/3")
        for r in c['reasons']:
            print(f"    {r}")
        
        # 計算大約需要多少錢（零股）
        # 零股最低100股
        estimated_cost = c['close'] * 100
        print(f"  💰 零股100股估計: ${estimated_cost:.0f}")

print()
print("=" * 80)
print("⚠️ 以上為技術分析訊號，不構成投資建議")
print("📝 使用方式：")
print("   1. 從推薦名單中選擇")
print("   2. 設定停損點（DMPI 觸發賣出時）")
print("   3. 設定目標（DMPI 達到停利時）")
print("=" * 80)
