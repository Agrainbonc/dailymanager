@echo off
title DailyManager - 后端服务 (8000)
cd /d "%~dp0"
echo 正在启动后端服务 (FastAPI, 端口 8000)...
echo.
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
if errorlevel 1 (
    echo.
    echo 后端服务异常退出！
    pause
)
