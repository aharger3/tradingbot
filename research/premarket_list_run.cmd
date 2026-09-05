@echo off
REM OMEN 10.0 V1 -- the 09:25 ET premarket list, pushed to ntfy.
REM Registered as scheduled task "OmenPremarketList", weekdays 09:25 ET.
REM   run by hand:  research\premarket_list_run.cmd
REM   unregister:   schtasks /delete /tn OmenPremarketList /f
setlocal
cd /d "%~dp0.."

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set LDT=%%I
set DAY=%LDT:~0,4%-%LDT:~4,2%-%LDT:~6,2%
set LOG=journal\premarket-list-%DAY%.log

echo === OMEN premarket list %DAY% === > "%LOG%"
python research\premarket_list.py >> "%LOG%" 2>&1
if errorlevel 1 (
  echo PREMARKET LIST FAILED >> "%LOG%"
  exit /b 1
)
type "%LOG%"
endlocal
