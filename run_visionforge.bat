@echo off
title VisionForge AI - Master Launcher
color 0B

echo ===============================================================================
echo                VISIONFORGE AI - INDUSTRIAL HARDWARE QA PLATFORM
echo ===============================================================================
echo [1/3] Verifying System Prerequisites...

where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found in system PATH. Please install Python 3.11+.
    pause
    exit /b 1
)

where npm >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js / npm not found in system PATH. Please install Node.js v18+.
    pause
    exit /b 1
)

echo [OK] Python and Node.js detected.
echo.

echo [2/3] Launching FastAPI Backend Server on port 8000...
start "VisionForge - Backend Server (:8000)" cmd /k "cd /d %~dp0backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

echo [OK] Backend process initialized. Waiting for startup...
timeout /t 3 /nobreak >nul

echo.
echo [3/3] Launching Vite React Frontend on port 5173...
start "VisionForge - Frontend Workstation (:5173)" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ===============================================================================
echo [SUCCESS] VisionForge AI is now running!
echo  - Frontend Workstation: http://localhost:5173
echo  - Backend API:          http://localhost:8000
echo  - API Swagger Docs:     http://localhost:8000/docs
echo ===============================================================================
echo Opening browser to http://localhost:5173 in 2 seconds...
timeout /t 2 /nobreak >nul
start http://localhost:5173

echo.
echo Both servers are active in separate terminal windows.
echo Keep those windows open while testing. You can close this launcher window.
echo.
pause
