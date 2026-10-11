@echo off
setlocal
cd /d "%~dp0"
set FRONTEND_DIR=%~dp0public\unihub
set ADMIN_TOKEN=%ADMIN_TOKEN%
if "%ADMIN_TOKEN%"=="" set ADMIN_TOKEN=admin123

echo Installing UniHub backend dependencies...
python -m pip install -r "%~dp0unihub\backend\requirements.txt"
if errorlevel 1 (
  echo Failed to install UniHub backend dependencies.
  exit /b 1
)

echo Starting UniSphere with the integrated UniHub module...
echo Vite will open the UniSphere portal at the actual available Local URL.
npm run dev -- --open
