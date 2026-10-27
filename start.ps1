# 课堂资料库 - PowerShell 一键启动脚本
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
$pythonExe = Join-Path $backendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "[错误] 未检测到后端虚拟环境: backend\.venv" -ForegroundColor Red
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
Start-Process "cmd.exe" -ArgumentList "/c `"$backendDir\run.bat`""

Write-Host "[3/3] 正在启动前端服务 (Vite, 端口 5173)..." -ForegroundColor White
Start-Process "cmd.exe" -ArgumentList "/c `"$frontendDir\run.bat`""

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "服务正在启动：" -ForegroundColor Green
Write-Host "  - 前端地址: http://localhost:5173" -ForegroundColor White
Write-Host "  - 后端接口: http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Cyan

Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"
Write-Host "`n已自动在默认浏览器中打开前端界面。若需停止服务，请运行 ./stop.ps1 或双击 stop.bat。" -ForegroundColor Gray
