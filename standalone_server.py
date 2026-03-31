import os
import sys
import uvicorn
import webbrowser
from threading import Timer
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# 修正 PyInstaller 打包後的檔案路徑抓取
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# 將專案目錄加入路徑，確保能正確 import backend.api
sys.path.append(os.path.abspath("."))

# 延遲載入以確保路徑已設置
import backend.api
from backend.api import app as api_app

# --- 外部維護與持久化邏輯 ---
# 取得 EXE 實際所在的資料夾 (非臨時解壓目錄)
if hasattr(sys, '_MEIPASS'):
    EXE_HOME = os.path.dirname(sys.executable)
else:
    EXE_HOME = os.path.abspath(".")

def sync_data_file(filename):
    """
    確保外部 (EXE 旁) 有檔案可供維護。
    如果外部沒有，就從內部 (MEIPASS) 複製一份出去當模板。
    """
    external_path = os.path.join(EXE_HOME, filename)
    internal_path = resource_path(filename)
    
    if not os.path.exists(external_path) and os.path.exists(internal_path):
        import shutil
        try:
            shutil.copy2(internal_path, external_path)
            print(f"[Standalone] 已產生外部維護檔案: {filename}")
        except Exception as e:
            print(f"[Standalone] 無法產生外部檔案 {filename}: {e}")
    
    return Path(external_path)

# 強制將 API 的數據路徑指向 EXE 旁邊，實現「可編輯」與「可存檔」
print(f"[Standalone] 資料持久化目錄: {EXE_HOME}")
backend.api._CSV_PATH = sync_data_file("股票代號表.csv")
backend.api.WATCHLIST_FILE = sync_data_file("watchlist_groups.json")

# 如果 API 有 portfolio.json (假設路徑在 BASE_DIR)，也要重導向
if hasattr(backend.api, 'PORTFOLIO_FILE'):
     backend.api.PORTFOLIO_FILE = sync_data_file("portfolio.json")

# 重新載入股票名稱地圖 (因為 _CSV_PATH 改變了)
if backend.api._CSV_PATH.exists():
    import pandas as pd
    print(f"[Standalone] 正在載入外部股票清單: {backend.api._CSV_PATH}")
    df_names = pd.read_csv(backend.api._CSV_PATH, dtype=str)
    for _, row in df_names.iterrows():
        code = str(row["代號"]).strip()
        name = str(row["名稱"]).strip()
        backend.api._STOCK_NAMES[code] = name

# --- 靜態網頁掛載 ---
# 檢查靜態網頁路徑是否存在
static_dir = resource_path("frontend/out")
if os.path.exists(static_dir):
    print(f"[Standalone] 正在掛載靜態網頁資源: {static_dir}")
    # 將 "/" 網頁請求導向靜態檔案
    api_app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
else:
    print(f"[Standalone] 警告: 找不到靜態網頁資料夾 ({static_dir})")

def open_browser():
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    print("==========================================")
    print("   冰可樂加熱 - 獨立運行伺服器 (Standalone)")
    print("==========================================")
    
    # 2秒後自動開啟瀏覽器
    Timer(2.0, open_browser).start()
    
    # 啟動 FastAPI 服務
    uvicorn.run(api_app, host="127.0.0.1", port=8000)
