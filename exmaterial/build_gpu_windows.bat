@echo off
setlocal
cd /d "%~dp0\.."
python -m pip install ".[build,gpu]"
if errorlevel 1 exit /b 1
cd exmaterial
python -m PyInstaller --noconfirm --clean --onefile --windowed --paths . --additional-hooks-dir . --collect-all cupy --collect-all cupy_backends --collect-all fastrlock --name ExMaterial-GPU --icon "..\docs\assets\exmaterial-logo.ico" exmaterial_app.py
if errorlevel 1 exit /b 1
echo Build finished: dist\ExMaterial-GPU.exe
echo Keep your information directory. NVIDIA CUDA drivers/runtime are required for GPU mode.
