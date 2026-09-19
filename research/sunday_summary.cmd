@echo off
REM OMEN Sunday summary -- append one week's receipt row to Projects/omen-tape-summary.md in the vault
REM Reads research/tape/nightly.md (last 7 days), extracts tried/shipped/held counts,
REM reads loop.json baseline_figures ($/day, green months), and appends exactly ONE row
REM to the vault's Projects/omen-tape-summary.md under a Weekly receipts table.
REM Append-only: never rewrites earlier weeks.
REM Then commits and pushes to the vault repo.
REM Registered as scheduled task OmenSundaySummary, Sundays 09:00.
REM
REM Run by hand: research\sunday_summary.cmd
REM Unregister: schtasks /delete /tn OmenSundaySummary /f
REM
REM Never fails the task: an empty queue, missing files, or git errors
REM all write to stderr and return 0, so a bad run never blocks the next scheduled run.

setlocal
cd /d "%~dp0.."

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set LDT=%%I
set DAY=%LDT:~0,4%-%LDT:~4,2%-%LDT:~6,2%
set LOG=journal\sunday-summary-%DAY%.log

echo === OMEN Sunday summary %DAY% === > "%LOG%"
python research\sunday_summary.py >> "%LOG%" 2>&1
type "%LOG%"
endlocal
exit /b 0
