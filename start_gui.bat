@echo off
title WhatsApp AI Platform - GUI Launcher
echo ========================================================
echo   Starting WhatsApp AI Automation Platform GUI
echo ========================================================
echo.

:: 1. Check if backend is already running
netstat -ano | findstr :8000 >nul
if %errorlevel% equ 0 (
    echo [OK] Backend API is already running on port 8000.
) else (
    echo [..] Starting Backend API Server (FastAPI)...
    start "Backend API (FastAPI)" cmd /k ".venv\Scripts\python.exe -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload"
)

:: 2. Check if web GUI is already running
netstat -ano | findstr :5173 >nul
if %errorlevel% equ 0 (
    echo [OK] Web GUI is already running on port 5173.
) else (
    echo [..] Starting Web GUI (Vite + React)...
    start "Web GUI (Dashboard)" cmd /k "cd apps\web && npm run dev -- --host 0.0.0.0 --port 5173"
)

echo.
echo ========================================================
echo   Web GUI Dashboard: http://localhost:5173
echo   Backend API Docs:  http://localhost:8000/docs
echo ========================================================
echo Opening browser...
timeout /t 2 /nobreak >nul
start http://localhost:5173
