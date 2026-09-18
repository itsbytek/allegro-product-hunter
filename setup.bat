@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3.12 -m venv .venv
  ) else (
    where python >nul 2>nul
    if errorlevel 1 (
      echo Nie znaleziono Python 3.12. Zainstaluj go z https://www.python.org/downloads/
      exit /b 1
    )
    python -m venv .venv
  )
)

echo Instalowanie backendu...
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 exit /b 1

where pnpm >nul 2>nul
if not errorlevel 1 (
  cd frontend
  call pnpm install
  call pnpm build
  cd ..
) else (
  where npm >nul 2>nul
  if errorlevel 1 (
    echo Nie znaleziono Node.js/npm. Zainstaluj Node.js 22 LTS lub nowszy.
    exit /b 1
  )
  cd frontend
  call npm install
  call npm run build
  cd ..
)

if errorlevel 1 exit /b 1
echo Gotowe. Uruchom start.bat
