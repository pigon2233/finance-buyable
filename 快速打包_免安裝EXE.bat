@echo off
setlocal
echo ==========================================
echo   冰可樂加熱 - 外掛式一鍵打包工具 (Standalone)
echo   目標: 在不破壞原始碼的情況下產出免安裝 EXE
echo ==========================================

:: 1. 檢查必要環境
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [錯誤] 找不到 npm！請確保已安裝 Node.js。
    pause
    exit /b 1
)

where pip >nul 2>nul
if %errorlevel% neq 0 (
    echo [錯誤] 找不到 pip！請確保已安裝 Python。
    pause
    exit /b 1
)

:: 2. 影子編譯前端 (Static Export)
echo [1/4] 正在進行前端影印編譯 (Static Export)...
cd frontend

:: 安全備份原始設定
if exist "next.config.ts" (
    copy /y "next.config.ts" "next.config.ts.bak" >nul
)

:: 寫入暫時的導出設定
echo import type { NextConfig } from "next"; const nextConfig: NextConfig = { output: 'export', images: { unoptimized: true } }; export default nextConfig; > next.config.ts

:: 執行編譯
echo 正在產生靜態網頁檔案 (npm run build)...
call npm run build

:: 還原原始設定
if exist "next.config.ts.bak" (
    move /y "next.config.ts.bak" "next.config.ts" >nul
)

cd ..

:: 3. 準備 Python 環境
echo [2/4] 正在檢查並安裝打包工具 (PyInstaller)...
pip install pyinstaller

:: 4. 進行封裝
echo [3/4] 正在封裝為獨立 EXE 執行檔...
echo 預計耗時 1-3 分鐘，請稍候...

:: 打包參數說明:
:: --onefile: 產生單一 EXE
:: --windowed: 執行時不顯示 Console 黑視窗
:: --add-data: 將靜態資源打包入內 (路徑格式: 來源;目的)
:: --icon: (若有圖示可加上)
pyinstaller --noconfirm --onefile --windowed --name "冰可樂加熱_交易版" ^
  --add-data "frontend/out;frontend/out" ^
  --add-data "股票代號表.csv;." ^
  --add-data "watchlist_groups.json;." ^
  --collect-all pandas ^
  standalone_server.py

:: 5. 完成
echo [4/4] 打包完成！
echo ------------------------------------------
echo 成果路徑: dist\冰可樂加熱_交易版.exe
echo ------------------------------------------
echo 請將該 EXE 傳送給媽媽使用即可 (不需再傳送其他資料夾)。
pause
