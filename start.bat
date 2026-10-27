@echo off
title 课堂资料库 - 一键启动

echo ========================================================
echo               课堂资料库 (DailyManager) 一键启动
echo ========================================================
echo.

set ROOT_DIR=%~dp0
set BACKEND_DIR=%ROOT_DIR%backend
set FRONTEND_DIR=%ROOT_DIR%frontend
set PYTHON_EXE=%BACKEND_DIR%\.venv\Scripts\python.exe

if not exist "%PYTHON_EXE%" (
    echo [错误] 未检测到后端虚拟环境: backend\.venv
    echo 请确认 backend 目录下是否存在 .venv 虚拟环境。
    echo.
    pause
    exit /b 1
)

echo [1/3] 检测 9001 端口 ASR 识别服务...
netstat -ano | findstr ":9001" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo [提示] 9001 端口未检测到 ASR 监听服务。
    echo        若需使用高精度课堂语音识别，请在开始转写前启动 ASR 服务。
) else (
    echo [OK] 9001 端口 ASR 语音服务已就绪！
)

echo.
echo [2/3] 正在启动后端服务 (FastAPI, 端口 8000)...
start "DailyManager-Backend" "%BACKEND_DIR%\run.bat"

echo [3/3] 正在启动前端服务 (Vite, 端口 5173)...
start "DailyManager-Frontend" "%FRONTEND_DIR%\run.bat"

echo.
echo ========================================================
echo 服务已在独立窗口中启动！
echo   - 前端访问地址: http://localhost:5173
echo   - 后端文档地址: http://127.0.0.1:8000/docs
echo.
echo 正在等待服务就绪 (约 3 秒) 并自动打开浏览器...
echo ========================================================

timeout /t 3 /nobreak >nul
start http://localhost:5173

echo.
echo 提示：若需停止服务，可双击运行 stop.bat 一键关闭相关窗口。
pause
