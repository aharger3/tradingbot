# X4 — ON WATCH / mid-candle entry: why it is not working

Austin: *"how is entry as candle forming 'on watch' working? not well so thats a priority to
make it work because thats another angle money is being left on the table. good entry for
good RR."*

And the original: *"the goal of my comments was for an entry to be made BEFORE the candle
closes, because most of the time the candle closes near/above HOD/LOD and the RR is shot."*

**Provenance.** Every number below is produced by `research/x4_onwatch_autopsy.py`
(`--selfcheck` GREEN, 16 assertions), measured at HEAD `c089b26b` over
`research/g3_arm_ow1.json` — the shipped ON_WATCH=1 two-year book, 45,193 signals / 1,017
traded / 500 sessions / 28 symbols, 2024-08-21..2026-08-21. Bars from `data_archive/` only,
**0 missing symbol-days and 0 missing bars over all 45,193 rows**. Regenerate with
`python research/x4_onwatch_autopsy.py build && python research/x4_onwatch_autopsy.py report`
(→ `research/_x4_summary.json`).

---

## 0. The answer in one paragraph

The feature is **not starved — it is the majority behaviour.** 913 of 1,017 traded entries
(89.8%) already fill intrabar. It moves nothing because of what it fills *at*: `fill_price`
back-dates the entry onto the **bare level**, and for break-and-retest `BNR_STOP_MODE ==
"level"` means the level **is** the stop, so the fill lands *on* the stop and `|entry−stop|`
goes to zero. The minimum-risk floor then deletes 86.7% of exactly those rows. So the engine
does the mid-candle entry, prices it, and throws it away — 6,210 S-graded signals across
4,487 symbol-days. And the two halves are written in **incompatible units**: the trigger is
volatility (0.25 × the previous bar's range), the floor is dollars-and-percent
(`max(0.10, 0.0015 × close)`). Expressed in the trigger's own unit, **the floor demands a
stop 3.90× wider than the trigger it is gating.** That single ratio is the bug.

---

## 1. How many entries actually fill intrabar

| population | n | intrabar | at close |
|---|---:|---:|---:|
| **traded** | 1,017 | **913 (89.8%)** | 104 (10.2%) |
| whole book | 45,193 | 29,377 (65.0%) | 15,816 (35.0%) |

Which predicate moved the fill, on the traded book:

| predicate | traded rows |
|---|---:|
| `bar_extreme_veto` only | 356 |
| `near_session_extreme` only (**everything `ON_WATCH` gates**) | 87 |
| both | 468 |
| neither (2dp rounding artefact) | 2 |

By setup: break_and_retest 865 of 947 intrabar (91.3%), one_candle_rule 46 of 67 (68.7%),
reentry_84_rule 2 of 3. `near_session_extreme` fires on **0** OCR and **0** 84% rows — it is
reachable from 2 of `fill_price`'s 10 call sites, exactly as `g3_onwatch_2y.md` said.

**So the answer to "is it starved?" is no, and that reframes the ticket.** The flag literally
named ON WATCH reaches only 87 traded rows, but the mid-candle *fill* — `bar_extreme_veto` and
`near_session_extreme` together — is what 89.8% of the book runs on. Turning ON_WATCH off does
not give you a close-fill book; it gives you 74.7% intrabar instead of 89.8% (`g3`).

### Where it *is* starved: the funnel

Over all 40,800 B&R signals:

| stage | n | |
|---|---:|---|
| B&R signals | 40,800 | |
| fill moved off the close by a predicate | **28,912** | 70.9% |
| … of those, `\|entry−stop\|` lands **under the floor** | **25,079** | **86.7%** |
| … of those under-floor rows, graded S by `downgrade.py` | 4,265 | |
| … of those under-floor rows actually traded | **3** | |
| … that would clear the floor on the structural geometry `\|close−level\|` | 5,361 | 21.4% |

The fill rule creates 28,912 mid-candle entries and the floor deletes 25,079 of them. That is
the starvation, and it is downstream of the fill, not upstream of it.

**The control matters more than the funnel.** B&R signals filled *at the close* are under the
floor **93.5%** of the time (11,114 of 11,888). So the floor is not mainly rejecting a fill
artefact — it is rejecting the break-and-retest **geometry**. On the bar a break confirms, the
close is typically only cents through the level: median structural risk `|close − level|` is
**$0.185** on the traded rows and **$0.100** on the dropped ones, against a median floor of
$0.261. The detector and the floor are at war, and the floor wins 40,800 → 947.

### The reconstruction, and how it is checked

`BNR_STOP_MODE == "level"` (`signal_runner.py:127`) lets the structural level be recovered from
the book row plus its entry bar without a replay. Three shapes, all asserted in `--selfcheck`:

| shape | B&R rows | traded | recovery |
|---|---:|---:|---|
| at-close fill | 12,527 | 82 | `level == stop` |
| collapse (level inside the bar) | 23,923 | 791 | `level == entry`, `intrabar_stop` moved the stop to the bar's extreme |
| squeeze (level below the bar) | 1,978 | 74 | `level == stop`, fill clamped to the bar's extreme |
| **degenerate — `entry == stop` exactly** | **2,218** | **0** | the bar's extreme *was* the level, so `intrabar_stop` had nothing to widen to |
| reject (failed the emit condition `close > level`) | 154 | 0 | excluded, not kept |

**2,218 B&R signals carry literally zero risk** — median `|entry−stop|` of $0.0000. None trade.
That is `intrabar_stop`'s dead zone, and it is a fifth of the size of the whole traded book.

---

## 2. The prize, and the denominator trap

### 2a. Entry → that bar's close, in R

Distance from the booked entry to the entry bar's close, denominated in the book's own risk
unit `|entry − stop|`, over all 1,017 traded rows:

| | min | p10 | p25 | **p50** | p75 | p90 | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| gain vs close, booked R | −0.042 | +0.012 | +0.118 | **+0.368** | +0.803 | +1.478 | +6.308 |

940 of 1,017 (92.4%) fill better than the close, 56 equal, 21 worse. On the intrabar rows
alone the median is **+0.4365 R**; on the at-close rows it is +0.0000 by construction.

Denominated **structurally** (`|close − level|`), the median is **exactly +1.0000 R** — and
that is not a coincidence, it is the disease stated as an identity. On a collapse row the fill
*is* the level *is* the stop, so the distance from the fill to the close is precisely one
structural risk unit. **The engine books an entire R of "entry improvement" by standing on its
own stop.**

### 2b. Four arms, one denominator

All four arms are the same 947 traded B&R rows, with **exit prices held fixed**, so the arms
differ by entry price and nothing else. The realised size-weighted price move is recovered
exactly as `M = r_booked × |entry − stop|` (the ladder rung fractions sum to 1, so this holds
for scale-outs too). The common denominator is `D = |close − structural stop|`, i.e. the risk
the setup carries measured from the price Austin can actually see.

`D` can be a cent or two on the confirming bar, and `1/D` then explodes, so the full pool is
read on the **median** and the mean is read on the sub-pool where `D` clears the engine's own
floor (409 of 947 — 56.8% of the traded book is *not* sizeable on its structural geometry).

| arm | full pool median (n=947) | D ≥ floor mean (n=409) | win% (sized) |
|---|---:|---:|---:|
| **BOOKED** — published, collapsed denominator | +0.6020 | **+1.3684** | 57.9 |
| **LEVEL / D** — shipped fill, honestly denominated | +0.7136 | **+1.0883** | 57.9 |
| **CLOSE / D** — entry at the bar's close | **+0.0240** | **+0.3764** | 50.6 |
| **TRIG / D** — level + one tolerance unit | +0.4993 | **+0.8861** | 57.9 |

Three deltas, and they are the whole answer to "better entry vs smaller denominator":

| delta | full pool median | D ≥ floor mean | what it is |
|---|---:|---:|---|
| LEVEL − CLOSE | +0.6896 | **+0.7118 R** | the mid-candle entry's **real price improvement** |
| TRIG − CLOSE | +0.4753 | **+0.5097 R** | the same, priced at a trigger you could actually rest an order at |
| BOOKED − LEVEL/D | −0.1116 | **+0.2801 R** | **pure denominator collapse — no price moved at all** |

**Read that middle column against the book's published +0.9551 R.** On the sizeable rows,
filling at the close instead of intrabar books **+0.3764 R**; the shipped fill books
**+1.0883 R**. Roughly *three quarters of the B&R book's mean R is the fill rule*, and
**+0.2801 R of the published number is arithmetic, not price** — the R unit shrinking, with
the entry and the exit unchanged.

Austin is right that money is on the table, and the size of it is **+0.51 R per trade**
(TRIG − CLOSE, sized pool) — half the 1.045 R the book is short of the 2.0 gate. But:

**The +0.71 R is real and unbankable.** Filling at the bare level means `|entry−stop| = 0`,
so there is nothing to size. Every R in the LEVEL arm is earned on a position the engine
cannot actually take, which is precisely why the floor deletes it and why the A/B "moves
nothing". A trigger one tolerance unit above the level keeps **+0.51 R of the +0.71 R** and
leaves a real stop — but one tolerance unit clears the shipped floor on only **143 of 947
rows (15.1%)**, so the floor deletes that too.

*Consistency with R9.* `r9_simple_book.md` found the intrabar fill **halves** P(2R)
(36.00% → 14.29%, intention-to-treat). That is the same mechanism counted at a different
gate: R9 prices the collapsed fill as **instant stop-outs** (135 of 175 candidates never
reach its book), X4 prices it as **floor rejections** (25,079 of 28,912 never reach a
tradeable grade). Both say the fill lands on the stop. Neither number contradicts the other.

### 2c. The selection effect, and it is not the one I expected

The floor admits a B&R signal only when the close ran far enough past the level. Naively that
should mean the book is made of exactly the bad entries Austin complains about. Measured, it
is subtler and worse:

| | n | `D` median | **`D` / previous bar range** | `D` / close |
|---|---:|---:|---:|---:|
| traded B&R | 947 | $0.1850 | **0.344** | 0.1177% |
| dropped B&R | 39,690 | $0.1000 | **0.386** | 0.0701% |

In dollars the traded rows ran 1.85× further past the level; in percent of price, 1.68×. **In
volatility units they ran 0.89× — slightly *less*.** So the floor buys no entry-quality
improvement at all. It is a **price filter wearing a risk filter's clothes**: what it selects
for is expensive stock, not room to trade.

---

## 3. The minimum-risk floor

**The constant.** `signal_runner.min_risk_floor()` at **`signal_runner.py:1054-1060`**:

```python
def min_risk_floor(close: float) -> float:
    return max(0.10, 0.0015 * close)
```

**Applied at** `signal_runner.py:2087` (long B&R) and `signal_runner.py:2327` (short B&R),
via `floor_reference_risk(...) < max(0.10, 0.0015 * current.close)` → `TradeGrade.D`, which is
an alias of `X` (`omen_bot.py:69`). It sits *after* every promotion, so it overrides the A+
stack floor and the confirmation-entry C. Second, weaker floor: `_min_viable_stop`
(`signal_runner.py:1401-1417`), applied at `:1908` **to grade C only**.

Both constants are un-authored. `research/hallucination-audit.md` rows: `B&R_MIN_RISK =
0.0015 × close` — *"Relative threshold; 0.0015 multiplier territory not swept"*, HIGH; and
`STOP_RANGE_MULT = 0.75×` — *"0.75 multiplier never stated (OURS)"*, HIGH. `min_risk_floor`'s
own docstring says so in as many words.

### What it suppresses

| | count |
|---|---:|
| signals graded **S** by `downgrade.py` in the 2-year book | 7,454 |
| … traded | **128** |
| … dropped | 7,326 |
| **dropped S sitting under the floor** | **6,210 (84.8% of dropped S)** |
| … of those, intrabar-filled (i.e. the fill rule put them there) | **4,330** |
| … of those, would clear the floor on the structural geometry | 1,186 |
| **distinct symbol-DAYS the floor suppresses at least one S on** | **4,487** |

Corroboration from two independent rigs, not re-derived here: `g4_dropped_s.md` attributed
1,385 B&R + 153 OCR dropped-S signals to the min-stop branch by instrumented replay (a
stricter attribution than "sits under the floor"); `g12_recall_regression.md` traced **six of
Austin's own S marks** to it on the 159-mark regression gate; `w3_recall_gate_fix.md` turned
that gate green (`s_grade` 5 → 13) by clamping the fill off the floor.

### The ratio that names the bug

The trigger is stated in **volatility**: one tolerance unit = `BAR_EXTREME_FRAC` × the
previous bar's range = 0.25 × range. The floor is stated in **dollars and percent**. Express
the floor in the trigger's own unit — `floor ÷ previous bar range`, over all B&R signals:

| p25 | **median** | p75 | one tolerance unit |
|---:|---:|---:|---:|
| 0.583 | **0.976** | 1.662 | **0.250** |

**The shipped floor demands a stop 3.90× wider than the trigger it is gating, at the median.**
Two rules that must agree about the same distance are written in units that cannot be
compared, so one manufactures signals the other deletes. That is the whole mechanism, and it
is the [[omen-rules-unreachable-in-code]] class one level up: not a branch that can never be
true, but a *pair* of rules that can almost never both be true.

Confirming it from the other side: one tolerance unit is **$0.1375** at the median against a
floor of **$0.2611**, and `tol ≥ floor` on only **143 of 947** traded rows (15.1%).

### Price, percent, or dollar premium?

**None of the three, on its own.** The measurements say the floor is doing two different jobs
badly at once, and the fix is to split them:

**(a) The structure question — "is this stop inside the noise?" — belongs in volatility
units.** That is the only unit commensurable with the trigger, and the engine *already owns
this gate*: `STOP_RANGE_MULT = 0.75 × avg 1-min range` (`signal_runner.py:161`, used at
`:1412`). It is applied to **grade C only** (`:1908`). Moving the structural half of the floor
onto that unit makes the trigger and the floor speak the same language by construction.

**(b) The sizing question — "is there enough premium to buy?" — belongs in dollars, and a
dollar-premium floor is STRICTER than today's, not looser.** At `_min_viable_stop`'s own
delta-0.5 conversion, a $0.20 premium bar means **$0.40 of stock risk** — against
`0.0015 × close`, which is $0.19 on a $128 stock and $0.90 on SPY. Measured on the shipped
traded book: median premium risk **$0.210/share** (p10 $0.085, p90 $0.575), **476 of 1,017
(46.8%) already under the $0.20 bar**, and **48 contracts at the median** to risk $1,000 (p90
118, max 200). Only 1 of 1,017 rows is under $0.05. So replacing the floor with a flat
dollar-premium floor would delete about half the current book and most of the recall it is
supposed to recover. **Do not do it.**

Also note the honest gap: the 0.5 delta is itself an un-authored constant
(`options_sizer.py:20 DEFAULT_DELTA = 0.5`, `_min_viable_stop`'s inline `# ATM delta ≈ 0.5
estimate`), the backtest sizes in **shares** and never calls `options_sizer` at all, and there
is **no options tape anywhere in this repo**. Any premium floor is a guess about an
instrument the rig has never seen.

**(c) The recommended fix is the STOP, not the floor.** Austin already stated the rule for a
mid-candle entry, five separate times in the recovered reviews: *"stop loss at the bottom of
the wick you entered"*. `intrabar_stop` implements it but only on **full collapse**, which is
why `g12`'s `--ab-stop-on-entry-bar` recovered **0 of 6** marks — in the squeeze case the fill
already *is* the bar's extreme, so "stop at the bar's extreme" resolves to the entry itself.
Fixing the **entry** fixes that: make the fill the trigger price, not the bare level.

> **Proposed ON WATCH geometry**
> `entry = level + one tolerance unit` (0.25 × previous bar range), filled as a stop order
> `stop  = the entry bar's own extreme` (Austin's stated rule)
> `risk  = |entry − stop| ≥ one tolerance unit, by construction — it cannot collapse`

Measured over all 40,637 B&R signals with a recoverable level:

| | value |
|---|---:|
| reachable (trigger traded inside the entry bar) | **38,066 (93.7%)** |
| risk `\|trigger − bar extreme\|` median | **$0.2300** (p10 $0.04, p90 $0.8175) |
| **clears the shipped floor** | **15,153 (39.8%)** — against **11.3%** for today's booked geometry |
| … of those, graded S by `downgrade.py` | **2,623** — against **128** S signals traded today |
| implied option premium risk (delta 0.5), median | $0.115 — 70.4% under $0.20 |

**A 3.5× increase in floor survival and a 20× increase in S supply, from moving the entry one
tolerance unit and the stop one wick.** That is a candidate, not a result: it is a geometry
measured on the existing book, not a replay, so it cannot say what those 2,623 S signals
*earn* — and it is a change to what trades, which per `DIRECTION.md` is Austin's call and
re-freezing `omen6_forward.py` VOIDS the forward book.

**And the recall caveat that has fired four times.** `W3`, `G13`, `R3` and `A3` each bought
in-sample recall and **zero held-out recall** (3/15 → 3/15 on
`research/marks/probe_omen_test1_2026-08-27.jsonl` every time, while false fires went 12/42 →
21/42 for W3 and 12/42 → 19/42 for G13). X4 has **not measured held-out recall** — it is a
geometry census, not an A/B, and the held-out number is what the A/B would have to report
before any of this ships. Expect the same result until something proves otherwise.

---

## 4. The time half of the trigger

Austin chose **both** a price trigger and a clock position inside the bar. The archive is
1-minute OHLCV. Split honestly:

**What 1-minute bars decide exactly, with no assumption:**
- **Did the bar trade at the trigger price.** `high ≥ trigger` (long) is exact. Measured:
  **736 of 947 (77.7%)** of traded B&R rows reach a level+one-tolerance-unit trigger inside
  their entry bar; 211 never do; **131 opened already through it**, so the earliest achievable
  fill is the bar's *open*, not the trigger — a distinction worth 131 rows that a naive
  "fill at the trigger" model would get wrong for free.
- **Did the bar close through the level.** Exact — it is the emit condition.
- **Whether the trigger preceded the close.** Trivially yes: the close is the last print.

**What 1-minute bars cannot decide:**
- **When inside the minute the trigger printed**, and therefore whether a resting order at
  that price actually filled given queue position. 637 of 947 entry bars (67.3%) have a range
  that also contains the level.
- **Whether a live trader would have committed at all.** That is clause 2's scratch, and
  `p8_scratch.md` already showed the backtest structurally cannot hold it — it reads the bar
  complete before deciding.

**Would finer data change a conclusion here? No, and the reason is a ruling, not a
measurement.** Sub-minute ordering would matter only if a stop could fire *inside* the entry
bar ahead of the back-dated fill. Austin settled that on 2026-08-28 — *"out on that same
close"* — a stop is triggered by a candle CLOSE and by nothing else, and one bar has exactly
one close. That retired the ±1.5799 R wide error bar; `p26`+`T3` had already shown the
residual ambiguity is **2 rows of 913**, with 790 of 792 being the stop sitting on the entry
bar's own extreme by construction and 21 of the last 23 being half-cent rounding. **Buying
tick data buys ~0.2% of the rows and changes nothing in this report.**

The genuinely missing data is a different purchase and a much bigger one: **there is no
options tape in the archive at all.** Every premium number in section 3 comes from a flat
0.5-delta conversion of a stock price. Whether a 23-cent stock stop is a tradeable option
risk — the actual question behind "good entry for good RR" on an options book — cannot be
answered from *any* amount of stock data, tick or otherwise. If something is worth buying, it
is an option chain, not a finer stock feed.

---

## 5. Status

- `research/x4_onwatch_autopsy.py` — `--selfcheck` GREEN (16 assertions: engine constants read
  never retyped, all three level-reconstruction shapes, `arm_r` exactness on longs and shorts,
  the 84% re-entry exclusion). Read-only: no default changed, no flag added, bars from
  `data_archive/` only, so it can never touch `POLYGON_API_KEY`.
- `research/_x4_rows.json` (per-signal geometry, 45,193 rows) and `research/_x4_summary.json`
  (every published number) are regenerable, not committed as results.
- **Nothing is wired.** No engine file was edited by this ticket.

### What is measured, and what is not

| claim | status |
|---|---|
| 89.8% of traded entries fill intrabar | **measured** |
| the floor deletes 86.7% of moved B&R fills; 6,210 dropped S under it | **measured** |
| floor is 3.90× the trigger, in the trigger's own unit | **measured** |
| entry-price prize is +0.71 R (level) / +0.51 R (trigger) vs the close, sized pool | **measured**, exits held fixed |
| +0.2801 R of the published book mean is denominator collapse | **measured**, sized pool |
| proposed geometry clears the floor 39.8% vs 11.3%, 2,623 S | **measured as geometry**, not replayed |
| what the proposed geometry **earns** (mean R, win rate, months green) | **not measured** — needs a replay arm |
| **held-out S recall of the proposed geometry** | **not measured** — and it is the gate that has killed the last four of these |
