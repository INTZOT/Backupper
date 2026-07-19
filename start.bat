@echo off
title Backupper - Minecraft Backup Runner

python --version >nul 2>&1
if %errorlevel% equ 0 goto run

echo ========================================
echo   Python not installed / not in PATH.
echo ========================================
echo.
choice /c yn /m "Open python.org download page? [y/n]"

if errorlevel 2 exit /b
start "" https://www.python.org/downloads/
echo Please install Python 3.9+ (recommended: 3.12) then restart.
pause
exit /b

:run
echo Starting Backupper v1.0.0...
python backup_runner.py
pause
