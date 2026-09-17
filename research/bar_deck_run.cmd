@echo off
REM AUGUR's bar-letter deck -- built by research\sm_deck.py (A/B/C candidate
REM entry bars per symbol-day, shipped 2026-09-15) and pushed to the phone the
REM same way research\deliver_homework.py pushes the 11:05 deck.
REM Registered as scheduled task OmenBarDeck, weekdays 19:45, interactive
REM principal.
REM   run by hand:   research\bar_deck_run.cmd
REM   unregister:    schtasks /delete /tn OmenBarDeck /f
REM
REM WHY THIS EXISTS. research\marks\sm_deck_2026-09-14_comments.jsonl: Austin's
REM first three sm_deck marks all say the engine's C bar (its own fire) is
REM late and his real entry was earlier -- A (break) or B (retest). sm_deck.py
REM already draws all three candidates on every card and already queues days
REM where the engine fired >=3 bars after the break first (THE LANE,
REM sm_deck.py:cmd_build) -- the one thing missing since the renderer shipped
REM is a scheduled run.
REM
REM The ntfy topic is a SECRET and is read from %OMEN_NTFY_TOPIC%, same as
REM every other push in this repo -- never written into a file here.
setlocal
cd /d "%~dp0.."

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set LDT=%%I
set DAY=%LDT:~0,4%-%LDT:~4,2%-%LDT:~6,2%
set LOG=journal\bar-deck-%DAY%.log

echo === OMEN bar deck %DAY% === > "%LOG%"

REM --n 3, not --build's own default of 8: this is a nightly probe of one
REM hypothesis (the engine bar is late), not a full sitting. cmd_build's own
REM lag sort already queues engine-late days first.
python research\sm_deck.py --build --n 3 --date %DAY% >> "%LOG%" 2>&1
if errorlevel 1 (
  echo BUILD FAILED -- nothing sent >> "%LOG%"
  type "%LOG%"
  exit /b 1
)

set DECK_DIR=research\decks\sm_%DAY%
if not exist "%DECK_DIR%\manifest.json" (
  echo no manifest at %DECK_DIR% -- nothing sent >> "%LOG%"
  type "%LOG%"
  exit /b 1
)

REM Same ntfy attach path deliver_homework.py uses for the 11:05 deck -- one
REM PUT per file, topic resolved from %OMEN_NTFY_TOPIC% inside notify_ntfy.py
REM itself, never passed or hardcoded here. sm_deck cards are separate PNGs,
REM not one self-contained HTML file, so each card is its own attachment
REM instead of one combined push.
set SENT_ANY=0
for %%F in ("%DECK_DIR%\*.png") do (
  set SENT_ANY=1
  python notify_ntfy.py --file "%%F" --filename "%%~nxF" --title "OMEN bar deck %DAY%" --body "Tap the entry bar you would actually have taken (A/B/C), then run sm_deck.py --mark-bar to record it." --tags books >> "%LOG%" 2>&1
)
if "%SENT_ANY%"=="0" (
  echo no cards built for %DAY% -- nothing to send >> "%LOG%"
  type "%LOG%"
  exit /b 1
)

echo deck: %DECK_DIR% >> "%LOG%"
type "%LOG%"
endlocal
exit /b 0
