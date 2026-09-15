# V5 contract — tap-to-fire, engine side

Row V5 (`omen-10-0-spec.md`, "Phase V addendum", 2026-09-14). This repo
(`tradingbot`) owns everything below the line; the card-dealing itself is
**not** in this repo — it is the stage-manager's job, a cron in the Desktop
session that reads the file this contract describes and deals
`AskUserQuestion` cards. This doc is the exact interface between the two.

## 1. The file: `journal/candidates_<YYYY-MM-DD>.json`

Written by `research/candidates_writer.py`, called from `live_scanner.py`
(`_emit_signal`) every time an S or A grade fires in the 09:30–10:30 ET
window. Updated in place as new candidates arrive during that hour — the
stage-manager should poll it, not assume it is final until 10:30.

```json
{
  "day": "2026-09-14",
  "candidates": [
    {
      "id": "AAPL_2026-09-14_0944",
      "symbol": "AAPL",
      "day": "2026-09-14",
      "ts": "09:44:00",
      "setup": "break_and_retest",
      "level": "PDH",
      "direction": "call",
      "entry": 231.40,
      "stop": 230.85,
      "pt1": 232.60,
      "grade": "S",
      "chart_png": "journal/candidate_charts/AAPL_2026-09-14_0944.png"
    }
  ]
}
```

- **At most 3 rows**, arrival order — the file is never reordered, and a
  candidate already written is never edited or removed (idempotent append).
- `id` is `<SYMBOL>_<DAY>_<HHMM>` (24h, no colon) — this exact string is what
  `research/paper_order.py --id` / `--pass` expects.
- `grade` is Austin's letter (`S` or `A`), already translated
  (`sac_grade`/`his_grade`, not the engine's internal A+/A/B/C/X ladder).
- `chart_png` is a repo-relative path to a PNG rendered the same way the
  daily homework deck renders (`research/g210_render_cards.py`'s pipeline:
  1-min candles + PMH/PML/PDH/PDL/ORH/ORL as labelled lines, cut at the
  signal bar — no lookahead), with ENTRY/STOP/PT1 added as three more level
  lines. It can be `null` if chart rendering failed (archive bars
  unavailable, e.g. mid-session on a day not yet archived) — the
  stage-manager should deal the card without an image rather than fail.

## 2. The two CLI calls

Both live in `research/paper_order.py`, invoked by the stage-manager when
Austin answers a card (or the 10:35 cutoff fires with no answer — see §3).

```
python research/paper_order.py --arm austin --id <candidate id>
python research/paper_order.py --arm austin --pass <candidate id>
```

- `--id` books a paper order on Alpaca's paper endpoint, sized to 1R =
  **$1,000** (the project-wide fixed unit, CLAUDE.md) floored by
  `signal_runner.min_risk_floor`, tagged `"arm": "austin"` and
  `"candidate_id": "<id>"` in `journal/alpaca-paper.jsonl`. `candidates_*.json`
  carries no `max_loss` today; the code reads one if a future row adds it.
- `--pass` writes one `{"event": "pass", "candidate_id": ..., "arm": "austin"}`
  line to the same ledger — no order.
- **Idempotent on `<id>`**: either call refuses (nonzero exit, prints
  `REFUSED:`) if that candidate id already has an `entry` or `pass` row in
  the ledger. Safe to retry a flaky invocation; never books twice.
- Exit codes: **0** = logged (booked or passed). **2** = refused because that
  id already has an `entry` or `pass` row -- already handled, do not retry.
  **1** = failed (no such candidate, broker error) -- nothing was written to
  the ledger, so the card is still unhandled and a retry or a `--pass` is
  needed. Never treat 1 and 2 the same: a swallowed 1 is a card that silently
  vanished from both arms.

## 3. The 10:35 cutoff

A candidate written at any point in the 09:30–10:30 window is dealt as a
card. If Austin has not answered by **10:35 ET**, the stage-manager calls
`--pass` on it itself — an unanswered card is a pass, not a silent drop, so
the ledger and the morning report both see it. This repo does not enforce
the cutoff; it only makes `--pass` idempotent and safe for the stage-manager
to call unprompted.

## 4. The ledger: `journal/alpaca-paper.jsonl`

Every line now carries `"arm"`: `"engine"` on every row `live_scanner.py`'s
existing Alpaca path writes (V4's `--paper-broker alpaca`, unchanged
otherwise — this row only added the tag plus `max_loss`/`pnl` for R
math), `"austin"` on every row `research/paper_order.py` writes. Exit rows
carry `pnl` (dollars) and `max_loss` (the position's own 1R) so a real R can
be computed instead of assuming a size.

## 5. The morning report

`research/morning_report.py` prints, after its existing per-symbol summary,
a two-column block reading the whole ledger (not just one day, since a
verdict needs the row's own sample floor — 30 trades / 12 months, SWARM.md
law 3):

```
Engine vs Austin (paper, 1R = $1,000):

            trades      wins    mean R       $/day
engine           X       W/N     +0.XXXR     $+NNN/day
austin            X       W/N     +0.XXXR     $+NNN/day
```

`trades` counts entries logged for that arm; `wins`/`mean R`/`$/day` are
computed only from exits that carry a `pnl` (an arm with entries but no
matched exit yet reports `-` rather than a fabricated number).

## What this row does NOT do

- No card-dealing, no `AskUserQuestion` call, no cron -- the stage-manager's
  job, out of this repo. Invoke both CLIs with the repo root as the working
  directory (`cd C:\Users\aharg\Desktop\Projects\tradingbot`); every
  path in this contract is repo-relative.
- **Arm B books the underlying, not an option.** `paper_order.py` sends a
  share order (a `put` candidate books a SHORT of the underlying). The
  engine arm tries an Alpaca option contract first and only falls back to
  shares. Until that is reconciled the two columns share a direction and a
  1R but not an instrument -- do not read the two `$/day` figures as a
  like-for-like score.
- No automatic exit management for Arm B: `research/paper_order.py` books
  the entry only. Until a matching exit path exists for Austin's own paper
  trades, the morning report's `austin` column may show entries with no
  closed trades yet (reads `-` for wins/R/$-day) — this is expected, not a
  bug, and the next row should close that loop before any 25-session
  verdict is written.
