import pandas as pd

def run_backtest(df: pd.DataFrame, initial_capital=100000.0) -> dict:
    """
    執行策略回測
    輸入 df 需要有 'Close', 'Signal'
    """
    capital = initial_capital
    position = 0
    shares = 0
    
    history = []
    trades = []
    
    buy_price = 0
    
    for date, row in df.iterrows():
        signal = row.get('Signal', 0)
        close_price = row['Close']
        
        # 買進
        if signal == 1 and shares == 0:
            shares = capital / close_price
            capital = 0
            buy_price = close_price
            trades.append({'Date': date, 'Type': 'Buy', 'Price': close_price})
            
        # 賣出
        elif signal == -1 and shares > 0:
            capital = shares * close_price
            shares = 0
            profit_pct = (close_price - buy_price) / buy_price * 100
            trades.append({'Date': date, 'Type': 'Sell', 'Price': close_price, 'Profit_%': profit_pct})
            
        # 每日結算總價值
        current_value = capital + (shares * close_price)
        history.append({
            'Date': date,
            'Total_Value': current_value,
            'Close': close_price,
            'DMPI': row.get('DMPI', 0),
            'Signal': signal
        })
        
    # 最後一天強制平倉計算總價值
    if shares > 0:
        capital = shares * df.iloc[-1]['Close']
        shares = 0
        profit_pct = (df.iloc[-1]['Close'] - buy_price) / buy_price * 100
        trades.append({'Date': df.index[-1], 'Type': 'Sell (Auto Close)', 'Price': df.iloc[-1]['Close'], 'Profit_%': profit_pct})
        
    final_capital = capital
    total_return = (final_capital - initial_capital) / initial_capital * 100
    
    # 計算最大回撤 (Max Drawdown)
    history_df = pd.DataFrame(history)
    max_drawdown = 0
    if not history_df.empty:
        history_df['Peak'] = history_df['Total_Value'].cummax()
        history_df['Drawdown'] = (history_df['Total_Value'] - history_df['Peak']) / history_df['Peak']
        # 預防 min() 在空或NaN情況下出錯
        min_dd = history_df['Drawdown'].min()
        if pd.notna(min_dd):
            max_drawdown = min_dd * 100

    # 勝率
    winning_trades = [t for t in trades if 'Sell' in t['Type'] and t.get('Profit_%', 0) > 0]
    total_sell_trades = len([t for t in trades if 'Sell' in t['Type']])
    win_rate = (len(winning_trades) / total_sell_trades * 100) if total_sell_trades > 0 else 0
    
    return {
        'initial_capital': initial_capital,
        'final_capital': final_capital,
        'total_return_pct': total_return,
        'max_drawdown_pct': max_drawdown,
        'total_trades': total_sell_trades,
        'win_rate_pct': win_rate,
        'trades': trades,
        'history': history_df
    }

def get_latest_recommendation(df: pd.DataFrame) -> dict:
    """
    根據最新的盤勢給出進出場建議
    """
    if df.empty or 'DMPI' not in df.columns:
        return {"action": "N/A", "reason": "No data"}
        
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2] if len(df) > 1 else last_row
    
    dmpi = last_row.get('DMPI', 0)
    prev_dmpi = prev_row.get('DMPI', 0)
    
    if pd.isna(dmpi) or pd.isna(prev_dmpi):
        return {"action": "N/A", "reason": "指標計算中 (資料不足)"}
        
    if prev_dmpi <= 0.5 and dmpi > 0.5:
        return {"action": "強烈買進 (Buy)", "reason": "DMPI 指標帶量突破門檻，買盤強勁", "price": last_row['Close']}
    elif prev_dmpi >= 0 and dmpi < 0:
        return {"action": "賣出/觀望 (Sell)", "reason": "DMPI 跌破零軸，轉為賣盤主導", "price": last_row['Close']}
    elif dmpi > 0.5:
        return {"action": "持有 (Hold)", "reason": "指標維持高檔，趨勢偏多"}
    else:
        return {"action": "觀望 (Wait)", "reason": "指標偏弱，無明顯進場訊號"}
