@echo off
set "WORKDIR=%~dp0"
set "PYTHON=%WORKDIR%\.venv\Scripts\python.exe"
set "IG_AUTO_DM=1"
echo === %date% %time% DM check start === >> "%WORKDIR%\scheduler_run.log"
"%PYTHON%" -u "%WORKDIR%\lumistory_dm_auto.py" >> "%WORKDIR%\scheduler_run.log" 2>&1
echo === %date% %time% DM check done === >> "%WORKDIR%\scheduler_run.log"
