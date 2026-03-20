import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import pandas as pd
import customtkinter as ctk
import mplfinance as mpf
import warnings
warnings.filterwarnings('ignore') # 忽略 mplfinance 的有些警告

def plot_stock_chart(master_frame, df: pd.DataFrame, ticker: str, indicator_name: str = "DMPI"):
    """
    在指定的 customtkinter frame 內繪製 K線圖與所選的技術指標
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

    # 確保資料為 float
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df_plot[col] = df_plot[col].astype(float)

    apds = []
    
    # === 標記進出場訊號 ===
    if 'Signal' in df_plot.columns:
        buy_signals = df_plot['Signal'] == 1
        sell_signals = df_plot['Signal'] == -1
        
        buy_markers = df_plot['Low'].copy()
        buy_markers[~buy_signals] = float('nan')
        # 標記在略低於低點的地方 (往下拉一點)
        buy_markers = buy_markers * 0.98  
        
        sell_markers = df_plot['High'].copy()
        sell_markers[~sell_signals] = float('nan')
        # 標記在略高於高點的地方 (往上拉一點)
        sell_markers = sell_markers * 1.02  
        
        if buy_signals.any():
            apds.append(mpf.make_addplot(buy_markers, type='scatter', markersize=150, marker='^', color='#00ff00', panel=0))
        if sell_signals.any():
            apds.append(mpf.make_addplot(sell_markers, type='scatter', markersize=150, marker='v', color='#ff0000', panel=0))

    # === 動態繪出對應的副圖指標 ===
    if indicator_name == "自創 DMPI" and 'DMPI' in df_plot.columns:
        apds.append(mpf.make_addplot(df_plot['DMPI'], panel=2, color='orange', ylabel='DMPI'))
        # 畫零軸
        apds.append(mpf.make_addplot([0]*len(df_plot), panel=2, color='white', linestyle='dashed', alpha=0.5))
        
    elif indicator_name == "RSI" and 'RSI' in df_plot.columns:
        apds.append(mpf.make_addplot(df_plot['RSI'], panel=2, color='purple', ylabel='RSI (14)'))
        # RSI 輔助線 30 (超賣區) 與 70 (超買區)
        apds.append(mpf.make_addplot([70]*len(df_plot), panel=2, color='red', linestyle='dashed', alpha=0.6))
        apds.append(mpf.make_addplot([30]*len(df_plot), panel=2, color='green', linestyle='dashed', alpha=0.6))
        
    elif indicator_name == "MACD" and 'MACD' in df_plot.columns:
        # MACD 包含 MACD 線 (快-慢), Signal 線, Hist 柱狀圖
        colors = ['red' if val < 0 else 'green' for val in df_plot['MACD_Hist']]
        apds.append(mpf.make_addplot(df_plot['MACD'], panel=2, color='#00bfff', ylabel='MACD'))
        apds.append(mpf.make_addplot(df_plot['MACD_Signal'], panel=2, color='orange'))
        apds.append(mpf.make_addplot(df_plot['MACD_Hist'], type='bar', panel=2, color=colors, alpha=0.5))

    # 針對 Windows 中文顯示與深色樣式
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei'] 
    plt.rcParams['axes.unicode_minus'] = False
    
    # 定義自訂客製化美化風格 (Dark Mode)
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
        facecolor='#1e1e1e',     # K線圖底色
        figcolor='#1e1e1e',      # 整個圖片的外圍底色
        y_on_right=True,
        rc={'text.color': 'white', 'axes.labelcolor': 'white', 
            'xtick.color': 'white', 'ytick.color': 'white'}
    )
    
    # 建立 mplfinance 畫布
    has_subpanel = indicator_name in ["自創 DMPI", "RSI", "MACD"]
    fig, axes = mpf.plot(
        df_plot,
        type='candle',
        volume=True,
        addplot=apds,
        style=s,
        title=f"\n{ticker} 股價與 {indicator_name} 分析",
        ylabel='股價 (Price)',
        ylabel_lower='成交量 (Vol)',
        returnfig=True,
        figsize=(12, 7),
        panel_ratios=(4, 1, 1.5) if has_subpanel else (3, 1),
        tight_layout=True
    )
    
    # 將 matplotlib figure 嵌入 Tkinter (customtkinter)
    canvas = FigureCanvasTkAgg(fig, master=master_frame)
    
    # 建立原生的 Matplotlib 互動控制列 (可縮放、平移)
    toolbar = NavigationToolbar2Tk(canvas, master_frame)
    toolbar.update()
    
    canvas.draw()
    canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
    
    # 清理避免記憶體洩漏
    plt.close(fig)
