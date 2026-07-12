# GLM Coding Spec — OMEN nitty-gritty only (2026-07-11)

Austin's scope: NO dashboards, NO cron/channel setup, NO polish. Only: Discord signal
webhooks firing reliably + backtest infrastructure + edge understanding support.
HARD RULE: do not touch `omen_bot.py` or `signal_runner.py` detection/grading logic — Fable-only.

## Task 1 — Discord webhook reliability (highest priority)
Goal: every signal the scanner generates MUST reach Discord, and we must know when it doesn't.
- Read `discord_bot.py` + how `live_scanner.py` posts signals (and `signal_tracker.log_signal`).
- Add: retry with backoff (3 attempts) on webhook POST failure; on final failure append the
  full payload to `journal/failed_webhooks.jsonl` so nothing is silently lost.
- Add: startup self-test `python discord_bot.py --test` → posts one test card, prints HTTP status.
- Add: each scan cycle logs `posted=N failed=M` line so scanner-*.log shows delivery health.
- Verify end-to-end with a dry run (paper mode, fake signal injection if needed).
- Env/keys: webhook URLs come from .env / settings — never hardcode, never print full URLs.

## Task 2 — Backtest infrastructure hardening
- `backtest_12mo.py`: add `--snapshot` flag that on completion copies backtest_charts.json →
  backtest_charts_12mo.json and backtest_report.md → backtest_report_12mo.md (manual cp today).
- Data completeness check: script `check_archive.py` — for each symbol in watchlist × last 251
  trading days, report % days with cached Polygon data; list gaps. (Gaps silently shrink backtests.)
- Add per-entry-HOUR split to `write_report` in backtest_week.py (9:30-10:00 / 10:00-10:30 /
  10:30-11:00): YouTube stat says 75% of Scarface trades cluster ~10:00 AM — we need our own
  hour-by-hour win-rate table to test time-weighting. (Report-only change, no detection logic.)
- news_days.json builder: FOMC/CPI/PPI/NFP dates, past 24mo + next 3mo (hardcoded list from BLS/Fed
  calendars is fine — no fancy fetcher). Used by Fable's news-day filter in backtests.

## Task 3 — 84% rule data prep (supports conflict resolution)
- From backtest_charts_12mo.json: extract every reentry_84_rule trade with its outcome + the
  original stopped trade's context into `research/84rule_trades.json` (mechanical join, no analysis).

## Explicitly OUT of scope
Dashboards, morning briefing, pm2/schtask changes, new channels, UI anything, refactors,
git commits (Austin pushes).
