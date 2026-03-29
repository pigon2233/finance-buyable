import customtkinter as ctk
import threading
import queue
import os
from datetime import datetime
import pandas as pd

from data_loader import fetch_stock_info, fetch_financials
from backtester import run_backtest, get_latest_recommendation
from chart import plot_stock_chart

# ── 台股掃描模組路徑 ────────────────────────────────────────────────────────
_SCAN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'running_at_agent')
_STOCKS_FILE = os.path.join(_SCAN_DIR, 'stocks.txt')
_PORTFOLIO_FILE = os.path.join(_SCAN_DIR, 'portfolio.txt')

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class HelpWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("多指標綜合儀表板說明")
        self.geometry("600x550")
        self.attributes("-topmost", True)
        self.configure(fg_color="#121212")
        
        title_lbl = ctk.CTkLabel(self, text="【 儀表板三大核心指標 】 說明", font=("Microsoft JhengHei", 20, "bold"), text_color="#00bfff")
        title_lbl.pack(pady=20)
        
        textbox = ctk.CTkTextbox(self, font=("Microsoft JhengHei", 14), wrap="word", fg_color="#1e1e1e", corner_radius=10)
        textbox.pack(fill="both", expand=True, padx=25, pady=(0, 25))
        
        desc = (
            "本系統整合了四套強大的動能與趨勢指標，全方位解析盤勢：\n\n"
            "一、綜合共振 (Tri-Core Resonance) 👑\n"
            "完美融合四大情境的通道動態策略：\n"
            "• MACD 大(多頭)：DMPI 保持在 -15 ~ +27 之間持續做多 (過熱停利/破線停損)\n"
            "• MACD 小(空頭)：DMPI 保持在 -40 ~ +5 之間搶反彈多 (過熱停利/破線停損)\n"
            "• MACD 持平(盤整)：切換為 RSI 測定進出 (超跌<30買 / 超買>70賣)\n\n"
            "二、自創 DMPI (動態市場壓力指數) 🚀\n"
            "結合價格壓力、成交流量與 ATR 波動。\n"
            "• 買進：突破零軸 / 賣出：跌破零軸\n\n"
            "三、RSI (相對強弱指標) 📊\n"
            "衡量近期價位強弱。\n"
            "• 買進：向上穿越 30 / 賣出：向下穿越 70\n\n"
            "四、MACD (平滑異同移動平均線) 📈\n"
            "捕捉中長線趨勢與波段。\n"
            "• 買進：柱狀圖出水面由負轉正 (黃金交叉)\n"
            "• 賣出：柱狀圖下沉由正轉負 (死亡交叉)\n\n"
            "勝率與穩定度完美融合，是最高階的實戰戰法！"
        )
        textbox.insert("0.0", desc)
        textbox.configure(state="disabled")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("進階股票分析與多指標回測系統")
        self.geometry("1400x900")
        self.configure(fg_color="#121212")
        
        # 實例化 AI 推論引擎
        from ml_engine import MLExpertEngine
        self.ai_engine = MLExpertEngine()
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  
        self.grid_rowconfigure(1, weight=1)  
        self.grid_rowconfigure(2, weight=0)  
        
        # --- Top Search Frame (Card Layout) ---
        self.top_frame = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=15, border_width=1, border_color="#333333")
        self.top_frame.grid(row=0, column=0, padx=25, pady=25, sticky="ew")
        
        self.ticker_label = ctk.CTkLabel(self.top_frame, text="股票代號:", font=("Microsoft JhengHei", 15, "bold"))
        self.ticker_label.pack(side="left", padx=(25, 10), pady=20)
        
        self.ticker_entry = ctk.CTkEntry(self.top_frame, placeholder_text="例如: 2330.TW 或 AAPL", width=180, font=("Microsoft JhengHei", 15), height=38)
        self.ticker_entry.pack(side="left", padx=10)
        
        self.period_label = ctk.CTkLabel(self.top_frame, text="回測期間:", font=("Microsoft JhengHei", 15, "bold"))
        self.period_label.pack(side="left", padx=10)
        
        self.period_combo = ctk.CTkComboBox(self.top_frame, values=["1mo", "3mo", "6mo", "1y", "2y", "5y"], width=100, font=("Microsoft JhengHei", 15), height=38)
        self.period_combo.set("1y")
        self.period_combo.pack(side="left", padx=10)
        
        self.strategy_label = ctk.CTkLabel(self.top_frame, text="主圖與回測基準:", font=("Microsoft JhengHei", 15, "bold"), text_color="#00bfff")
        self.strategy_label.pack(side="left", padx=10)
        
        self.strategy_seg = ctk.CTkSegmentedButton(self.top_frame, values=["自創 DMPI", "RSI", "MACD", "綜合共振"], font=("Microsoft JhengHei", 14), selected_color="#0052cc", selected_hover_color="#0066ff")
        self.strategy_seg.set("綜合共振")
        self.strategy_seg.pack(side="left", padx=5)
        
        self.help_btn = ctk.CTkButton(self.top_frame, text="指標介紹 ❓", width=120, height=38, font=("Microsoft JhengHei", 15, "bold"), command=self.show_help, fg_color="#333333", hover_color="#555555", corner_radius=8)
        self.help_btn.pack(side="left", padx=(10, 20))
        
        self.search_btn = ctk.CTkButton(self.top_frame, text="開始分析", font=("Microsoft JhengHei", 15, "bold"), command=self.on_search_clicked, height=45, corner_radius=10)
        self.search_btn.pack(side="left", padx=20)
        
        self.price_label = ctk.CTkLabel(self.top_frame, text="等待資料...", font=("Consolas", 15, "bold"), text_color="gray")
        self.price_label.pack(side="right", padx=25)

        self.status_label = ctk.CTkLabel(self.top_frame, text="", text_color="gray", font=("Microsoft JhengHei", 14))
        self.status_label.pack(side="left", fill="x", expand=True, padx=10)
        
        # --- Suggestion Dashboard (Grid Layout) ---
        self.sugg_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.sugg_frame.grid(row=2, column=0, padx=25, pady=(0, 25), sticky="ew")
        self.sugg_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        # AI 模型大腦 Card (Span 4 columns to be wider and shorter)
        self.card_ai = ctk.CTkFrame(self.sugg_frame, fg_color="#111111", corner_radius=12, border_width=2, border_color="#ffcc00")
        self.card_ai.grid(row=0, column=0, columnspan=4, padx=5, pady=(2, 5), sticky="nsew")
        self.lbl_ai_title = ctk.CTkLabel(self.card_ai, text="🧠 深度強化學習大腦 (DRL-LSTM) 預測結果", font=("Microsoft JhengHei", 14, "bold"), text_color="#ffcc00")
        self.lbl_ai_title.pack(pady=(5, 1))
        self.lbl_ai_act = ctk.CTkLabel(self.card_ai, text="等待分析或模型未載入", font=("Microsoft JhengHei", 18, "bold"))
        self.lbl_ai_act.pack(pady=1)
        self.lbl_ai_desc = ctk.CTkLabel(self.card_ai, text=self.ai_engine.error_msg if not self.ai_engine.is_loaded else "即時處理歷史數據推論中...", font=("Microsoft JhengHei", 12), text_color="gray", wraplength=800)
        self.lbl_ai_desc.pack(pady=(1, 5), padx=20)
        
        # DMPI Card
        self.card_dmpi = ctk.CTkFrame(self.sugg_frame, fg_color="#1a1a1a", corner_radius=10, border_width=1, border_color="#333333")
        self.card_dmpi.grid(row=1, column=0, padx=5, pady=2, sticky="nsew")
        self.lbl_dmpi_title = ctk.CTkLabel(self.card_dmpi, text="自創 DMPI 動能", font=("Microsoft JhengHei", 13, "bold"), text_color="#00bfff")
        self.lbl_dmpi_title.pack(pady=(5, 1))
        self.lbl_dmpi_act = ctk.CTkLabel(self.card_dmpi, text="等待分析", font=("Microsoft JhengHei", 16, "bold"))
        self.lbl_dmpi_act.pack(pady=1)
        self.lbl_dmpi_desc = ctk.CTkLabel(self.card_dmpi, text="請輸入股票代號", font=("Microsoft JhengHei", 11), text_color="gray", wraplength=200)
        self.lbl_dmpi_desc.pack(pady=(1, 5), padx=5)
        
        # RSI Card
        self.card_rsi = ctk.CTkFrame(self.sugg_frame, fg_color="#1a1a1a", corner_radius=10, border_width=1, border_color="#333333")
        self.card_rsi.grid(row=1, column=1, padx=5, pady=2, sticky="nsew")
        self.lbl_rsi_title = ctk.CTkLabel(self.card_rsi, text="RSI 相對強弱", font=("Microsoft JhengHei", 13, "bold"), text_color="#c266ff")
        self.lbl_rsi_title.pack(pady=(5, 1))
        self.lbl_rsi_act = ctk.CTkLabel(self.card_rsi, text="等待分析", font=("Microsoft JhengHei", 16, "bold"))
        self.lbl_rsi_act.pack(pady=1)
        self.lbl_rsi_desc = ctk.CTkLabel(self.card_rsi, text="請輸入股票代號", font=("Microsoft JhengHei", 11), text_color="gray", wraplength=200)
        self.lbl_rsi_desc.pack(pady=(1, 5), padx=5)
        
        # MACD Card
        self.card_macd = ctk.CTkFrame(self.sugg_frame, fg_color="#1a1a1a", corner_radius=10, border_width=1, border_color="#333333")
        self.card_macd.grid(row=1, column=2, padx=5, pady=2, sticky="nsew")
        self.lbl_macd_title = ctk.CTkLabel(self.card_macd, text="MACD 趨勢", font=("Microsoft JhengHei", 13, "bold"), text_color="#ff9900")
        self.lbl_macd_title.pack(pady=(5, 1))
        self.lbl_macd_act = ctk.CTkLabel(self.card_macd, text="等待分析", font=("Microsoft JhengHei", 16, "bold"))
        self.lbl_macd_act.pack(pady=1)
        self.lbl_macd_desc = ctk.CTkLabel(self.card_macd, text="請輸入股票代號", font=("Microsoft JhengHei", 11), text_color="gray", wraplength=200)
        self.lbl_macd_desc.pack(pady=(1, 5), padx=5)
        
        # 綜合共振 Card
        self.card_comp = ctk.CTkFrame(self.sugg_frame, fg_color="#1a1a1a", corner_radius=10, border_width=1, border_color="#333333")
        self.card_comp.grid(row=1, column=3, padx=5, pady=2, sticky="nsew")
        self.lbl_comp_title = ctk.CTkLabel(self.card_comp, text="👑 綜合共振", font=("Microsoft JhengHei", 13, "bold"), text_color="#ffff00")
        self.lbl_comp_title.pack(pady=(5, 1))
        self.lbl_comp_act = ctk.CTkLabel(self.card_comp, text="等待分析", font=("Microsoft JhengHei", 16, "bold"))
        self.lbl_comp_act.pack(pady=1)
        self.lbl_comp_desc = ctk.CTkLabel(self.card_comp, text="請輸入股票代號", font=("Microsoft JhengHei", 11), text_color="gray", wraplength=200)
        self.lbl_comp_desc.pack(pady=(1, 5), padx=5)
        
        # --- Main Tabview ---
        self.tabview = ctk.CTkTabview(self, fg_color="#1e1e1e", segmented_button_selected_color="#0052cc", segmented_button_selected_hover_color="#0066ff", text_color="white", corner_radius=15)
        self.tabview.grid(row=1, column=0, padx=25, pady=(0, 25), sticky="nsew")
        
        self.tab_chart = self.tabview.add("📊 互動 K 線圖與指標")
        self.tab_backtest = self.tabview.add("📈 策略回測報告")
        self.tab_fundamentals = self.tabview.add("🏢 基本面與財報")
        self.tab_scanner = self.tabview.add("🔍 台股精銳掃描")
        
        self.setup_chart_tab()
        self.setup_backtest_tab()
        self.setup_fundamentals_tab()
        self.setup_scanner_tab()
        
        self.bind('<Return>', lambda event: self.on_search_clicked())

    def show_help(self):
        HelpWindow(self)

    def setup_chart_tab(self):
        self.tab_chart.grid_columnconfigure(0, weight=1)
        self.tab_chart.grid_rowconfigure(0, weight=1)
        self.chart_container = ctk.CTkFrame(self.tab_chart, fg_color="transparent")
        self.chart_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
    def setup_fundamentals_tab(self):
        self.tab_fundamentals.grid_columnconfigure(0, weight=1)
        self.tab_fundamentals.grid_rowconfigure(0, weight=1)
        self.fund_textbox = ctk.CTkTextbox(self.tab_fundamentals, font=("Consolas", 16), fg_color="#121212", corner_radius=10)
        self.fund_textbox.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
    def setup_backtest_tab(self):
        self.tab_backtest.grid_columnconfigure(0, weight=1)
        self.tab_backtest.grid_rowconfigure(0, weight=1)
        self.backtest_textbox = ctk.CTkTextbox(self.tab_backtest, font=("Consolas", 16), fg_color="#121212", corner_radius=10)
        self.backtest_textbox.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def setup_scanner_tab(self):
        """台股精銳掃描分頁"""
        tab = self.tab_scanner
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_columnconfigure(2, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # ── 頂部控制列 ────────────────────────────────────────────
        ctrl = ctk.CTkFrame(tab, fg_color="#1e1e1e", corner_radius=12, border_width=1, border_color="#333333")
        ctrl.grid(row=0, column=0, columnspan=3, padx=10, pady=(10, 5), sticky="ew")

        ctk.CTkLabel(ctrl, text="🔍 台股精銳掃描（綜合共振策略）",
                     font=("Microsoft JhengHei", 16, "bold"), text_color="#00bfff").pack(side="left", padx=20, pady=10)

        self.scan_status_lbl = ctk.CTkLabel(ctrl, text="點擊「開始掃描」啟動三階段自動掃描",
                                             font=("Microsoft JhengHei", 13), text_color="gray")
        self.scan_status_lbl.pack(side="left", padx=10)

        self.scan_progress = ctk.CTkProgressBar(ctrl, width=180, mode="indeterminate")
        self.scan_progress.pack(side="left", padx=10)
        self.scan_progress.stop()

        self.scan_btn = ctk.CTkButton(
            ctrl, text="▶ 開始掃描", width=130, height=38,
            font=("Microsoft JhengHei", 14, "bold"),
            fg_color="#0052cc", hover_color="#0066ff", corner_radius=8,
            command=self.on_scan_clicked
        )
        self.scan_btn.pack(side="right", padx=20, pady=10)

        # ── 三欄輸出區 ────────────────────────────────────────────
        # 欄1：掃描訊號
        col1 = ctk.CTkFrame(tab, fg_color="#161616", corner_radius=10, border_width=1, border_color="#333")
        col1.grid(row=1, column=0, padx=(10, 4), pady=(0, 10), sticky="nsew")
        col1.grid_rowconfigure(1, weight=1)
        col1.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(col1, text="📡 第一階段：掃描訊號",
                     font=("Microsoft JhengHei", 13, "bold"), text_color="#00bfff").grid(row=0, column=0, pady=(8, 2))
        self.scan_signal_box = ctk.CTkTextbox(col1, font=("Consolas", 12), fg_color="#0d0d0d", corner_radius=8)
        self.scan_signal_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        # 欄2：評分排名
        col2 = ctk.CTkFrame(tab, fg_color="#161616", corner_radius=10, border_width=1, border_color="#333")
        col2.grid(row=1, column=1, padx=4, pady=(0, 10), sticky="nsew")
        col2.grid_rowconfigure(1, weight=1)
        col2.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(col2, text="🏆 第二階段：評分排名",
                     font=("Microsoft JhengHei", 13, "bold"), text_color="#ffcc00").grid(row=0, column=0, pady=(8, 2))
        self.scan_rank_box = ctk.CTkTextbox(col2, font=("Consolas", 12), fg_color="#0d0d0d", corner_radius=8)
        self.scan_rank_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        # 欄3：持股檢查
        col3 = ctk.CTkFrame(tab, fg_color="#161616", corner_radius=10, border_width=1, border_color="#333")
        col3.grid(row=1, column=2, padx=(4, 10), pady=(0, 10), sticky="nsew")
        col3.grid_rowconfigure(1, weight=1)
        col3.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(col3, text="💼 第三階段：持股檢查",
                     font=("Microsoft JhengHei", 13, "bold"), text_color="#ff9900").grid(row=0, column=0, pady=(8, 2))
        self.scan_portfolio_box = ctk.CTkTextbox(col3, font=("Consolas", 12), fg_color="#0d0d0d", corner_radius=8)
        self.scan_portfolio_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

    # ─────────────────────────────────────────────────────────────────────────
    # 台股掃描：事件驅動
    # ─────────────────────────────────────────────────────────────────────────

    def on_scan_clicked(self):
        """按下開始掃描"""
        self.scan_btn.configure(state="disabled", text="掃描中...")
        self.scan_progress.start()
        self.scan_status_lbl.configure(text="載入股票清單中...", text_color="yellow")

        for box in (self.scan_signal_box, self.scan_rank_box, self.scan_portfolio_box):
            box.configure(state="normal")
            box.delete("0.0", "end")

        self._scan_queue = queue.Queue()
        threading.Thread(target=self._run_scan_thread, daemon=True).start()
        self.after(100, self._poll_scan_queue)

    def _scan_append(self, box_name: str, text: str):
        """把訊息放入 queue，供主執行緒更新 UI"""
        self._scan_queue.put((box_name, text))

    def _poll_scan_queue(self):
        """主執行緒輪詢 queue 並更新 UI"""
        try:
            while True:
                item = self._scan_queue.get_nowait()
                if item == '__DONE__':
                    self.scan_btn.configure(state="normal", text="▶ 開始掃描")
                    self.scan_progress.stop()
                    return
                box_name, text = item
                box = getattr(self, box_name)
                box.configure(state="normal")
                box.insert("end", text)
                box.see("end")
        except queue.Empty:
            pass
        self.after(80, self._poll_scan_queue)

    def _run_scan_thread_impl(self):
        """背景執行緒：三階段掃描真實邏輯"""
        import sys, warnings, traceback
        import yfinance as yf
        warnings.filterwarnings('ignore')
        # strategy.py 在專案根目錄，不需要插入 _SCAN_DIR
        from strategy import calculate_dmpi, calculate_rsi, calculate_macd, generate_signals, evaluate_resonance_stateless

        def fetch_df(ticker, days=120):
            from datetime import datetime, timedelta
            from data_loader import get_yf_ticker
            try:
                df = get_yf_ticker(ticker).history(
                    start=(datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                )
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                if df.empty or len(df) < 60:
                    return None
                return df
            except Exception:
                return None

        def compute(df):
            df = calculate_dmpi(df)
            df = calculate_rsi(df)
            df = calculate_macd(df)
            df = generate_signals(df, indicator='綜合共振')
            return df

        def regime(macd, hist):
            if macd > 0 and hist >= 0: return '多頭'
            if macd < 0 and hist <= 0: return '空頭'
            return '盤整'

        def score_zone(s):
            if s >= 100: return '🔴極熱'
            if s >= 90:  return '⚠️過熱'
            if s >= 50:  return '✅甜區'
            return '🔸普通'

        def calc_score(df, code):
            last = df.iloc[-1]
            dmpi   = last['DMPI']
            macd   = last['MACD']
            hist   = last.get('MACD_Hist', 0)
            rsi    = last['RSI']
            
            sig = evaluate_resonance_stateless(dmpi, rsi, macd, hist)
            if sig != 1: return None
            
            reg    = regime(macd, hist)
            vol20  = df['Volume'].rolling(20).mean().iloc[-1]
            volr   = last['Volume'] / vol20 if vol20 > 0 else 1.0
            reg_sc = 100 if reg == '多頭' else (40 if reg == '盤整' else 0)
            if 50 <= rsi <= 70:
                rsi_sc = 100
            elif rsi < 50:
                rsi_sc = max(0, 50 + 50 * rsi / 50)
            else:
                rsi_sc = max(0, 100 - (rsi - 70) * 3)
            vol_sc  = min(100.0, volr * 100)
            bonus   = min(5.0, max(0.0, (dmpi + 20) / 50 * 5)) if reg == '多頭' and -20 <= dmpi <= 30 else 0.0
            total   = reg_sc * 0.50 + rsi_sc * 0.30 + vol_sc * 0.20 + bonus
            return {'stock': code, 'regime': reg, 'dmpi': dmpi, 'rsi': rsi,
                    'vol_ratio': volr, 'total_score': total, 'close': last['Close'],
                    'reg_sc': reg_sc, 'rsi_sc': rsi_sc, 'vol_sc': vol_sc, 'bonus': bonus}

        # ── 讀取清單 ─────────────────────────────────────────────
        def load_stocks():
            if not os.path.exists(_STOCKS_FILE):
                return []
            result = []
            with open(_STOCKS_FILE, encoding='utf-8') as f:
                for line in f:
                    c = line.strip()
                    if c and not c.startswith('#'):
                        result.append(c)
            return result

        def load_portfolio():
            if not os.path.exists(_PORTFOLIO_FILE):
                return []
            result = []
            with open(_PORTFOLIO_FILE, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split(',')
                    if len(parts) == 3:
                        try:
                            result.append((parts[0].strip(), float(parts[1]), float(parts[2])))
                        except ValueError:
                            pass
            return result

        stocks = load_stocks()
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        self.after(0, lambda: self.scan_status_lbl.configure(
            text=f"{now_str} ─ 掃描 {len(stocks)} 支股票中...", text_color="yellow"))

        # ══ 第一階段：掃描 ════════════════════════════════════════
        hdr = f"{'代碼':<10} {'DMPI':>6} {'RSI':>5} {'MACD':>8} {'趨勢':>4}  訊號\n"
        hdr += '=' * 50 + '\n'
        self._scan_append('scan_signal_box', hdr)

        rows = []
        buy_list, sell_list = [], []

        for i, stock in enumerate(stocks):
            self.after(0, lambda s=stock, n=i+1, t=len(stocks): self.scan_status_lbl.configure(
                text=f"[{n}/{t}] 分析 {s}...", text_color="yellow"))
            try:
                df = fetch_df(stock, 120)
                if df is None:
                    continue
                df = compute(df)
                last  = df.iloc[-1]
                dmpi  = last['DMPI']
                rsi   = last['RSI']
                macd  = last['MACD']
                hist  = last.get('MACD_Hist', 0)
                
                sig   = int(last.get('Signal', 0))
                pos   = int(last.get('Position', 0))
                reg   = regime(macd, hist)
                
                if sig == 1: icon = '🔥新買'
                elif sig == -1: icon = '🧹賣出'
                elif pos == 1: icon = '☕持有'
                else: icon = '☕觀望'
                
                line  = f"{stock:<10} {dmpi:>6.1f} {rsi:>5.1f} {macd:>8.2f} {reg:>4}  {icon}\n"
                self._scan_append('scan_signal_box', line)
                sc = calc_score(df, stock) if sig == 1 else None
                if sig == 1: buy_list.append(stock)
                if sig == -1: sell_list.append(stock)
                rows.append({'stock': stock, 'signal': sig, 'score_data': sc, 'close': last['Close']})
            except Exception as e:
                self._scan_append('scan_signal_box', f"{stock:<10} ❌ Error: {e}\n")

        total = len(buy_list) + len(sell_list)
        summary = (
            '=' * 50 + '\n'
            f"🔥 強烈買進: {', '.join(buy_list) if buy_list else '無'} ({len(buy_list)} 支)\n"
            f"🧹 強烈賣出: {', '.join(sell_list) if sell_list else '無'} ({len(sell_list)} 支)\n"
            f"📊 統計：{total}/{len(stocks)} 支有訊號\n"
        )
        self._scan_append('scan_signal_box', summary)

        # ══ 第二階段：評分排名 ════════════════════════════════════
        ranked = sorted(
            [r['score_data'] for r in rows if r['score_data'] is not None],
            key=lambda x: x['total_score'], reverse=True
        )
        if ranked:
            rank_txt  = f"共 {len(ranked)} 支買訊，依評分排名：\n\n"
            rank_txt += f"{'#':<3} {'代碼':<12} {'總分':>6} {'評級':<8} {'趨勢':<4} {'RSI':>5} {'量比':>6} {'現價':>8}\n"
            rank_txt += '-' * 60 + '\n'
            for i, r in enumerate(ranked):
                icon2 = '📈' if r['regime'] == '多頭' else ('➡️' if r['regime'] == '盤整' else '📉')
                rank_txt += (
                    f"{i+1:<3} {r['stock']:<12} {r['total_score']:>6.1f} "
                    f"{score_zone(r['total_score']):<8} {icon2}{r['regime']:<3} "
                    f"{r['rsi']:>5.1f} {r['vol_ratio']:>6.2f}x {r['close']:>8.2f}\n"
                )
            rank_txt += '-' * 60 + '\n'
            rank_txt += "💡 評分邏輯：多頭趨勢50% + RSI強勢區30% + 量比20% + DMPI加分\n"
        else:
            rank_txt = "本次掃描無合格買訊號股票。\n"
        self._scan_append('scan_rank_box', rank_txt)

        # ══ 第三階段：持股檢查 ════════════════════════════════════
        positions = load_portfolio()
        if not positions:
            pf_txt = "portfolio.txt 無持股紀錄。\n"
        else:
            pf_txt  = f"{'代碼':<12} {'現價':>6} {'PnL':>12} {'DMPI':>6} {'RSI':>5}  結論\n"
            pf_txt += '=' * 55 + '\n'
            has_sell = False
            for stock, cost, qty in positions:
                try:
                    df = fetch_df(stock, 120)
                    if df is None:
                        pf_txt += f"{stock:<12} 資料不足\n"
                        continue
                    df = compute(df)
                    last   = df.iloc[-1]
                    close  = last['Close']
                    dmpi   = last['DMPI']
                    rsi    = last['RSI']
                    macd   = last['MACD']
                    hist   = last.get('MACD_Hist', 0)
                    sig    = int(last.get('Signal', 0))
                    pos    = int(last.get('Position', 0))
                    pnl    = (close - cost) * qty
                    pnl_p  = (close - cost) / cost * 100
                    
                    if sig == 1: result = '🔥加碼'
                    elif sig == -1: result = '🧹出場'
                    elif pos == 1: result = '☕續抱'
                    else: result = '☕觀望'
                    
                    if sig == -1: has_sell = True
                    pf_txt += f"{stock:<12} {close:>6.0f} {pnl:>+7.0f}({pnl_p:>+5.1f}%) {dmpi:>6.1f} {rsi:>5.1f}  {result}\n"
                except Exception:
                    pf_txt += f"{stock:<12} Error\n"
            pf_txt += '=' * 55 + '\n'
            pf_txt += '⚠️ 有持股出現賣訊！請注意風控！\n' if has_sell else '✅ 全數持有中，無賣訊\n'
        self._scan_append('scan_portfolio_box', pf_txt)

        # ── 完成 ─────────────────────────────────────────────────
        done_str = datetime.now().strftime('%H:%M:%S')
        self.after(0, lambda: self.scan_status_lbl.configure(
            text=f"✅ 掃描完成 {done_str}，共 {len(stocks)} 支", text_color="#00ff00"))

    def _run_scan_thread(self):
        """背景執行緒：三階段掃描（加 try/finally 確保 __DONE__ 一定送出）"""
        try:
            self._run_scan_thread_impl()
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            err_msg = str(e)
            self._scan_append('scan_signal_box', f"\n❌ 掃描發生嚴重錯誤：\n{err}\n")
            self.after(0, lambda m=err_msg: self.scan_status_lbl.configure(
                text=f"❌ 掃描失敗: {m}", text_color="#ff5555"))
        finally:
            self._scan_queue.put('__DONE__')
        
    def on_search_clicked(self):
        ticker = self.ticker_entry.get().strip().upper()
        if not ticker:
            self.status_label.configure(text="請輸入股票代號！", text_color="#ff5555")
            return
            
        period = self.period_combo.get()
        base_strategy = self.strategy_seg.get()
        
        self.status_label.configure(text=f"正在分析 {ticker} ...這可能需要幾十秒鐘", text_color="yellow")
        
        self.lbl_ai_act.configure(text="AI 擷取特徵推論中...", text_color="white")
        self.lbl_dmpi_act.configure(text="分析處理中...", text_color="white")
        self.lbl_rsi_act.configure(text="分析處理中...", text_color="white")
        self.lbl_macd_act.configure(text="分析處理中...", text_color="white")
        self.lbl_comp_act.configure(text="分析處理中...", text_color="white")
        
        self.fund_textbox.delete("0.0", "end")
        self.backtest_textbox.delete("0.0", "end")
        
        for widget in self.chart_container.winfo_children():
            widget.destroy()
            
        # [Crucial fix] Force garbage collection on the main thread.
        # Matplotlib's NavigationToolbar creates PhotoImage objects. When the widget is destroyed,
        # they become unreferenced. If the background thread's garbage collector sweeps them,
        # Tkinter will throw a "main thread is not in main loop" error during PhotoImage.__del__.
        import gc
        gc.collect()
            
        threading.Thread(target=self.run_analysis, args=(ticker, period, base_strategy), daemon=True).start()
        
    def run_analysis(self, ticker, period, base_strategy):
        from data_loader import get_yf_ticker
        try:
            stock = get_yf_ticker(ticker)
            df = stock.history(period=period)
        except Exception as e:
            self.update_status(f"獲取歷史股價失敗: {e}", "#ff5555")
            return
            
        if df is None or df.empty:
            self.update_status(f"找不到 {ticker} 的歷史資料，請確認代號是否正確。", "#ff5555")
            return
            
        try:
            from strategy import calculate_dmpi, calculate_rsi, calculate_macd, generate_signals
            df = calculate_dmpi(df)
            df = calculate_rsi(df)
            df = calculate_macd(df)
        except Exception as e:
            self.update_status(f"計算指標發生錯誤: {e}", "#ff5555")
            return

        # === 主圖下單策略：僅用於 K 線圖標註 ===
        try:
            df_main = generate_signals(df.copy(), indicator=base_strategy)
        except Exception as e:
            self.update_status(f"計算指標發生錯誤: {e}", "#ff5555")
            return

        # === 四大策略全部回測 ===
        all_strategies = ["自創 DMPI", "RSI", "MACD", "綜合共振"]
        all_backtest_results = {}
        try:
            for strat in all_strategies:
                df_s = generate_signals(df.copy(), indicator=strat)
                all_backtest_results[strat] = run_backtest(df_s, indicator_name=strat)
        except Exception as e:
            self.update_status(f"回測引擎發生錯誤: {e}", "#ff5555")
            return

        try:
            recs = get_latest_recommendation(df_main)
        except Exception as e:
            self.update_status(f"回測引擎發生錯誤: {e}", "#ff5555")
            return
            
        try:
            ai_recs = self.ai_engine.predict_action(df)
        except Exception as e:
            ai_recs = {"action": "AI 離線", "reason": str(e)}
            
        try:
            info = fetch_stock_info(ticker)
            financials = fetch_financials(ticker)
        except Exception as e:
            info = {"Error": str(e)}
            financials = {}
        
        self.after(0, self.update_ui_post_analysis, ticker, df_main, info, financials, all_backtest_results, recs, base_strategy, ai_recs)
        
    def update_status(self, msg, color):
        self.after(0, lambda: self.status_label.configure(text=msg, text_color=color))

    def update_ui_post_analysis(self, ticker, df, info, financials, all_backtest_results, recs, base_strategy, ai_recs):
        self.status_label.configure(text=f"{ticker} 分析完成！ (結合 AI DRL 強化學習與多指標大腦)", text_color="#00ff00")
        
        # ==== 更新價格資訊 ====
        if not df.empty:
            last_close = df['Close'].iloc[-1]
            last_high = df['High'].iloc[-1]
            last_low = df['Low'].iloc[-1]
            # 計算漲跌幅 (與前一日收盤價相比)
            if len(df) > 1:
                prev_close = df['Close'].iloc[-2]
                change_pct = (last_close - prev_close) / prev_close * 100
                color = "#ff5555" if change_pct >= 0 else "#00ff00"
                sign = "+" if change_pct >= 0 else ""
                price_text = f"最新收盤: {last_close:,.2f} ({sign}{change_pct:.2f}%) | 高: {last_high:,.2f} | 低: {last_low:,.2f}"
            else:
                price_text = f"最新收盤: {last_close:,.2f} | 高: {last_high:,.2f} | 低: {last_low:,.2f}"
                color = "white"
            
            self.price_label.configure(text=price_text, text_color=color)
        
        plot_stock_chart(self.chart_container, df, ticker)
        
        # ==== 更新 AI 大腦卡片 ====
        ai_act = ai_recs.get("action", "N/A")
        self.lbl_ai_act.configure(text=ai_act)
        self.lbl_ai_desc.configure(text=ai_recs.get("reason", ""))
        if "買" in ai_act or "Long" in ai_act: self.lbl_ai_act.configure(text_color="#ff5555")
        elif "賣" in ai_act or "Short" in ai_act: self.lbl_ai_act.configure(text_color="#00ff00")
        else: self.lbl_ai_act.configure(text_color="orange")
        
        # ==== 更新三大指標建議卡片 ====
        def update_card(lbl_act, lbl_desc, rec_data):
            act = rec_data.get("action", "N/A")
            val = rec_data.get("value")
            if val is not None:
                act += f"  [ 數值: {val:.2f} ]"
            lbl_act.configure(text=act)
            lbl_desc.configure(text=rec_data.get("reason", ""))
            
            if "買" in act or "Add" in act: lbl_act.configure(text_color="#ff5555")
            elif "賣" in act or "Clear" in act or "Reduce" in act or "逃意" in act or "逃命" in act: lbl_act.configure(text_color="#00ff00")
            elif "Hold" in act: lbl_act.configure(text_color="orange")
            else: lbl_act.configure(text_color="white")
            
        update_card(self.lbl_dmpi_act, self.lbl_dmpi_desc, recs.get("自創 DMPI", recs.get("DMPI", {})))
        update_card(self.lbl_rsi_act, self.lbl_rsi_desc, recs.get("RSI", {}))
        update_card(self.lbl_macd_act, self.lbl_macd_desc, recs.get("MACD", {}))
        update_card(self.lbl_comp_act, self.lbl_comp_desc, recs.get("綜合共振", {}))
        
        # ==== 更新基本面與財報 ====
        fund_text = f"========== 【 {ticker} 基本面摘要 】 ==========\n\n"
        for k, v in info.items():
            fund_text += f"{k:20s}: {v}\n"
            
        fund_text += "\n\n========== 【 年度財報 (部分摘要) 】 ==========\n"
        fs = financials.get('financials', pd.DataFrame())
        if not fs.empty:
            keywords = ["Total Revenue", "Net Income", "Gross Profit", "Operating Income"]
            for row in fs.index:
                if any(kw in str(row) for kw in keywords):
                    fund_text += f"\n{row}:\n"
                    cols = fs.columns[:3]
                    for col in cols:
                        val = fs.loc[row, col]
                        date_str = col.strftime('%Y-%m-%d') if hasattr(col, 'strftime') else str(col)
                        fund_text += f"    [{date_str}] : {val:,.0f} \n"
        else:
            fund_text += "無財報資料或該資產為 ETF / 指數。\n"
            
        self.fund_textbox.insert("0.0", fund_text)
        
        # ==== 更新回測結果：同時顯示四大策略 ====
        strategy_icons = {"自創 DMPI": "🚀", "RSI": "📊", "MACD": "📈", "綜合共振": "👑"}
        bt_text = f"========== 【 {ticker} 四大策略回測比較表 】 ==========\n"
        bt_text += f"(K線圖標註買賣點以「{base_strategy}」為主)\n\n"
        
        for strat_name, res in all_backtest_results.items():
            icon = strategy_icons.get(strat_name, "⭐")
            ret_val = res['total_return_pct']
            ret_emoji = "🟢" if ret_val > 0 else "🔴"
            star = " ◄「主圖」" if strat_name == base_strategy else ""
            bt_text += f"{icon} {strat_name}{star}\n"
            bt_text += f"   总報酬: {ret_emoji} {ret_val:+.2f}%   MDD: {res['max_drawdown_pct']:.1f}%   分析次數: {res['total_trades']}次   勝率: {res['win_rate_pct']:.1f}%\n"
            bt_text += "-"*55 + "\n"
        
        bt_text += "\n"
        
        # 主要策略的近期交易明細表 (15 筆)
        main_res = all_backtest_results.get(base_strategy, {})
        bt_text += f"===== 【主回測策略「{base_strategy}」近期 15 筆交易明細】 =====\n\n"
        trades = main_res.get('trades', [])
        if not trades:
            bt_text += "期間內無觸發任何交易。\n"
        else:
            for t in trades[-15:]:
                date_str = t['Date'].strftime('%Y-%m-%d')
                reason = t.get('Reason', '')
                if 'Buy' in t['Type']:
                    bt_text += f"[ {date_str} ] 🔺 買進  | 價格: {t['Price']:,.2f}\n"
                    bt_text += f"              📋 理由: {reason}\n"
                else:
                    prof = t.get('Profit_%', 0)
                    prof_mark = "🟢" if prof > 0 else "🔴"
                    bt_text += f"[ {date_str} ] 🔻 賣出  | 價格: {t['Price']:,.2f} | 獲利: {prof_mark} {prof:+.2f}%\n"
                    bt_text += f"              📋 理由: {reason}\n"
                    
        self.backtest_textbox.insert("0.0", bt_text)

if __name__ == "__main__":
    app = App()
    app.mainloop()
