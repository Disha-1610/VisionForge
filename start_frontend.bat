@echo off
title VisionForge - Vite React Frontend
color 0B

echo ===============================================================================
echo                VISIONFORGE AI - VITE REACT FRONTEND (:5173)
echo ===============================================================================
cd /d "%~dp0frontend"
echo Working Directory: %CD%
echo Starting Vite development server...
echo Frontend UI URL: http://localhost:5173
echo.
npm run dev
pause
