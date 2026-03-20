import pandas as pd
import numpy as np

def calculate_dmpi(df: pd.DataFrame, window=5, vol_window=20, atr_window=14) -> pd.DataFrame:
    """
    計算動態市場壓力指數 (DMPI)
    需要欄位: Open, High, Low, Close, Volume
    """
    df = df.copy()
    
    # 確保有極小值避免除以零
    epsilon = 1e-8
    
    # 1. 淨壓力 (Net Pressure, NP)
    high_low_range = df['High'] - df['Low'] + epsilon
    buy_pressure = (df['Close'] - df['Low']) / high_low_range
    sell_pressure = (df['High'] - df['Close']) / high_low_range
    df['Net_Pressure'] = buy_pressure - sell_pressure # -1 to 1
    
    # 2. 成交量因子 (Volume Factor, VF)
    avg_volume = df['Volume'].rolling(window=vol_window).mean()
    df['Volume_Factor'] = df['Volume'] / (avg_volume + epsilon)
    
    # 3. 波動率懲罰因子 (VP) - 使用 ATR / Close
    # 計算 True Range (TR)
    df['Prev_Close'] = df['Close'].shift(1)
    df['TR'] = df[['High', 'Prev_Close']].max(axis=1) - df[['Low', 'Prev_Close']].min(axis=1)
    
    # 計算 ATR
    df['ATR'] = df['TR'].rolling(window=atr_window).mean()
    df['VP'] = df['ATR'] / (df['Close'] + epsilon)
    
    # 避免 VP 太小導致指標過度放大，設定 VP 的下限，例如 0.01 (1%)
    df['VP'] = df['VP'].clip(lower=0.01)
    
    # 4. 計算 Raw DMPI
    df['Raw_DMPI'] = (df['Net_Pressure'] * df['Volume_Factor']) / (df['VP'] * 100)
    
    # 5. 平滑化 DMPI
    df['DMPI'] = df['Raw_DMPI'].rolling(window=window).mean()
    
    return df

def generate_signals(df: pd.DataFrame, threshold=0.5) -> pd.DataFrame:
    """
    根據 DMPI 產生進出場訊號
    1: 買進 (DMPI 由下往上穿越 threshold)
    -1: 賣出 (DMPI 由上往下穿越 0 或停損)
    0: 觀望
    """
    df = df.copy()
    df['Signal'] = 0
    df['Position'] = 0
    
    if 'DMPI' not in df.columns:
        return df
        
    df['Prev_DMPI'] = df['DMPI'].shift(1)
    
    # 買進訊號
    buy_condition = (df['Prev_DMPI'] <= threshold) & (df['DMPI'] > threshold)
    
    # 賣出訊號
    sell_condition = (df['Prev_DMPI'] >= 0) & (df['DMPI'] < 0)
    
    df.loc[buy_condition, 'Signal'] = 1
    df.loc[sell_condition, 'Signal'] = -1
    
    # 持倉狀態
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
