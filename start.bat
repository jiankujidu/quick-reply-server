@echo off
chcp 65001 >nul
title 快回复后端服务器 v4.0

echo ======================================
echo   快回复后端服务器 v4.0 - 团队协作版
echo ======================================
echo.

pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERROR] 依赖安装失败
    pause
    exit /b 1
)

echo [OK] 依赖安装完成
echo [STARTING] 启动服务器...
python server.py

pause
