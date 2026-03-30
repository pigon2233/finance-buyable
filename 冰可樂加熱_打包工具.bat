@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo ╔══════════════════════════════════════════════╗
echo ║   冰可樂加熱 - 打包發布工具 (Release Maker)║
echo ╚══════════════════════════════════════════════╝
echo.

set RELEASE_DIR=冰可樂加熱_發布版
if exist "%RELEASE_DIR%" (
    echo [!TIME!] 正在清理舊的發布資料夾...
    rmdir /s /q "%RELEASE_DIR%"
)

:: 1. Build Frontend
echo [!TIME!] [1/3] 正在編譯前端介面 (Next.js)...
cd frontend
call npm run build
if %errorlevel% neq 0 (
    echo.
    echo [錯誤] 前端編譯失敗！請檢查 Node.js 環境。
    pause
    exit /b %errorlevel%
)
cd ..

:: 2. Create Structure
echo [!TIME!] [2/3] 正在準備發布檔案結構...
mkdir "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%\backend"
mkdir "%RELEASE_DIR%\frontend\out"
mkdir "%RELEASE_DIR%\running_at_agent"

:: Copy Python code
copy *.py "%RELEASE_DIR%\"
copy backend\*.py "%RELEASE_DIR%\backend\"
copy requirements.txt "%RELEASE_DIR%\"
copy 股票代號表.csv "%RELEASE_DIR%\"
if exist watchlist_groups.json copy watchlist_groups.json "%RELEASE_DIR%\"
if exist running_at_agent\stocks.txt copy running_at_agent\stocks.txt "%RELEASE_DIR%\running_at_agent\"

:: Copy Frontend Build
xcopy /e /i /y frontend\out "%RELEASE_DIR%\frontend\out"

:: 3. Generate Launcher
echo [!TIME!] [3/3] 正在產生媽媽專用啟動程式...

(
echo @echo off
echo chcp 65001 ^>nul
echo echo ╔══════════════════════════════════════════════╗
echo echo ║   冰可樂加熱 - 尊榮極簡啟動器  v2.0         ║
echo echo ╚══════════════════════════════════════════════╝
echo echo.
echo :: Check Python
echo python --version ^>nul 2^>^&1
echo if %%errorlevel%% neq 0 (
echo     echo [錯誤] 找不到 Python！請先安裝 Python 3.10 以上版本。
echo     echo 建議下載網址: https://www.python.org/downloads/
echo     pause
echo     exit /b 1
echo )
echo.
echo :: Create Venv
echo if not exist "venv" (
echo     echo [!] 第一次運行，正在幫您準備環境，請稍候...
echo     python -m venv venv
echo     if %%errorlevel%% neq 0 (
echo         echo [錯誤] 無法建立虛擬環境。
echo         pause
echo         exit /b 1
echo     )
echo )
echo.
echo :: Install Requirements
echo if not exist "venv\.installed" (
echo     echo [!] 正在安裝必要的分析組件...
echo     venv\Scripts\python.exe -m pip install --upgrade pip ^>nul
echo     venv\Scripts\python.exe -m pip install -r requirements.txt
echo     if %%errorlevel%% neq 0 (
echo         echo [錯誤] 組件安裝失敗，請檢查網路連線。
echo         pause
echo         exit /b 1
echo     )
echo     echo installed ^> venv\.installed
echo )
echo.
echo echo [OK] 環境準備就緒！
echo echo [!] 正在啟動分析大腦，請稍候...
echo.
echo :: Auto-start browser
echo start cmd /c "timeout /t 5 /nobreak ^>nul ^&^& start http://localhost:8000"
echo.
echo :: Run Backend only (It serves UI too)
echo venv\Scripts\python.exe -m uvicorn backend.api:app --host 0.0.0.0 --port 8000
echo.
echo pause
) > "%RELEASE_DIR%\冰可樂加熱_點我啟動.bat"

echo.
echo ╔══════════════════════════════════════════════╗
echo ║   完成！請將 【%RELEASE_DIR%】 資料夾打包       ║
echo ║   傳送給媽媽使用即可。                         ║
echo ╚══════════════════════════════════════════════╝
echo.
pause
