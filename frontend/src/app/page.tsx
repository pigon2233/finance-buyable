"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Plus, Trash2, ChevronDown, ChevronRight, Star, AlertTriangle, X, Loader2, BarChart2, TrendingUp, Building2, Radar, Edit2 } from "lucide-react";
import {
  analyzeStock, searchStocks, getWatchlist, addToWatchlist,
  removeFromWatchlist, createGroup, deleteGroup,
  getFundamentals, getBacktest, getPortfolio, addPortfolio, deletePortfolio, runScan,
  type AnalysisResult, type WatchlistGroups, type SearchResult,
  type Fundamentals, type BacktestResult, type PortfolioItem, type ScanResult
} from "@/lib/api";
import dynamic from "next/dynamic";

const StockChart = dynamic(() => import("@/components/StockChart"), { ssr: false });

type TabMode = "CHART" | "BACKTEST" | "FUNDAMENTALS" | "SCANNER";

// ══════════════════════════════════════════════════════════════════════════
// Helpers
// ══════════════════════════════════════════════════════════════════════════
function actionColor(action: string) {
  if (action.includes("買") || action.includes("Long")) return "text-[#ff4d6a]";
  if (action.includes("賣") || action.includes("Clear")) return "text-[#00e5a0]";
  if (action.includes("持有") || action.includes("Hold")) return "text-[#f0a030]";
  return "text-gray-400";
}

function regimeBadge(regime: string) {
  const map: Record<string, string> = {
    "多頭": "bg-[#ff4d6a]/20 text-[#ff4d6a] border-[#ff4d6a]/30",
    "空頭": "bg-[#00e5a0]/20 text-[#00e5a0] border-[#00e5a0]/30",
    "盤整": "bg-[#f0a030]/20 text-[#f0a030] border-[#f0a030]/30",
  };
  return map[regime] ?? "bg-gray-500/20 text-gray-400";
}

