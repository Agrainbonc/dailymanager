# -*- coding: utf-8 -*-
from pathlib import Path

backend_run_content = """@echo off
title DailyManager - 后端服务 (8000)
cd /d "%~dp0"
echo 正在启动后端服务 (FastAPI, 端口 8000)...
echo.
.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
if errorlevel 1 (
    echo.
    echo 后端服务异常退出！
    pause
)
"""

frontend_run_content = """@echo off
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
"""

start_bat_content = """@echo off
title 课堂资料库 - 一键启动

echo ========================================================
echo               课堂资料库 (DailyManager) 一键启动
echo ========================================================
echo.

set ROOT_DIR=%~dp0
set BACKEND_DIR=%ROOT_DIR%backend
set FRONTEND_DIR=%ROOT_DIR%frontend
set PYTHON_EXE=%BACKEND_DIR%\\.venv\\Scripts\\python.exe

if not exist "%PYTHON_EXE%" (
    echo [错误] 未检测到后端虚拟环境: backend\\.venv
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
start "DailyManager-Backend" "%BACKEND_DIR%\\run.bat"

echo [3/3] 正在启动前端服务 (Vite, 端口 5173)...
start "DailyManager-Frontend" "%FRONTEND_DIR%\\run.bat"

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
"""

stop_bat_content = """@echo off
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
"""

start_ps1_content = """# 课堂资料库 - PowerShell 一键启动脚本
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "              课堂资料库 (DailyManager) 一键启动" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$rootDir = $PSScriptRoot
if (-not $rootDir) {
    $rootDir = (Get-Location).Path
}
$backendDir = Join-Path $rootDir "backend"
$frontendDir = Join-Path $rootDir "frontend"
$pythonExe = Join-Path $backendDir ".venv\\Scripts\\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "[错误] 未检测到后端虚拟环境: backend\\.venv" -ForegroundColor Red
    Write-Host "请确认 backend 目录下是否存在 .venv 虚拟环境。" -ForegroundColor Yellow
    exit 1
}

# 1. 检查 9001 ASR 服务
Write-Host "[1/3] 检测 9001 端口 ASR 识别服务..." -ForegroundColor White
$asrConn = Get-NetTCPConnection -LocalPort 9001 -State Listen -ErrorAction SilentlyContinue
if ($asrConn) {
    Write-Host "[OK] 9001 端口 ASR 服务已就绪！" -ForegroundColor Green
} else {
    Write-Host "[提示] 9001 端口未检测到 ASR 服务监听。" -ForegroundColor Yellow
    Write-Host "       如需进行课堂录音转文字，请先启动 ASR 语音模型服务。" -ForegroundColor Yellow
}

# 2. 启动后端与前端独立窗口
Write-Host "`n[2/3] 正在启动后端服务 (FastAPI, 端口 8000)..." -ForegroundColor White
Start-Process "cmd.exe" -ArgumentList "/c `"$backendDir\\run.bat`""

Write-Host "[3/3] 正在启动前端服务 (Vite, 端口 5173)..." -ForegroundColor White
Start-Process "cmd.exe" -ArgumentList "/c `"$frontendDir\\run.bat`""

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "服务正在启动：" -ForegroundColor Green
Write-Host "  - 前端地址: http://localhost:5173" -ForegroundColor White
Write-Host "  - 后端接口: http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Cyan

Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"
Write-Host "`n已自动在默认浏览器中打开前端界面。若需停止服务，请运行 ./stop.ps1 或双击 stop.bat。" -ForegroundColor Gray
"""

stop_ps1_content = """# 课堂资料库 - 一键停止服务
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "              课堂资料库 (DailyManager) 停止服务" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$ports = @(8000, 5173)
foreach ($port in $ports) {
    Write-Host "检查端口 $port 上的监听进程..." -ForegroundColor White
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($p in $pids) {
            try {
                Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
                Write-Host "已终止端口 $port 上的进程 (PID: $p)" -ForegroundColor Green
            } catch {
                Write-Host "终止 PID $p 失败: $_" -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "端口 $port 当前未被占用。" -ForegroundColor Gray
    }
}

Write-Host "`n[OK] 服务清理完毕。" -ForegroundColor Green
"""

files = [
    ("backend/run.bat", backend_run_content),
    ("frontend/run.bat", frontend_run_content),
    ("start.bat", start_bat_content),
    ("stop.bat", stop_bat_content),
]

for filename, content in files:
    with open(filename, "w", encoding="gbk", newline="\r\n") as f:
        f.write(content)
    print(f"Written {filename} (GBK)")

ps_files = [
    ("start.ps1", start_ps1_content),
    ("stop.ps1", stop_ps1_content),
]

for filename, content in ps_files:
    with open(filename, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(content)
    print(f"Written {filename} (UTF-8 with BOM)")

print("All batch and powershell scripts generated successfully!")
