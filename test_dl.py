from data_loader import get_yf_ticker
try:
    print("Testing NU ticker...")
    stock = get_yf_ticker("NU")
    df = stock.history(period="1mo")
    print("history: ", df.shape)
    info = stock.info
    print("info success!")
    fin = stock.financials
    print("financials success!")
except Exception as e:
    print(f"Error: {e}")
