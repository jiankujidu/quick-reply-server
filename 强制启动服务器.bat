@echo off
chcp 65001 >nul
echo ================================
echo 快回复服务器 - 强制启动脚本
echo ================================
echo.

REM 1. 检查Python是否可用
echo [1/5] 检查 Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未找到 Python！请安装 Python 并添加到 PATH
    pause
    exit /b 1
)
echo ✅ Python 已安装
python --version
echo.

REM 2. 检查端口是否被占用
echo [2/5] 检查端口 5000...
netstat -ano | findstr :5000 >nul 2>&1
if %errorlevel% equ 0 (
    echo ⚠️  端口 5000 已被占用，尝试释放...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 2 >nul
    echo ✅ 端口已释放
) else (
    echo ✅ 端口 5000 可用
)
echo.

REM 3. 检查 server.py 是否存在
echo [3/5] 检查 server.py...
if not exist "D:\quick-reply-server\server.py" (
    echo ❌ 未找到 server.py！
    echo    请确认路径：D:\quick-reply-server\server.py
    pause
    exit /b 1
)
echo ✅ server.py 已找到
echo.

REM 4. 安装/检查依赖
echo [4/5] 检查依赖包...
cd /d D:\quick-reply-server
pip install -q flask flask-cors 2>nul
echo ✅ 依赖检查完成
echo.

REM 5. 启动服务器
echo [5/5] 启动服务器...
echo ================================
echo 服务器启动中...（不要关闭此窗口）
echo 访问地址： <ADDRESS_REDACTED>
echo ================================
echo.
python server.py
pause
