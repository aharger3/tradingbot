@echo off
cd /d C:\Users\aharg\Desktop\Projects\tradingbot
set EYE_LABEL_TOKEN=sthjqnwdb0573oy6rlcup824fm1a9zvigkxe
set EYE_LABEL_BASE_URL=http://100.66.129.60:9135
"C:\Users\aharg\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" eye_runner.py --date 2026-09-07 --title-prefix "OMEN TEST -- ignore" --speed 60 --confirm-window-s 20 --journal-path C:\Users\aharg\Desktop\Projects\tradingbot\logs\dryrun-0927\journal.jsonl --labels-csv C:\Users\aharg\Desktop\Projects\tradingbot\logs\dryrun-0927\labels.csv --max-wall-minutes 8 > C:\Users\aharg\Desktop\Projects\tradingbot\logs\dryrun-0927\runner.log 2>&1
"C:\Users\aharg\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" eye_report.py --date 2026-09-07 --journal-path C:\Users\aharg\Desktop\Projects\tradingbot\logs\dryrun-0927\journal.jsonl --title-prefix "OMEN TEST -- ignore" > C:\Users\aharg\Desktop\Projects\tradingbot\logs\dryrun-0927\report.log 2>&1
echo DONE %errorlevel% > C:\Users\aharg\Desktop\Projects\tradingbot\logs\dryrun-0927\done.txt
