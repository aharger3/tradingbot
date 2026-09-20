@echo off
REM omen-v5-session-counter (2026-09-20) -- daily count of unique V5 trading
REM dates (arm=engine or arm=austin) across journal/alpaca-paper.jsonl and
REM journal/signal_log_*.jsonl. Appends one row/day to research/tape/v5_progress.json.
REM Queues a card in research/tape/card_queue.json once count hits 25.
REM Read-only against journal files; places no order.
setlocal
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
"C:\Users\aharg\AppData\Local\Programs\Python\Python313\python.exe" research\v5_session_counter.py >> "%~dp0journal\v5-session-counter.log" 2>&1
