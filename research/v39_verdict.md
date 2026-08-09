# v39_verdict — omen-3.9 T8

Read-only synthesis of T1–T7 plus the one measurement this row runs. **Every
number below is quoted from a file, not recomputed in this prose.** The
measurement figures come from `research/t8_measure_output.json`, the stored
output of `research/t8_verdict_measure.py` — the backtester replayed twice
over the same window (the 15 measurable priority-pool symbols' full
`data_archive`, the source `research/t4_engine_recall.py` uses; yfinance is
dead for OMEN). The taxonomy counts come from `research/t1_taxonomy_rerun.md`
and `research/t2_timing_miss.md`; the corpus counts from
`research/t3_marks_v3.md`; the per-pool recall from `research/t7_pools.md`;
the gate output from a live `python research/regression_gate.py` run (exit 0,
quoted verbatim below). Flags confirmed at write time:
`signal_runner.TRADE_S_ONLY = False` (verified by the gate's own check),
`signal_runner.HTF_OPPOSITION_VETO = "hard"` (the shipped default; the measure
script restores it on exit). **Nothing is armed.** `TRADE_S_ONLY` was forced
True in-process only inside the measure script and is False in the committed
code.

The grep-able lines, in the form the row requires:

    s_fired_recall_v3: 12/77
    s_only_trades: 591
    htf_hard_S: 591
    htf_fill_override_S: 591
    gate exit code: 0

---

## 1. The new taxonomy (T1/T2): One Candle Rule candidates vs timing_miss

T1 (`research/t1_taxonomy_rerun.md`) restructured `classify_no_detection` so
the order block (`detect_order_block_setup`, i.e. the One Candle Rule per
`omen_bot.py`'s `SignalType.ONE_CANDLE_RULE`) is evaluated **before**
`no_break_retest` is assigned. The old code short-circuited to
`no_break_retest` the instant break-and-retest was falsy, so the One Candle
Rule was structurally invisible — not one of the 27 `no_break_retest` S marks
of omen-3.8 was ever tested for it. The re-run collapses that S column from
**27 → 1** and surfaces a new bucket, `no_setup_any`, of **29 S marks** where
neither a break-and-retest nor an order block exists on either side — nothing
the engine knows how to trade.

T2 (`research/t2_timing_miss.md`) added the `timing_miss` reason: the engine
fired on the symbol-day but took a later, worse bar when a qualifying entry
existed earlier (checked before `fired_wrong_bar`, takes precedence).

So the two *actionable* categories the new taxonomy now exposes among the S
misses:

| category | S count | meaning | source |
|---|---:|---|---|
| One Candle Rule candidates (`OB present:`, no B&R) | **1** | the sole S mark with an order block but no break-and-retest — `SPY 2025-03-18` (bearish OB); the only bar the One Candle Rule could have caught that the old taxonomy was blind to | `t1_taxonomy_rerun.md` (`ob_present_S: 1`) |
| `timing_miss` | **4** | engine fired a later, worse bar when an earlier qualifying bar existed: `COIN 2025-10-21`, `MARA 2024-12-17`, `ORCL 2025-11-03`, `TSLA 2024-06-24` | `t2_timing_miss.md` (`timing_miss_S: 4`) |

Both numbers are small on purpose. The remaining S misses are **true
negatives or vetoes, not hidden setups**: `no_setup_any` 29 (no setup at
all), `vetoed_htf` 10, `fired_wrong_bar` 6 (after T2 peeled off the 4
`timing_miss`), `vetoed_stop_too_tight` 8, `no_reference_level` 7,
`vetoed_candle_colour` 2, `no_break_retest` 1 — totalling 77 (`t1_taxonomy_rerun.md`
reason × tier table, with T2's reclassification applied). The One Candle Rule
is not a latent recall mine; it is one mark. `timing_miss` is four. Everything
else the engine either correctly declines or vetoes for a reason Austin set.

---

## 2. v3 corpus size (T3) and S-grade fired recall on it vs the 10/77 baseline

T3 (`research/t3_marks_v3.md`) merged `austin_marks_v2.jsonl` (159 rows) with
`mark_batch_02_grades.jsonl` (60 rows): 25 new keys appended, 7 overwrites
(grade changed). **v3 total = 184 marks (159 → 184)**, still **77 S** (the 7
S-marks demoted to A/X by batch_02 are offset by 7 newly-graded-S marks). Per
tier: S 77→77, A 60→71, X 22→36.

S-grade **fired** recall measured on the v3 corpus (`research/t8_measure_output.json`,
`s_fired_recall_v3`): **12/77 = 15.6%**, vs the omen-3.8 v2 baseline of
**10/77 = 13.0%** (`research/baseline_3.8.json` / `v38_verdict.md`).

That +2 is **a corpus-refresh effect, not a detection improvement.** Of the 12
fired S marks, 10 are the unchanged v2-overlap fires (the same 10 the gate
reports as `s_grade 10` on the v2 corpus) and 2 — `COIN 2026-04-09` (entry 8)
and `QQQ 2025-01-10` (entry 16) — are marks batch_02 *newly* graded S that the
engine already fired on. The engine's S detection did not get better; the
grading corpus swapped 7 marks in and 2 of the new ones happened to be already
fired. The regression gate confirms this directly: on the v2 corpus S fired
recall is **flat at 10/77** with `s_grade +0` new fires (see §6 below) — zero
regression, zero new S detection. So the honest reading of "13.0% → 15.6%" is
"the headline moved because the marks file changed, not because the engine
sees more."

---

## 3. S-only vs all-grades backtest — same window, two arms

The backtester replayed once as today (`_SKIP_GRADES = ("X","D")`, i.e.
A+/A/B/C all trade — exactly as shipped) and once with the trading set
restricted to `austin_tier == "S"` under `HTF_OPPOSITION_VETO = "hard"`
(`TRADE_S_ONLY` forced True in-process only; not committed). Both arms are cut
from the **same** detection replay: S-only is a strict subset of the all-grades
set (the engine accepts the same entries; only which arm a trade falls into
changes). Binary 2R target vs stop, scratch at EOD, RULE6/LADDER/SSCORE off —
today's shipped default. The 84% re-entry is not armed (detection-only replay,
matching the gate). Window: 15 measurable priority-pool symbols over their
full `data_archive`. Source: `research/t8_measure_output.json`.

| arm | trades | wins | losses | scratches | win rate | expectancy (R) | total P&L |
|---|---:|---:|---:|---:|---:|---:|---:|
| all-grades (today) | 2854 | 1002 | 1844 | 8 | 35.2% | +0.0591 | +$168,604.60 |
| S-only (hard) | 591 | 215 | 376 | 0 | 36.4% | +0.0914 | +$54,000.00 |

The S-only arm is **higher quality per trade** — +1.2pp win rate, +0.032 R
expectancy — but takes **~1/5 the trades (591 vs 2854)** and earns **~1/3 the
dollars (+$54k vs +$168.6k)**. Of those 591 S-only trades, 495 are
break-and-retest and **96 are the One Candle Rule** (order block) — 16% of the
S set is the setup T1 just made visible (`t8_measure_output.json`
`s_only_by_setup`).

This is exactly the ruling this row is told to quote rather than argue with
(`research/detect_wide.md:161`): engine-grade **B is the only profitable tier
(+$62,451 at 36.6% over 693 trades)** while A+ and A lose, and Austin's ruling
is *"the only reason B makes money is because of the massive amounts of
trades; it doesn't prove edge, because none of it is accurate to a system."*
The all-grades arm here is the same phenomenon at a different scale: it makes
**3× the money of S-only on volume, not per-trade edge.** And S-only does not
yet prove edge either — +0.091 R over 591 trades at 36.4% is the same
"profitable but thin" shape Austin flagged on B, just on a smaller, more
honestly-graded set. Both arms are reported honestly; **neither is armed.**

**The HTF clause (clause 4) — Austin left it unsettled; T8 measures both
arms.** `htf_hard_S = 591` and `htf_fill_override_S = 591` — **identical.**
Switching `HTF_OPPOSITION_VETO` from the shipped `"hard"` veto to the
`"fill_override"` alternative changes the S trade count by **zero** on this
window, so the S-only stats above are the same under either arm and there is
nothing to decide between them here. The fill-override path can neither add
nor drop an S trade on this data; it is a parameter with no measured effect
today, left as a parameter (default `hard`, unchanged) for when a window shows
a difference.

---

## 4. Per-pool recall (T7)

Pool definitions from `config.yaml` (index 3, equity 14, everything else
"other"). T7 (`research/t7_pools.md`), on the 159 v2 marks:

| Pool | Marks | Fired recall | Any-signal recall | Raw-signal recall | Precision (engine→mark) |
|------|------:|-------------:|------------------:|------------------:|------------------------:|
| index (QQQ, SPY, IWM) | 71 | 7/71 = 9.9% | 30/71 = 42.3% | 32/71 = 45.1% | 8/19 = 42.1% |
| equity (14 high-options-volume) | 36 | 4/36 = 11.1% | 14/36 = 38.9% | 16/36 = 44.4% | 4/18 = 22.2% |
| other | 52 | 11/52 = 21.2% | 20/52 = 38.5% | 23/52 = 44.2% | 13/29 = 44.8% |

The index pool is 71 of 159 marks (44.7%) and, per T7, the dominant driver of
overall S recall — but its **fired** recall is the *lowest* of the three pools
(9.9%); its any-signal recall (42.3%) is the highest, i.e. the engine *sees*
index S marks but rarely *takes* them. The equity pool has the lowest precision
(22.2%) — the engine fires on more equity-pool bars Austin doesn't mark. The
"other" pool has the highest fired recall (21.2%). Coverage caveat from T7: 2
of the 14 equity symbols (SPCX, HTZ) have no `data_archive` at all, so the
measurable priority pool is 12/14 equity + 3 index = 15 symbols — the same 15
the §3 window runs over.

---

## 5. What the 95% target needs next — the single biggest remaining lever

Against a 95% S-recall target the engine is at **12/77 = 15.6% fired**
(~73/77 would be 95%): the gap is ~61 marks, and it is not a filter gap. The
single biggest remaining lever is **new detection vocabulary for the 29
`no_setup_any` S marks** (T1) — bars where the engine today has neither a
break-and-retest nor an order block on either side, so no tolerance tweak, no
gate removal, and no S-only restriction can recover them; the engine simply
has no setup to fire. That bucket (29 S marks) dwarfs every actionable
category combined (1 One Candle Rule candidate + 4 timing_miss = 5), and it is
where the 27 `no_break_retest` S marks of 3.8 actually went once the
short-circuit was fixed — they were never hidden One Candle Rule entries; they
were bars the engine has no pattern for. Closing the gap therefore means
teaching the engine a new setup those bars satisfy (T4's named path: OB / FVG
/ flag lows as reference levels, and recovery of the 6 pre-window-break marks
via the existing `LATE` tag) — not widening `detect_break_retest`, not arming
`DETECT_WIDE` (already disproven at `t5_wide_probe.py`: zero new distinct S
marks after dedup, precision halved 38.5%→19.4%), and not gating on S. Arm
nothing; the next increment is detection, and the 29 `no_setup_any` S marks
are the work.

---

## 6. Regression gate — zero baseline-fired marks regressed

Final `python research/regression_gate.py` (exit code **0**), quoted verbatim:

```
baseline: any_signal 60, s_grade 10
current:  any_signal 64, s_grade 10
new fires (not a failure): any_signal +4, s_grade +0
by_tier: {'A': {'fired': 6, 'any_signal': 23, 'total': 60}, 'X': {'fired': 6, 'any_signal': 13, 'total': 22}, 'S': {'fired': 10, 'any_signal': 28, 'total': 77}}

PASS: no baseline-fired mark went silent.
```

`dropped_any` and `dropped_s` are both empty — the gate prints `PASS: no
baseline-fired mark went silent` and exits 0. Every mark the T0 engine fired
on or signalled within ±2 bars, the 3.9 engine still does; the T1–T7 changes
only *added* detections (`any_signal +4, s_grade +0`, explicitly "not a
failure"). **S-grade fired recall on the v2 corpus is flat at 10/77** —
confirming §2's reading that the 12/77 v3 figure is a corpus-refresh effect,
not a detection gain. `signal_runner.TRADE_S_ONLY is False` (the gate's third
check), so nothing about which signals the bot trades changed.

gate exit code: 0

---

## FOR AUSTIN
1. On your refreshed trade list, the bot now catches 12 of your 77 top setups (was 10) — but both new ones were trades it already caught; it just didn't see any more of them.
2. Of the setups it still misses, only 1 (SPY 2025-03-18) is a real one-candle-rule chance; 4 it took too late; and 29 it has no pattern for at all.
3. Trading only your top setups: 591 trades, 36% win, +0.09R each, +$54k — better per trade than today's everything-trades set, but only a fifth as many trades and a third as much money (+$169k).
4. That's exactly your call on the B grade: the everything-set makes 3× the money on sheer volume, not real edge — and your top-set doesn't prove edge yet either.
5. The higher-timeframe rule you left open makes zero difference here — strict vs relaxed both give the same 591 trades, so there's nothing to choose between them on this data.
6. To get anywhere near 95% recall the one lever is new pattern-spotting for those 29 setups the bot has no rule for today — not a stricter filter, and nothing is turned on.
