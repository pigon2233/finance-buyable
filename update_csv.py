import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

df = pd.read_csv("股票代號表.csv", dtype=str)
# Filter rows where code doesn't already have .TW or .TWO
df['代號'] = df['代號'].str.strip()
df['名稱'] = df['名稱'].str.strip()

updated_codes = []

def check_suffix(row):
    code = row['代號']
    name = row['名稱']
    if code.endswith('.TW') or code.endswith('.TWO') or not code[0].isdigit():
        return (code, name)
        
    try:
        t_tw = yf.Ticker(code + '.TW')
        if 'symbol' in t_tw.fast_info:
            return (code + '.TW', name)
    except:
        pass
        
    try:
        t_two = yf.Ticker(code + '.TWO')
        if 'symbol' in t_two.fast_info:
            return (code + '.TWO', name)
    except:
        pass
    
    # default fallback
    return (code + '.TW', name)

print("Checking ~2000 stocks...")
with ThreadPoolExecutor(max_workers=50) as executor:
    results = list(executor.map(check_suffix, [row for _, row in df.iterrows()]))

df_new = pd.DataFrame(results, columns=['代號', '名稱'])
df_new.to_csv("股票代號表.csv", index=False, encoding='utf-8-sig')
print("Done saving updated CSV.")
