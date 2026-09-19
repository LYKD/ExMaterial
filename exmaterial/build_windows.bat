@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_CMD="
where py >nul 2>nul
if %errorlevel%==0 set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
    where python >nul 2>nul
    if %errorlevel%==0 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo Python was not found by cmd. Trying PowerShell python...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '%~dp0'; python -m pip install pyinstaller pillow; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; python -m PyInstaller --noconfirm --clean --onefile --windowed --name ExMaterial --icon '..\docs\assets\exmaterial-logo.ico' exmaterial_app.py; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Copy-Item -LiteralPath 'dist\ExMaterial.exe' -Destination 'ExMaterial.exe' -Force; exit 0"
    if not %errorlevel%==0 (
        echo Failed to build exe.
        pause
        exit /b 1
    )
    echo.
    echo Build finished. The exe is: %~dp0ExMaterial.exe
    echo Keep the information folder beside this exmaterial folder.
    pause
    exit /b 0
)
%PYTHON_CMD% -m pip install pyinstaller pillow
if not %errorlevel%==0 (
    echo Failed to install PyInstaller.
    pause
    exit /b 1
)
%PYTHON_CMD% -m PyInstaller --noconfirm --clean --onefile --windowed --name ExMaterial --icon "..\docs\assets\exmaterial-logo.ico" exmaterial_app.py
if not %errorlevel%==0 (
    echo Failed to build exe.
    pause
    exit /b 1
)
copy /Y "dist\ExMaterial.exe" "ExMaterial.exe" >nul
if not %errorlevel%==0 (
    echo Failed to copy ExMaterial.exe.
    pause
    exit /b 1
)
echo.
echo Build finished. The exe is: %~dp0ExMaterial.exe
echo Keep the information folder beside this exmaterial folder.
pause
