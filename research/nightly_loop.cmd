@echo off
REM OMEN nightly loop -- pops one candidate off research\tape\loop_queue.json
REM and runs it through loop_cycle.py --stage all. All the logic (pop, run,
REM one-line receipt in research\tape\nightly.md) lives in nightly_loop.py --
REM this is the thin trigger, same split as daily_run.cmd/daily_fetch.py.
REM Registered as scheduled task OmenNightlyLoop, weekdays 20:00.
REM   run by hand:  research\nightly_loop.cmd
REM   unregister:   schtasks /delete /tn OmenNightlyLoop /f
REM
REM Never fails: an empty queue, a held or blocked cycle, or even an
REM unexpected crash in nightly_loop.py all still write one receipt line and
REM this always exits 0, so a bad night never blocks the next scheduled run.
setlocal
cd /d "%~dp0.."

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set LDT=%%I
set DAY=%LDT:~0,4%-%LDT:~4,2%-%LDT:~6,2%
set LOG=journal\nightly-loop-%DAY%.log

echo === OMEN nightly loop %DAY% === > "%LOG%"
python research\nightly_loop.py >> "%LOG%" 2>&1
type "%LOG%"
endlocal
exit /b 0
