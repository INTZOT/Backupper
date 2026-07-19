@echo off
title Backupper - Minecraft Backup Runner

python --version >nul 2>&1
if %errorlevel% equ 0 goto run

echo ========================================
echo   Python not installed / not in PATH.
echo ========================================
echo.
echo   [1] Install from Microsoft Store
echo   [2] Download from python.org
echo   [3] Try winget install
echo   [4] Exit
echo.
choice /c 1234 /m "Choose"

if errorlevel 4 exit /b
if errorlevel 3 (
    winget install Python.Python.3.12 --silent
    goto end
)
if errorlevel 2 (
    start "" https://www.python.org/downloads/
    goto end
)
if errorlevel 1 (
    start "" https://apps.microsoft.com/detail/9PJPW5LDXLZ5
    goto end
)

:end
echo Please restart after installing Python.
pause
exit /b

:run
echo Starting Backupper v1.0.0...
python backup_runner.py
pause
