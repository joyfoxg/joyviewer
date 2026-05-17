@echo off
setlocal enabledelayedexpansion
title JoyViewer Compiler

:: ANSI Color Codes using Powershell for premium visual feedback
set "ESC="
for /f %%A in ('echo prompt $E ^| cmd') do set "ESC=%%A"

echo ===================================================
powershell -Command "Write-Host '   JoyViewer Premium Compiler (v4.1)   ' -ForegroundColor Black -BackgroundColor Cyan"
echo ===================================================
echo.

:: 1. Check/Activate Virtual Environment
if exist ".venv\Scripts\activate.bat" (
    powershell -Command "Write-Host '[+] Found local virtual environment (.venv). Activating...' -ForegroundColor Green"
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    powershell -Command "Write-Host '[+] Found local virtual environment (venv). Activating...' -ForegroundColor Green"
    call venv\Scripts\activate.bat
) else (
    echo [i] No local virtual environment found. Using system Python.
)

:: 2. Check Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    powershell -Command "Write-Host '[ERROR] Python is not installed or not in PATH!' -ForegroundColor Red"
    echo Please install Python 3.8 or higher and check 'Add Python to PATH' during installation.
    goto ERROR_EXIT
)

for /f "tokens=*" %%i in ('python --version') do set PYTHON_VER=%%i
powershell -Command "Write-Host '[+] Using %PYTHON_VER%' -ForegroundColor Green"
echo.

:: 3. Install dependencies from requirements.txt
if exist "requirements.txt" (
    powershell -Command "Write-Host '[*] Installing requirements from requirements.txt...' -ForegroundColor Yellow"
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        powershell -Command "Write-Host '[WARNING] Failed to install some requirements. Continuing anyway...' -ForegroundColor Yellow"
    )
) else (
    echo [i] requirements.txt not found. Skipping library install.
)

:: 4. Ensure PyInstaller is installed
powershell -Command "Write-Host '[*] Checking/Installing PyInstaller...' -ForegroundColor Yellow"
python -m pip install pyinstaller
if %errorlevel% neq 0 (
    powershell -Command "Write-Host '[ERROR] Failed to install PyInstaller!' -ForegroundColor Red"
    goto ERROR_EXIT
)
echo.

:: 5. Compile with PyInstaller
powershell -Command "Write-Host '[*] Starting PyInstaller compilation...' -ForegroundColor Cyan"
if exist "JoyViewer.spec" (
    powershell -Command "Write-Host '[i] Found JoyViewer.spec. Compiling using spec file...' -ForegroundColor Gray"
    pyinstaller JoyViewer.spec --clean
) else (
    powershell -Command "Write-Host '[i] JoyViewer.spec not found. Compiling webtoon_viewer.py directly...' -ForegroundColor Gray"
    pyinstaller -w -F --name "JoyViewer" webtoon_viewer.py --clean
)

if %errorlevel% neq 0 (
    powershell -Command "Write-Host '[ERROR] Compilation failed during PyInstaller execution.' -ForegroundColor Red"
    goto ERROR_EXIT
)
echo.

:: 6. Copying config and renaming target executable
powershell -Command "Write-Host '[*] Post-processing output files...' -ForegroundColor Cyan"
if exist "dist\JoyViewer.exe" (
    powershell -Command "Write-Host '[+] Successfully compiled JoyViewer.exe!' -ForegroundColor Green"
    
    :: Rename to include version v4.1 for the final build
    copy /Y "dist\JoyViewer.exe" "dist\JoyViewer-v4.1.exe" >nul
    if %errorlevel% equ 0 (
        powershell -Command "Write-Host '[+] Version-stamped copy created: dist\JoyViewer-v4.1.exe' -ForegroundColor Green"
    )
    
    :: Ensure config file exists in the dist directory
    if exist "joyviewer_config.json" (
        if not exist "dist\joyviewer_config.json" (
            copy /Y "joyviewer_config.json" "dist\" >nul
            powershell -Command "Write-Host '[+] Copied joyviewer_config.json to dist folder.' -ForegroundColor Green"
        )
    )
) else (
    powershell -Command "Write-Host '[ERROR] Could not find compiled executable in dist\JoyViewer.exe' -ForegroundColor Red"
    goto ERROR_EXIT
)

echo.
echo ===================================================
powershell -Command "Write-Host '   BUILD COMPLETED SUCCESSFULLY!   ' -ForegroundColor Black -BackgroundColor Green"
echo ===================================================
echo [Location] e:\joyviewer\dist\JoyViewer-v4.1.exe
echo.
pause
exit /b 0

:ERROR_EXIT
echo.
echo ===================================================
powershell -Command "Write-Host '         BUILD FAILED!          ' -ForegroundColor Black -BackgroundColor Red"
echo ===================================================
echo.
pause
exit /b 1
