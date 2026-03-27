#!/usr/bin/env python3
"""
美股每日掃描（使用 strategy.py 參數）
IONQ, CMPS, NU, SCHD + 可擴展其他美股
"""
import yfinance as yf
import pandas as pd
import sys

def calc_indicators(df):
    df = df.copy()
    e = 1e-8
    hl = df['High'] - df['Low'] + e
    df['NP'] = (df['Close']-df['Low'])/hl - (df['High']-df['Close'])/hl
    df['VF'] = df['Volume']/(df['Volume'].rolling(20).mean()+e)
    df['PC'] = df['Close'].shift(1)
    df['TR'] = df[['High','PC']].max(axis=1) - df[['Low','PC']].min(axis=1)
    df['ATR'] = df['TR'].rolling(14).mean()
    df['VP'] = (df['ATR']/(df['Close']+e)).clip(lower=0.01)
    df['DMPI'] = ((df['NP']*df['VF'])/df['VP']).rolling(2).mean()
    d = df['Close'].diff()
    g = d.where(d>0,0).rolling(14).mean()
    l = (-d.where(d<0,0)).rolling(14).mean()
    df['RSI'] = 100-(100/(1+g/(l+e)))
    df['EMAF'] = df['Close'].ewm(span=12,adjust=False).mean()
    df['EMAS'] = df['Close'].ewm(span=26,adjust=False).mean()
    df['MACD'] = df['EMAF']-df['EMAS']
    df['MACDS'] = df['MACD'].ewm(span=9,adjust=False).mean()
    df['MACDH'] = df['MACD']-df['MACDS']
    return df

# strategy.py 參數
LARGE_UPPER, LARGE_LOWER = 30, -20
SMALL_UPPER, SMALL_LOWER = 5, -35

def get_signal(df):
    if len(df) < 2:
        return 0
    last = df.iloc[-1]
    dmpi = last['DMPI'] if not pd.isna(last['DMPI']) else 0
    rsi = last['RSI'] if not pd.isna(last['RSI']) else 50
    macd = last['MACD'] if not pd.isna(last['MACD']) else 0
    macdh = last['MACDH'] if not pd.isna(last['MACDH']) else 0
    
    if macd > 0 and macdh >= 0:
        regime = '多頭'
        if dmpi >= LARGE_UPPER or dmpi <= LARGE_LOWER:
            return -1
        return 0
    elif macd < 0 and macdh <= 0:
        regime = '空頭'
        if dmpi >= SMALL_UPPER or dmpi <= SMALL_LOWER:
            return -1
        return 0
    else:
        regime = '盤整'
        if rsi > 80:
            return -1
        return 0

US_STOCKS = ['IONQ', 'CMPS', 'NU', 'SCHD', 'AAPL', 'AMZN', 'META', 'NFLX', 'GOOGL', 'MSFT', 'NVDA', 'TSLA', 'BIDU', 'SNAP']

stocks = sys.argv[1:] if len(sys.argv) > 1 else US_STOCKS

print(f'{"代碼":<8} {"DMPI":>6} {"RSI":>5} {"MACD":>7} {"趨勢":>4} {"結論"}')
print('=' * 50)

for stock in stocks:
    try:
        df = yf.Ticker(stock).history(period='6mo')
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if len(df) < 60:
            print(f'{stock:<8} 資料不足')
            continue
        df = calc_indicators(df)
        signal = get_signal(df)
        last = df.iloc[-1]
        dmpi = last['DMPI'] if not pd.isna(last['DMPI']) else 0
        rsi = last['RSI'] if not pd.isna(last['RSI']) else 0
        macd = last['MACD'] if not pd.isna(last['MACD']) else 0
        macdh = last['MACDH'] if not pd.isna(last['MACDH']) else 0
        macd_val = macd
        
        if macd > 0 and macdh >= 0:
            regime = '多頭'
        elif macd < 0 and macdh <= 0:
            regime = '空頭'
        else:
            regime = '盤整'
        
        result = '🔥買' if signal == 1 else ('🧹賣' if signal == -1 else '☕觀')
        print(f'{stock:<8} {dmpi:>6.1f} {rsi:>5.1f} {macd:>7.2f} {regime:>4} {result}')
    except Exception as e:
        print(f'{stock:<8} Error')
