@echo off
set "WORKDIR=%~dp0"
set "PYTHON=%WORKDIR%\.venv\Scripts\python.exe"
set "IG_AUTO_PUBLISH=1"
echo === %date% %time% start === >> "%WORKDIR%\scheduler_run.log"
"%PYTHON%" -u "%WORKDIR%\lumistory_auto.py" >> "%WORKDIR%\scheduler_run.log" 2>&1
echo === %date% %time% done === >> "%WORKDIR%\scheduler_run.log"
