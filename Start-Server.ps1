# 快回复服务器 - PowerShell启动脚本
# 使用方法：右键点击 → "使用 PowerShell 运行"

Write-Host "================================" -ForegroundColor Cyan
Write-Host "快回复服务器 - PowerShell启动" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查Python
Write-Host "[1/5] 检查 Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python 已安装: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ 未找到 Python！请安装 Python 并添加到 PATH" -ForegroundColor Red
    Read-Host "按 Enter 退出"
    exit 1
}
Write-Host ""

# 2. 检查端口5000
Write-Host "[2/5] 检查端口 5000..." -ForegroundColor Yellow
$portInUse = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Host "⚠️  端口 5000 已被占用，尝试释放..." -ForegroundColor Yellow
    Stop-Process -Id $portInUse.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Write-Host "✅ 端口已释放" -ForegroundColor Green
} else {
    Write-Host "✅ 端口 5000 可用" -ForegroundColor Green
}
Write-Host ""

# 3. 检查server.py
Write-Host "[3/5] 检查 server.py..." -ForegroundColor Yellow
if (-not (Test-Path "D:\quick-reply-server\server.py")) {
    Write-Host "❌ 未找到 server.py！" -ForegroundColor Red
    Write-Host "    请确认路径：D:\quick-reply-server\server.py" -ForegroundColor Red
    Read-Host "按 Enter 退出"
    exit 1
}
Write-Host "✅ server.py 已找到" -ForegroundColor Green
Write-Host ""

# 4. 检查依赖
Write-Host "[4/5] 检查依赖包..." -ForegroundColor Yellow
Set-Location D:\quick-reply-server
pip install -q flask flask-cors 2>$null
Write-Host "✅ 依赖检查完成" -ForegroundColor Green
Write-Host ""

# 5. 启动服务器
Write-Host "[5/5] 启动服务器..." -ForegroundColor Yellow
Write-Host "================================" -ForegroundColor Cyan
Write-Host "服务器启动中..." -ForegroundColor Green
Write-Host "访问地址： <ADDRESS_REDACTED>
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

python server.py

Read-Host "服务器已停止，按 Enter 退出"
