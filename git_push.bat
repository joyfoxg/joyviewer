@echo off
setlocal enabledelayedexpansion
title JoyViewer Git Pusher

echo ===================================================
powershell -Command "Write-Host '     JoyViewer Git Auto-Pusher     ' -ForegroundColor Black -BackgroundColor Green"
echo ===================================================
echo.

:: 1. Check if Git is installed
where git >nul 2>nul
if %errorlevel% neq 0 (
    powershell -Command "Write-Host '[ERROR] Git is not installed or not in PATH!' -ForegroundColor Red"
    echo Please install Git and make sure it is added to your environment variables.
    goto ERROR_EXIT
)

:: 2. Detect active branch
for /f "tokens=*" %%i in ('git branch --show-current 2^>nul') do set BRANCH=%%i
if "%BRANCH%"=="" (
    powershell -Command "Write-Host '[WARNING] Could not detect current branch. Defaulting to standard push.' -ForegroundColor Yellow"
    set BRANCH=main
) else (
    powershell -Command "Write-Host '[+] Active branch detected: %BRANCH%' -ForegroundColor Green"
)
echo.

:: 3. Show status of modified files
powershell -Command "Write-Host '[*] Checking modified files...' -ForegroundColor Cyan"
git status -s
echo.

:: 4. Prompt for commit message
set "MSG="
set /p MSG="Enter commit message (Press Enter for default: 'Update JoyViewer compilation and scripts'): "
if "!MSG!"=="" set MSG=Update JoyViewer compilation and scripts

:: 5. Git workflow
powershell -Command "Write-Host '[*] Staging files (git add)...' -ForegroundColor Yellow"
git add .
if %errorlevel% neq 0 (
    powershell -Command "Write-Host '[ERROR] Failed to stage files!' -ForegroundColor Red"
    goto ERROR_EXIT
)

powershell -Command "Write-Host '[*] Committing changes (git commit)...' -ForegroundColor Yellow"
git commit -m "!MSG!"
if %errorlevel% neq 0 (
    powershell -Command "Write-Host '[WARNING] Nothing to commit or commit failed. Proceeding to push anyway...' -ForegroundColor Yellow"
)

powershell -Command "Write-Host '[*] Pushing to remote (git push origin %BRANCH%)...' -ForegroundColor Yellow"
git push origin %BRANCH%
if %errorlevel% neq 0 (
    powershell -Command "Write-Host '[ERROR] Failed to push changes to remote!' -ForegroundColor Red"
    goto ERROR_EXIT
)

echo.
echo ===================================================
powershell -Command "Write-Host '    GIT PUSH COMPLETED SUCCESSFULLY!    ' -ForegroundColor Black -BackgroundColor Green"
echo ===================================================
echo [Branch] %BRANCH%
echo [Message] !MSG!
echo.
pause
exit /b 0

:ERROR_EXIT
echo.
echo ===================================================
powershell -Command "Write-Host '          GIT PUSH FAILED!           ' -ForegroundColor Black -BackgroundColor Red"
echo ===================================================
echo.
pause
exit /b 1
