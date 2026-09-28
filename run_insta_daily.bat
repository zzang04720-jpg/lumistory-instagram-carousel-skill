@echo off
setlocal
set "WORKDIR=%~dp0"
set "PYTHON=%WORKDIR%\.venv\Scripts\python.exe"
rem Opt in using the repository .env file; default is disabled.
echo === %date% %time% start === >> "%WORKDIR%\scheduler_run.log"
"%PYTHON%" -u "%WORKDIR%\lumistory_auto.py" >> "%WORKDIR%\scheduler_run.log" 2>&1
set "RUN_RESULT=%ERRORLEVEL%"
echo === %date% %time% done === >> "%WORKDIR%\scheduler_run.log"
exit /b %RUN_RESULT%
