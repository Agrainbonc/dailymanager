param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$rootDir = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $rootDir "backend"
$frontendDir = Join-Path $rootDir "frontend"
$packageVenv = Join-Path $backendDir ".package-venv"
$packagePython = Join-Path $packageVenv "Scripts\python.exe"
$releaseDir = Join-Path $rootDir "release"
$workDir = Join-Path $rootDir "build\pyinstaller"
$specDir = Join-Path $rootDir "build"

Write-Host "[1/5] Building frontend..." -ForegroundColor Cyan
Push-Location $frontendDir
try {
    if (-not (Test-Path -LiteralPath (Join-Path $frontendDir "node_modules"))) {
        corepack pnpm install --frozen-lockfile
        if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
    }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
} finally {
    Pop-Location
}

Write-Host "[2/5] Preparing isolated packaging environment..." -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $packagePython)) {
    & $Python -m venv $packageVenv
}
& $packagePython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $packagePython -m pip install -r (Join-Path $backendDir "requirements.txt") pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Packaging dependency installation failed." }

Write-Host "[3/5] Bundling DailyManager..." -ForegroundColor Cyan
& $packagePython -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --noupx `
    --name "DailyManager" `
    --paths $backendDir `
    --add-data "$(Join-Path $frontendDir 'dist');frontend\dist" `
    --hidden-import dashscope.aigc.multimodal_conversation `
    --collect-all imageio_ffmpeg `
    --distpath $releaseDir `
    --workpath $workDir `
    --specpath $specDir `
    (Join-Path $backendDir "desktop.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

Write-Host "[4/5] Adding user guide..." -ForegroundColor Cyan
Copy-Item -LiteralPath (Join-Path $rootDir "README_WINDOWS.md") -Destination (Join-Path $releaseDir "DailyManager\使用说明.md") -Force

Write-Host "[5/5] Creating ZIP archive..." -ForegroundColor Cyan
$zipPath = Join-Path $releaseDir "DailyManager-Windows-x64.zip"
Compress-Archive -LiteralPath (Join-Path $releaseDir "DailyManager") -DestinationPath $zipPath -Force

Write-Host "Package ready: $zipPath" -ForegroundColor Green
