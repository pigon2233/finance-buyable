@echo off
echo ╔══════════════════════════════════════════════╗
echo ║   冰可樂加熱 次世代交易儀表板  v2.0         ║
echo ║   Backend: FastAPI :8000                     ║
echo ║   Frontend: Next.js :3000                   ║
echo ╚══════════════════════════════════════════════╝
echo.

:: Start Python backend in background
echo [1/2] 啟動 FastAPI 後端...
start "FastAPI Backend" /B cmd /c ".\venv\Scripts\python.exe -m uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload"

:: Wait for backend
timeout /t 3 /nobreak >nul

:: Start Next.js frontend
echo [2/2] 啟動 Next.js 前端...
echo.
echo ► 自動打開瀏覽器訪問: http://localhost:3000
echo.
:: Delay open browser to wait for Next.js to be ready
start cmd /c "timeout /t 5 /nobreak >nul && start http://localhost:3000"

cd frontend
call npm run dev
