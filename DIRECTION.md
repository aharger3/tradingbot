# DIRECTION — what this repo is trying to finish

Read this **after** `CLAUDE.md` and **before** picking up work. `CLAUDE.md` holds the
invariants you must not break. This file holds the goal, where we stand against it, and
what an agent is allowed to do without Austin in the room.

Charted 2026-08-26, gates re-measured 2026-08-28. Supersedes nothing; it pulls the OMEN 6 destination
(`Austin's Vault/.scratch/omen-6/map.md`) into the repo so an agent that never opens the
vault still knows what "done" means.

---

## The goal

OMEN closes when all three are true at once, on one fixed measurement rig:

| gate | target | where we stand (2026-08-29, after T0) |
|---|---|---|
| **Recall** | fires on >=90% of Austin's **S-grade** days it has never seen | **52.9%** (18 of 34) on the 100 fresh cards of 2026-08-28. **T0's ratified re-baseline did not move it: 18/34 before, 18/34 after, the same 16 misses card for card** (`research/t0_ratified_rebaseline.md`). Precision on the same sample is 35.3%. |
| **Money** | >=55% win rate, mean R >= 2.0 | **43.1% / +0.5481R** on 2,595 trades after T0 landed R1-R27 (was 53.1% / +0.8341R on 1,017). The book got bigger and worse per trade; the fall is -0.2860R against a +/-0.1725R bar, so it is real. |
| **Durability** | every month green | **25 of 25 months** -- MET for the first time (was 23 of 25). |

Recall is the wound. Money went backwards. Durability is **met**.

**Re-baselined 2026-08-29 by T0** (`research/t0_ratified_rebaseline.md`,
`research/t0_rebaseline.py`): Austin's 33 ratified answers landed as configuration,
the two-year book went 1,017 -> 2,595 traded and +848R -> +1,422R total, and every
money number above is from that book. Every earlier money figure in this file and in
`research/omen6_backtest_truth.md` describes the pre-ratification engine.

**Three things reframe all three rows, all measured 2026-08-28. Read them before acting on
any number above.**

1. **The live scanner does not run this book.** `live_scanner._tier():546` promotes to TRADE
   only on `grade == "A+"`, and `A+` fires **twice in 45,193 signals over two years**. The
   1,017-trade book comes from `backtest_week`, a different gate. **Every number in this table
   describes a system the live path would not trade.** This is the real-money blocker and it
   outranks every gate.
2. **The miss is grading, end to end.** T1 (`research/t1_entry_minute_autopsy.md`) found the
   engine is **never silent** on his S days — 0 of 34 — and its timing is **exact** (median
   +0.0 bars). It reaches his setup and grades it `X`. Zero of his 34 S days were graded S.
3. **Mean R 2.0 is arithmetically unreachable on the current exit.** `mean R = wT − (1−w)`;
   at 54% win the average *winner* must make **4.56R**, and every row plans exactly 2.000 R:R.
   The whole exit family is worth **+0.06R** against a 1.10R gap. What clears the gate is the
   **instrument** (the same rows as 0DTE ATM contracts read **+1.4988R**) and **selection**
   (one-trade-per-day oracle **+2.2125R at 76.6% win**). See `Projects/omen-x-board.md`.

**And the standing method finding: every A/B this project has run moves less than its own
±1.5799R error bar.** Gate on held-out recall against the 100-card sample, never on mean R.

Two supporting conditions, in scope because the gates are unreachable without them:

- **Elicitation** — getting a rule out of Austin costs minutes, not a deck-day.
- **Corpus** — the corpus **validates rules Austin states**. It never invents them.

---

## Two grading ladders. Do not mix them.

This is the single most confusing thing in the codebase and it has cost real time.

| ladder | values | who owns it | where it lives | wired into detection? |
|---|---|---|---|---|
| **Austin's** | `S` · `A` · `C` · `none` | Austin | `research/downgrade.py`, `Projects/omen-rulebook.md` | **No — measured only** |
| **Engine legacy** | `A+` · `A` · `B` · `C` · `X` | the code | `signal_runner.py::_grade_pa` | Yes, and it is the one that gates trades |

- **S = zero downgrades tripped · A = one · C = two (C is the floor).** Confluence
  (BR + OCR + level) is **+1**, so one downgrade plus clean confluence is still S.
  The arithmetic is `score = tripped − confluence`; it exists because a grade has to be
  reproducible from bars, not from a person's memory of a chart.
- **`X` is not a grade.** It means *the engine should not have fired at all* — a
  detection error, not a bad setup. 42,916 of 45,170 two-year signals are X. Any report
  that ranks X alongside S/A/C is comparing a grade to a bug report.
- **`none` is a judgement**, not a blank: Austin looked and refused the day.
- The legacy ladder is effectively one bucket — **999 of 1,016 traded signals are B**.
  It answers "is this candle a hammer at a level" (shape). Austin's eight variables are
  about structure. It is not a buggy grader; it answers a different question
  (`research/t62_veto_autopsy.md`).
- **And it is not what selects the trades.** 968 of those 1,016 are `B` only because
  `_calibration_grade` floors the *first with-trend signal of the day, inside 90 minutes*
  to B. `_grade_pa` is effectively binary — `C` (alert) or `X` (silent). The engine's real
  entry rule is arrival order (`research/g4_dropped_s.md` §6).
- **`at_key_level` is NOT hardcoded to the opening range.** Every `grade_trade` call site
  passes the level the setup actually broke; the parameter is merely still *named*
  `or_high`. Corrected in `t62_veto_autopsy.md` 2026-08-23, re-verified by G4: OR levels
  drop at 96.6%, everything else at 96.4%. Do not scope a ticket against this bug.

