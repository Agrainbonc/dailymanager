# 课堂资料库 - 一键停止服务
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
