# Daily Vanquish runner — launched by Task Scheduler at 9:25 AM ET.
# Pulls Hermes's latest rule changes, then starts the live scanner.
# Output tees to journal\scanner-YYYY-MM-DD.log for review.
# --paper enables paper-trade simulation (logs to journal/paper-trades.jsonl)

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

# Force UTF-8 stdout/stderr so emoji in print() statements (📝🚀✓✗📕📗⚠) don't
# crash with UnicodeEncodeError under PowerShell's cp1252 pipe encoding.
$env:PYTHONIOENCODING = "utf-8"

$python = "C:\Users\aharg\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

$logDir = Join-Path $PSScriptRoot "journal"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$log = Join-Path $logDir ("scanner-" + (Get-Date -Format "yyyy-MM-dd") + ".log")

"=== $(Get-Date -Format o) starting daily run ===" | Tee-Object -FilePath $log -Append

# Pull latest rules from GitHub (Hermes commits here). Non-fatal on failure.
git pull --rebase --autostash 2>&1 | Tee-Object -FilePath $log -Append

# Run with paper trading enabled (logs paper trades alongside live signals)
& $python live_scanner.py --paper 2>&1 | Tee-Object -FilePath $log -Append
