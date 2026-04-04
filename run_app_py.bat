@echo off
setlocal

cd /d "%~dp0"

set "APP_DIR=%cd%\admission-diagnosis"
set "APP_FILE=%APP_DIR%\app.py"
set "REQ_FILE=%APP_DIR%\requirements.txt"

if not exist "%APP_FILE%" (
  echo [ERROR] admission-diagnosis\app.py not found.
  echo Current path: %cd%
  pause
  exit /b 1
)

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo [INFO] Installing/updating dependencies...
%PY% -m pip install -r "%REQ_FILE%"
if errorlevel 1 (
  echo [ERROR] Failed to install requirements.
  pause
  exit /b 1
)

echo [INFO] Starting Streamlit app (admission-diagnosis\app.py)...
cd /d "%APP_DIR%"
%PY% -m streamlit run app.py

if errorlevel 1 (
  echo [ERROR] Streamlit failed to start.
  pause
  exit /b 1
)

endlocal
