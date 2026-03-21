import customtkinter as ctk
import threading
from datetime import datetime
import pandas as pd

from data_loader import fetch_stock_info, fetch_financials
from backtester import run_backtest, get_latest_recommendation
from chart import plot_stock_chart

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
            "本系統整合了三套強大的動能與趨勢指標，由上而下為您進行全方位的盤勢解析：\n\n"
            "一、自創 DMPI (動態市場壓力指數) 🚀\n"
            "結合價格壓力、成交流量與 ATR 波動懲罰的客製化指標。\n"
            "• 買進：由下往上突破零軸 (空翻多)\n"
            "• 賣出：由上往下跌破零軸 (多翻空)\n\n"
            "二、RSI (相對強弱指標) 📊\n"
            "衡量近期價格變動幅度，評估資產是否超買或超賣。\n"
            "• 買進：從低於 30 (超賣區) 反彈向上穿越 30\n"
            "• 賣出：從高於 70 (超買區) 回落向下穿越 70\n\n"
            "三、MACD (平滑異同移動平均線) 📈\n"
            "捕捉中長期的股價趨勢與波段動能變化。\n"
            "• 買進：柱狀圖出水面由負轉正 (黃金交叉)\n"
            "• 賣出：柱狀圖下沉由正轉負 (死亡交叉)\n\n"
            "綜合參考三個指標的共振訊號，勝率與穩定度將大幅提升！"
        )
        textbox.insert("0.0", desc)
        textbox.configure(state="disabled")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("進階股票分析與多指標回測系統")
        self.geometry("1400x900")
        self.configure(fg_color="#121212")
        
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
        
        self.strategy_seg = ctk.CTkSegmentedButton(self.top_frame, values=["自創 DMPI", "RSI", "MACD"], font=("Microsoft JhengHei", 14), selected_color="#0052cc", selected_hover_color="#0066ff")
        self.strategy_seg.set("自創 DMPI")
        self.strategy_seg.pack(side="left", padx=5)
        
        self.help_btn = ctk.CTkButton(self.top_frame, text="指標介紹 ❓", width=120, height=38, font=("Microsoft JhengHei", 15, "bold"), command=self.show_help, fg_color="#333333", hover_color="#555555", corner_radius=8)
        self.help_btn.pack(side="left", padx=(10, 20))
        
        self.search_btn = ctk.CTkButton(self.top_frame, text="開始分析", font=("Microsoft JhengHei", 15, "bold"), command=self.on_search_clicked, height=45, corner_radius=10)
        self.search_btn.pack(side="left", padx=20)
        
        self.status_label = ctk.CTkLabel(self.top_frame, text="", text_color="gray", font=("Microsoft JhengHei", 14))
        self.status_label.pack(side="left", fill="x", expand=True, padx=10)
        
        # --- Suggestion Dashboard (Grid Layout) ---
        self.sugg_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.sugg_frame.grid(row=2, column=0, padx=25, pady=(0, 25), sticky="ew")
        self.sugg_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # DMPI Card
        self.card_dmpi = ctk.CTkFrame(self.sugg_frame, fg_color="#1a1a1a", corner_radius=15, border_width=1, border_color="#333333")
        self.card_dmpi.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        self.lbl_dmpi_title = ctk.CTkLabel(self.card_dmpi, text="自創 DMPI 動能", font=("Microsoft JhengHei", 16, "bold"), text_color="#00bfff")
        self.lbl_dmpi_title.pack(pady=(15, 5))
        self.lbl_dmpi_act = ctk.CTkLabel(self.card_dmpi, text="等待分析", font=("Microsoft JhengHei", 22, "bold"))
        self.lbl_dmpi_act.pack(pady=5)
        self.lbl_dmpi_desc = ctk.CTkLabel(self.card_dmpi, text="請輸入股票代號並開始分析", font=("Microsoft JhengHei", 13), text_color="gray", wraplength=350)
        self.lbl_dmpi_desc.pack(pady=(5, 15), padx=10)
        
        # RSI Card
        self.card_rsi = ctk.CTkFrame(self.sugg_frame, fg_color="#1a1a1a", corner_radius=15, border_width=1, border_color="#333333")
        self.card_rsi.grid(row=0, column=1, padx=5, sticky="nsew")
        self.lbl_rsi_title = ctk.CTkLabel(self.card_rsi, text="RSI (14) 相對強弱", font=("Microsoft JhengHei", 16, "bold"), text_color="#c266ff")
        self.lbl_rsi_title.pack(pady=(15, 5))
        self.lbl_rsi_act = ctk.CTkLabel(self.card_rsi, text="等待分析", font=("Microsoft JhengHei", 22, "bold"))
        self.lbl_rsi_act.pack(pady=5)
        self.lbl_rsi_desc = ctk.CTkLabel(self.card_rsi, text="請輸入股票代號並開始分析", font=("Microsoft JhengHei", 13), text_color="gray", wraplength=350)
        self.lbl_rsi_desc.pack(pady=(5, 15), padx=10)
        
        # MACD Card
        self.card_macd = ctk.CTkFrame(self.sugg_frame, fg_color="#1a1a1a", corner_radius=15, border_width=1, border_color="#333333")
        self.card_macd.grid(row=0, column=2, padx=(10, 0), sticky="nsew")
        self.lbl_macd_title = ctk.CTkLabel(self.card_macd, text="MACD 趨勢跟蹤", font=("Microsoft JhengHei", 16, "bold"), text_color="#ff9900")
        self.lbl_macd_title.pack(pady=(15, 5))
        self.lbl_macd_act = ctk.CTkLabel(self.card_macd, text="等待分析", font=("Microsoft JhengHei", 22, "bold"))
        self.lbl_macd_act.pack(pady=5)
        self.lbl_macd_desc = ctk.CTkLabel(self.card_macd, text="請輸入股票代號並開始分析", font=("Microsoft JhengHei", 13), text_color="gray", wraplength=350)
        self.lbl_macd_desc.pack(pady=(5, 15), padx=10)
        
        # --- Main Tabview ---
        self.tabview = ctk.CTkTabview(self, fg_color="#1e1e1e", segmented_button_selected_color="#0052cc", segmented_button_selected_hover_color="#0066ff", text_color="white", corner_radius=15)
        self.tabview.grid(row=1, column=0, padx=25, pady=(0, 25), sticky="nsew")
        
        self.tab_chart = self.tabview.add("📊 互動 K 線圖與指標")
        self.tab_backtest = self.tabview.add("📈 策略回測報告")
        self.tab_fundamentals = self.tabview.add("🏢 基本面與財報")
        
        self.setup_chart_tab()
        self.setup_backtest_tab()
        self.setup_fundamentals_tab()
        
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
        
    def on_search_clicked(self):
        ticker = self.ticker_entry.get().strip().upper()
        if not ticker:
            self.status_label.configure(text="請輸入股票代號！", text_color="#ff5555")
            return
            
        period = self.period_combo.get()
        base_strategy = self.strategy_seg.get()
        
        self.status_label.configure(text=f"正在分析 {ticker} ...這可能需要幾十秒鐘", text_color="yellow")
        
        self.lbl_dmpi_act.configure(text="分析處理中...", text_color="white")
        self.lbl_rsi_act.configure(text="分析處理中...", text_color="white")
        self.lbl_macd_act.configure(text="分析處理中...", text_color="white")
        
        self.fund_textbox.delete("0.0", "end")
        self.backtest_textbox.delete("0.0", "end")
        
        for widget in self.chart_container.winfo_children():
            widget.destroy()
            
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
            # 以選擇的基準策略來產生主圖的買賣點與進行歷史回測
            df = generate_signals(df, indicator=base_strategy)
        except Exception as e:
            self.update_status(f"計算指標發生錯誤: {e}", "#ff5555")
            return
            
        try:
            backtest_res = run_backtest(df, indicator_name=base_strategy)
            recs = get_latest_recommendation(df)
        except Exception as e:
            self.update_status(f"回測引擎發生錯誤: {e}", "#ff5555")
            return
            
        try:
            info = fetch_stock_info(ticker)
            financials = fetch_financials(ticker)
        except Exception as e:
            info = {"Error": str(e)}
            financials = {}
        
        self.after(0, self.update_ui_post_analysis, ticker, df, info, financials, backtest_res, recs, base_strategy)
        
    def update_status(self, msg, color):
        self.after(0, lambda: self.status_label.configure(text=msg, text_color=color))

    def update_ui_post_analysis(self, ticker, df, info, financials, backtest_res, recs, base_strategy):
        self.status_label.configure(text=f"{ticker} 分析完成！ (三指標綜合儀表板)", text_color="#00ff00")
        
        plot_stock_chart(self.chart_container, df, ticker)
        
        # ==== 更新三大指標建議卡片 ====
        def update_card(lbl_act, lbl_desc, rec_data):
            act = rec_data.get("action", "N/A")
            lbl_act.configure(text=act)
            lbl_desc.configure(text=rec_data.get("reason", ""))
            
            if "買" in act or "Add" in act: lbl_act.configure(text_color="#ff5555")
            elif "賣" in act or "Clear" in act or "Reduce" in act or "逃意" in act or "逃命" in act: lbl_act.configure(text_color="#00ff00")
            elif "Hold" in act: lbl_act.configure(text_color="orange")
            else: lbl_act.configure(text_color="white")
            
        update_card(self.lbl_dmpi_act, self.lbl_dmpi_desc, recs.get("DMPI", {}))
        update_card(self.lbl_rsi_act, self.lbl_rsi_desc, recs.get("RSI", {}))
        update_card(self.lbl_macd_act, self.lbl_macd_desc, recs.get("MACD", {}))
        
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
        
        # ==== 更新回測結果 ====
        bt_text = f"========== 【 {ticker} 策略歷史回測報告 】 ==========\n\n"
        bt_text += f"(註：目前歷史回測圖表特徵點與明細以剛才選擇的「{base_strategy}」為主核心驗證)\n"
        bt_text += "-"*50 + "\n"
        bt_text += f"> 初始資金: {backtest_res['initial_capital']:,.2f}\n"
        bt_text += f"> 最終資金: {backtest_res['final_capital']:,.2f}\n"
        bt_text += "-"*50 + "\n"
        
        ret_val = backtest_res['total_return_pct']
        ret_str = f"{ret_val:+.2f} %"
        bt_text += f"> 總報酬率: {ret_str}\n"
        bt_text += f"> 最大權益回撤 (MDD): {backtest_res['max_drawdown_pct']:.2f} %\n"
        bt_text += f"> 總賣出交易次數: {backtest_res['total_trades']} 次\n"
        bt_text += f"> 勝率: {backtest_res['win_rate_pct']:.1f} %\n\n"
        
        bt_text += "========== 【 近期 15 筆交易明細 】 ==========\n\n"
        trades = backtest_res['trades']
        if not trades:
            bt_text += "期間內無觸發任何交易。\n"
        else:
            for t in trades[-15:]: 
                date_str = t['Date'].strftime('%Y-%m-%d')
                if 'Buy' in t['Type']:
                    bt_text += f"[ {date_str} ] 🔺 買進 (Buy)   | 價格: {t['Price']:,.2f}\n"
                else:
                    prof = t.get('Profit_%', 0)
                    prof_mark = "🟢" if prof > 0 else "🔴"
                    bt_text += f"[ {date_str} ] 🔻 賣出 (Sell)  | 價格: {t['Price']:,.2f} | 獲利: {prof_mark} {prof:+.2f} %\n"
                    
        self.backtest_textbox.insert("0.0", bt_text)

if __name__ == "__main__":
    app = App()
    app.mainloop()
