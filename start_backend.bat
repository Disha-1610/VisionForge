@echo off
title VisionForge - FastAPI Backend Server
color 0A

echo ===============================================================================
echo                VISIONFORGE AI - FASTAPI BACKEND SERVER (:8000)
echo ===============================================================================
cd /d "%~dp0backend"
echo Working Directory: %CD%
echo Starting Uvicorn server with hot-reload...
echo Backend API URL: http://localhost:8000
echo API Swagger Docs: http://localhost:8000/docs
echo.
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause
