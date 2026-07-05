@echo off
setlocal enabledelayedexpansion
title JoyViewer Auto Release ^& Deploy Script

:: ANSI Color Codes using Powershell for premium visual feedback
echo ===================================================
powershell -Command "Write-Host '   JoyViewer Premium Auto-Release Script   ' -ForegroundColor Black -BackgroundColor Yellow"
echo ===================================================
echo.

:: 1. Check if Git is installed
where git >nul 2>nul
if %errorlevel% neq 0 (
    powershell -Command "Write-Host '[ERROR] Git is not installed or not in PATH!' -ForegroundColor Red"
    goto ERROR_EXIT
)

:: 2. Detect active branch
for /f "tokens=*" %%i in ('git branch --show-current 2^>nul') do set BRANCH=%%i
if "%BRANCH%"=="" set BRANCH=main
powershell -Command "Write-Host '[+] Active branch detected: %BRANCH%' -ForegroundColor Green"

:: 3. Automatically parse version from webtoon_viewer.py
for /f "tokens=*" %%i in ('powershell -Command "if ((Get-Content webtoon_viewer.py) -match 'APP_NAME\s*=\s*\"[^\"]+v([\d\.]+)\"') { $Matches[1] } else { '4.3' }"') do set VERSION=%%i
powershell -Command "Write-Host '[+] Parsed version from source: v%VERSION%' -ForegroundColor Green"
echo.

:: 4. Prompt for verification or custom version
set "USER_VER="
set /p USER_VER="Enter release version (Press Enter for default: 'v%VERSION%'): "
if not "%USER_VER%"=="" (
    set "VERSION=%USER_VER%"
    :: strip 'v' if user typed it
    set "VERSION=!VERSION:v=!"
)
powershell -Command "Write-Host '[*] Building and releasing version: v%VERSION%' -ForegroundColor Cyan"
echo.

:: 5. Clean up old builds
powershell -Command "Write-Host '[*] Cleaning old build and dist folders...' -ForegroundColor Yellow"
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

:: 6. Check Python & PyInstaller
where python >nul 2>nul
if %errorlevel% neq 0 (
    powershell -Command "Write-Host '[ERROR] Python is not installed!' -ForegroundColor Red"
    goto ERROR_EXIT
)
powershell -Command "Write-Host '[*] Installing/upgrading PyInstaller...' -ForegroundColor Yellow"
python -m pip install pyinstaller --quiet

:: 7. Compile using Spec file
powershell -Command "Write-Host '[*] Running PyInstaller compilation...' -ForegroundColor Yellow"
if exist "JoyViewer.spec" (
    python -m PyInstaller --clean JoyViewer.spec
) else (
    python -m PyInstaller -w -F --name "JoyViewer" webtoon_viewer.py --clean
)

if %errorlevel% neq 0 (
    powershell -Command "Write-Host '[ERROR] PyInstaller compilation failed!' -ForegroundColor Red"
    goto ERROR_EXIT
)

:: 8. Post-processing (Rename and config copy)
if exist "dist\JoyViewer.exe" (
    copy /Y "dist\JoyViewer.exe" "dist\JoyViewer-v%VERSION%.exe" >nul
    powershell -Command "Write-Host '[+] Created version-stamped copy: dist\JoyViewer-v%VERSION%.exe' -ForegroundColor Green"
    if exist "joyviewer_config.json" (
        copy /Y "joyviewer_config.json" "dist\" >nul
        powershell -Command "Write-Host '[+] Copied configuration file to dist folder.' -ForegroundColor Green"
    )
) else (
    powershell -Command "Write-Host '[ERROR] Could not find compiled executable in dist!' -ForegroundColor Red"
    goto ERROR_EXIT
)
echo.

:: 9. Git Commit and Tagging
powershell -Command "Write-Host '[*] Staging files for Git...' -ForegroundColor Yellow"
git add .
powershell -Command "Write-Host '[*] Committing release changes...' -ForegroundColor Yellow"
git commit -m "Release v%VERSION%: Build executable and update documentation"
if %errorlevel% neq 0 (
    powershell -Command "Write-Host '[WARNING] No changes to commit.' -ForegroundColor Yellow"
)

powershell -Command "Write-Host '[*] Pushing branch commits to remote origin...' -ForegroundColor Yellow"
git push origin %BRANCH%
if %errorlevel% neq 0 (
    powershell -Command "Write-Host '[ERROR] Failed to push commits!' -ForegroundColor Red"
    goto ERROR_EXIT
)

:: Delete existing tag locally and remotely if it exists, to avoid conflicts
git tag -d v%VERSION% >nul 2>nul
git push origin :refs/tags/v%VERSION% >nul 2>nul

powershell -Command "Write-Host '[*] Creating Git Tag v%VERSION%...' -ForegroundColor Yellow"
git tag -a v%VERSION% -m "Release version %VERSION%"
if %errorlevel% neq 0 (
    powershell -Command "Write-Host '[ERROR] Failed to create Git tag!' -ForegroundColor Red"
    goto ERROR_EXIT
)

powershell -Command "Write-Host '[*] Pushing Git Tag to remote origin...' -ForegroundColor Yellow"
git push origin v%VERSION%
if %errorlevel% neq 0 (
    powershell -Command "Write-Host '[ERROR] Failed to push Git tag!' -ForegroundColor Red"
    goto ERROR_EXIT
)

echo.
echo ===================================================
powershell -Command "Write-Host '    AUTO-RELEASE SUCCESSFUL!    ' -ForegroundColor Black -BackgroundColor Green"
echo ===================================================
echo [Release Executable] E:\joyviewer\dist\JoyViewer-v%VERSION%.exe
echo [Git Tag] v%VERSION% (Pushed to origin)
echo.
pause
exit /b 0

:ERROR_EXIT
echo.
echo ===================================================
powershell -Command "Write-Host '       AUTO-RELEASE FAILED!       ' -ForegroundColor Black -BackgroundColor Red"
echo ===================================================
echo.
pause
exit /b 1
