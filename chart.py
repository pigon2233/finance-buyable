import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import pandas as pd
import customtkinter as ctk
import mplfinance as mpf
import warnings
import logging

warnings.filterwarnings('ignore') # 忽略 mplfinance 的有些警告
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR) # 忽略找不到特定中文字型的洗頻警告

def plot_stock_chart(master_frame, df: pd.DataFrame, ticker: str):
    """
    在指定的 customtkinter frame 內同時繪製 K線圖與多個技術指標儀表板
    """
    for widget in master_frame.winfo_children():
        widget.destroy()
        
    if df is None or df.empty:
        label = ctk.CTkLabel(master_frame, text="無資料可供繪圖")
        label.pack(expand=True)
        return

    df_plot = df.copy()
    if not isinstance(df_plot.index, pd.DatetimeIndex):
        df_plot.index = pd.to_datetime(df_plot.index)
        
    # 不強制裁切長度，讓 K 線圖完整呈現使用者所選的回測期間 (1y, 2y, 5y 等)
    # 使用者若覺得太擠，可以利用圖表下方的 Navigation Toolbar (放大鏡) 自行縮放觀看細節

    # 確保資料為 float，並填補指標空值避免繪圖崩潰
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df_plot[col] = df_plot[col].astype(float)
        
    for col in ['DMPI', 'RSI', 'MACD', 'MACD_Signal', 'MACD_Hist']:
        if col in df_plot.columns:
            df_plot[col] = df_plot[col].fillna(0)

    apds = []
    
    # === 標記進出場訊號 (以 DMPI 為主) ===
    if 'Signal' in df_plot.columns:
        buy_signals = df_plot['Signal'] == 1
        sell_signals = df_plot['Signal'] == -1
        
        buy_markers = df_plot['Low'].copy()
        buy_markers[~buy_signals] = float('nan')
        buy_markers = buy_markers * 0.98  
        
        sell_markers = df_plot['High'].copy()
        sell_markers[~sell_signals] = float('nan')
        sell_markers = sell_markers * 1.02  
        
        if buy_signals.any():
            apds.append(mpf.make_addplot(buy_markers, type='scatter', markersize=150, marker='^', color='#00ff00', panel=0))
        if sell_signals.any():
            apds.append(mpf.make_addplot(sell_markers, type='scatter', markersize=150, marker='v', color='#ff0000', panel=0))

    # === 動態繪出對應的副圖指標 ===
    panels_count = 2 # panel 0: K線, panel 1: Volume
    ratios = [4, 1]
    
    # DMPI (Panel 2)
    if 'DMPI' in df_plot.columns:
        colors_dmpi = ['#ff5555' if val > 0 else '#00ff00' for val in df_plot['DMPI']]
        apds.append(mpf.make_addplot(df_plot['DMPI'], type='bar', panel=panels_count, color=colors_dmpi, ylabel='DMPI 動能', alpha=0.7))
        apds.append(mpf.make_addplot([0]*len(df_plot), panel=panels_count, color='white', linestyle='dashed', alpha=0.5))
        panels_count += 1
        ratios.append(1)
        
    # RSI (Panel 3)
    if 'RSI' in df_plot.columns:
        apds.append(mpf.make_addplot(df_plot['RSI'], panel=panels_count, color='#c266ff', ylabel='RSI (14)'))
        apds.append(mpf.make_addplot([70]*len(df_plot), panel=panels_count, color='#ff5555', linestyle='dashed', alpha=0.6))
        apds.append(mpf.make_addplot([30]*len(df_plot), panel=panels_count, color='#00ff00', linestyle='dashed', alpha=0.6))
        panels_count += 1
        ratios.append(1)
        
    # MACD (Panel 4)
    if 'MACD' in df_plot.columns:
        colors_macd = ['#ff5555' if val > 0 else '#00ff00' for val in df_plot['MACD_Hist']]
        apds.append(mpf.make_addplot(df_plot['MACD'], panel=panels_count, color='#00bfff', ylabel='MACD'))
        apds.append(mpf.make_addplot(df_plot['MACD_Signal'], panel=panels_count, color='orange'))
        apds.append(mpf.make_addplot(df_plot['MACD_Hist'], type='bar', panel=panels_count, color=colors_macd, alpha=0.5))
        panels_count += 1
        ratios.append(1.5)

    # 解決 mplfinance 強制覆寫字型導致的中文亂碼問題，利用 rc 傳入中文字型
    mc = mpf.make_marketcolors(
        up='#ef5350', down='#26a69a',
        edge='inherit',
        wick={'up':'#ef5350', 'down':'#26a69a'},
        volume={'up':'#ef5350', 'down':'#26a69a'}
    )
    s  = mpf.make_mpf_style(
        marketcolors=mc,
        gridcolor='#333333',
        gridstyle='--',
        facecolor='#121212',     # K線圖底色改深一點
        figcolor='#121212',      # 整個圖片的外圍底色
        y_on_right=True,
        rc={
            'font.family': ['Microsoft JhengHei', 'sans-serif'],
            'axes.unicode_minus': False,
            'text.color': 'white', 
            'axes.labelcolor': 'white', 
            'xtick.color': 'white', 
            'ytick.color': 'white'
        }
    )
    
    # 建立 mplfinance 畫布
    fig, axes = mpf.plot(
        df_plot,
        type='candle',
        volume=True,
        addplot=apds,
        style=s,
        title=f"\n{ticker} 多指標綜合分析儀表板",
        ylabel='股價 (Price)',
        ylabel_lower='成交量 (Vol)',
        returnfig=True,
        figsize=(12, 10),
        panel_ratios=ratios,
        tight_layout=True
    )
    
    fig.patch.set_facecolor('#121212')
    
    # 將 matplotlib figure 嵌入 Tkinter (customtkinter)
    canvas = FigureCanvasTkAgg(fig, master=master_frame)
    toolbar = NavigationToolbar2Tk(canvas, master_frame)
    toolbar.update()
    
    canvas.draw()
    canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
    
    plt.close(fig)