// ══════════════════════════════════════════════════════════════════════════
// Sidebar
// ══════════════════════════════════════════════════════════════════════════
function Sidebar({
  watchlist, onSelect, activeTicker, onRefreshWatchlist
}: {
  watchlist: WatchlistGroups; onSelect: (t: string) => void;
  activeTicker?: string; onRefreshWatchlist: () => void;
}) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [newGroupName, setNewGroupName] = useState("");
  const [adding, setAdding] = useState(false);

  const toggleGroup = (g: string) => setCollapsed(p => ({ ...p, [g]: !p[g] }));

  return (
    <aside className="w-72 flex-shrink-0 h-full flex flex-col border-r shadow-2xl z-40" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
      {/* Header */}
      <div className="px-5 pt-8 pb-5 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-widest text-[var(--accent-gold)] uppercase">冰可樂加熱</h1>
          <p className="text-sm text-[var(--text-muted)] mt-0.5 font-medium">綜合共振 · 交易儀表板</p>
        </div>
        <div className="w-10 h-10 rounded-xl overflow-hidden bg-white/10 flex items-center justify-center border border-white/20 shadow-lg"><img src="/cola_pig.png" alt="logo" className="w-full h-full object-cover" /></div>
      </div>
      <div className="h-0.5 mx-5 mb-5 opacity-20" style={{ background: "linear-gradient(to right, var(--accent-gold), transparent)" }} />
      {/* Groups */}
      <div className="flex-1 overflow-y-auto px-3 space-y-2">
        {Object.entries(watchlist).map(([group, stocks]) => (
          <div key={group} className="mb-2">
            <div className="flex items-center gap-2 px-3 py-3 rounded-xl cursor-pointer group hover:bg-[var(--bg-elevated)] transition-all border border-transparent hover:border-[var(--border)]" onClick={() => toggleGroup(group)}>
              <button className="text-[var(--text-muted)] group-hover:text-[var(--text-primary)] transition-colors">{collapsed[group] ? <ChevronRight size={20} /> : <ChevronDown size={20} />}</button>
              <span className="text-lg font-black text-[var(--text-secondary)] flex-1 uppercase tracking-tight">{group}</span>
              <span className="text-xs font-black bg-[var(--bg-base)] px-2 py-1 rounded-full text-[var(--text-muted)] border border-[var(--border)]">{stocks.length}</span>
              <button className="opacity-0 group-hover:opacity-100 text-[var(--text-muted)] hover:text-red-500 transition-all p-1" onClick={e => { e.stopPropagation(); deleteGroup(group).then(onRefreshWatchlist); }}><Trash2 size={16} /></button>
            </div>
            <AnimatePresence>
              {!collapsed[group] && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden mt-1 space-y-1">
                  {stocks.map(({ ticker, name }) => (
                    <div key={ticker} onClick={() => onSelect(ticker)} className={`flex items-center gap-4 px-5 py-3.5 rounded-xl cursor-pointer group mx-1 transition-all border-2 ${activeTicker === ticker ? "bg-[#3b8bff]/20 border-[#3b8bff] shadow-lg shadow-blue-500/10" : "bg-transparent border-transparent hover:bg-[var(--bg-hover)]"}`}>
                      <div className="flex-1 min-w-0">
                        <div className="text-lg font-black text-[var(--text-primary)] truncate leading-none mb-1">{ticker}</div>
                        <div className="text-sm font-bold text-[var(--text-muted)] truncate opacity-80">{name || "—"}</div>
                      </div>
                      <button className="opacity-0 group-hover:opacity-100 text-[var(--text-muted)] hover:text-red-400 transition-all p-1" onClick={e => { e.stopPropagation(); removeFromWatchlist(group, ticker).then(onRefreshWatchlist); }}><X size={16} /></button>
                    </div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}
      </div>
      {/* Add Group */}
      <div className="p-4 border-t-2" style={{ borderColor: "var(--border)" }}>
        {adding ? (
          <div className="flex gap-2">
            <input autoFocus value={newGroupName} onChange={e => setNewGroupName(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && newGroupName.trim()) { createGroup(newGroupName.trim()).then(onRefreshWatchlist); setNewGroupName(""); setAdding(false); } }} placeholder="輸入新分組名稱..." className="flex-1 text-base font-bold bg-[var(--bg-elevated)] border-2 border-[var(--border-bright)] rounded-xl px-4 py-2.5 outline-none text-[var(--text-primary)] focus:border-[var(--accent-blue)] transition-all" />
            <button onClick={() => { if (newGroupName.trim()) { createGroup(newGroupName.trim()).then(onRefreshWatchlist); setNewGroupName(""); setAdding(false); } }} className="text-[#3b8bff] hover:bg-blue-500/10 p-2 rounded-xl"><Plus size={24} /></button>
          </div>
        ) : (
          <button onClick={() => setAdding(true)} className="w-full flex items-center justify-center gap-2 text-base font-black text-[var(--text-muted)] hover:text-[var(--accent-blue)] py-3 px-4 rounded-xl hover:bg-[var(--bg-hover)] transition-all border-2 border-dashed border-[var(--border)]"><Plus size={18} /> 建立新自選分組</button>
        )}
      </div>
    </aside>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// Subviews
// ══════════════════════════════════════════════════════════════════════════
function BacktestView({ ticker, period }: { ticker: string, period: string }) {
  const [res, setRes] = useState<BacktestResult | null>(null);
  const [load, setLoad] = useState(true);
  useEffect(() => {
    setLoad(true);
    getBacktest(ticker, period).then(setRes).finally(() => setLoad(false));
  }, [ticker, period]);

  if (load) return <div className="p-10 flex justify-center"><Loader2 className="animate-spin text-blue-500" size={32} /></div>;
  if (!res) return <div className="p-10 text-red-400">無法回測 {ticker}</div>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <div className="glass p-4 rounded-xl border border-[var(--border)]">
          <div className="text-xs text-[var(--text-muted)] uppercase">總報酬率 (Total Return)</div>
          <div className={`text-2xl font-bold mt-1 ${res.total_return_pct >= 0 ? 'text-[#ff4d6a]' : 'text-[#00e5a0]'}`}>{res.total_return_pct.toFixed(2)}%</div>
          <div className="text-sm text-[var(--text-muted)] mt-1">最終資產: ${res.final_capital.toLocaleString()}</div>
        </div>
        <div className="glass p-4 rounded-xl border border-[var(--border)]">
          <div className="text-xs text-[var(--text-muted)] uppercase">勝率 (Win Rate)</div>
          <div className="text-2xl font-bold text-[#f5c842] mt-1">{res.win_rate_pct.toFixed(1)}%</div>
        </div>
        <div className="glass p-4 rounded-xl border border-[var(--border)]">
          <div className="text-xs text-[var(--text-muted)] uppercase">最大回撤 (Max Drawdown)</div>
          <div className="text-2xl font-bold text-[#00e5a0] mt-1">{res.max_drawdown_pct.toFixed(2)}%</div>
        </div>
      </div>
      <div className="glass rounded-xl border border-[var(--border)] overflow-hidden">
        <div className="px-5 py-3 border-b border-[var(--border)] bg-[#1e1e28] text-sm font-bold flex gap-2"><BarChart2 size={16}/> 歷史交易明細</div>
        <div className="p-0 max-h-[400px] overflow-y-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-[#151520] sticky top-0 border-b border-[var(--border)]">
              <tr>
                <th className="p-3 text-[var(--text-muted)] font-medium">日期</th>
                <th className="p-3 text-[var(--text-muted)] font-medium">動作</th>
                <th className="p-3 text-[var(--text-muted)] font-medium text-right">價格</th>
                <th className="p-3 text-[var(--text-muted)] font-medium text-right">績效</th>
                <th className="p-3 text-[var(--text-muted)] font-medium">理由</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {res.trades.map((t, i) => (
                <tr key={i} className="hover:bg-[var(--bg-hover)]">
                  <td className="p-3 font-mono text-[var(--text-secondary)]">{t.Date}</td>
                  <td className={`p-3 font-bold ${t.Type.includes("Buy")?'text-[#ff4d6a]':'text-[#00e5a0]'}`}>{t.Type.replace("Buy","買進").replace("Sell","賣出")}</td>
                  <td className="p-3 text-right font-mono">{t.Price.toFixed(2)}</td>
                  <td className={`p-3 text-right font-bold ${!t["Profit_%"] ? 'text-gray-500' : t["Profit_%"] > 0 ? 'text-[#ff4d6a]' : 'text-[#00e5a0]'}`}>
                    {t["Profit_%"] ? `${t["Profit_%"] > 0 ? '+' : ''}${t["Profit_%"].toFixed(2)}%` : '-'}
                  </td>
                  <td className="p-3 text-xs text-[var(--text-secondary)] truncate max-w-[200px]">{t.Reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function FundamentalsView({ ticker }: { ticker: string }) {
  const [f, setF] = useState<Fundamentals | null>(null);
  const [L, setL] = useState(true);
  useEffect(() => { setL(true); getFundamentals(ticker).then(setF).catch(()=>{}).finally(()=>setL(false)); }, [ticker]);
  
  if (L) return <div className="p-10 flex justify-center"><Loader2 className="animate-spin text-blue-500" size={32} /></div>;
  if (!f) return <div className="p-10 text-red-400">無基本面資料</div>;

  return (
    <div className="glass p-6 rounded-xl border border-[var(--border)] space-y-6">
      <div className="flex justify-between items-end border-b border-[var(--border)] pb-4">
        <div>
          <h2 className="text-2xl font-bold">{f.name}</h2>
          <div className="text-sm text-[var(--text-muted)] mt-1">{f.sector} · {f.industry}</div>
        </div>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
        <div><div className="text-xs text-[var(--text-muted)]">本益比 (Trailing P/E)</div><div className="text-xl font-bold mt-1">{f.pe_ratio ? f.pe_ratio.toFixed(2) : 'N/A'}</div></div>
        <div><div className="text-xs text-[var(--text-muted)]">預估本益比 (Forward P/E)</div><div className="text-xl font-bold mt-1">{f.forward_pe ? f.forward_pe.toFixed(2) : 'N/A'}</div></div>
        <div><div className="text-xs text-[var(--text-muted)]">EPS (每股盈餘)</div><div className="text-xl font-bold mt-1">{f.eps ? f.eps.toFixed(2) : 'N/A'}</div></div>
        <div><div className="text-xs text-[var(--text-muted)]">殖利率 (Yield)</div><div className="text-xl font-bold mt-1 text-[#f5c842]">{f.dividend_yield ? (f.dividend_yield*100).toFixed(2)+'%' : 'N/A'}</div></div>
        <div><div className="text-xs text-[var(--text-muted)]">市值 (Market Cap)</div><div className="text-xl font-bold mt-1">{(f.market_cap / 1e8).toFixed(2)} 億</div></div>
        <div><div className="text-xs text-[var(--text-muted)]">52週最高</div><div className="text-xl font-bold mt-1 text-[#ff4d6a]">{f["52_week_high"]}</div></div>
        <div><div className="text-xs text-[var(--text-muted)]">52週最低</div><div className="text-xl font-bold mt-1 text-[#00e5a0]">{f["52_week_low"]}</div></div>
      </div>
    </div>
  );
}

function ScannerView({ onSelect }: { onSelect: (t: string) => void }) {
  const [port, setPort] = useState<PortfolioItem[]>([]);
  const [scan, setScan] = useState<ScanResult[]>([]);
  const [L, setL] = useState({ p: true, s: false });
  const [edit, setEdit] = useState<Partial<PortfolioItem> | null>(null);

  const fetchPort = () => { setL(p => ({...p, p:true})); getPortfolio().then(setPort).finally(()=>setL(p => ({...p, p:false}))); };
  useEffect(() => { fetchPort(); }, []);

  const handleScan = () => { setL(p => ({...p, s:true})); runScan().then(setScan).finally(()=>setL(p => ({...p, s:false}))); };

  return (
    <div className="space-y-8 p-1">
      {/* Portfolio Card */}
      <div className="glass rounded-3xl border-2 border-[var(--border)] overflow-hidden shadow-2xl relative" style={{ background: "var(--bg-surface)" }}>
        <div className="px-8 py-6 border-b-2 border-[var(--border)] flex justify-between items-center bg-[#1e1dd8]/5">
          <h3 className="text-xl font-black flex items-center gap-3 tracking-tighter uppercase italic"><Building2 size={24} className="text-[var(--accent-blue)]"/> 我的核心持股部位監測</h3>
          <button onClick={() => setEdit({ticker:"", cost:0, qty:1})} className="text-base bg-[var(--accent-blue)] px-6 py-3 rounded-2xl text-white font-black hover:opacity-80 transition flex items-center gap-2 shadow-lg shadow-blue-500/20 active:scale-95"><Plus size={20}/> 登記新部位</button>
        </div>
        <div className="overflow-auto max-h-[500px]">
          {L.p ? <div className="p-16 flex justify-center"><Loader2 className="animate-spin text-[var(--accent-blue)]" size={48} /></div> : (
            <table className="w-full text-left text-base whitespace-nowrap">
              <thead className="bg-[#151520] border-b-2 border-[var(--border)] sticky top-0 z-10">
                <tr>
                  <th className="p-5 text-[var(--text-muted)] font-black uppercase tracking-widest text-xs">投資標的 (Symbol)</th>
                  <th className="p-5 text-[var(--text-muted)] text-right font-black uppercase tracking-widest text-xs">持倉成本 / 數量</th>
                  <th className="p-5 text-[var(--text-muted)] text-right font-black uppercase tracking-widest text-xs">當前市價</th>
                  <th className="p-5 text-[var(--text-muted)] text-right font-black uppercase tracking-widest text-xs">未實現損益 (PnL)</th>
                  <th className="p-5 text-[var(--text-muted)] text-right font-black uppercase tracking-widest text-xs">即時動能強弱</th>
                  <th className="p-5 text-[var(--text-muted)] font-black uppercase tracking-widest text-xs">AI 佈局建議</th>
                  <th className="p-5"></th>
                </tr>
              </thead>
              <tbody className="divide-y-2 divide-[var(--border)]">
                {port.map(p => (
                  <tr key={p.ticker} className="hover:bg-[var(--bg-hover)] transition-all duration-300 group">
                    <td className="p-5"><div className="font-black text-xl text-[var(--text-primary)] tracking-tight">{p.ticker}</div><div className="text-sm font-black text-gray-500 uppercase tracking-widest">{p.name}</div></td>
                    <td className="p-5 text-right font-bold text-lg tabular-nums"><span className="opacity-50 text-sm">$</span>{p.cost} <span className="text-[var(--text-muted)] ml-2 font-black text-sm">x {p.qty}</span></td>
                    <td className="p-5 text-right font-black text-xl tabular-nums text-[var(--text-secondary)]">{p.current_price?.toFixed(2)}</td>
                    <td className={`p-5 text-right font-black text-2xl tabular-nums ${p.pnl! >= 0 ? 'text-[#ff4d6a]' : 'text-[#00e5a0]'}`}>
                      {p.pnl! > 0 ? '+' : ''}{p.pnl?.toFixed(0)} <span className="text-sm font-black ml-1 opacity-60">({p.pnl_pct?.toFixed(2)}%)</span>
                    </td>
                    <td className="p-5 text-right">
                      <div className="flex flex-col items-end">
                        <span className={`font-black tracking-widest tabular-nums text-sm ${p.dmpi! > 0 ? "text-[#ff4d6a]":"text-[#00e5a0]"}`}>DMPI: {p.dmpi?.toFixed(1)}</span>
                        <div className="w-24 h-1.5 bg-[var(--border)] rounded-full mt-1.5 overflow-hidden">
                            <div className="h-full bg-purple-500 transition-all duration-1000" style={{ width: `${Math.min(100, Math.max(0, p.rsi!))}%` }} />
                        </div>
                        <span className="text-xs font-black text-purple-400 tabular-nums mt-1 uppercase">RSI(14): {p.rsi?.toFixed(1)}</span>
                      </div>
                    </td>
                    <td className={`p-5 font-black text-lg italic ${actionColor(p.action||"")}`}>{p.action}</td>
                    <td className="p-3 text-right">
                      <button onClick={() => { onSelect(p.ticker); }} className="text-[#3b8bff] hover:text-[#5fa1ff] p-1.5 font-bold transition-all hover:scale-110"><Radar size={16}/></button>
                      <button onClick={() => setEdit(p)} className="text-[var(--text-muted)] hover:text-white p-1.5 transition-all"><Edit2 size={16}/></button>
                      <button onClick={() => deletePortfolio(p.ticker).then(fetchPort)} className="text-[var(--text-muted)] hover:text-red-400 p-1.5 transition-all"><Trash2 size={16}/></button>
                    </td>
                  </tr>
                ))}
                {port.length === 0 && <tr><td colSpan={7} className="p-20 text-center text-xl font-black text-[var(--text-muted)] opacity-30 italic">尚未監測任何部位 · 渴望您的第一筆交易...</td></tr>}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {edit && (
        <div className="fixed inset-0 bg-black/90 backdrop-blur-xl z-[100] flex items-center justify-center p-6">
          <motion.div initial={{ opacity: 0, scale: 0.8, y: 50, rotateX: 20 }} animate={{ opacity: 1, scale: 1, y: 0, rotateX: 0 }} className="glass p-10 rounded-[2.5rem] w-full max-w-lg space-y-8 border-4 border-[var(--border-bright)] shadow-[0_0_100px_rgba(59,139,255,0.3)] relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-2 bg-gradient-to-right from-blue-500 to-purple-500" />
            <h3 className="text-3xl font-black tracking-tighter flex items-center gap-4 italic uppercase"><Plus className="text-[var(--accent-blue)]" size={32} /> 登記核心持倉部位</h3>
            <div className="space-y-6">
              <div>
                <label className="text-sm font-black text-[var(--text-muted)] uppercase tracking-[0.2em] ml-1">股票交易代碼</label>
                <input value={edit.ticker} onChange={e=>setEdit({...edit, ticker: e.target.value})} placeholder="例如: 2330.TW, AAPL..." className="w-full mt-3 bg-[var(--bg-elevated)] border-2 border-[var(--border)] rounded-2xl px-6 py-4 outline-none font-black text-2xl tracking-tight focus:border-[var(--accent-blue)] focus:ring-4 focus:ring-blue-500/10 transition-all placeholder:text-[var(--text-muted)] placeholder:font-normal" />
              </div>
              <div className="grid grid-cols-2 gap-6">
                <div>
                    <label className="text-sm font-black text-[var(--text-muted)] uppercase tracking-[0.2em] ml-1">每股平均成本</label>
                    <input type="number" value={edit.cost} onChange={e=>setEdit({...edit, cost: parseFloat(e.target.value)})} className="w-full mt-3 bg-[var(--bg-elevated)] border-2 border-[var(--border)] rounded-2xl px-6 py-4 outline-none font-black text-2xl tabular-nums focus:border-[var(--accent-blue)] transition-all" />
                </div>
                <div>
                    <label className="text-sm font-black text-[var(--text-muted)] uppercase tracking-[0.2em] ml-1">持有總股數</label>
                    <input type="number" value={edit.qty} onChange={e=>setEdit({...edit, qty: parseFloat(e.target.value)})} className="w-full mt-3 bg-[var(--bg-elevated)] border-2 border-[var(--border)] rounded-2xl px-6 py-4 outline-none font-black text-2xl tabular-nums focus:border-[var(--accent-blue)] transition-all" />
                </div>
              </div>
            </div>
            <div className="flex gap-4 pt-4">
              <button onClick={() => setEdit(null)} className="flex-1 py-5 rounded-2xl text-lg font-black text-[var(--text-muted)] hover:bg-[var(--bg-hover)] transition-all border-2 border-transparent">放棄更動</button>
              <button onClick={() => { if(edit.ticker) { addPortfolio(edit.ticker, edit.cost||0, edit.qty||1).then(()=>{ setEdit(null); fetchPort(); }) } }} className="flex-1 py-5 rounded-2xl text-lg font-black bg-[var(--accent-blue)] text-white hover:brightness-110 shadow-2xl shadow-blue-500/30 transition-all active:scale-95 uppercase tracking-widest">鎖定並記錄</button>
            </div>
          </motion.div>
        </div>
      )}

      {/* Scanner Card */}
      <div className="glass rounded-3xl border-2 border-[var(--border)] overflow-hidden flex flex-col flex-1 min-h-[500px] shadow-2xl" style={{ background: "var(--bg-surface)" }}>
        <div className="px-8 py-6 border-b-2 border-[var(--border)] flex justify-between items-center bg-[#1e1dd8]/5">
          <div className="flex items-center gap-4">
            <h3 className="text-xl font-black flex items-center gap-3 tracking-tighter uppercase italic"><Radar size={24} className="text-[#a855f7]"/> 全方位叢集雷達掃描器</h3>
            <span className="hidden lg:inline-flex items-center gap-2 bg-[#ff4d6a]/10 text-[#ff4d6a] px-3 py-1 rounded-full text-xs font-black uppercase tracking-widest border border-[#ff4d6a]/20"><span className="w-2 h-2 bg-[#ff4d6a] rounded-full animate-ping" /> Live Scan Active</span>
          </div>
          <div className="flex items-center gap-6">
            <div className="text-right hidden xl:block">
                <div className="text-xs font-black text-[var(--text-muted)] uppercase tracking-widest leading-none mb-1">正在並行處理</div>
                <div className="text-base font-black text-[var(--accent-gold)]">150 支核心追蹤股 (TW High Gain)</div>
            </div>
            <button onClick={handleScan} disabled={L.s} className="text-base bg-[#5b21b6] px-8 py-3 rounded-2xl text-white font-black hover:bg-[#6d28d9] transition flex items-center gap-3 whitespace-nowrap shadow-2xl shadow-purple-500/30 active:scale-95 border-b-4 border-[#3b0764]">
              {L.s ? <Loader2 className="animate-spin" size={20}/> : <Radar size={20}/>} {L.s ? "大數據解析中..." : "立刻啟動深度全掃描"}
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-auto bg-[#050508]/40">
          {!L.s && scan.length > 0 ? (
            <table className="w-full text-left text-base whitespace-nowrap">
              <thead className="bg-[#151520] sticky top-0 border-b-2 border-[var(--border)] z-10 shadow-xl backdrop-blur-md">
                <tr>
                  <th className="p-5 text-[var(--text-muted)] font-black uppercase tracking-widest text-xs">個股標的資訊</th>
                  <th className="p-5 text-[var(--text-muted)] text-right font-black uppercase tracking-widest text-xs">成交價格</th>
                  <th className="p-5 text-[var(--text-muted)] text-right font-black uppercase tracking-widest text-xs">單日波幅</th>
                  <th className="p-5 text-[var(--text-muted)] font-black uppercase tracking-widest text-xs">市場週期</th>
                  <th className="p-5 text-[var(--text-muted)] text-center font-black uppercase tracking-widest text-xs">綜合評分 (Score)</th>
                  <th className="p-5 text-[var(--text-muted)] text-right font-black uppercase tracking-widest text-xs">DMPI 強度</th>
                  <th className="p-5 text-[var(--text-muted)] text-right font-black uppercase tracking-widest text-xs">RSI 指數</th>
                  <th className="p-5 text-[var(--text-muted)] font-black uppercase tracking-widest text-xs">戰略訊號</th>
                  <th className="p-5"></th>
                </tr>
              </thead>
              <tbody className="divide-y-2 divide-[var(--border)]">
                {scan.map((s, idx) => (
                  <tr key={s.ticker} className={`transition-all duration-300 group hover:bg-[var(--accent-blue)]/5 ${idx < 5 ? 'bg-[var(--accent-gold)]/5' : ''}`}>
                    <td onClick={() => onSelect(s.ticker)} className="p-5 cursor-pointer group-hover:pl-7 transition-all"><div className="font-black text-xl flex items-center gap-2">{idx < 3 && <Star size={16} className="text-[var(--accent-gold)]" fill="currentColor"/>} {s.ticker}</div><div className="text-sm font-black text-gray-500 uppercase tracking-widest leading-none mt-1">{s.name}</div></td>
                    <td className="p-5 text-right font-black text-xl tabular-nums tracking-tighter">{s.price.toFixed(2)}</td>
                    <td className={`p-5 text-right font-black text-xl tabular-nums tracking-tighter ${s.change_pct >= 0 ? 'text-[#ff4d6a]' : 'text-[#00e5a0]'}`}>{s.change_pct > 0 ? '+' : ''}{s.change_pct.toFixed(2)}%</td>
                    <td className="p-5"><span className={`px-4 py-1.5 rounded-xl text-xs font-black border-2 shadow-2xl transition-all group-hover:border-white/20 ${regimeBadge(s.regime)}`}>{s.regime}</span></td>
                    <td className="p-5 text-center"><div className="text-3xl font-black text-[var(--accent-gold)] tabular-nums italic tracking-tighter drop-shadow-[0_0_10px_rgba(245,200,66,0.3)]">{s.score}</div></td>
                    <td className={`p-5 text-right font-black text-lg tabular-nums ${s.dmpi > 0 ? "text-[#ff4d6a]" : "text-[#00e5a0]"}`}>{s.dmpi.toFixed(2)}</td>
                    <td className="p-5 text-right font-black text-lg tabular-nums text-purple-400">{s.rsi.toFixed(1)}</td>
                    <td className={`p-5 font-black text-2xl italic tracking-tighter ${actionColor(s.action)}`}>{s.action}</td>
                    <td className="p-5 text-right">
                      <button onClick={() => onSelect(s.ticker)} className="bg-white/5 text-white p-3 rounded-2xl transition-all hover:bg-[var(--accent-blue)] hover:shadow-xl hover:scale-110 active:scale-95 border border-white/10" title="進入同步戰鬥室分析"><Radar size={22}/></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : !L.s && (
            <div className="h-full flex flex-col items-center justify-center p-32 text-center space-y-8 group transition-all">
              <div className="relative">
                <Radar size={120} className="text-[var(--text-muted)] opacity-20 animate-spin-slow group-hover:opacity-40 group-hover:text-[var(--accent-blue)] transition-all duration-1000" style={{ animationDuration: '10s' }} />
                <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-4 h-4 bg-[var(--accent-blue)] rounded-full animate-ping" />
                </div>
              </div>
              <div className="space-y-3">
                <div className="text-4xl font-black text-[var(--text-muted)] uppercase tracking-tighter italic opacity-30">系統處於低耗能待命模式</div>
                <p className="text-xl font-bold text-[var(--text-muted)] opacity-20 uppercase tracking-[0.3em]">點擊上方按鈕開始 150 支個股偵測分析</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// Main App
// ══════════════════════════════════════════════════════════════════════════
export default function Home() {
  const [ticker, setTicker] = useState("");
  const [period, setPeriod] = useState("1y");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AnalysisResult | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistGroups>({});
  const [searchSuggestions, setSearchSuggestions] = useState<SearchResult[]>([]);
  const [showMenu, setShowMenu] = useState(false);
  const [tabMode, setTabMode] = useState<TabMode>("CHART");

  const sidebarSelect = (t: string) => {
    setTicker(t);
    handleSearch(t);
    setTabMode("CHART");
  };

  const refreshWatchlist = useCallback(() => { getWatchlist().then(setWatchlist); }, []);
  useEffect(() => { refreshWatchlist(); }, [refreshWatchlist]);

  const handleSearch = useCallback(async (t = ticker) => {
    if (!t.trim()) return;
    setLoading(true); setError(null); setSearchSuggestions([]);
    try {
      const result = await analyzeStock(t.trim().toUpperCase(), period);
      setData(result); setTicker(result.ticker);
      if (tabMode === "SCANNER") setTabMode("CHART"); // Switch to chart if searching specific ticker
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "分析失敗");
    } finally { setLoading(false); }
  }, [ticker, period, tabMode]);

  const handleInput = async (val: string) => {
    setTicker(val);
    if (val.length >= 2) setSearchSuggestions(await searchStocks(val));
    else setSearchSuggestions([]);
  };

  return (
    <div className="flex h-screen overflow-hidden text-sm" style={{ background: "var(--bg-base)" }}>
      <Sidebar watchlist={watchlist} onSelect={t => { setTicker(t); handleSearch(t); }} activeTicker={data?.ticker} onRefreshWatchlist={refreshWatchlist} />
      
      <div className="flex-1 flex flex-col overflow-hidden relative">
        {/* Top Header */}
        <header className="flex flex-col gap-4 px-6 pt-6 pb-6 glass border-b shadow-md z-30" style={{ borderColor: "var(--border)" }}>
          <div className="flex items-center gap-4">
            <div className="relative flex-1 max-w-xl">
              <AnimatePresence mode="wait">
                {ticker ? (
                  <motion.button 
                    key="clear" 
                    initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.8 }}
                    onClick={() => { setTicker(""); setSearchSuggestions([]); }}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--accent-blue)] hover:text-white transition-colors z-10 p-1"
                  >
                    <X size={20} />
                  </motion.button>
                ) : (
                  <motion.div key="search" initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.8 }} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]">
                    <Search size={22} />
                  </motion.div>
                )}
              </AnimatePresence>
              <input value={ticker} onChange={e => handleInput(e.target.value)} onKeyDown={e => e.key === "Enter" && handleSearch()} placeholder="搜尋股號或中文 (例如: 2330, 台積電)..." className="w-full text-lg font-bold bg-[var(--bg-elevated)] border-2 border-[var(--border)] rounded-xl pl-4 pr-11 py-3 outline-none text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:ring-4 focus:ring-[var(--accent-blue)]/10 transition-all placeholder:font-normal placeholder:text-[var(--text-muted)]" />
              <AnimatePresence>
                {searchSuggestions.length > 0 && (
                  <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} className="absolute top-full left-0 right-0 mt-2 glass rounded-xl shadow-2xl border-2 overflow-hidden z-[100]" style={{ borderColor: "var(--border-bright)" }}>
                    {searchSuggestions.map(s => (
                      <button key={s.code} className="w-full text-left px-5 py-4 hover:bg-[var(--bg-hover)] text-base transition-colors flex gap-4 border-b border-[var(--border)] last:border-0" onClick={() => { setTicker(s.code); setSearchSuggestions([]); handleSearch(s.code); }}>
                        <span className="text-[var(--accent-blue)] font-mono font-black w-24 text-lg">{s.code}</span>
                        <span className="text-[var(--text-primary)] font-bold">{s.name}</span>
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <button onClick={() => handleSearch()} disabled={loading} className="flex items-center gap-2 px-8 py-3.5 rounded-xl text-base font-black text-white transition-all disabled:opacity-50 shadow-lg shadow-blue-500/20 active:scale-95" style={{ background: "linear-gradient(135deg, #3b8bff, #a855f7)" }}>
              {loading ? <Loader2 size={20} className="animate-spin" /> : <Radar size={20} />} 深度分析
            </button>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex gap-1.5 bg-[var(--bg-elevated)] rounded-xl p-1.5 border-2 shadow-inner" style={{ borderColor: "var(--border)" }}>
              {["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"].map(p => (
                <button key={p} onClick={() => { setPeriod(p); if (data) handleSearch(); }} className={`text-sm px-4 py-2 rounded-lg font-black transition-all ${period === p ? "bg-[var(--accent-blue)] text-white shadow-lg" : "text-[var(--text-muted)] hover:text-white"}`}>{p.toUpperCase()}</button>
              ))}
            </div>

            <div className="flex items-center gap-3">
              {data && (
                <div className="relative">
                  <button onClick={() => setShowMenu(v => !v)} className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-black border-2 transition-all text-[#f5c842] border-[#f5c842]/50 hover:bg-[#f5c842]/10 active:scale-95"><Star size={18} /> 加入自選</button>
                  <AnimatePresence>
                    {showMenu && (
                      <motion.div initial={{ opacity: 0, scale: 0.95, y: -8 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, y: -8 }} className="absolute right-0 top-full mt-2 z-50 glass rounded-xl py-2 min-w-56 border-2 border-[var(--border-bright)] shadow-2xl">
                        {Object.keys(watchlist).map(g => (
                          <button key={g} className="w-full text-left px-6 py-3 text-base hover:bg-[var(--bg-hover)] transition-colors font-bold border-b border-[var(--border)] last:border-0" onClick={() => { addToWatchlist(g, data.ticker).then(refreshWatchlist); setShowMenu(false); }}>{g}</button>
                        ))}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}

              {data && (
                <div className="flex items-center gap-5 glass px-5 py-2.5 rounded-xl border-2 border-[var(--border-bright)]">
                  <div className="text-right">
                    <div className="text-sm font-black text-[var(--accent-gold)] tracking-tight uppercase">{data.ticker} <span className="text-[var(--text-muted)] font-bold ml-1">({data.name})</span></div>
                    <div className={`text-xl font-black tabular-nums ${data.change_pct >= 0 ? "text-[#ff4d6a]" : "text-[#00e5a0]"}`}>{data.close.toLocaleString()} <span className="text-base ml-1">{data.change_pct >= 0 ? "▲" : "▼"}{Math.abs(data.change_pct).toFixed(2)}%</span></div>
                  </div>
                  <div className="h-10 w-px bg-[var(--border)]" />
                  <span className={`text-base font-black px-4 py-1.5 rounded-lg border-2 shadow-sm ${regimeBadge(data.regime)}`}>{data.regime}</span>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Tab Navigation */}
        <div className="flex px-6 pt-3 gap-6 border-b border-[var(--border)] bg-[#111118]">
          {[ { id: "CHART", label: "📊 互動 K 線與策略" }, { id: "BACKTEST", label: "📈 策略回測報告" }, { id: "FUNDAMENTALS", label: "🏢 財報與基本面" }, { id: "SCANNER", label: "🔍 台股雷達掃描與持倉" } ].map(t => (
            <button key={t.id} onClick={() => setTabMode(t.id as TabMode)} className={`pb-3 text-sm font-bold transition-colors border-b-2 ${tabMode === t.id ? "border-[var(--accent-blue)] text-[var(--text-primary)]" : "border-transparent text-[var(--text-muted)] hover:text-gray-300"}`}>{t.label}</button>
          ))}
        </div>

        {error && <div className="flex items-center gap-2 px-6 py-3 bg-red-500/10 border-b border-red-500/20 text-red-400 text-sm font-medium"><AlertTriangle size={16} /> {error}</div>}

        {/* Dynamic Content Area (FLEX to fill remaining height) */}
        <div className="flex-1 overflow-auto p-6 bg-[#0a0a0f] flex flex-col">
          {tabMode === "SCANNER" ? ( <ScannerView /> ) : (
            !data ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center gap-6">
                <div className="w-32 h-32 rounded-3xl overflow-hidden border-4 border-white/20 shadow-2xl"><img src="/cola_pig.png" className="w-full h-full object-cover" /></div>
                <h2 className="text-3xl font-extrabold tracking-widest text-[#f0f0f5]">冰可樂加熱</h2>
                <p className="text-[var(--text-muted)] text-base max-w-sm leading-relaxed">輸入股票代號（例如：<span className="text-[var(--accent-blue)] font-mono">2330.TW</span>），立即進行高階動能通道分析與回測</p>
              </div>
            ) : (
              tabMode === "CHART" ? (
                <div className="flex flex-col h-full gap-5">
                  <div className="grid grid-cols-4 gap-4 flex-shrink-0">
                    {[
                      { t: "👑 綜合共振", a: data.action, d: `DMPI ${data.indicators.dmpi.toFixed(1)}`, c: "#f5c842", v: data.indicators.dmpi },
                      { t: "📊 RSI (14)", a: data.indicators.rsi > 70 ? "⚠️ 超買" : data.indicators.rsi < 30 ? "✅ 超跌" : "中性", d: `相對強弱`, c: "#a855f7", v: data.indicators.rsi },
                      { t: "📈 MACD", a: data.indicators.macd_hist > 0 ? "偏多" : "偏空", d: `MACD ${data.indicators.macd.toFixed(3)}`, c: "#f0a030", v: data.indicators.macd_hist },
                      { t: "🧠 AI 模型", a: data.ai?.action||"離線", d: data.ai?.reason||"-", c: "#3b8bff" }
                    ].map((c, i) => (
                      <div key={i} className="glass p-5 rounded-xl border-2" style={{ borderColor: `${c.c}44`, background: `${c.c}0a` }}>
                        <div className="text-sm font-black uppercase tracking-widest mb-2" style={{ color: c.c }}>{c.t}</div>
                        <div className={`text-xl font-black ${actionColor(c.a)}`}>{c.a}</div>
                        {c.v !== undefined && <div className="text-3xl font-black mt-2 tabular-nums" style={{ color: c.c }}>{typeof c.v === 'number' ? c.v.toFixed(2) : c.v}</div>}
                        <div className="text-xs text-[var(--text-muted)] font-bold mt-2 uppercase tracking-tight">{c.d}</div>
                      </div>
                    ))}
                  </div>
                  {/* flex-1 min-h-[400px] Fixes the invisible bottom issue! */}
                  <div className="glass rounded-xl flex-1 min-h-[500px] border-2 border-[var(--border)] overflow-hidden flex flex-col shadow-2xl relative" style={{ background: "var(--bg-surface)" }}>
                    <div className="px-6 py-4 border-b-2 text-base font-black text-[var(--text-primary)] bg-[#1e1dd8]/5 flex items-center justify-between" style={{ borderColor: "var(--border)" }}>
                      <div className="flex items-center gap-2">📊 互動 K 線圖與動能通道分析</div>
                      <div className="text-xs text-[var(--text-muted)] font-bold">同步週期: {period.toUpperCase()}</div>
                    </div>
                    <div className="flex-1 min-h-0 relative">
                      <StockChart data={data.kline} />
                    </div>
                  </div>
                </div>
              ) : tabMode === "BACKTEST" ? (
                <BacktestView ticker={data.ticker} period={period} />
              ) : tabMode === "FUNDAMENTALS" ? (
                <FundamentalsView ticker={data.ticker} />
              ) : null
            )
          )}
        </div>
      </div>
    </div>
  );
}
