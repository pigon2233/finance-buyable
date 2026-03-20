import customtkinter as ctk
import threading
from datetime import datetime
import pandas as pd

from data_loader import fetch_stock_history, fetch_stock_info, fetch_financials
from strategy import calculate_dmpi, generate_signals
from backtester import run_backtest, get_latest_recommendation
from chart import plot_stock_chart

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("進階股票分析與自創 DMPI 策略系統")
        self.geometry("1400x900")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Search bar
        self.grid_rowconfigure(1, weight=1)  # Tabview
        self.grid_rowconfigure(2, weight=0)  # Sugg Frame
        
        # --- Top Search Frame ---
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        
        self.ticker_label = ctk.CTkLabel(self.top_frame, text="股票代號:", font=("Arial", 14))
        self.ticker_label.pack(side="left", padx=10)
        
        self.ticker_entry = ctk.CTkEntry(self.top_frame, placeholder_text="例如: 2330.TW 或 AAPL", width=200)
        self.ticker_entry.pack(side="left", padx=10)
        
        self.period_label = ctk.CTkLabel(self.top_frame, text="回測期間:")
        self.period_label.pack(side="left", padx=10)
        
        self.period_combo = ctk.CTkComboBox(self.top_frame, values=["1mo", "3mo", "6mo", "1y", "2y", "5y"], width=100)
        self.period_combo.set("1y")
        self.period_combo.pack(side="left", padx=10)
        
        self.search_btn = ctk.CTkButton(self.top_frame, text="開始分析", command=self.on_search_clicked)
        self.search_btn.pack(side="left", padx=20)
        
        self.status_label = ctk.CTkLabel(self.top_frame, text="", text_color="gray")
        self.status_label.pack(side="left", fill="x", expand=True, padx=10)
        
        # --- Suggestion Frame ---
        self.sugg_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.sugg_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        
        self.sugg_label = ctk.CTkLabel(self.sugg_frame, text="最新進出場建議: 尚未分析", font=("Microsoft JhengHei", 18, "bold"))
        self.sugg_label.pack(pady=15)
        
        # --- Main Tabview ---
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        self.tab_chart = self.tabview.add("📊 K線圖與指標")
        self.tab_fundamentals = self.tabview.add("🏢 基本面與財報")
        self.tab_backtest = self.tabview.add("📈 策略回測報告")
        
        self.setup_chart_tab()
        self.setup_fundamentals_tab()
        self.setup_backtest_tab()
        
        self.bind('<Return>', lambda event: self.on_search_clicked())

    def setup_chart_tab(self):
        self.tab_chart.grid_columnconfigure(0, weight=1)
        self.tab_chart.grid_rowconfigure(0, weight=1)
        self.chart_container = ctk.CTkFrame(self.tab_chart)
        self.chart_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
    def setup_fundamentals_tab(self):
        self.tab_fundamentals.grid_columnconfigure(0, weight=1)
        self.tab_fundamentals.grid_rowconfigure(0, weight=1)
        self.fund_textbox = ctk.CTkTextbox(self.tab_fundamentals, font=("Consolas", 16))
        self.fund_textbox.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
    def setup_backtest_tab(self):
        self.tab_backtest.grid_columnconfigure(0, weight=1)
        self.tab_backtest.grid_rowconfigure(0, weight=1)
        self.backtest_textbox = ctk.CTkTextbox(self.tab_backtest, font=("Consolas", 16))
        self.backtest_textbox.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
    def on_search_clicked(self):
        ticker = self.ticker_entry.get().strip().upper()
        if not ticker:
            self.status_label.configure(text="請輸入股票代號！", text_color="red")
            return
            
        period = self.period_combo.get()
        self.status_label.configure(text=f"正在分析 {ticker} ...這可能需要幾十秒鐘", text_color="yellow")
        self.sugg_label.configure(text="最新進出場建議: 分析資料處理中...")
        
        self.fund_textbox.delete("0.0", "end")
        self.backtest_textbox.delete("0.0", "end")
        
        for widget in self.chart_container.winfo_children():
            widget.destroy()
            
        threading.Thread(target=self.run_analysis, args=(ticker, period), daemon=True).start()
        
    def run_analysis(self, ticker, period):
        from data_loader import get_yf_ticker
        try:
            stock = get_yf_ticker(ticker)
            df = stock.history(period=period)
        except Exception as e:
            self.update_status(f"獲取歷史股價失敗: {e}", "red")
            return
            
        if df is None or df.empty:
            self.update_status(f"找不到 {ticker} 的歷史資料，請確認代號是否正確。", "red")
            return
            
        try:
            df = calculate_dmpi(df)
            df = generate_signals(df)
        except Exception as e:
            self.update_status(f"計算指標發生錯誤: {e}", "red")
            return
            
        try:
            backtest_res = run_backtest(df)
            rec = get_latest_recommendation(df)
        except Exception as e:
            self.update_status(f"回測引擎發生錯誤: {e}", "red")
            return
            
        try:
            info = fetch_stock_info(ticker)
            financials = fetch_financials(ticker)
        except Exception as e:
            info = {"Error": str(e)}
            financials = {}
        
        self.after(0, self.update_ui_post_analysis, ticker, df, info, financials, backtest_res, rec)
        
    def update_status(self, msg, color):
        self.after(0, lambda: self.status_label.configure(text=msg, text_color=color))

    def update_ui_post_analysis(self, ticker, df, info, financials, backtest_res, rec):
        self.status_label.configure(text=f"{ticker} 分析完成！", text_color="green")
        
        plot_stock_chart(self.chart_container, df, ticker)
        
        # ==== 更新建議 ====
        action = rec.get('action', '')
        reason = rec.get('reason', '')
        price = rec.get('price', '')
        price_str = f" @ {price:.2f}" if price else ""
        
        sugg_color = "white"
        if "Buy" in action: sugg_color = "#44ff44"
        elif "Sell" in action: sugg_color = "#ff4444"
        elif "Hold" in action: sugg_color = "orange"
        
        self.sugg_label.configure(text=f"最新建議: {action}{price_str}  ({reason})", text_color=sugg_color)
        
        # ==== 更新基本面與財報 ====
        fund_text = f"========== 【 {ticker} 基本面摘要 】 ==========\n\n"
        for k, v in info.items():
            fund_text += f"  {k}: {v}\n"
            
        fund_text += "\n\n========== 【 年度財報 (部分摘要) 】 ==========\n"
        fs = financials.get('financials', pd.DataFrame())
        if not fs.empty:
            # 由於 yfinance 抓下來的財報欄位很多，我們取幾個關鍵字
            keywords = ["Total Revenue", "Net Income", "Gross Profit", "Operating Income"]
            for row in fs.index:
                if any(kw in str(row) for kw in keywords):
                    fund_text += f"\n{row}:\n"
                    # 最多抓最新3個年度
                    cols = fs.columns[:3]
                    for col in cols:
                        val = fs.loc[row, col]
                        date_str = col.strftime('%Y-%m-%d') if hasattr(col, 'strftime') else str(col)
                        fund_text += f"    [{date_str}] : {val:,.0f} \n"
        else:
            fund_text += "無財報資料或該資產為 ETF / 指數。\n"
            
        self.fund_textbox.insert("0.0", fund_text)
        
        # ==== 更新回測結果 ====
        bt_text = f"========== 【 DMPI 策略 回測報告 ({ticker}) 】 ==========\n\n"
        bt_text += f"> 初始資金: {backtest_res['initial_capital']:,.2f}\n"
        bt_text += f"> 最終資金: {backtest_res['final_capital']:,.2f}\n"
        bt_text += "-"*40 + "\n"
        bt_text += f"> 總報酬率: {backtest_res['total_return_pct']:.2f} %\n"
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
                    bt_text += f"[ {date_str} ] 🔺 買進 (Buy)  | 價格: {t['Price']:,.2f}\n"
                else:
                    prof = t.get('Profit_%', 0)
                    prof_mark = "🟢" if prof > 0 else "🔴"
                    bt_text += f"[ {date_str} ] 🔻 賣出 (Sell) | 價格: {t['Price']:,.2f} | 獲利: {prof_mark} {prof:+.2f} %\n"
                    
        self.backtest_textbox.insert("0.0", bt_text)

if __name__ == "__main__":
    app = App()
    app.mainloop()
