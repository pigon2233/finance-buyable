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
    def __init__(self, master, indicator_name):
        super().__init__(master)
        self.title("指標說明")
        self.geometry("500x380")
        self.attributes("-topmost", True)
        self.configure(fg_color="#121212")
        
        title_lbl = ctk.CTkLabel(self, text=f"【 {indicator_name} 】 說明", font=("Microsoft JhengHei", 20, "bold"), text_color="#00bfff")
        title_lbl.pack(pady=20)
        
        textbox = ctk.CTkTextbox(self, font=("Microsoft JhengHei", 14), wrap="word", fg_color="#1e1e1e", corner_radius=10)
        textbox.pack(fill="both", expand=True, padx=25, pady=(0, 25))
        
        if indicator_name == "自創 DMPI":
            desc = (
                "動態市場壓力指數 (DMPI) 是結合價格壓力、成交量動能與波動懲罰的客製化指標。\n\n"
                "【權重與原理】\n"
                "1. 計算實體 K 線在總振幅中的淨壓力位置 (-1 ~ 1)\n"
                "2. 乘上近期成交量相對放大的倍數\n"
                "3. 除以真實波動率 (ATR) 懲罰高風險時段\n"
                "4. 經過平滑後，常態數值會在 -50 到 50 震盪。\n\n"
                "【訊號條件】\n"
                "• 買進：由下往上突破零軸 (空翻多)\n"
                "• 賣出：由上往下跌破零軸 (多翻空)\n\n"
                "適合作為動能確認與波段起漲點的捕捉。"
            )
        elif indicator_name == "RSI":
            desc = (
                "相對強弱指標 (RSI) 用於衡量近期價格變動的幅度，評估資產是否超買或超賣。\n\n"
                "【權重與原理】\n"
                "預設週期：14 天\n"
                "數值範圍：0 ~ 100\n\n"
                "【訊號條件】\n"
                "• 買進：RSI 從低於 30 (超賣區) 反彈向上穿越 30\n"
                "• 賣出：RSI 從高於 70 (超買區) 回落向下穿越 70\n\n"
                "此策略適合在震盪盤整區間進行低買高賣操作。"
            )
        else:
            desc = (
                "平滑異同移動平均線 (MACD) 捕捉股價趨勢與動能的變化。\n\n"
                "【權重與原理】\n"
                "快線EMA(12), 慢線EMA(26), 訊號線(9)\n\n"
                "【訊號條件】\n"
                "• 買進：柱狀圖(MACD - Signal) 由負轉正 (黃金交叉)\n"
                "• 賣出：柱狀圖由正轉負 (死亡交叉)\n\n"
                "典型的趨勢跟蹤指標，適合在中長期的趨勢盤中捕捉主升段。"
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
        
        self.ind_label = ctk.CTkLabel(self.top_frame, text="指標策略:", font=("Microsoft JhengHei", 15, "bold"), text_color="#00bfff")
        self.ind_label.pack(side="left", padx=10)

        self.ind_combo = ctk.CTkComboBox(self.top_frame, values=["自創 DMPI", "RSI", "MACD"], width=140, font=("Microsoft JhengHei", 15), height=38, button_color="#0052cc", border_color="#0052cc")
        self.ind_combo.set("自創 DMPI")
        self.ind_combo.pack(side="left", padx=5)
        
        self.help_btn = ctk.CTkButton(self.top_frame, text="❓", width=38, height=38, font=("Arial", 16, "bold"), command=self.show_help, fg_color="#333333", hover_color="#555555", corner_radius=8)
        self.help_btn.pack(side="left", padx=(0, 20))
        
        self.search_btn = ctk.CTkButton(self.top_frame, text="開始分析", font=("Microsoft JhengHei", 15, "bold"), command=self.on_search_clicked, height=45, corner_radius=10)
        self.search_btn.pack(side="left", padx=20)
        
        self.status_label = ctk.CTkLabel(self.top_frame, text="", text_color="gray", font=("Microsoft JhengHei", 14))
        self.status_label.pack(side="left", fill="x", expand=True, padx=10)
        
        # --- Suggestion Frame (Card Layout) ---
        self.sugg_frame = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=15, border_width=1, border_color="#333333")
        self.sugg_frame.grid(row=2, column=0, padx=25, pady=(0, 25), sticky="ew")
        
        self.sugg_label = ctk.CTkLabel(self.sugg_frame, text="最新進出場建議: 尚未分析", font=("Microsoft JhengHei", 22, "bold"))
        self.sugg_label.pack(pady=25)
        
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
        ind = self.ind_combo.get()
        HelpWindow(self, ind)

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
        ind_name = self.ind_combo.get()
        
        self.status_label.configure(text=f"正在分析 {ticker} ...這可能需要幾十秒鐘", text_color="yellow")
        self.sugg_label.configure(text="最新進出場建議: 分析資料處理中...", text_color="white")
        
        self.fund_textbox.delete("0.0", "end")
        self.backtest_textbox.delete("0.0", "end")
        
        for widget in self.chart_container.winfo_children():
            widget.destroy()
            
        threading.Thread(target=self.run_analysis, args=(ticker, period, ind_name), daemon=True).start()
        
    def run_analysis(self, ticker, period, ind_name):
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
            if ind_name == "自創 DMPI":
                from strategy import calculate_dmpi
                df = calculate_dmpi(df)
            elif ind_name == "RSI":
                from strategy import calculate_rsi
                df = calculate_rsi(df)
            elif ind_name == "MACD":
                from strategy import calculate_macd
                df = calculate_macd(df)
                
            from strategy import generate_signals
            df = generate_signals(df, indicator=ind_name)
        except Exception as e:
            self.update_status(f"計算指標發生錯誤: {e}", "#ff5555")
            return
            
        try:
            backtest_res = run_backtest(df, indicator_name=ind_name)
            rec = get_latest_recommendation(df, indicator_name=ind_name)
        except Exception as e:
            self.update_status(f"回測引擎發生錯誤: {e}", "#ff5555")
            return
            
        try:
            info = fetch_stock_info(ticker)
            financials = fetch_financials(ticker)
        except Exception as e:
            info = {"Error": str(e)}
            financials = {}
        
        self.after(0, self.update_ui_post_analysis, ticker, df, info, financials, backtest_res, rec, ind_name)
        
    def update_status(self, msg, color):
        self.after(0, lambda: self.status_label.configure(text=msg, text_color=color))

    def update_ui_post_analysis(self, ticker, df, info, financials, backtest_res, rec, ind_name):
        self.status_label.configure(text=f"{ticker} 分析完成！ ({ind_name} 策略)", text_color="#00ff00")
        
        plot_stock_chart(self.chart_container, df, ticker, indicator_name=ind_name)
        
        # ==== 更新建議 ====
        action = rec.get('action', '')
        reason = rec.get('reason', '')
        price = rec.get('price', '')
        price_str = f" @ {price:.2f}" if price else ""
        
        sugg_color = "white"
        if "Buy" in action: sugg_color = "#00ff00"
        elif "Sell" in action: sugg_color = "#ff5555"
        elif "Hold" in action: sugg_color = "orange"
        
        self.sugg_label.configure(text=f"最新建議: {action}{price_str}  ({reason})", text_color=sugg_color)
        
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
        bt_text = f"========== 【 {ind_name} 策略 回測報告 ({ticker}) 】 ==========\n\n"
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
