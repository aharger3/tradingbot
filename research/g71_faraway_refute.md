# G7.1 / adversarial verify of track `faraway` — verdict: REFUTED (as a recommendation)

Scripts, all committed with this note:
`research/g71_advrefute_faraway.py`, `..._sweep.py`, `..._mech.py`, `..._cluster.py`.
JSON: `research/g71_advrefute_faraway{,_sweep,_mech,_cluster}.json`.
Nothing in `research/g71_faraway.{py,md,json}` was touched. No engine file was edited.

## 0. What reproduces, and it reproduces exactly

Re-derived from `research/bt2y_trades.json` with a fresh implementation of the shipped
runner, the measured move, the pairing and the greens — reusing only `t5.replay`
(exit semantics) and `polygon_feed` (bars), which the claim is not allowed to re-implement.

| number | claimed | re-derived | |
|---|---:|---:|---|
| shipped whole-book mean R | +0.5487 | **+0.54867238** | match |
| `or_mmove` whole-book mean R | +0.5715 | **+0.57147230** | match |
| paired mean diff | +0.0228 | **+0.02279992** | match |
| its ±95% bar | 0.0183 | **0.01828185** | match |
| rows moved | 1,316 | **1,316** | match |
| mean extra distance | +1.104 R | **+1.10398 R** | match |
| total | +55.6 R | **+55.563 R** | match |
| months / weeks green, `or_mmove` | 25/25, 90/105 | **25/25, 90/105** | match |
| months / weeks green, shipped | 25/25, 90/105 | **25/25, 90/105** | match |

**The arithmetic is not the problem.** Look-ahead is not the problem either — see §2.
The problem is that four of the claim's load-bearing sentences are false, and the
survivor does not survive a single out-of-sample split.

## 1. FALSE — "the first exit-side arm in this project to move outside its own bar in the positive direction"

Contradicted by the table the claim cites. `research/g71_faraway.md` §4c, whole-book column:

| arm | vs inc | ±95% | report's own verdict |
|---|---:|---:|---|
| `or_mmove` | +0.0228 | 0.0183 | **no** (outside) |
| `or_atr3` | +0.0282 | 0.0229 | **no** (outside) |
| `or_2r` | +0.0110 | 0.0060 | **no** (outside) |

Three arms in the same run are positive and outside their bar, and `or_atr3` is larger.
"First" is false in the same table that is offered as evidence.

The T5 comparison behind "first" is also cross-book: `research/t5_structural-target.md:3`
measured its 47 arms and its "29 arms outside their bar, every one down" on **2,595**
traded rows. `research/bt2y_trades.json` today holds **2,437** (see §6).

## 2. FALSE — "proven by `--selftest` truncated-tape check"

Run it and the check passes, but it never touches `measured_move`. The hand-built tape in
`research/g71_faraway.py:958-961` is five identical bars (`l=99.5`) plus three; a
strength-1 swing low needs `bars[j]["l"] < bars[j-1]["l"]` strictly, so no swing exists:

```
mmove at i=5 full tape: None
candidates: {... 'swing': None, 'mmove': None, 'vwap': None ...}
```

`c_full == c_trunc` is therefore `None == None` for the one candidate the recommendation
rests on. The check is vacuous for `mmove` **by construction anyway**: `measured_move`
(`g71_faraway.py:167-176`) never indexes past `i`, so truncating at `i+1` cannot change it.

I ran the real causality test the selftest does not: recompute with the swing confirmation
window pulled back to `i-1` so bar `i`'s own print cannot confirm the leg origin
(`g71_advrefute_faraway.py::mmove`, `last_confirm_bar=i-1`). Result **+0.5741 mean R,
paired +0.02541 ±0.02029, 1,289 rows moved** — slightly *larger*, not smaller.
**There is no look-ahead.** The causality claim is true; the proof offered for it is not.

Note also that the proposed diff's own docstring is wrong about this:
"the leg origin is the most recent swing CONFIRMED at or before bar `i-1`" — the loop is
`for j in range(i - 1, ...)` and `j+1 == i`, so confirmation is at bar `i`. Harmless
(the rig treats bar `i` as complete at entry, exactly as `backtest_week.py:851` does for
`scale_level`), but it is the sentence being used as the causality argument.

