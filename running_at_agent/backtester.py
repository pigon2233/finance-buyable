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

    def build_reason(row, action_type: str) -> str:
        """ 根據當前指標數值生成一行可讀的交易理由。 """
        is_buy = (action_type == 'Buy')
        if indicator_name == "自創 DMPI":
            v = float(row.get('DMPI', 0))
            label = "突破零軸，動能正向" if is_buy else "跌破零軸，動能轉負"
            return f"DMPI = {v:.2f} » {label}"
        elif indicator_name == "RSI":
            v = float(row.get('RSI', 0))
            label = "超跌區 (<30)，買進訊號" if is_buy else "超買區 (>70)，賣出訊號"
            return f"RSI = {v:.1f} » {label}"
        elif indicator_name == "MACD":
            v = float(row.get('MACD_Hist', 0))
            label = "柱狀由負轉正 (黃金交叉)" if is_buy else "柱狀由正轉負 (死亡交叉)"
            return f"MACD柱 = {v:.4f} » {label}"
        else:  # 綜合共振
            dmpi = float(row.get('DMPI', 0))
            rsi_v = float(row.get('RSI', 0))
            macd = float(row.get('MACD', 0))
            macd_h = float(row.get('MACD_Hist', 0))
            
            if macd > 0 and macd_h >= 0:
                regime = 'LARGE'
            elif macd < 0 and macd_h <= 0:
                regime = 'SMALL'
            else:
                regime = 'FLAT'

            if regime == 'FLAT':
                label = "超跌<30，回歸買進" if is_buy else "超買>70，回歸賣出"
                return f"[FLAT盤整] RSI={rsi_v:.1f} » {label}"
            else:
                tag = "LARGE多頭" if regime == 'LARGE' else "SMALL空頭"
                label = "入通道(動能健康)買進" if is_buy else "離開通道(過熱/破線)賣出"
                return f"[{tag}] DMPI={dmpi:.2f} » {label}"

    
    for date, row in df.iterrows():
        signal = row.get('Signal', 0)
        close_price = float(row['Close'])
        
        # 買進
        if signal == 1 and shares == 0:
            shares = capital / close_price
            capital = 0
            buy_price = close_price
            trades.append({'Date': date, 'Type': 'Buy', 'Price': close_price, 'Reason': build_reason(row, 'Buy')})
            
        # 賣出
        elif signal == -1 and shares > 0:
            capital = shares * close_price
            shares = 0
            profit_pct = (close_price - buy_price) / buy_price * 100
            trades.append({'Date': date, 'Type': 'Sell', 'Price': close_price, 'Profit_%': profit_pct, 'Reason': build_reason(row, 'Sell')})
            
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
        capital = shares * float(df.iloc[-1]['Close'])
        shares = 0
        profit_pct = (float(df.iloc[-1]['Close']) - buy_price) / buy_price * 100
        trades.append({'Date': df.index[-1], 'Type': 'Sell (Auto Close)', 'Price': float(df.iloc[-1]['Close']), 'Profit_%': profit_pct, 'Reason': '到期強制平倉'})
        
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

