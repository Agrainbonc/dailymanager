@echo off
title DailyManager - 前端服务 (5173)
cd /d "%~dp0"
echo 正在启动前端开发服务 (Vite, 端口 5173)...
echo.
call npm run dev
if errorlevel 1 (
    echo.
    echo 前端服务异常退出！
    pause
)
