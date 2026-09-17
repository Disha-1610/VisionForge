@echo off
setlocal
title VisionForge AI - Master Launcher
color 0B

set "ROOT=%~dp0"
set "FRONTEND=%ROOT%frontend"
set "BACKEND=%ROOT%backend"

echo ===============================================================================
echo                VISIONFORGE AI - INDUSTRIAL HARDWARE QA PLATFORM
echo ===============================================================================
echo.

echo [1/5] Verifying System Prerequisites...
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

echo [2/5] Preflight - freeing ports 5173 and 8000 from stale processes...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 5173,8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1
timeout /t 2 /nobreak >nul
echo [OK] Ports clean.
echo.

echo [3/5] Mobile HTTPS tunnel setup...
choice /c YN /n /m "Enable Cloudflare HTTPS tunnel for mobile camera testing? (Y/N): "
if errorlevel 2 (
    echo [SKIP] Tunnel disabled. Using localhost / LAN IP only.
    if exist "%FRONTEND%\.env" powershell -NoProfile -Command "(Get-Content '%FRONTEND%\.env' | Where-Object { $_ -notmatch '^VITE_PUBLIC_URL=' }) | Set-Content '%FRONTEND%\.env'" >nul 2>&1
    goto :no_tunnel
)

echo Starting Cloudflare tunnel in a separate window...
if exist "%FRONTEND%\.tunnel.url" del "%FRONTEND%\.tunnel.url" >nul 2>&1
start "VisionForge - Mobile HTTPS Tunnel" cmd /k "cd /d %FRONTEND% && npm run tunnel"

set /a WAIT=0
:wait_tunnel
if exist "%FRONTEND%\.tunnel.url" goto :tunnel_ready
timeout /t 1 /nobreak >nul
set /a WAIT+=1
if %WAIT% LSS 90 goto :wait_tunnel
echo [WARN] Tunnel did not report a URL in time - continuing anyway.
goto :no_tunnel

:tunnel_ready
set /p TUNNEL_URL=<"%FRONTEND%\.tunnel.url"
if not defined TUNNEL_URL set "TUNNEL_URL=<unknown>"
echo [OK] Mobile HTTPS URL: %TUNNEL_URL%
echo.

:no_tunnel
echo [4/5] Launching FastAPI Backend Server on port 8000...
start "VisionForge - Backend Server (:8000)" cmd /k "cd /d %BACKEND% && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul
echo [OK] Backend process initialized.
echo.

echo [5/5] Launching Vite React Frontend on port 5173...
start "VisionForge - Frontend Workstation (:5173)" cmd /k "cd /d %FRONTEND% && npm run dev"
echo.

echo ===============================================================================
echo [SUCCESS] VisionForge AI is now running!
echo  - Frontend Workstation: http://localhost:5173
echo  - Backend API:          http://localhost:8000
echo  - API Swagger Docs:     http://localhost:8000/docs
if defined TUNNEL_URL (
echo  - Mobile HTTPS URL:     %TUNNEL_URL%
echo    (Scan the QR in the app on your phone to test the live camera)
)
echo ===============================================================================
echo Opening browser to http://localhost:5173 in 2 seconds...
timeout /t 2 /nobreak >nul
start http://localhost:5173

echo.
echo Keep the Backend, Frontend and Tunnel windows open while testing.
echo You can close this launcher window.
echo.
pause
endlocal