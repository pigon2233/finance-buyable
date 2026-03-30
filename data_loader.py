import yfinance as yf
import pandas as pd
import socket

# 強制 Python 使用 IPv4 (解決某些 Windows 電腦 IPv6 路由中斷導致 browser 可連但 Python timeout 的問題)
orig_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = getaddrinfo_ipv4
from curl_cffi import requests, CurlOpt

def get_yf_ticker(ticker: str):
    """
    使用自訂標頭與強制 IPv4 解析的 Session 來避免 yfinance 連線失敗
    """
    session = requests.Session(impersonate="chrome", verify=False, curl_options={CurlOpt.IPRESOLVE: 1})
    return yf.Ticker(ticker, session=session)

def fetch_stock_history(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    獲取股票歷史股價資料 (K棒資料)
    """
    try:
        stock = get_yf_ticker(ticker)
        df = stock.history(start=start_date, end=end_date)
        if df.empty:
            return None
        return df
    except Exception as e:
        print(f"Error fetching history data for {ticker}: {e}")
        return None

def fetch_stock_info(ticker: str) -> dict:
    """
    獲取股票基本面資訊
    """
    try:
        stock = get_yf_ticker(ticker)
        info = stock.info
        return {
            "name": info.get("shortName", "N/A"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "market_cap": info.get("marketCap", "N/A"),
            "pe_ratio": info.get("trailingPE", "N/A"),
            "forward_pe": info.get("forwardPE", "N/A"),
            "eps": info.get("trailingEps", "N/A"),
            "dividend_yield": info.get("dividendYield", info.get("trailingAnnualDividendYield", "N/A")),
            "52_week_high": info.get("fiftyTwoWeekHigh", "N/A"),
            "52_week_low": info.get("fiftyTwoWeekLow", "N/A"),
        }
    except Exception as e:
        print(f"Error fetching info for {ticker}: {e}")
        return {}

def fetch_financials(ticker: str) -> dict:
    """
    獲取財報摘要 (包含最新的損益表、資產負債表、現金流量表)
    """
    try:
        stock = get_yf_ticker(ticker)
        # 轉換為較好呈現的格式 (轉置，並保留最新幾季/年)
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        cashflow = stock.cashflow
        
        return {
            "financials": financials,
            "balance_sheet": balance_sheet,
            "cashflow": cashflow
        }
    except Exception as e:
        print(f"Error fetching financials for {ticker}: {e}")
        return {}
