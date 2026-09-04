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

REM Austin, 2026-09-04: every S signal, main 10 stocks (+SPY), one card per S
REM bar, 60 max. Projects/AUGUR.md: "Deck = all S from the top-10, under 60".
python research\daily_homework.py --day %DAY% --mode s-blind --pool core --per-signal >> "%LOG%" 2>&1
if errorlevel 1 (
  echo BUILD FAILED -- nothing sent >> "%LOG%"
  type "%LOG%"
  exit /b 1
)

REM OMEN 8.1 S3: same non-fatal, log-only regression check as daily_run.cmd's
REM 16:15 pass (research/g112_regression_gate.md) -- this pass is a second
REM daily entry point and the gate going silently red on one path while the
REM other logs it is the same blind spot in miniature. Local log only, never
REM reaches deliver_homework.py / the phone push below.
echo --- regression gate --- >> "%LOG%"
python research\regression_gate.py >> "%LOG%" 2>&1
if errorlevel 1 (
  echo REGRESSION GATE: FAIL -- a baseline-fired mark went silent, see above >> "%LOG%"
) else (
  echo REGRESSION GATE: PASS >> "%LOG%"
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
