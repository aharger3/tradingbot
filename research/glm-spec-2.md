# GLM Spec 2 (2026-07-12) — mechanical infra

Predecessor: `glm-spec.md` (done 2026-07-11: Discord retry, --snapshot, check_archive,
news_days.json, hour table, 84rule_trades.json).

HARD RULES (same as last time — held, keep holding):
- Do NOT touch `omen_bot.py`, `signal_runner.py`, or `simulate_day` internals in `backtest_week.py`. Driver-level / new files only.
- No dashboards UI, no cron creation without Austin. Never commit — Austin pushes.
- Scheduled jobs: Python313 (`py -3.13`), NEVER hermes venv (updates wipe packages).
- Verify each task with a real run before calling it done.

Order: G1 (Fable waits on nothing, but wants these flags) → G2 → G3.

## G1. Backtest A/B flags (supports Fable session)
`backtest_12mo.py` + `backtest_week.py` `main()` only:
- `--entry-cutoff HH:MM` — overrides ENTRY_CUTOFF (default 11:00). Wire through however is cleanest WITHOUT editing simulate_day's signature semantics (module-level assignment before the loop is fine).
- `--skip-news` — drop dates in `news_days.json`→`news_days` from the day loop.
Verify: 30d run with `--entry-cutoff 10:30` vs without → signal counts differ sensibly; `--skip-news` run excludes 7/14-style dates from By Day table.

## G2. SPEC12 daily session review
After-close report (schtask 16:10 ET, Python313), new file `daily_review.py`:
- Read today's `journal/` signal log + paper trade results.
- One Discord embed via existing `discord_bot` (has retry): signals fired (symbol, grade, S, tags, outcome), paper P&L, tier-rule compliance check (S≥4+[hammer], max 2, stop-when-green — flag any violation), news-day note if applicable, posted/failed webhook counters.
- Empty day = one-line "no signals" post. Verify with a dry run against yesterday's journal.

## G3. Scanner status file (P6)
`live_scanner` writes `journal/scanner_status.json` each scan cycle: timestamp, symbols
scanned, signals fired today, session-halt state (losses/max-trades), last error, regime
state. Atomic write (temp + rename). Dashboard reads it later — file only, NO UI work now.
Touch live_scanner only at the scan_once call site / main loop, not signal logic.