## 3. FALSE as stated — "25/25 months green and 90/105 weeks green, both identical to shipped"

True only at an undisclosed, unswept free parameter. `measured_move` uses a **strength-1**
(3-bar) swing (`t5.is_swing_low`, `t5_structural_target.py:249`). The same script's `swing`
candidate uses the project's standing **`PIVOT_STRENGTH=2`** T10 pivot
(`g71_faraway.py:53` docstring, `t5_structural_target.py:48`). Nothing in the report
discloses or justifies the split.

Sweep of both parameters (`g71_advrefute_faraway_sweep.py`, all 2,437 rows):

| swing strength | lookback 10 | 15 | 20 | 25 | **30 (shipped claim)** | 35 | 40 | 45 | 60 |
|---|---|---|---|---|---|---|---|---|---|
| **s=1** paired mu | +0.0156 | +0.0219 | +0.0214 | +0.0206 | **+0.0228** | +0.0224 | +0.0228 | +0.0237 | +0.0242 |
| s=1 outside bar? | **no** | yes | yes | yes | yes | yes | yes | yes | yes |
| s=1 months / weeks | 25/25 91/105 | 25/25 91/105 | 25/25 90/105 | 25/25 90/105 | **25/25 90/105** | 25/25 90/105 | 25/25 90/105 | 25/25 90/105 | 25/25 90/105 |
| **s=2 (project's own pivot)** mu | +0.0305 | +0.0417 | +0.0373 | +0.0354 | **+0.0386** | +0.0383 | +0.0391 | +0.0404 | +0.0404 |
| s=2 months / weeks | 25/25 90/105 | **24/25** 88/105 | **24/25** 88/105 | **24/25** 88/105 | **24/25 89/105** | **24/25** 89/105 | **24/25** 89/105 | **24/25** 89/105 | **24/25** 88/105 |

At the project's own pivot strength the arm is **24/25 months and 89/105 weeks** — worse on
both. That is the exact criterion §7 reason 2 uses to reject `or_atr3`: *"it breaks
durability — 24/25 months green against the shipped 25/25. Durability is a gate, not a
tiebreak."* The recommendation's durability parity is a coin-flip on an undeclared knob,
and the knob that is *more* consistent with the rest of the repo fails the gate.

## 4. The bar is uncorrected, and the arm fails correction against its own report

`g71_faraway.md` tables **45 rows carrying a `null?` verdict** (§4 ladder 10, §4 single 10,
§4c 8, §5 9, §6 9 — counted from the file, minus the base rows). `or_mmove` is the one
picked out of them.

| correction | z needed | `or_mmove` t | passes? |
|---|---:|---:|---|
| none (as reported) | 1.960 | 2.4444 | yes |
| Bonferroni over §4c's own 4 arms | 2.498 | 2.4444 | **no** |
| Bonferroni over §4c's 8 tested columns | 2.734 | 2.4444 | **no** |
| Bonferroni over the report's 45 tabled tests | 3.261 | 2.4444 | **no** |

Uncorrected p = 0.0145. It does not clear correction against even the four-arm table it
appears in.

## 5. It survives no out-of-sample split

`g71_advrefute_faraway{,_mech,_cluster}.py`. Paired mu vs its own ±95% bar:

| split | n | mu | ±95% | outside? |
|---|---:|---:|---:|---|
| whole book (the claim) | 2,437 | +0.02280 | 0.01828 | yes |
| first calendar half | 1,036 | +0.01465 | 0.02539 | **no** |
| second calendar half | 1,401 | +0.02883 | 0.02567 | yes (barely) |
| drop 2026 | 1,511 | +0.01277 | 0.02105 | **no** |
| drop 2025 | 1,254 | +0.02545 | 0.02821 | **no** |
| drop 2024 | 2,109 | +0.02841 | 0.01959 | yes |
| drop AMD + IREN (2 of 28 symbols, 217 rows) | 2,220 | +0.01662 | 0.01874 | **no** |

Concentration and breadth:

- Only **544 of 2,437 rows change R at all** (413 better, 131 worse).
- The **top 25 rows carry 96.1%** of the +55.6 R; the top 10 carry 53.7%.
- The gain is **positive in only 15 of 25 months** (10 months are negative).
- Per-symbol: AMD +9.7 R, IREN +9.0 R … AVGO **−9.3 R**, ORCL −3.5 R.

What is robust: session-clustered, symbol-day-clustered and symbol-clustered bootstraps
(496 / 2,154 / 28 clusters, 20k draws) all exclude zero, and leave-one-*symbol*-out stays
outside the bar for all 28. So it is not one symbol and not one session. It **is** one
year and it **is** two symbols, and it is a null in the first half of the tape.

Mechanism (`..._mech.py`): the gain is **not** a hold-to-close artefact — only 2 rows flip
to a session-close exit (17 → 19), and stripping them leaves +0.02290 ±0.01829. The arm
genuinely lets 413 runners travel further. It just doesn't do it reliably.

## 6. Book: 2,437, not 2,595, and not 1,017

`research/bt2y_trades.json` meta: 76,019 signals, **2,437 traded**, `loss_halt: true`,
`halted: 857`, generated 2026-08-29T03:14:29 — written by commit `145d564e` (T23).
`research/t0_ratified_rebaseline.md:24` and `DIRECTION.md` both still describe that path as
**2,595 traded / +0.5481 R**, and `research/t5_structural-target.md:3` measured its 47 arms
on 2,595. The faraway run used the newest committed book, which is defensible — but it is
**neither** the book the claim's T5 comparison came from **nor** the book the standing
money gate quotes. `DIRECTION.md`'s money row is now stale by 158 trades and nobody has
said so.

## 7. Reachability — the branch is dead twice over

1. The proposed flag ships OFF: `RUNNER_MEASURED_MOVE = os.getenv("RUNNER_MEASURED_MOVE", "0")`.
   Applied as written, nothing changes.
2. The live path has **no runner leg at all**. `options_sizer.py:25 DEFAULT_RR = 2.0` sells
   the whole position at exactly 2R; `backtest_week.py:851-858` is backtest-only. The
   report says this itself in its last paragraph — the CLAIM does not.

So the +55.6 R is +55.6 R in a rig the live scanner does not run, gated behind a flag that
defaults off.

## 8. And the standing method rule says this is the wrong gate

`DIRECTION.md`: *"the standing method finding: every A/B this project has run moves less
than its own ±1.5799R error bar. Gate on held-out recall against the 100-card sample, never
on mean R."* This arm fixes entry, stop, side and entry bar, so it moves held-out S recall
by **exactly 0** — `g71_faraway.py`'s own docstring (lines 36-38) says so. +0.0228 R closes
**1.6%** of the 1.4513 R gap to the 2.0 R money gate.

## 9. Verdict

| the claim's assertion | status |
|---|---|
| +0.5715 vs +0.5487, +0.0228 ±0.0183, +55.6 R, 1,316 moved | **reproduced exactly** |
| measured move is causal | **true** (verified independently at `i-1` confirmation) |
| "proven by the `--selftest` truncated-tape check" | **false** — mmove is `None` on that tape |
| "first exit-side arm outside its bar, positive" | **false** — `or_atr3` and `or_2r` too, same table |
| "25/25 months, 90/105 weeks, identical to shipped" | **artefact** — 24/25 and 89/105 at `PIVOT_STRENGTH=2` |
| "outside its bar" | **fails Bonferroni over its own 4-arm table** |
| RECOMMENDED as a change to ship | **refuted** — null in the first half of the tape, null without 2026, null without AMD+IREN, 15/25 months positive, top-25 rows = 96% of it, and unreachable in the live path |

Recommend: do not ship, do not queue. If it is kept alive, it must first be re-run with
`PIVOT_STRENGTH=2` and reported as 24/25 months, and it must be measured on the same book
as whatever it is compared against.
