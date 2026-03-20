import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import customtkinter as ctk
import mplfinance as mpf
import warnings
warnings.filterwarnings('ignore') # 忽略 mplfinance 的有些警告

def plot_stock_chart(master_frame, df: pd.DataFrame, ticker: str):
    """
    在指定的 customtkinter frame 內繪製 K線圖與 DMPI 指標
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
    if 'DMPI' in df_plot.columns:
        apds.append(mpf.make_addplot(df_plot['DMPI'], panel=2, color='orange', secondary_y=False, ylabel='DMPI'))
        
        # 標記進出場訊號
        if 'Signal' in df_plot.columns:
            buy_signals = df_plot['Signal'] == 1
            sell_signals = df_plot['Signal'] == -1
            
            buy_markers = df_plot['Low'].copy()
            buy_markers[~buy_signals] = float('nan')
            buy_markers = buy_markers * 0.98  # 標記在略低於低點的地方
            
            sell_markers = df_plot['High'].copy()
            sell_markers[~sell_signals] = float('nan')
            sell_markers = sell_markers * 1.02  # 標記在略高於高點的地方
            
            # mplfinance scatter requires a size array or scalar
            if buy_signals.any():
                apds.append(mpf.make_addplot(buy_markers, type='scatter', markersize=100, marker='^', color='green', panel=0))
            if sell_signals.any():
                apds.append(mpf.make_addplot(sell_markers, type='scatter', markersize=100, marker='v', color='red', panel=0))

    # 針對 Windows 中文顯示
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei'] 
    plt.rcParams['axes.unicode_minus'] = False
    
    # 建立 mplfinance 畫布
    fig, axes = mpf.plot(
        df_plot,
        type='candle',
        volume=True,
        addplot=apds,
        style='mike',
        title=f"{ticker} 股價與 DMPI 分析",
        ylabel='Price',
        ylabel_lower='Volume',
        returnfig=True,
        figsize=(10, 6),
        panel_ratios=(4, 1, 1) if 'DMPI' in df_plot.columns else (3, 1),
        tight_layout=True
    )
    
    # 將 matplotlib figure 嵌入 Tkinter (customtkinter)
    canvas = FigureCanvasTkAgg(fig, master=master_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
    
    # 清理避免記憶體洩漏
    plt.close(fig)
