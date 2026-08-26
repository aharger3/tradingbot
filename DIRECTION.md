# DIRECTION — what this repo is trying to finish

Read this **after** `CLAUDE.md` and **before** picking up work. `CLAUDE.md` holds the
invariants you must not break. This file holds the goal, where we stand against it, and
what an agent is allowed to do without Austin in the room.

Charted 2026-08-26. Supersedes nothing; it pulls the OMEN 6 destination
(`Austin's Vault/.scratch/omen-6/map.md`) into the repo so an agent that never opens the
vault still knows what "done" means.

---

## The goal

OMEN closes when all three are true at once, on one fixed measurement rig:

| gate | target | where we stand (2026-08-26, 2-year replay, 1,016 traded signals) |
|---|---|---|
| **Recall** | fires on ≥90% of Austin's **S-grade** days it has never seen | **17.9%** with today's grader; 42.9% with `research/downgrade.py` (t66) |
| **Money** | ≥55% win rate, mean R ≥ 2.0 | **53.2% / +0.957R** |
| **Durability** | every month green, every slice | **23 of 25 months** green |

Recall is the wound. Money is half-paid. Durability is nearly there.

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

**Every new measurement must carry both grades side by side** until the day
`downgrade.py` is wired in and the legacy ladder is deleted.

---

## Standing invariants

Beyond `CLAUDE.md`'s "never lose a mark":

1. **Stops trigger on the candle CLOSE**, fill at that close, floored at **−1.25R**.
   Wicks stop nothing. Verified in the 2-year replay: worst traded outcome is −1.000R,
   so the floor never binds today — it exists for the slippage case.
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

- **The 84% rule is effectively dead in backtest** — 3 fired signals in two years.
  Either the arming gate is too strict or detection never reaches it. Unmeasured.
- **One Candle Rule is 4,389 detections → 67 traded** (98.5% graded X). Same shape of
  problem as the recall gate, one setup down.
- **Scratch is nearly extinct** — 5 of 1,016 traded outcomes. The T4(b) failed-entry
  scratch and the EOD scratch may not be reaching the ladder path.
- **ON WATCH has no A/B on the 2-year rig.** `t61_onwatch_ab.py` measures it over 120
  graded day-cards only.
- **Symbol coverage is wildly uneven** — COIN 104 traded signals, SOFI and ACHR 2 each.
  Per-symbol numbers below ~20 trades are noise and should not be read.
