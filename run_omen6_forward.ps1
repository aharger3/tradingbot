# OMEN 6 forward-only clock -- daily tick.
#
# 1. bank today's 1-min bars (archive_1m.py, Polygon; already-archived days are
#    a no-op, so a re-run costs nothing)
# 2. score any unscored trading day since the freeze into the forward book
#
# Scoring refuses to run if the frozen engine's hashes have moved, so a refit
# surfaces here as a loud failure rather than a quietly contaminated book.
#
# Registered as scheduled task \OmenForwardClock, weekdays 17:30 ET.

$ErrorActionPreference = "Stop"
$repo = "C:\Users\aharg\Desktop\Projects\tradingbot"
$log  = Join-Path $repo "logs\omen6_forward.log"

New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
"=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Add-Content $log

Set-Location $repo

# Polygon 403s the CURRENT day on this plan, so ask for completed sessions and
# let the last few days catch up anything a missed run dropped. Already-archived
# days are disk reads, so the overlap is free.
try {
    & python archive_1m.py --back 5 2>&1 | Add-Content $log
} catch {
    # A data-feed problem must not stop scoring the days we already have.
    "archive step failed (continuing to score): $_" | Add-Content $log
}

try {
    & python research\omen6_forward.py score 2>&1 | Add-Content $log
    "ok" | Add-Content $log
} catch {
    "SCORE FAILED: $_" | Add-Content $log
    exit 1
}
