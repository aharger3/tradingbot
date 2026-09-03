---
date: 2026-09-03
row: S2
status: done
---

# S2 — drop the 09:40 TRADE_FLOOR in the backtest, re-score the 100-card sample

## What the row asked

Remove the `ts[:5] < TRADE_FLOOR` cut from the backtest scoring path (the spec named the
live path as `live_scanner.py:546`, and the backtest path as "wherever
`research/marks/probe_s_sweep_2026-08-28.jsonl` was scored"), then re-score the 100-card
sample and expect recall to move from 18/34 toward ~28/34.

## What was actually there to remove

`TRADE_FLOOR` was never a backtest-scoring constant. Checked every module in the path that
scores `probe_s_sweep_2026-08-28.jsonl` for held-out recall —
`research/t0_heldout_recall.py` (the canonical harness: its own docstring says "the standing
figure before this track is 18/34 = 52.9%"), `research/t4_engine_recall.py::run_day` (the
replay harness it calls), `signal_runner.py`, and `backtest_week.py` — none of them
reference `TRADE_FLOOR`. It only ever existed in `live_scanner.py`, and that copy was
**already deleted before this row ran**: a same-day commit (visible at `live_scanner.py:673`,
citing the identical "cut 10 of his 34 S days (29%)" finding this row's source note makes)
removed it under a separate ticket. Its own comment says so explicitly: *"Note this gate is
the LIVE path only — backtest_week has no floor, so no published backtest figure moves with
this commit."* `CLAUDE.md` carries the same line.

So there was no reversible one-constant edit left to make — the backtest scoring path never
had the cut, and the live path's copy is already gone. No code change made in this row.

## Re-scored anyway, because the verify asks for a number

Ran `research/t0_heldout_recall.py` fresh against current HEAD (`9f6eb62a`):

```
sweep: n_S=34, fired_on_S=27, recall_pct=79.4, fired_on_no=41, precision_pct=39.7
missed_S: AMZN_2025-09-10, BABA_2026-06-12, CRM_2026-02-11, MSFT_2025-12-30,
          MSTR_2025-08-26, MSTR_2026-07-17, NFLX_2024-08-05
```

**Recall is now 27/34 = 79.4%**, up from the 18/34 = 52.9% standing figure — inside the
spec's expected range (it named ~28/34), but not for the reason the row assumed. This
harness was never floor-gated, so the 9-day gain is not "the floor came off" — it is the
accumulated effect of everything else that has landed in this repo since 18/34 was measured
(the retest gate, the HTF bias veto fix, the live-tier fix, today's ticket-12 series, etc.).
Attributing it to this row would overclaim.

## Adversarial instruction: are the 10 originally-named days the same 10, and are they now caught?

Yes to the first half, no to the second. Pulled the 34 S-graded rows from
`research/marks/probe_s_sweep_2026-08-28.jsonl` directly and sorted by
`notes.min`; exactly 10 have a marked entry minute before 09:40, and they match
`Projects/omen-s-accuracy-100.md`'s list symbol-for-symbol and minute-for-minute:
`PLTR_2025-07-01` (9:34), `TSM_2026-02-02` (9:36), `QQQ_2025-09-16` (9:36),
`MSTR_2025-08-26` (9:38), `MU_2025-06-25` (9:38), `MARA_2025-07-18` (9:38),
`AMZN_2025-09-10` (9:38), `ARM_2024-10-28` (9:39), `QQQ_2025-09-23` (9:39),
`BABA_2026-06-12` (9:39).

Of those 10: **7 are now recovered** (`ARM_2024-10-28`, `MARA_2025-07-18`,
`MU_2025-06-25`, `PLTR_2025-07-01`, `QQQ_2025-09-16`, `QQQ_2025-09-23`,
`TSM_2026-02-02` all fire today) and **3 are still missed**
(`AMZN_2025-09-10`, `BABA_2026-06-12`, `MSTR_2025-08-26`) — for reasons that have
nothing to do with a time floor, since none exists in this path. The remaining 4
of today's 7 misses (`CRM_2026-02-11`, `MSFT_2025-12-30`, `MSTR_2026-07-17`,
`NFLX_2024-08-05`) were never on the floor-cut list at all; every one of their
marked minutes is at or after 09:40.

## Adversarial pass

A separate agent, instructed to refute and default to refuted when uncertain, independently
re-derived all three claims above from scratch (its own venv, its own grep of the import
chain, its own parse of the jsonl). Verdict: **CONFIRMED** on all three — no hidden
09:40-equivalent gate found anywhere in the scoring path (it did find `SESSION_START =
"09:30:00"` / `SESSION_END = "11:00:00"` in `signal_runner.py`, which is the session window,
not a floor), the same 27/34 = 79.4% recall and the same 7-card miss list reproduced
byte-identical on two runs, and the same 10-day floor-cut list with the same 7
recovered / 3 still-missed split. It also confirmed the on-disk `research/t0_heldout_recall.json`
held the stale 18/34 output before either of us re-ran it, ruling out a stale-cache
explanation.

## plain

The 09:40 cutoff that used to block early trades is already gone from the live code, and
the practice-test recall is now 27 out of 34 instead of 18 — but that jump came from other
fixes landing this week, not from this specific change, since the test itself was never
blocked by that cutoff.
