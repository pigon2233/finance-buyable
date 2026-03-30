#!/usr/bin/env python3
"""
冰可樂龍蝦 - 台股儀表板 FastAPI Backend
提供股票分析、自選股群組管理 API 給 Next.js 前端使用
"""
import os
import sys
import json
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── 路徑設定 ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent  # finance-buyable/
sys.path.insert(0, str(BASE_DIR))

from strategy import calculate_dmpi, calculate_rsi, calculate_macd, generate_signals
from data_loader import get_yf_ticker

# ── 初始化 ────────────────────────────────────────────────────────────────
app = FastAPI(title="冰可樂加熱 Stock API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 股票名稱對照表 (啟動時載入，記憶體常駐)
_STOCK_NAMES: dict[str, str] = {}
_CSV_PATH = BASE_DIR / "股票代號表.csv"
if _CSV_PATH.exists():
    df_names = pd.read_csv(_CSV_PATH, dtype=str)
    for _, row in df_names.iterrows():
        code = str(row["代號"]).strip()
        name = str(row["名稱"]).strip()
        _STOCK_NAMES[code] = name

# 自選股群組檔案
WATCHLIST_FILE = BASE_DIR / "watchlist_groups.json"

def _load_watchlist() -> dict:
    if WATCHLIST_FILE.exists():
        return json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
    return {"我的最愛": [], "AI概念": [], "金融": []}

def _save_watchlist(data: dict):
    WATCHLIST_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# AI 引擎（非同步初始化，避免啟動阻塞）
_ai_engine = None
def _get_ai():
    global _ai_engine
    if _ai_engine is None:
        try:
            from ml_engine import MLExpertEngine
            _ai_engine = MLExpertEngine()
        except Exception:
            pass
    return _ai_engine

# ══════════════════════════════════════════════════════════════════════
# 工具
# ══════════════════════════════════════════════════════════════════════

def get_chinese_name(ticker: str) -> str:
    """取得股票中文名稱，找不到回傳空字串"""
    clean = ticker.upper()
    return _STOCK_NAMES.get(clean, _STOCK_NAMES.get(clean.replace(".TW", ""), ""))

def fetch_and_analyze(ticker: str, period: str = "1y") -> dict:
    """核心分析函式：抓資料 → 計算指標 → 生成訊號"""
    try:
        stock = get_yf_ticker(ticker)
        df = stock.history(period=period)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"無法取得 {ticker} 資料: {e}")

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"找不到 {ticker} 的歷史資料")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = calculate_dmpi(df)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    df_signals = generate_signals(df.copy(), indicator="綜合共振")

    last = df_signals.iloc[-1]
    prev = df_signals.iloc[-2] if len(df_signals) > 1 else last

    close = float(last["Close"])
    prev_close = float(prev["Close"])
    change_pct = (close - prev_close) / prev_close * 100

    dmpi = float(last["DMPI"])
    rsi = float(last["RSI"])
    macd = float(last["MACD"])
    macd_hist = float(last.get("MACD_Hist", 0))
    signal = int(last.get("Signal", 0))
    position = int(last.get("Position", 0))

    if macd > 0 and macd_hist >= 0:
        regime = "多頭"
    elif macd < 0 and macd_hist <= 0:
        regime = "空頭"
    else:
        regime = "盤整"

    # 訊號圖示
    if signal == 1:
        action = "🔥新買"
    elif signal == -1:
        action = "🧹賣出"
    elif position == 1:
        action = "☕持有"
    else:
        action = "☕觀望"

    # K 線資料（最近 200 根）
    kline = []
    df_k = df_signals.tail(200)
    for date, row in df_k.iterrows():
        kline.append({
            "time": date.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
            "signal": int(row.get("Signal", 0)),
            "dmpi": round(float(row["DMPI"]) if pd.notna(row["DMPI"]) else 0, 2),
            "rsi": round(float(row["RSI"]) if pd.notna(row["RSI"]) else 50, 2),
            "macd": round(float(row["MACD"]) if pd.notna(row["MACD"]) else 0, 4),
            "macd_hist": round(float(row.get("MACD_Hist", 0)) if pd.notna(row.get("MACD_Hist", 0)) else 0, 4),
        })
    # Score calculation
    vol20 = df_signals["Volume"].rolling(20).mean().iloc[-1]
    volr = float(last["Volume"]) / float(vol20) if vol20 > 0 else 1.0
    
    reg_sc = 100 if regime == "多頭" else (40 if regime == "盤整" else 0)
    if 50 <= rsi <= 70:
        rsi_sc = 100
    elif rsi < 50:
        rsi_sc = max(0, 50 + 50 * rsi / 50)
    else:
        rsi_sc = max(0, 100 - (rsi - 70) * 3)
    
    vol_sc = min(100.0, volr * 100)
    total_score = reg_sc * 0.50 + rsi_sc * 0.30 + vol_sc * 0.20

    return {
        "ticker": ticker,
        "name": get_chinese_name(ticker),
        "close": round(close, 2),
        "change_pct": round(change_pct, 2),
        "regime": regime,
        "action": action,
        "score": round(total_score, 1),
        "indicators": {
            "dmpi": round(dmpi, 2),
            "rsi": round(rsi, 2),
            "macd": round(macd, 4),
            "macd_hist": round(macd_hist, 4),
        },
        "signal": signal,
        "position": position,
        "kline": kline,
    }

