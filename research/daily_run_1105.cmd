@echo off
REM AUGUR's 11:05 pass -- fetch blind to 11:00, build the deck, send it.
REM Registered as scheduled task "OmenDailyHomework1105", weekdays 11:05 ET.
REM   run by hand:  research\daily_run_1105.cmd
REM   unregister:   schtasks /delete /tn OmenDailyHomework1105 /f
REM
REM This is NOT daily_run.cmd with a different clock. That one runs at 16:15 and
REM is the REVEAL: the whole session, one card per symbol. This one runs while
REM the day is still open and is BLIND -- the fetch itself stops at 11:00, so
REM the archive file for today physically cannot hold the answer.
REM
REM The ntfy topic is a SECRET and is read from %OMEN_NTFY_TOPIC%. This repo is
REM public; anyone holding the topic name can read every deck and push anything
REM to his phone, so it is set once on the box with:
REM     setx OMEN_NTFY_TOPIC <topic>
setlocal
cd /d "%~dp0.."

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set LDT=%%I
set DAY=%LDT:~0,4%-%LDT:~4,2%-%LDT:~6,2%
set LOG=journal\daily-1105-%DAY%.log

echo === AUGUR 11:05 blind homework %DAY% === > "%LOG%"

REM --until 11:00 is the blindness guarantee at the data layer. It refuses to
REM shorten a file that already holds more of the session, so an afternoon rerun
REM can never eat the 16:15 pass's bars.
python research\daily_fetch.py --day %DAY% --until 11:00 >> "%LOG%" 2>&1
if errorlevel 1 (
  echo FETCH FAILED -- no deck built, archive untouched >> "%LOG%"
  type "%LOG%"
  exit /b 1
)

python research\daily_homework.py --day %DAY% --mode s-blind >> "%LOG%" 2>&1
if errorlevel 1 (
  echo BUILD FAILED -- nothing sent >> "%LOG%"
  type "%LOG%"
  exit /b 1
)

REM Mirrors to Desktop\AI-Outputs\omen-daily\ and pushes the file to the phone.
python research\deliver_homework.py --day %DAY% >> "%LOG%" 2>&1
if errorlevel 1 (
  echo SEND FAILED -- the deck is built, it just did not reach the phone >> "%LOG%"
  type "%LOG%"
  exit /b 1
)

echo deck: research\decks\omen-daily-%DAY%-s.html >> "%LOG%"
type "%LOG%"
endlocal
