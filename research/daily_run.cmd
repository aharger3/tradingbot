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

REM OMEN 8.1 S3: regression_gate.py used to run only by hand and went
REM silently red for 16 days (5e3677ea, 2026-08-11) unnoticed. It now runs
REM every weekday and its verdict lands in this log -- non-fatal to the
REM deck build (a detection regression is a finding, not a fetch/build
REM failure), but no longer invisible.
echo --- regression gate --- >> "%LOG%"
python research\regression_gate.py >> "%LOG%" 2>&1
if errorlevel 1 (
  echo REGRESSION GATE: FAIL -- a baseline-fired mark went silent, see above >> "%LOG%"
) else (
  echo REGRESSION GATE: PASS >> "%LOG%"
)

REM W7/g207 (2026-09-05): the 14 failing tests B-08 found were never run by
REM anything -- research/run_tests.py is the canonical selftest set (every
REM test_*.py, minus retired ones and a short documented exclusion list).
REM Log-only, non-fatal on purpose: this is a triage instrument, not the
REM verify: gate in CLAUDE.md, which stays regression_gate.py +
REM test_runner_stop.py, unchanged.
echo --- canonical test suite (research/run_tests.py) --- >> "%LOG%"
python research\run_tests.py >> "%LOG%" 2>&1
if errorlevel 1 (
  echo CANONICAL TESTS: FAIL -- see above for which ones, non-fatal >> "%LOG%"
) else (
  echo CANONICAL TESTS: PASS >> "%LOG%"
)

REM B3 B-08 (2026-09-05): the verify gate ran only regression_gate.py here,
REM so a private ticker list (research/g83_*.py INDEX_POOL/INDEX_SYMS) could
REM appear and nothing caught it -- test_universe_single_source.py existed
REM but was never wired into either gate. Now run alongside regression_gate.
echo --- universe single-source gate --- >> "%LOG%"
python research\test_universe_single_source.py >> "%LOG%" 2>&1
if errorlevel 1 (
  echo UNIVERSE SINGLE-SOURCE: FAIL -- a module defined a private symbol list, see above >> "%LOG%"
) else (
  echo UNIVERSE SINGLE-SOURCE: PASS >> "%LOG%"
)

REM O2 (2026-09-05): keep the recall index fresh so every agent's first move
REM can be a search instead of a re-ask (research/omen_recall.py).
echo --- omen recall rebuild --- >> "%LOG%"
python research\omen_recall.py --rebuild >> "%LOG%" 2>&1

type "%LOG%"
endlocal
