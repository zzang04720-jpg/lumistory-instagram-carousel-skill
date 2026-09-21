@echo off
rem NOTE: keep this file ASCII-only. cmd reads .bat as cp949, so UTF-8 Korean text breaks parsing.
setlocal EnableExtensions
set "WORKDIR=%~dp0"
set "PYTHON=%WORKDIR%.venv\Scripts\python.exe"
set "URL=http://127.0.0.1:8501"

if not exist "%PYTHON%" (
  echo Python environment not found:
  echo %PYTHON%
  pause
  exit /b 1
)

netstat -ano | findstr /R /C:":8501 .*LISTENING" >nul
if errorlevel 1 (
  start "LumiStory Card News" /min "%PYTHON%" -m streamlit run "%WORKDIR%app.py" --server.headless=true --server.address=127.0.0.1 --server.port=8501 --browser.gatherUsageStats=false
  timeout /t 5 /nobreak >nul
)

netstat -ano | findstr /R /C:":8501 .*LISTENING" >nul
if errorlevel 1 (
  echo Failed to start the card news app.
  echo Keep this window open and send a screenshot.
  pause
  exit /b 1
)

start "" "%URL%"
endlocal
