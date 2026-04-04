@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo [INFO] Installing/updating dependencies...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install requirements.
  pause
  exit /b 1
)

echo [INFO] Starting Streamlit app...
%PY% -m streamlit run web_app.py

if errorlevel 1 (
  echo [ERROR] Streamlit failed to start.
  pause
  exit /b 1
)

endlocal
