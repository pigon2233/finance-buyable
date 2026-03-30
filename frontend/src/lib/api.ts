// src/lib/api.ts - API client for backend

const BASE = "http://localhost:8000";

export interface AnalysisResult {
  ticker: string;
  name: string;
  close: number;
  change_pct: number;
  regime: "多頭" | "空頭" | "盤整";
  action: string;
  indicators: { dmpi: number; rsi: number; macd: number; macd_hist: number };
  signal: number;
  position: number;
  kline: KlineBar[];
  ai?: { action: string; reason: string };
}

export interface KlineBar {
  time: string;
  open: number; high: number; low: number; close: number;
  volume: number; signal: number;
  dmpi: number; rsi: number; macd: number; macd_hist: number;
}

export interface WatchlistGroups {
  [group: string]: Array<{ ticker: string; name: string }>;
}

export interface SearchResult {
  code: string;
  name: string;
}

export async function analyzeStock(ticker: string, period = "1y"): Promise<AnalysisResult> {
  const res = await fetch(`${BASE}/api/analyze/${encodeURIComponent(ticker)}?period=${period}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "分析失敗");
  }
  return res.json();
}

export async function searchStocks(q: string): Promise<SearchResult[]> {
  if (!q.trim()) return [];
  const res = await fetch(`${BASE}/api/search?q=${encodeURIComponent(q)}`);
  return res.ok ? res.json() : [];
}

export async function getWatchlist(): Promise<WatchlistGroups> {
  const res = await fetch(`${BASE}/api/watchlist`);
  return res.ok ? res.json() : {};
}

export async function addToWatchlist(group: string, ticker: string) {
  await fetch(`${BASE}/api/watchlist/${encodeURIComponent(group)}/${encodeURIComponent(ticker)}`, { method: "POST" });
}

export async function removeFromWatchlist(group: string, ticker: string) {
  await fetch(`${BASE}/api/watchlist/${encodeURIComponent(group)}/${encodeURIComponent(ticker)}`, { method: "DELETE" });
}

export async function createGroup(name: string) {
  await fetch(`${BASE}/api/watchlist/group`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export async function deleteGroup(name: string) {
  await fetch(`${BASE}/api/watchlist/group/${encodeURIComponent(name)}`, { method: "DELETE" });
}

// ──────────────────────────────────────────────────────────────────
// Expansion Endpoints

export interface Fundamentals {
  name: string; sector: string; industry: string; market_cap: number;
  pe_ratio: number; forward_pe: number; eps: number; dividend_yield: number;
  "52_week_high": number; "52_week_low": number;
}

export interface Trade {
  Type: string; Price: number; "Profit_%": number; Reason: string; Date: string;
}

export interface BacktestResult {
  final_capital: number; total_return_pct: number;
  win_rate_pct: number; max_drawdown_pct: number;
  trades: Trade[];
}

export interface PortfolioItem {
  ticker: string; cost: number; qty: number;
  name?: string; current_price?: number; pnl?: number; pnl_pct?: number;
  action?: string; dmpi?: number; rsi?: number; error?: string;
}

export interface ScanResult {
  ticker: string; name: string; action: string; price: number;
  change_pct: number; regime: string; dmpi: number; rsi: number;
  score: number;
}

export async function getFundamentals(ticker: string) {
  const res = await fetch(`${BASE}/api/fundamentals/${encodeURIComponent(ticker)}`);
  if (!res.ok) throw new Error("基本面讀取失敗");
  return res.json().then(x => x.info as Fundamentals);
}

export async function getBacktest(ticker: string, period = "2y", capital = 100000) {
  const res = await fetch(`${BASE}/api/backtest/${encodeURIComponent(ticker)}?period=${period}&capital=${capital}`);
  if (!res.ok) throw new Error("回測失敗");
  return res.json() as Promise<BacktestResult>;
}

export async function getPortfolio() {
  const res = await fetch(`${BASE}/api/portfolio`);
  if (!res.ok) throw new Error("持股讀取失敗");
  return res.json().then(x => x.positions as PortfolioItem[]);
}

export async function addPortfolio(ticker: string, cost: number, qty: number) {
  await fetch(`${BASE}/api/portfolio`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker, cost, qty })
  });
}

export async function deletePortfolio(ticker: string) {
  await fetch(`${BASE}/api/portfolio/${encodeURIComponent(ticker)}`, { method: "DELETE" });
}

export async function runScan() {
  const res = await fetch(`${BASE}/api/scan`);
  if (!res.ok) throw new Error("掃描失敗");
  return res.json().then(x => x.results as ScanResult[]);
}