# ══════════════════════════════════════════════════════════════════════
# API Endpoints
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/analyze/{ticker}")
async def analyze_ticker(ticker: str, period: str = "1y"):
    """分析單一股票（指標 + K 線 + 訊號）"""
    result = fetch_and_analyze(ticker.upper(), period)

    # 嘗試附加 AI 推論
    ai = _get_ai()
    if ai and ai.is_loaded:
        try:
            stock = get_yf_ticker(ticker)
            df_raw = stock.history(period="2y")
            ai_result = ai.predict_action(df_raw)
            result["ai"] = ai_result
        except Exception:
            result["ai"] = {"action": "AI 離線", "reason": ""}
    else:
        result["ai"] = {"action": "AI 引擎未啟動", "reason": ""}

    return result


@app.get("/api/search")
async def search_stocks(q: str = ""):
    """搜尋股票中文名稱 / 代號（用於 Autocomplete）"""
    q = q.strip().upper()
    if not q or len(q) < 1:
        return []
    results = []
    for code, name in _STOCK_NAMES.items():
        if q in code.upper() or q in name:
            results.append({"code": code, "name": name})
        if len(results) >= 20:
            break
    return results


@app.get("/api/watchlist")
async def get_watchlist():
    """取得所有自選股群組"""
    data = _load_watchlist()
    # 附上中文名稱
    enriched = {}
    for group, tickers in data.items():
        enriched[group] = [
            {"ticker": t, "name": get_chinese_name(t)} for t in tickers
        ]
    return enriched


class GroupBody(BaseModel):
    name: str

@app.post("/api/watchlist/group")
async def create_group(body: GroupBody):
    """新增自選股群組"""
    data = _load_watchlist()
    if body.name in data:
        raise HTTPException(status_code=409, detail="群組已存在")
    data[body.name] = []
    _save_watchlist(data)
    return {"ok": True}


@app.delete("/api/watchlist/group/{group_name}")
async def delete_group(group_name: str):
    """刪除自選股群組"""
    data = _load_watchlist()
    if group_name not in data:
        raise HTTPException(status_code=404, detail="群組不存在")
    del data[group_name]
    _save_watchlist(data)
    return {"ok": True}


@app.post("/api/watchlist/{group_name}/{ticker}")
async def add_to_watchlist(group_name: str, ticker: str):
    """新增股票到指定群組"""
    data = _load_watchlist()
    if group_name not in data:
        data[group_name] = []
    if ticker not in data[group_name]:
        data[group_name].append(ticker)
    _save_watchlist(data)
    return {"ok": True}


@app.delete("/api/watchlist/{group_name}/{ticker}")
async def remove_from_watchlist(group_name: str, ticker: str):
    """從指定群組移除股票"""
    data = _load_watchlist()
    if group_name in data and ticker in data[group_name]:
        data[group_name].remove(ticker)
    _save_watchlist(data)
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════
# Expansion Endpoints (回測、基本面、持股、掃描)
# ══════════════════════════════════════════════════════════════════════
from backtester import run_backtest
from data_loader import fetch_stock_info, fetch_financials

@app.get("/api/fundamentals/{ticker}")
async def get_fundamentals(ticker: str):
    try:
        info = fetch_stock_info(ticker)
        # We skip downloading raw financials matrices to keep JSON size small and fast
        # Just return the summary info
        return {"ok": True, "info": info}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/backtest/{ticker}")
