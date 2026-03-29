#!/bin/bash
# 冰可樂龍蝦：150 支精銳台股自動化掃描（使用 strategy.py 綜合共振策略）

cd ~/.openclaw/workspace/skills/finance_buyable
source .venv/bin/activate

# 第一階段：掃描所有股票
SCAN_OUTPUT=$(python3 << 'PYEOF'
import yfinance as yf
import pandas as pd
from strategy import calculate_dmpi, calculate_rsi, calculate_macd, generate_signals
from datetime import datetime, timedelta

STOCKS = '''2330.TW 2317.TW 2454.TW 2308.TW 2382.TW 2412.TW 2881.TW 2882.TW 2303.TW 3711.TW
2886.TW 2891.TW 1301.TW 1303.TW 1216.TW 2884.TW 2002.TW 2885.TW 2357.TW 2892.TW
2880.TW 3008.TW 2603.TW 5880.TW 2327.TW 2890.TW 2883.TW 2887.TW 2207.TW 3034.TW
2379.TW 2912.TW 1326.TW 2409.TW 1101.TW 3231.TW 4938.TW 5871.TW 2615.TW 2609.TW
3045.TW 2845.TW 6669.TW 2395.TW 3037.TW 2345.TW 1605.TW 9904.TW 2812.TW 2105.TW
3661.TW 3443.TW 3035.TW 1513.TW 1519.TW 1503.TW 2376.TW 2368.TW 6239.TW 6176.TW
3189.TW 8046.TW 2360.TW 3406.TW 6213.TW 2449.TW 6415.TW 2313.TW 2408.TW 2329.TW
3017.TW 3324.TWO 3583.TW 6278.TW 3533.TW 6443.TW 2383.TW 2385.TW 2421.TW 3013.TW
3044.TW 6235.TW 2458.TW 3010.TW 3592.TW 4919.TW 4958.TW 4961.TW 4967.TW 4968.TW
5269.TW 6120.TW 6153.TW 6177.TW 6206.TW 6271.TW 6282.TW 6285.TW 8016.TW 8081.TW
8150.TW 8210.TW 2618.TW 2610.TW 2633.TW 2723.TW 2722.TW 2204.TW 2206.TW 2211.TW
2542.TW 2501.TW 2548.TW 1402.TW 1455.TW 1717.TW 1708.TW 1718.TW 1722.TW 1723.TW
1727.TW 4763.TW 1802.TW 1904.TW 1909.TW 2049.TW 2101.TW 2103.TW 2106.TW 9910.TW
9921.TW 9945.TW 2534.TW 2520.TW 3005.TW 3532.TW 3545.TW 3576.TW 3605.TW 3617.TW
3686.TW 3701.TW 3702.TW 3703.TW 3706.TW 4912.TW 4943.TW 4960.TW 4976.TW 5284.TW'''.split()

print('{:<8} {:>6} {:>5} {:>7} {:>4} {:>3} {}'.format('代碼','DMPI','RSI','MACD','趨勢','綜合','結果'))
print('=' * 55)

buy_list = []
sell_list = []

for stock in STOCKS:
    try:
        ticker = yf.Ticker(stock)
        df = ticker.history(start=(datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d'))
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if len(df) < 60:
            continue
        df = calculate_dmpi(df)
        df = calculate_rsi(df)
        df = calculate_macd(df)
        df = generate_signals(df, indicator='綜合共振')

        signal = int(df['Signal'].iloc[-1])
        dmpi = df['DMPI'].iloc[-1]
        rsi = df['RSI'].iloc[-1]
        macd = df['MACD'].iloc[-1]
        macd_hist = df.get('MACD_Hist', 0).iloc[-1]

        if macd > 0 and macd_hist >= 0:
            regime = '多頭'
        elif macd < 0 and macd_hist <= 0:
            regime = '空頭'
        else:
            regime = '盤整'

        if signal == 1:
            comp = '買'
            result = '🔥買'
            buy_list.append(stock)
        elif signal == -1:
            comp = '賣'
            result = '🧹賣'
            sell_list.append(stock)
        else:
            comp = '觀'
            result = '☕觀'

        print('{:<8} {:>6.1f} {:>5.1f} {:>7.2f} {:>4} {:>3} {}'.format(stock, dmpi, rsi, macd, regime, comp, result))
    except:
        pass

print('=' * 55)
print('🔥 強烈買進: ' + (', '.join(buy_list) if buy_list else '無') + ' (' + str(len(buy_list)) + ' 支)')
print('🧹 強烈賣出: ' + (', '.join(sell_list) if sell_list else '無') + ' (' + str(len(sell_list)) + ' 支)')
print('📊 統計：共 ' + str(len(buy_list)+len(sell_list)) + '/' + str(len(STOCKS)) + ' 支有訊號')

# 输出 buy_list 供下一阶段使用
print('__BUY_LIST__:' + ','.join(buy_list))
PYEOF
)

# 解析買進列表
BUY_STOCKS=$(echo "$SCAN_OUTPUT" | grep '^__BUY_LIST__:' | sed 's/^__BUY_LIST__://')
SCAN_RESULT=$(echo "$SCAN_OUTPUT" | grep -v '^__BUY_LIST__:')

# 第二階段：對買進股票評分排序
if [ -n "$BUY_STOCKS" ]; then
    # 把逗點換成空白，讓 daily_pick.py 能正確解析每個代碼
    BUY_STOCKS_SPACE=$(echo "$BUY_STOCKS" | tr ',' ' ')
    PICK_OUTPUT=$(python3 daily_pick.py $BUY_STOCKS_SPACE 2>&1)
else
    PICK_OUTPUT="無買訊號股票"
fi

# 第三階段：持股檢查
PORTFOLIO_OUTPUT=$(python3 << 'PYEOF'
import yfinance as yf
from strategy import calculate_dmpi, calculate_rsi, calculate_macd, generate_signals
from datetime import datetime, timedelta

# 持股列表：代碼, 成本, 股數
positions = [
    ('2357.TW', 567, 1),
    ('2376.TW', 235, 1),
    ('2548.TW', 122.5, 4),
    ('3045.TW', 109.5, 4),
]

print('{:<10} {:>6} {:>7} {:>6} {:>5} {:>4} {}'.format('代碼','現價','PnL','DMPI','RSI','Signal','結論'))
print('=' * 60)

has_sell = False
for stock, cost, qty in positions:
    try:
        df = yf.Ticker(stock).history(start=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        df = calculate_dmpi(df)
        df = calculate_rsi(df)
        df = calculate_macd(df)
        df = generate_signals(df, indicator='綜合共振')
        
        last = df.iloc[-1]
        close = last['Close']
        dmpi = last['DMPI']
        rsi = last['RSI']
        signal = int(last['Signal'])
        
        pnl = (close - cost) * qty
        pnl_pct = (close - cost) / cost * 100
        
        if signal == 1:
            result = '🔥買'
        elif signal == -1:
            result = '🧹賣'
            has_sell = True
        else:
            result = '☕觀'
        
        print('{:<10} {:>6.0f} {:>+6.0f}({:>+5.1f}%) {:>6.1f} {:>5.1f} {:>4} {}'.format(
            stock, close, pnl, pnl_pct, dmpi, rsi, signal, result))
    except:
        print('{:<10} Error'.format(stock))

print('=' * 60)
if has_sell:
    print('⚠️ 【警告】有持股出現賣訊！')
else:
    print('✅ 全數持有中，無賣訊')
PYEOF
)

# 發送 Discord 訊息
/home/pigon/.npm-global/bin/openclaw message send --channel discord --target 1484229476916138014 --message "📈 台股每日精銳掃描 $(date '+%Y-%m-%d')（綜合共振策略）

\`\`\`
$SCAN_RESULT
\`\`\`

🏆 每日選股評分

\`\`\`
$PICK_OUTPUT
\`\`\`

💼 持股檢查

\`\`\`
$PORTFOLIO_OUTPUT
\`\`\`"