@echo off
REM omen-v5-legacy-exit-test (2026-09-20) -- nightly check that every filled
REM legacy g88 paper entry has a matching flatten_legacy close/cancel row.
REM Read-only against journal/alpaca-paper.jsonl; places no order.
setlocal
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
"C:\Users\aharg\AppData\Local\Programs\Python\Python313\python.exe" -m pytest test_v5_legacy_exit.py -q >> "%~dp0journal\legacy-exit-test.log" 2>&1
