@echo off
REM OMEN loop supervisor -- watchdog for scheduled task OmenNightlyLoop.
REM All the logic (nightly.md check, schtasks status, restart/long-run/noop,
REM ntfy) lives in loop_supervisor.py -- this is the thin trigger, same
REM split as daily_run.cmd/daily_fetch.py and nightly_loop.cmd/nightly_loop.py.
REM Registered as scheduled task OmenLoopSupervisor, weekdays 21:30.
REM   run by hand:  research\loop_supervisor.cmd
REM   unregister:   schtasks /delete /tn OmenLoopSupervisor /f
REM
REM Never edits loop_queue.json, never calls loop_cycle.py or
REM signal_runner.py -- read-only against nightly.md, schtasks status only.
REM Always exits 0: a bad supervisor run must never block the next one.
setlocal
cd /d "%~dp0.."

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set LDT=%%I
set DAY=%LDT:~0,4%-%LDT:~4,2%-%LDT:~6,2%
set LOG=journal\loop-supervisor-%DAY%.log

echo === OMEN loop supervisor %DAY% === > "%LOG%"
python research\loop_supervisor.py >> "%LOG%" 2>&1
type "%LOG%"
endlocal
exit /b 0
