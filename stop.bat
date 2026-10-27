@echo off
title 课堂资料库 - 一键停止

echo ========================================================
echo               课堂资料库 (DailyManager) 停止服务
echo ========================================================
echo.

echo 正在停止 8000 端口 (后端 FastAPI/uvicorn)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo 已终止进程 PID: %%a
)

echo 正在停止 5173 端口 (前端 Vite)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo 已终止进程 PID: %%a
)

echo.
echo [OK] 相关服务进程已清理完成。
echo ========================================================
pause
