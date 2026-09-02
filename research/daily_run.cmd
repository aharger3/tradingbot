@echo off
REM OMEN daily pass -- fetch the session, run the engine, build the deck.
REM Registered as scheduled task "OmenDailyHomework", weekdays 16:15 ET.
REM   run by hand:  research\daily_run.cmd
REM   unregister:   schtasks /delete /tn OmenDailyHomework /f
setlocal
cd /d "%~dp0.."

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set LDT=%%I
set DAY=%LDT:~0,4%-%LDT:~4,2%-%LDT:~6,2%
set LOG=journal\daily-%DAY%.log

echo === OMEN daily pass %DAY% === > "%LOG%"

REM yfinance is the only source on this box that reaches the current session:
REM Polygon returns 403 for recent timeframes on this plan and Tastytrade is
REM 401 invalid_credentials. See research/daily_fetch.py.
python research\daily_fetch.py --day %DAY% >> "%LOG%" 2>&1
if errorlevel 1 (
  echo FETCH FAILED -- no deck built, archive untouched >> "%LOG%"
  exit /b 1
)

python research\daily_homework.py --day %DAY% >> "%LOG%" 2>&1
if errorlevel 1 (
  echo BUILD FAILED >> "%LOG%"
  exit /b 1
)

echo deck: research\decks\omen-daily-%DAY%.html >> "%LOG%"
type "%LOG%"
endlocal