**Every new measurement must carry both grades side by side** until the day
`downgrade.py` is wired in and the legacy ladder is deleted.

---

## Standing invariants

Beyond `CLAUDE.md`'s "never lose a mark":

1. **Stops trigger on the candle CLOSE**, fill at that close, floored at **−1.25R**.
   Wicks stop nothing. **The claim that used to sit here — "worst traded outcome is
   −1.000R, so the floor never binds" — was true of the file and circular as
   evidence.** `backtest_week.py` triggered on the close and then filled at `t.stop`,
   which is −1.000R by construction, so the floor was unreachable code. 458 of the
   book's 474 stop-outs (96.6%) had already closed past 1R
   (`research/x2_stop_floor_audit.md`). Fixed 2026-08-28 by
   `stop_rule.stop_fill_price`, the one fill definition every rig now routes through
   (`research/t11_stop_fill_fix.md`): the floor clamps 303 of 475 traded losses and
   the book means −0.1210 R less.
2. **One tolerance unit**: 25% of the previous candle's range (`BAR_EXTREME_FRAC`).
3. **R is the result; dollars are a sizing skin.** 1R = $1,000, instrument is options.
4. **`universe.py` is the only place a symbol list may live.** A test fails the build if
   a module grows a private one.
5. **If you publish a number, commit the script that made it** — in the same commit.
6. **Measure, then wire.** 5.2 published a scale-out table nobody could reproduce.
   `downgrade.py` is deliberately unwired for exactly this reason.

---

## What an agent may do unattended

Ranked by how safely it runs without Austin.

**Green — go.**
- **Corpus validation.** `research/corpus_query.py` over `corpus_index.jsonl` (5,460
  provenance-tagged rows). Answers land as CONFIRMED / CONTRADICTED / UNMENTIONED
  against a rule Austin already stated. Never as a new rule. This is the most
  productive unattended lane in the project.
- **Measurement rigs.** `t60_baseline`, `t61_onwatch_ab`, `backtest_2y`, sweeps.
  Re-runs are free and reproducible; write the finding next to the script.
- **Bug fixes with a failing test first**, in the `research/test_*.py` style already here.
- **Building homework instruments** — decks, probes, Q&A pages. The delivery contract is
  hard: saves as he works, exports without a round trip, works on a phone, static SVG
  charts, never relies on the artifact runtime to persist answers.
- **Repo hygiene** that touches no mark file and no published number.

**Amber — do it, then flag it in the summary.**
- Threshold tuning inside `downgrade.py`. Austin gave the eight variables, never the
  numbers. Every constant there is a guess and is commented as one.
- Anything that moves a published figure. Say which figure moved and by how much.

**Red — needs Austin.**
- Grading cards. His judgements are the only scarce input; nothing else in the project
  is unrecoverable.
- Any new rule, or resolving a contradiction between two things he said.
- Flipping `INCLUDE_SPY_IN_BACKTEST`, retiring a symbol, changing the money gate.
- Wiring `downgrade.py` into detection.

---

## Session pickup protocol

1. Read `CLAUDE.md`, then this file, then `TASKS.md`.
2. Take the top **green** task in `TASKS.md` that is not claimed.
3. Do it end to end, including its check. No half-landings.
4. Append the result to `TASKS.md` under Done, with the commit hash and the number
   that changed. Move anything you discovered into the queue rather than doing it now.
5. If you touched a human-judgement file, run `git status` and **look** — the
   `.gitignore` in this repo has silently eaten mark files twice.

---

## Known open bugs (2026-08-26)

- ~~**The 84% rule is effectively dead in backtest**~~ — **measured 2026-08-26**
  (`research/p7_84_rule.md`, `40fdadd3`). It is the arming gate: 7 of 472 opportunities
  survive it. Opening it yields 116 re-entries at +0.792R — positive, but under the
  book's own mean, so it dilutes. Default unchanged. The remaining unmeasured piece is
  the detector: 433 armings produced 116 signals and the 317 that never fired are
  un-autopsied.
- **One Candle Rule is 4,389 detections → 67 traded** (98.5% graded X). G4 attributed the
  drop: the order-block path demotes every `B` to `C` at the detection site, so it can
  never ship a tradeable grade on its own, and its $0.50 / 0.4%-of-price stop gates were
  tuned on a stale 12-month yfinance split. The bigger gap is upstream — 40,783 B&R
  detections against 4,389 OCR, 9.3x.
- ~~**Scratch is nearly extinct**~~ — **answered 2026-08-26** (`research/p8_scratch.md`).
  All 5 are EOD scratches, and that is correct: the T4(b) failed-entry scratch was
  **unreachable over 43,374 trades** (closest approach +0.0001 bar-ranges, zero crossings)
  and is now deleted, book byte-identical. Austin's clause-2 scratch is a *live fill
  correction* the backtest structurally cannot hold — it already knows the entry bar's
  close, so it declines the entry instead of scratching it. `ENTRY_SCRATCH=level` is the
  nearest expressible rule, default OFF, and costs −107.06R. Still open: **nothing in the
  live path implements clause 2 either** (`paper_trader.py` has no scratch outcome), and
  the backtest is optimistic *in count* on ON WATCH fills — 65.3% of entries are filled at
  the level, and live, some share of those would scratch instead of never opening.
- **ON WATCH has no A/B on the 2-year rig.** `t61_onwatch_ab.py` measures it over 120
  graded day-cards only.
- **Symbol coverage is wildly uneven** — COIN 104 traded signals, SOFI and ACHR 2 each.
  Per-symbol numbers below ~20 trades are noise and should not be read.
