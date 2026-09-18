@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Pierwsze uruchomienie - instalowanie zaleznosci...
  call setup.bat
  if errorlevel 1 exit /b 1
)

if not exist "frontend\dist\index.html" (
  echo Brak buildu frontendu. Uruchom setup.bat.
  exit /b 1
)

echo Allegro Product Hunter: http://127.0.0.1:8000
start "" "http://127.0.0.1:8000"
".venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