def get_latest_recommendation(df: pd.DataFrame) -> dict:
    """
    根據最新的盤勢給出三大指標統整進出場建議 (包含加碼、減碼、清倉等)。
    以字典型態回傳: {"DMPI": {...}, "RSI": {...}, "MACD": {...}}
    """
    if df.empty:
        return {"DMPI": {"action": "N/A", "reason": "No data"}, "RSI": {"action": "N/A", "reason": "No data"}, "MACD": {"action": "N/A", "reason": "No data"}}
        
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2] if len(df) > 1 else last_row
    
    recs = {}
    
    # --- DMPI 分析 ---
    dmpi = last_row.get('DMPI', 0)
    prev_dmpi = prev_row.get('DMPI', 0)
    if pd.isna(dmpi) or pd.isna(prev_dmpi):
        recs["DMPI"] = {"action": "N/A", "reason": "指標資料不足，建議更長回測週期"}
    elif prev_dmpi <= 0 and dmpi > 0:
        recs["DMPI"] = {"action": "強烈買進 (Buy)", "reason": "DMPI 突破零軸，買盤翻多強勢上攻"}
    elif dmpi > 0 and dmpi > prev_dmpi:
        recs["DMPI"] = {"action": "建議加碼 (Add)", "reason": f"DMPI 持續向上發散 ({dmpi:.2f})，多頭動能強"}
    elif dmpi > 0 and dmpi < prev_dmpi:
        recs["DMPI"] = {"action": "分批獲利 (Reduce)", "reason": f"DMPI 達高點後回落 ({dmpi:.2f})，動能減弱"}
    elif prev_dmpi >= 0 and dmpi < 0:
        recs["DMPI"] = {"action": "建議清倉 (Clear)", "reason": "DMPI 跌破零軸，轉為弱勢賣盤主導"}
    elif dmpi > 0:
        recs["DMPI"] = {"action": "續抱持有 (Hold)", "reason": f"DMPI 維持正值 ({dmpi:.2f})，趨勢偏多"}
    else:
        recs["DMPI"] = {"action": "空手觀望 (Wait)", "reason": f"DMPI 為負 ({dmpi:.2f})，趨勢偏空不宜摸底"}

    # --- RSI 分析 ---
    rsi = last_row.get('RSI', 0)
    prev_rsi = prev_row.get('RSI', 0)
    if pd.isna(rsi):
        recs["RSI"] = {"action": "N/A", "reason": "資料不足"}
    elif prev_rsi <= 30 and rsi > 30:
        recs["RSI"] = {"action": "強烈買進 (Buy)", "reason": "RSI 超跌反彈，突破 30 金叉抄底訊號"}
    elif rsi > 70 and rsi > prev_rsi:
        recs["RSI"] = {"action": "逢高減碼 (Reduce)", "reason": f"RSI 登頂過熱區 ({rsi:.1f})，隨時有獲利了結賣壓"}
    elif rsi > prev_rsi and 30 < rsi < 70:
        recs["RSI"] = {"action": "建議加碼 (Add)", "reason": f"RSI 穩定攀升中 ({rsi:.1f})，多方籌碼安定"}
    elif prev_rsi >= 70 and rsi < 70:
        recs["RSI"] = {"action": "急著逃命 (Clear)", "reason": "RSI 漲多回調跌破 70，強力反轉警報！"}
    elif rsi < 30:
        recs["RSI"] = {"action": "準備抄底 (Wait)", "reason": f"RSI 探底中 ({rsi:.1f})，已深入超賣區"}
    else:
        recs["RSI"] = {"action": "盤整中立 (Hold)", "reason": f"RSI 處於中性區間整理 ({rsi:.1f})"}
            
    # --- MACD 分析 ---
    hist = last_row.get('MACD_Hist', 0)
    prev_hist = prev_row.get('MACD_Hist', 0)
    if pd.isna(hist):
        recs["MACD"] = {"action": "N/A", "reason": "資料不足"}
    elif prev_hist <= 0 and hist > 0:
        recs["MACD"] = {"action": "波段買進 (Buy)", "reason": "MACD 柱狀由負轉正，黃金交叉確認"}
    elif hist > 0 and hist > prev_hist:
        recs["MACD"] = {"action": "強勢加碼 (Add)", "reason": "MACD 紅柱持續放長，推升力道強勁"}
    elif hist > 0 and hist < prev_hist:
        recs["MACD"] = {"action": "轉弱減碼 (Reduce)", "reason": "MACD 紅柱縮短，上漲推升力道漸衰"}
    elif prev_hist >= 0 and hist < 0:
        recs["MACD"] = {"action": "破線清倉 (Clear)", "reason": "MACD 柱狀翻綠，長線死亡交叉確認"}
    elif hist > 0:
        recs["MACD"] = {"action": "偏多持有 (Hold)", "reason": "MACD 位於零軸之上，結構偏多"}
    else:
        recs["MACD"] = {"action": "順勢空手 (Wait)", "reason": "MACD 處於綠柱空方區，隨波逐流"}

    # --- 綜合共振 分析 ---
    try:
        from strategy import generate_signals
        df_comp = generate_signals(df.copy(), indicator="綜合共振")
        comp_sig = df_comp['Signal'].iloc[-1]
        
        if comp_sig == 1:
            recs["綜合共振"] = {"action": "強勢共振買進 (Buy)", "reason": "綜合共振四大情境滿足，死抱突破趨勢發出買進訊號"}
        elif comp_sig == -1:
            recs["綜合共振"] = {"action": "動能衰退清倉 (Clear)", "reason": "綜合共振四大情境警示破底，發出清倉賣出訊號"}
        else:
            recs["綜合共振"] = {"action": "等待時機 (Wait/Hold)", "reason": "綜合系統未達關鍵轉折點，若持有中則續抱，若空手則觀望"}
    except Exception as e:
        recs["綜合共振"] = {"action": "N/A", "reason": f"綜合運算錯誤 {e}"}

    return recs
