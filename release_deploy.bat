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
powershell -NoProfile -Command "if ((Get-Content webtoon_viewer.py) -match 'APP_NAME\s*=\s*\"[^\"]+v([\d\.]+)\"') { Set-Content temp_ver.txt $Matches[1] } else { Set-Content temp_ver.txt '4.4' }"
set /p VERSION=<temp_ver.txt
del temp_ver.txt
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
set "PYTHON_EXE=python"
if exist "C:\Python\Python313\python.exe" (
    set "PYTHON_EXE=C:\Python\Python313\python.exe"
) else (
    where python >nul 2>nul
    if !errorlevel! neq 0 (
        powershell -Command "Write-Host '[ERROR] Python is not installed or not in PATH!' -ForegroundColor Red"
        goto ERROR_EXIT
    )
)
powershell -Command "Write-Host '[*] Using python path: %PYTHON_EXE%' -ForegroundColor Green"
powershell -Command "Write-Host '[*] Installing/upgrading PyInstaller...' -ForegroundColor Yellow"
"%PYTHON_EXE%" -m pip install pyinstaller --quiet

:: 7. Compile using Spec file
powershell -Command "Write-Host '[*] Running PyInstaller compilation...' -ForegroundColor Yellow"
if exist "JoyViewer.spec" (
    "%PYTHON_EXE%" -m PyInstaller --clean JoyViewer.spec
) else (
    "%PYTHON_EXE%" -m PyInstaller -w -F --name "JoyViewer" webtoon_viewer.py --clean
)

if !errorlevel! neq 0 (
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

:: 10. Check if GitHub CLI (gh) is installed and authenticated
gh --version >nul 2>&1
if !errorlevel! equ 0 (
    powershell -Command "Write-Host '[*] GitHub CLI (gh) detected. Checking auth status...' -ForegroundColor Yellow"
    
    :: Temporarily clear GITHUB_TOKEN if it was set in the environment (common in agent workspaces)
    set "GITHUB_TOKEN="
    
    gh auth status >nul 2>&1
    if !errorlevel! equ 0 (
        powershell -Command "Write-Host '[*] Creating GitHub Release and uploading dist\JoyViewer-v%VERSION%.exe...' -ForegroundColor Yellow"
        
        :: Delete existing GitHub release first to allow clean overwrite
        gh release delete v%VERSION% -y >nul 2>&1
        
        gh release create v%VERSION% "dist\JoyViewer-v%VERSION%.exe" --title "JoyViewer v%VERSION%" --notes "Release v%VERSION%"
        if !errorlevel! equ 0 (
            powershell -Command "Write-Host '[+] Successfully created GitHub Release and uploaded executable!' -ForegroundColor Green"
        ) else (
            powershell -Command "Write-Host '[WARNING] Failed to create GitHub Release.' -ForegroundColor Yellow"
        )
    ) else (
        powershell -Command "Write-Host '[WARNING] GitHub CLI is not authenticated. Skipping automatic GitHub Release creation. Run \"gh auth login\" to authenticate.' -ForegroundColor Yellow"
    )
) else (
    powershell -Command "Write-Host '[i] GitHub CLI (gh) not detected. Skipping automatic GitHub Release creation.' -ForegroundColor Gray"
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
