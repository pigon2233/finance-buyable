import pandas as pd
import numpy as np

def calculate_dmpi(df: pd.DataFrame, window=5, vol_window=20, atr_window=14) -> pd.DataFrame:
    """
    計算動態市場壓力指數 (DMPI)
    修正公式權重，使其數值能有效地產生可用訊號。
    """
    df = df.copy()
    epsilon = 1e-8
    
    # 1. 淨壓力 (Net Pressure, NP)
    high_low_range = df['High'] - df['Low'] + epsilon
    buy_pressure = (df['Close'] - df['Low']) / high_low_range
    sell_pressure = (df['High'] - df['Close']) / high_low_range
    df['Net_Pressure'] = buy_pressure - sell_pressure # 介於 -1 到 1
    
    # 2. 成交量因子 (Volume Factor, VF)
    avg_volume = df['Volume'].rolling(window=vol_window).mean()
    df['Volume_Factor'] = df['Volume'] / (avg_volume + epsilon)
    
    # 3. 波動率懲罰因子 (VP) - 使用 ATR / Close
    df['Prev_Close'] = df['Close'].shift(1)
    df['TR'] = df[['High', 'Prev_Close']].max(axis=1) - df[['Low', 'Prev_Close']].min(axis=1)
    df['ATR'] = df['TR'].rolling(window=atr_window).mean()
    
    df['VP'] = df['ATR'] / (df['Close'] + epsilon)
    df['VP'] = df['VP'].clip(lower=0.01) # 波動率通常在 1% ~ 5% 之間
    
    # 4. 原始 DMPI (取消過度縮小的除以 100 動作)
    # 將其放大到合理的波動區間 (約 -50 到 50 之間)
    df['Raw_DMPI'] = (df['Net_Pressure'] * df['Volume_Factor']) / df['VP']
    
    # 5. 平滑化
    df['DMPI'] = df['Raw_DMPI'].rolling(window=window).mean()
    
    return df

def calculate_rsi(df: pd.DataFrame, window=14) -> pd.DataFrame:
    """計算 相對強弱指標 (RSI)"""
    df = df.copy()
    delta = df['Close'].diff()
    
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    
    rs = gain / (loss + 1e-8)
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def calculate_macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> pd.DataFrame:
    """計算 平滑異同移動平均線 (MACD)"""
    df = df.copy()
    # 使用指數移動平均
    df['EMA_Fast'] = df['Close'].ewm(span=fast, adjust=False).mean()
    df['EMA_Slow'] = df['Close'].ewm(span=slow, adjust=False).mean()
    
    df['MACD'] = df['EMA_Fast'] - df['EMA_Slow']
    df['MACD_Signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    return df

def generate_signals(df: pd.DataFrame, indicator: str = "自創 DMPI") -> pd.DataFrame:
    """
    根據選定的技術指標產生買賣訊號
    1: 買進, -1: 賣出, 0: 觀望
    """
    df = df.copy()
    df['Signal'] = 0
    df['Position'] = 0
    
    buy_condition = pd.Series(False, index=df.index)
    sell_condition = pd.Series(False, index=df.index)
    
    if indicator == "自創 DMPI":
        if 'DMPI' not in df.columns: return df
        df['Prev_DMPI'] = df['DMPI'].shift(1)
        # DMPI 修正後通常在 -50 到 50 震盪，零軸以上翻紅作為買點
        buy_condition = (df['Prev_DMPI'] <= 0) & (df['DMPI'] > 0)
        # 跌破零軸作為賣點
        sell_condition = (df['Prev_DMPI'] >= 0) & (df['DMPI'] < 0)

    elif indicator == "RSI":
        if 'RSI' not in df.columns: return df
        df['Prev_RSI'] = df['RSI'].shift(1)
        # 傳統 RSI 策略：自超賣區(30)反彈向上視為買進
        buy_condition = (df['Prev_RSI'] <= 30) & (df['RSI'] > 30)
        # 傳統 RSI 策略：自超買區(70)反轉向下視為賣出
        sell_condition = (df['Prev_RSI'] >= 70) & (df['RSI'] < 70)

    elif indicator == "MACD":
        if 'MACD_Hist' not in df.columns: return df
        df['Prev_Hist'] = df['MACD_Hist'].shift(1)
        # MACD 柱狀圖由負轉正 (黃金交叉) 視為買進
        buy_condition = (df['Prev_Hist'] <= 0) & (df['MACD_Hist'] > 0)
        # MACD 柱狀圖由正轉負 (死亡交叉) 視為賣出
        sell_condition = (df['Prev_Hist'] >= 0) & (df['MACD_Hist'] < 0)
        
    df.loc[buy_condition, 'Signal'] = 1
    df.loc[sell_condition, 'Signal'] = -1
    
    # 建立持倉狀態 (Position: 1為持有, 0為空手)
    current_position = 0
    positions = []
    for signal in df['Signal']:
        if signal == 1:
            current_position = 1
        elif signal == -1:
            current_position = 0
        positions.append(current_position)
        
    df['Position'] = positions
    return df
