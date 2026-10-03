# tradingbot — OMEN

Intraday signal engine (break-and-retest / one-candle-rule setups, 09:30–11:00 ET). Repo
`aharger3/tradingbot`, production working copy `C:\Users\aharg\Desktop\Projects\tradingbot`.

**New here? Read `SWARM.md` first** — the base-hash rule, the done rule, and the
never-lose-a-mark rule. `CLAUDE.md` is the detailed agent manual underneath it. This file is
a map: what's running today, where things live, how to touch the code safely.

```
verify: python research/regression_gate.py && python research/test_runner_stop.py && python research/test_universe_single_source.py && python research/test_propfirm_gate.py && python research/test_propfirm_luck_check.py
```

## Where the project stands (2026-09-27)

The v3 signal engine (`signal_runner.py`) does **not** survive out-of-sample on the eye-loop's
own instrument (MNQ, −0.17R, n=46 proxy book). It is not fundable and nothing wires it to a
live order. Paper only, everywhere, always.

The active build is the **eye loop**: instead of the engine grading its own setups, it shows
Austin a chart card and asks *him* — S or Not-S — and only trades what he confirms. Shipped
2026-09-26/27 (PRs #39–#43), replay mode only (see below).

## The eye loop, end to end

```
candidate generator  →  phone card (chart PNG + ntfy S / Not-S)  →  120s S-gate  →  paper trade  →  journal  →  4:30pm report
research/agent_runs/      eye_card/chart.py, notify.py             research/agent_runs/   research/paper_journal/   eye_report.py
v3-eye2-candidates/                                                  v3-eye4-paper/
```

- `eye_runner.py` wires the pipeline. **Replay mode only as of 2026-09-26** — no live 1-minute
  feed is connected (`research/agent_runs/v3-eye2-candidates/README.md`). It replays one
  recovered historical NQ session (sized as MNQ), pacing card sends to the same wall-clock
  offset the setup actually fired at, so it feels live for tapping practice. Every card title
  carries `--title-prefix` and every row lands in `research/paper_journal/acks_replay.jsonl`,
  never a live journal. **No orders are ever placed.** Detail: `research/omen/v3/eye-live.md`.
- `eye_card/` — `chart.py` renders the candidate PNG; `notify.py` sends the ntfy card;
  `server.py` is the local label endpoint (port **9135**) the ntfy buttons call back to;
  `labels.py` appends every tap to `eye_card/labels.csv`.
- `eye1` classifier (`omen-eye1-classifier` branch, PR #39, unmerged to main): interpretable
  S/Not-S classifier trained on Austin's own marks, out-of-sample by date. **Can't copy his
  eye** — AUC 0.54, near coin-flip. Measured, not shipped.
- `eye_report.py` — reads `eye_paper.daily_summary()` off the loop's own (replay) journal and
  pushes one ntfy summary card at 16:30 ET. Paper only.

## Gates (what has to stay green before anything ships as default)

| gate | file | what it checks |
|---|---|---|
| no-regression | `research/regression_gate.py` | green-months don't fall, $/day doesn't fall >5%, both halves (H1/H2) — Austin's rule, 2026-09-05 |
| runner stop | `research/test_runner_stop.py` | stops fire on closes, floor at −1R, wicks stop nothing |
| universe | `research/test_universe_single_source.py` | no module keeps a private ticker list — `universe.py` is the one source |
| prop-firm drawdown | `research/test_propfirm_gate.py` | funded-account drawdown limit, wired into the nightly loop (weekly) |
| prop-firm luck check | `research/test_propfirm_luck_check.py` | day-shuffle check so a green run isn't order-of-days luck |

All five run in `verify:` above and in the nightly loop. A change that fails any of them stays
behind a flag, OFF — holding a change is a normal outcome, shipping a regression is the failure.

## Reports

| report | when | what |
|---|---|---|
| `OMEN-DailyReport` | weekdays 16:30 ET | daily engine summary, ntfy |
| `OmenEyeLoopReport` (`eye_report.py`) | Mon–Thu 16:30 ET | eye-loop paper-trade summary for the day's replay session, ntfy |
| `research/g215_precision.py` | nightly | pick-level precision stats (Wilson intervals, recall, per symbol/setup/grade) — `research/g215_precision.md` |
| `research/daily_homework.py` | weekdays 16:15 ET | homework deck, `research/decks/omen-daily-<day>.html` |

## Scheduled tasks (Windows box, `Get-ScheduledTask`)

Eye loop: `OmenEyeLoopReplay` (Mon–Thu 09:28 ET, replays a session and sends cards),
`OmenEyeLabelServer` (always-on, the ntfy-button callback), `OmenEyeLoopReport` (Mon–Thu
16:30 ET, above).

Eye cards are tap-to-answer (`eye_card/tap.py`): one push to the vault's `NTFY_TOPIC` with S / Not S / Skip
buttons that post to the `tap-answer` service, which writes `eye_card/labels.csv` (S/notS) or `skips.csv`.
Mon-Thu only, max 5 cards/day (`cards_sent.jsonl`). `--blind` hides ticker, date, grade and absolute prices;
`--legacy-label-server` restores the old Tailscale buttons. `python -m eye_card.tap sample [--blind]` prints a
masked payload and sends nothing.

Engine / homework / infra: `OmenNightlyLoop` (20:00, the no-regression loop + gates),
`OMEN-DailyReport` (weekdays 16:30), `OmenDailyHomework` / `OmenDailyHomework1105`,
`OmenDailyReview`, `OmenBarDeck`, `OmenPremarketCard` / `OmenPremarketList`,
`OmenSignalBot`, `OmenScannerSentry`, `OmenHealthCheck`, `OmenForwardClock`,
`OmenLoopSupervisor`, `OmenArchiveRetry`, `omen-corpus-harvest`, `OmenSundayBacktest`,
`OmenSundaySummary`, `OmenA6PaperLog`, `OmenV5LegacyExitTest`.
`EVGradeLegs` (04:00) is the separate EV-engine grader, not OMEN, sharing this box.
Disabled: `OmenHealthDaily`, `OmenSignalDigest`, `OmenWeeklyDigest`.
Run `Get-ScheduledTask | Where TaskName -match Omen` for the live list — this table goes
stale the day a task is added or renamed.

## Production vs experiments — the worktree rule (Austin, 2026-09-26)

**`C:\Users\aharg\Desktop\Projects\tradingbot` is production.** It stays on `main`, clean.
The scheduled tasks above all run from this checkout. **Never `git checkout` a branch in it.**

Experiments run in a separate worktree:

```
git worktree add ..\tradingbot-lab <branch>     # or a one-off name, e.g. tradingbot-docs-readme
```

An experiment that only chases S-trade accuracy in isolation doesn't justify touching
production. After any build that switched branches anywhere, confirm production is back on
`main` and clean before 19:30 ET (`OmenNightlyLoop` runs at 20:00):

```
cd C:\Users\aharg\Desktop\Projects\tradingbot; git checkout main; git status
```

## Data locations

| path | what | notes |
|---|---|---|
| `data_archive/` | frozen 2-year OHLCV archive, `backtest_2y.py`'s source | frozen 2026-09-13 (`research/tape/archive_manifest_2026-09-13.json`); read-only during a rebuild (`ARCHIVE_READONLY=1`); `--allow-drift` required to build past the manifest |
| `research/tape/` | the book ledger — `cycles.md`, `loop.json` (live source of book ids), `.rebuild_lock` | `daily_fetch.py` skips while the lock is held (>6h old = warns and fetches anyway) |
| `research/marks/`, `research/*_marks*.jsonl` | Austin's judged symbol-days — the only scarce input in this project | see "never lose a mark" in `CLAUDE.md`/`SWARM.md`; never delete or rewrite |
| `research/paper_journal/acks_replay.jsonl` | eye loop's replay-only paper-trade journal | never a live journal; no live equivalent exists yet |
| `eye_card/sent_charts/`, `eye_card/labels.csv` | rendered candidate PNGs and every S/Not-S tap | |
| `journal/` | daily run logs (`daily-<day>.log`, scanner logs) | |
| `logs/` | task/process logs | |
| `research/decks/` | homework decks (HTML) served to Austin | |
| `.env` | `POLYGON_API_KEY` and other secrets — never printed, never committed | filter tool output with `grep -v apiKey` before showing a traceback |

## Gaps

- `eye1` classifier (PR #39) and `eye4` paper execution (PR #42) are on branches, not yet
  merged to `main` — `main`'s `eye_runner.py` (PR #43) already imports both by path, so a
  from-scratch `main`-only clone needs those modules present or the loop won't import.
  [unverified whether main is currently runnable standalone — check before relying on it.]
  <!-- Note in the parent's file, not restated by an update-pusher after this task closes. -->
- Nightly-loop gate wiring for the eye loop itself (beyond `regression_gate.py`'s engine
  scope) is not confirmed — the five gates above cover `signal_runner.py`, not `eye_runner.py`.
- Live 1-minute feed for the eye loop: not wired. Replay-only until that lands.

## Worktrees (read before `git worktree add`)

A plain `git worktree add` materialises every tracked file, and this repo tracks ~2.4 GB of data
(`data_archive/` 788 MB, plus ~1.6 GB of result JSONs directly under `research/`), so each worktree
costs ~2.9 GB. On 2026-09-26/27 dispatched builder agents made ~95 of them (`tradingbot-<wave>-<slug>`).
Use `.\new_worktree.ps1 <name>` instead: it sparse-checks-out without those paths (~0.5 GB), and
`omen_paths.py` makes code read the main checkout's `data_archive/` (override: env `OMEN_DATA_DIR`).
Never copy data into a worktree. Need a big result JSON? `git show origin/main:research/<file>`, or read it from the main checkout.
