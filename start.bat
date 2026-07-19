@echo off
title Backupper - Minecraft Backup Runner
chcp 65001 >nul

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% equ 0 goto :run

echo ========================================
echo   Python 未安装或不在 PATH 中
echo ========================================
echo.
echo   [1] 从 Microsoft Store 安装 Python 3
echo   [2] 从 python.org 下载安装包
echo   [3] 使用 winget 安装
echo   [4] 退出
echo.
choice /c 1234 /m "请选择安装方式"

if %errorlevel% equ 1 start ms-windows-store://pdp/?productid=9PJPW5LDXLZ5
if %errorlevel% equ 2 start https://www.python.org/downloads/
if %errorlevel% equ 3 (
    winget install Python.Python.3.12 --silent 2>nul
    if %errorlevel% neq 0 (
        echo winget 安装失败，请手动安装
        start https://www.python.org/downloads/
    )
)
echo 安装完成后请重新运行本程序
pause
exit /b

:run
echo Starting Backupper v1.0.0...
python backup_runner.py
pause
