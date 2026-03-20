import pandas as pd

def run_backtest(df: pd.DataFrame, initial_capital=100000.0, indicator_name="自創 DMPI") -> dict:
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
    
    # 決定要儲存哪個指標的歷史數值在明細中
    if indicator_name == "自創 DMPI": ind_col = 'DMPI'
    elif indicator_name == "RSI": ind_col = 'RSI'
    elif indicator_name == "MACD": ind_col = 'MACD_Hist'
    else: ind_col = None
    
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
            'Indicator_Value': row.get(ind_col, 0) if ind_col else 0,
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

def get_latest_recommendation(df: pd.DataFrame, indicator_name="自創 DMPI") -> dict:
    """
    根據最新的盤勢給出更細緻的進出場建議 (包含加碼、減碼、清倉等)
    """
    if df.empty:
        return {"action": "N/A", "reason": "No data"}
        
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2] if len(df) > 1 else last_row
    
    if indicator_name == "自創 DMPI":
        dmpi = last_row.get('DMPI', 0)
        prev_dmpi = prev_row.get('DMPI', 0)
        if pd.isna(dmpi) or pd.isna(prev_dmpi):
            return {"action": "N/A", "reason": "指標計算中 (資料不足)"}
            
        if prev_dmpi <= 0 and dmpi > 0:
            return {"action": "強烈買進 (Buy)", "reason": "DMPI 突破零軸，買盤翻多轉強", "price": last_row['Close']}
        elif dmpi > 0 and dmpi > prev_dmpi:
            return {"action": "建議加碼 (Add)", "reason": f"DMPI 持續上揚發散 ({dmpi:.2f})，多頭動能轉強"}
        elif dmpi > 0 and dmpi < prev_dmpi:
            return {"action": "建議減碼 (Reduce)", "reason": f"DMPI 為正且高點回落 ({dmpi:.2f})，動能開始減弱"}
        elif prev_dmpi >= 0 and dmpi < 0:
            return {"action": "建議清倉 (Clear)", "reason": "DMPI 跌破零軸，轉為賣盤主導，建議離場", "price": last_row['Close']}
        elif dmpi > 0:
            return {"action": "續抱持有 (Hold)", "reason": f"DMPI 維持正值 ({dmpi:.2f})，趨勢偏多"}
        else:
            return {"action": "空手觀望 (Wait)", "reason": f"DMPI 為負 ({dmpi:.2f})，趨勢偏空不宜進場"}

    elif indicator_name == "RSI":
        rsi = last_row.get('RSI', 0)
        prev_rsi = prev_row.get('RSI', 0)
        
        if pd.isna(rsi): return {"action": "N/A", "reason": "資料不足"}
        
        if prev_rsi <= 30 and rsi > 30:
            return {"action": "強烈買進 (Buy)", "reason": "RSI 跌深反彈，突破 30 超賣區金叉", "price": last_row['Close']}
        elif rsi > 70 and rsi > prev_rsi:
            return {"action": "建議減碼 / 分批獲利 (Reduce)", "reason": f"RSI 進入超買區 ({rsi:.1f})，風險逐漸攀升"}
        elif rsi > prev_rsi and 30 < rsi < 70:
            return {"action": "建議加碼 (Add)", "reason": f"RSI 向上攀升中 ({rsi:.1f})，多方上攻動能浮現"}
        elif prev_rsi >= 70 and rsi < 70:
            return {"action": "建議清倉 (Clear)", "reason": "RSI 漲多回調，跌破 70 超買區，有反轉風險", "price": last_row['Close']}
        elif rsi < 30:
            return {"action": "觀望 / 準備抄底 (Wait)", "reason": f"RSI 偏低 ({rsi:.1f})，已進入超賣區"}
        else:
            return {"action": "中性持有 (Hold)", "reason": f"RSI 在中性區間整理 ({rsi:.1f})"}
            
    elif indicator_name == "MACD":
        hist = last_row.get('MACD_Hist', 0)
        prev_hist = prev_row.get('MACD_Hist', 0)
        
        if pd.isna(hist): return {"action": "N/A", "reason": "資料不足"}
        
        if prev_hist <= 0 and hist > 0:
            return {"action": "強烈買進 (Buy)", "reason": "MACD 柱狀圖由負轉正，黃金交叉確認", "price": last_row['Close']}
        elif hist > 0 and hist > prev_hist:
            return {"action": "建議加碼 (Add)", "reason": "MACD 多頭紅柱持續伸長，上漲動能強勁"}
        elif hist > 0 and hist < prev_hist:
            return {"action": "建議減碼 (Reduce)", "reason": "MACD 多頭紅柱縮短，上漲動能開始衰退"}
        elif prev_hist >= 0 and hist < 0:
            return {"action": "建議清倉 (Clear)", "reason": "MACD 柱狀圖由正轉負，死亡交叉確認", "price": last_row['Close']}
        elif hist > 0:
            return {"action": "強勢持有 (Hold)", "reason": "MACD 位於零軸上方，趨勢偏多"}
        else:
            return {"action": "空手觀望 (Wait)", "reason": "MACD 處於空手綠柱區間，趨勢向下"}

    return {"action": "N/A", "reason": "未知指標"}