async def get_backtest(ticker: str, period: str = "5y", capital: float = 100000):
    try:
        stock = get_yf_ticker(ticker.upper())
        df = stock.history(period=period)
        if df.empty:
            raise HTTPException(status_code=404, detail="No data")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = calculate_dmpi(df)
        df = calculate_rsi(df)
        df = calculate_macd(df)
        df = generate_signals(df, indicator="綜合共振")
        
        # 執行回測
        bt_res = run_backtest(df, initial_capital=capital, indicator_name="綜合共振")
        
        # Handle nan in trades/history to avoid JSON serialization error
        import math
        def clean(val):
            if isinstance(val, float) and math.isnan(val): return None
            return val
            
        trades = []
        for t in bt_res["trades"]:
            trades.append({k: clean(v) for k, v in t.items() if k != "Date"})
            trades[-1]["Date"] = t["Date"].strftime("%Y-%m-%d")
            
        return {
            "ok": True,
            "final_capital": clean(bt_res["final_capital"]),
            "total_return_pct": clean(bt_res["total_return_pct"]),
            "win_rate_pct": clean(bt_res["win_rate_pct"]),
            "max_drawdown_pct": clean(bt_res["max_drawdown_pct"]),
            "trades": trades
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


PORTFOLIO_FILE = BASE_DIR / "running_at_agent" / "portfolio.txt"

def _load_portfolio() -> list:
    if not PORTFOLIO_FILE.exists():
        return []
    res = []
    with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"): continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                res.append({"ticker": parts[0], "cost": float(parts[1]), "qty": float(parts[2])})
    return res

def _save_portfolio(data: list):
    PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        for p in data:
            f.write(f"{p['ticker']},{p['cost']},{p['qty']}\n")

@app.get("/api/portfolio")
async def get_portfolio():
    positions = _load_portfolio()
    # Grade them
    graded = []
    for p in positions:
        try:
            res = fetch_and_analyze(p["ticker"], "3mo")
            current_price = res["close"]
            pnl = (current_price - p["cost"]) * p["qty"]
            pnl_pct = (current_price - p["cost"]) / p["cost"] * 100
            graded.append({
                **p,
                "name": res["name"],
                "current_price": current_price,
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "action": res["action"],
                "dmpi": res["indicators"]["dmpi"],
                "rsi": res["indicators"]["rsi"]
            })
        except:
            graded.append({**p, "error": "Fetch failed"})
    return {"positions": graded}

class PortItem(BaseModel):
    ticker: str
    cost: float
    qty: float

@app.post("/api/portfolio")
async def add_portfolio(body: PortItem):
    data = _load_portfolio()
    # Update if exists
    for p in data:
        if p["ticker"].upper() == body.ticker.upper():
            p["cost"] = body.cost
            p["qty"] = body.qty
            _save_portfolio(data)
            return {"ok": True}
    data.append({"ticker": body.ticker.upper(), "cost": body.cost, "qty": body.qty})
    _save_portfolio(data)
    return {"ok": True}

@app.delete("/api/portfolio/{ticker}")
async def del_portfolio(ticker: str):
    data = _load_portfolio()
    data = [p for p in data if p["ticker"].upper() != ticker.upper()]
    _save_portfolio(data)
    return {"ok": True}

from concurrent.futures import ThreadPoolExecutor

@app.get("/api/scan")
async def run_scan():
    """背景執行 150 支台股掃描器"""
    sf = BASE_DIR / "running_at_agent" / "stocks.txt"
    if not sf.exists():
        return {"results": []}
    
    with open(sf, "r") as f:
        stocks = [L.strip() for L in f if L.strip() and not L.startswith("#")]
        
    def _scan_one(tk):
        try:
            res = fetch_and_analyze(tk, "6mo")
            return {
                "ticker": tk,
                "name": res["name"],
                "action": res["action"],
                "price": res["close"],
                "change_pct": res["change_pct"],
                "regime": res["regime"],
                "dmpi": res["indicators"]["dmpi"],
                "rsi": res["indicators"]["rsi"],
                "score": res["score"],
            }
        except:
            return None
            
    results = []
    # Use ThreadPool for fast fetching
    with ThreadPoolExecutor(max_workers=10) as executor:
        for r in executor.map(_scan_one, stocks):
            if r and r["action"] in ["🔥新買", "🧹賣出", "☕持有", "☕觀望"]:
                results.append(r)
                
    # Filter only actionable ones and sort by score desc
    actionables = [r for r in results if r["action"] in ["🔥新買", "🧹賣出", "☕持有"]]
    actionables.sort(key=lambda x: x["score"], reverse=True)
    return {"results": actionables}


@app.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


# ── 靜態檔案服務 (用於生產環境) ──
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# 檢查是否存在編譯後的前端資料夾 (frontend/out)
_frontend_out = BASE_DIR / "frontend" / "out"
if _frontend_out.exists():
    # 註冊靜態檔案
    app.mount("/_next", StaticFiles(directory=str(_frontend_out / "_next")), name="next-assets")
    
    @app.get("/{path:path}")
    async def serve_spa(path: str):
        # 優先檢查 API
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        
        # 檢查檔案是否存在
        file_path = _frontend_out / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
            
        # 否則回傳 index.html (SPA 路由)
        return FileResponse(_frontend_out / "index.html")

if __name__ == "__main__":
    import uvicorn
    # 生產環境建議關閉 reload
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
