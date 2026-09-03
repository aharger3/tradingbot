# G71/timing — the engine detects on his candle and fires two candles later

Script: `research/g71_timing.py` — no flag for the full surface, `--check` for the
identity gate alone, `--marks` for the held-out cross-check.
Raw output: `research/g71_timing_out.txt`, `research/g71_timing_marks.txt`,
`research/g71_timing.json`.
Book: `research/bt2y_trades.json` — 76,019 signals, **2,437 traded**, 500 sessions,
2024-08-21 → 2026-08-21, mean R **+0.5495**, win rate **49.16%**.
Read-only on every mark file. No engine file edited — the one proposed diff is
printed below and not applied.

---

## The four sentences

1. **His 8% is real and reproduces at 8.5%** — 203 of 2,401 traded rows have an
   earlier candidate the engine already had and could legally have taken.
2. **"Enter one candle earlier" measures +0.7189 R/trade and it is a mirage.**
   The entry bar's own move is **+0.7974 R** and is favourable on **93.4%** of
   trades *by construction* — the detector requires that bar to close through the
   level. Shifting the entry back one bar just books the confirmation candle as
   profit. The two numbers agree to 0.08 R. **Do not ship this.**
3. **Swapping to the earlier candidate the engine already had is worth nothing:
   +0.0337 R/trade, 95% CI [−0.3051, +0.3516].** A null. The data does *not*
   figure it out by itself.
4. **The real finding is not timing at all.** On the 9 held-out days where the
   engine both saw and traded a setup at a minute Austin typed, it entered
   **1–3 bars late, 9 times out of 9** — and **11 of the 12 signals it emitted at
   his candle are graded `X`**. It sees his candle, writes *should not have fired*
   on it, and buys the one two candles later. That is the grader, not the clock.

---

## 0. Where his "8 percent" came from

> Austin, on 7.1: *"8 percent of the book was a candle late or early, but it has
> the data to figure out itself, thats me saying im going to work smarter, not
> harder."*

`research/t12_earlier-entry-gap.md:208`:

> 218 traded rows (**8.4%**) have a candidate 1–6 bars earlier that scores **S on
> his own ladder**. On 139 of them (**5.4%**) the row the engine actually took is
> *not* S.

T12 also produced the same number from his prose — he volunteers a timing
complaint on **5.0–7.4%** of engine cards (`t12_earlier-entry-gap.md` §1). Two
independent counts, one number, **and no dollar attached to either**. T12 counted
the candidates. This track prices them.

**Reproduced on the current book** (T12 measured 2,595 traded; R31's loss halt has
since taken it to 2,437):

| | value |
|---|---:|
| traded rows in support | 2,401 |
| rows with **any** candidate 1–6 bars earlier, same direction | 1,101 |
| candidates dropped — inside `B&R_MIN_RISK` of their own stop | 1,288 |
| candidates dropped — `skipped_tight_stop` | 19 |
| **rows with a TAKEABLE earlier candidate** | **203 (8.5%)** |

**8.5% against his 8%.** The filter matters and is not cosmetic: the first cut of
the swap table, with the sub-floor candidates left in, read **+8.04 mean R at a
47.5% win rate**. That is arithmetic on a $0.01 denominator, not an edge. A
candidate whose entry sits inside `signal_runner.min_risk_floor()` of its own stop
is one the engine refuses as `skipped_tight_stop`, and 1,288 of them do.

---

## 1. The R surface

Every traded row re-managed from a shifted entry bar through
`backtest_week._ladder_bar` — the shipped management loop, not a copy. The stop
trigger, `stop_rule.stop_fill_price`'s −1.25 R floor, the −1 R disaster stop, the
PT1 scale rung and the pessimistic same-bar tie all come from the engine.

The fill at bar *i+k* is the shipped fill **translated** by what the tape moved
between the two bars, `entry_k = entry_0 + (close[i+k] − close[i])`, so **k = 0 is
the identity**. Two arms, because the stop decides what "the same trade one candle
earlier" means:

- **ARM T (translate)** — stop and target move with the entry. Risk is identical
  to the book's, so the R denominator is fixed and the surface is pure path.
  **This is the honest arm.**
- **ARM S (structural stop)** — the stop stays put, because on a break-and-retest
  the stop *is* a level and a level does not move because you were early. Risk
  becomes `|entry_k − stop|`. **Confounded**: entering earlier on a long shrinks
  the distance to the stop, which shrinks 1 R, which inflates R mechanically. It
  also loses 811 rows at k = −1 whose shifted entry lands through their own stop,
  so its support is a different, smaller population. Reported, never quoted alone.

| arm | k | n | mean R | WR % | total R | delta vs k=0 | 95% boot CI on delta |
|---|---:|---:|---:|---:|---:|---:|---|
| **T** | **−2** | 2401 | 0.8717 | 49.27 | 2093.0 | **+0.3184** | [+0.2435, +0.3961] |
| **T** | **−1** | 2401 | **1.2722** | **57.23** | **3054.7** | **+0.7189** | **[+0.6567, +0.7829]** |
| T | +0 | 2401 | 0.5533 | 49.65 | 1328.6 | — | — |
| T | +1 | 2401 | 0.5141 | 48.06 | 1234.3 | −0.0392 | [−0.1041, **+0.0266**] |
| T | +2 | 2401 | 0.5585 | 47.40 | 1341.0 | +0.0052 | [−0.0736, **+0.0876**] |
| S | −2 | 1190 | 2.0534 | 33.70 | 2443.6 | +1.3699 | [+0.0170, +3.7184] |
| S | −1 | 1190 | 0.8707 | 32.94 | 1036.2 | +0.1872 | [**−0.0860**, +0.4847] |
| S | +0 | 1190 | 0.6835 | 57.06 | 813.4 | — | — |
| S | +1 | 1190 | 0.6813 | 53.28 | 810.8 | −0.0022 | [**−0.1343**, +0.1483] |
| S | +2 | 1190 | 0.7723 | 51.68 | 919.0 | +0.0887 | [**−0.1601**, +0.3805] |

Read it in two halves:

- **Waiting is worth nothing.** k = +1 and k = +2 both straddle zero in both arms.
  There is no delay in the engine to remove.
- **Going earlier "pays" enormously, and the peak is at exactly −1**, not at −2.
  A sharp single-bar optimum is not what a drifting clock looks like.

### The book-level read (R31's loss halt re-applied per arm)

| k | traded after halt | mean R | total R | WR % |
|---:|---:|---:|---:|---:|
| −2 | 2165 | 0.8751 | 1894.7 | 48.41 |
| **−1** | **2331** | **1.2837** | **2992.3** | **56.46** |
| +0 | 2394 | 0.5564 | 1332.1 | 49.21 |
| +1 | 2159 | 0.5239 | 1131.1 | 48.31 |
| +2 | 2087 | 0.5634 | 1175.9 | 47.20 |

k = −1 clears the **55% win-rate half of the money gate (56.46%)** and still misses
the mean-R half (1.2837 vs 2.0). Durability is 25/25 months green at every k, so
that gate does not discriminate here.

---

## 2. Why the k = −1 peak is a mirage

**Every slice is positive at k = −1.** Both setups, both sides, all three
half-hour slots, all five entry-bar buckets, all three of Austin's ladder grades,
**all 24 symbols with n ≥ 40** (worst: IWM +0.2518), **all 25 months** (worst:
2024-10 +0.4391). Nothing is negative anywhere.

That uniformity is the tell. A real timing edge concentrates — in a symbol, a
setup, a time of day. A uniform one is a mechanism, and there is exactly one
candidate mechanism: **bar *i* is selected to be the confirmation bar.**
`detect_break_retest` step 4 requires bar *i* to close back through the level in
the trade's direction; the OCR requires `current.close > block.high`. Entering at
bar *i−1* books bar *i*'s own move as post-entry profit.

Measured directly — the signed move of the entry bar, `close[i] − close[i−1]`,
in units of the trade's own risk:

| | value |
|---|---|
| n | 2,401 |
| **mean** | **+0.7974 R** (95% boot [+0.7694, +0.8258]) |
| median | +0.7424 R |
| favourable | **2,243 of 2,401 = 93.4%** |
| **k = −1's measured gain** | **+0.7189 R** |

**+0.7974 against +0.7189.** The whole k = −1 peak is the confirmation candle,
handed to the trade for free by knowing it was going to confirm. It is not an
entry improvement; it is one bar of foreknowledge, priced.

Two more reads that say the same thing:

- **k = −1 vs k = 0 per trade: better 1,296 / same 988 / worse 117**, median delta
  **+0.1333 R**. Almost nothing gets worse. A genuine trade-off would have losers.
- **Argmax over k: k = 0 is already the single best bar on 37.7% of trades**, more
  than any other k (−1 is best on 29.0%). The engine's own bar wins the head count.
  The mean gain is magnitude, and the magnitude is bar *i*.

`research/t12_earlier-entry-gap.md` §3 reached the same destination by another
road and its conclusion stands: the FSM already enters on the retest candle 77% of
the time, there is no uniform bar to give back, and **a blanket shift would move
2,401 entries to fix 203**.

---

## 3. The tradable version: swap to a candidate the engine already had

Not a price translation — the earlier signal's **own** entry, stop and target,
managed from **its** bar, with its PT1 rung recomputed causally. These are trades
the engine really produced and then threw away, so taking one is causal.

| arm | n | median offset | engine took | swapped to | delta R/trade | 95% boot CI |
|---|---:|---:|---:|---:|---:|---|
| nearest earlier candidate | 203 | −3 | +0.4737 | +0.5074 | **+0.0337** | [−0.3051, +0.3516] |
| best Austin-ladder candidate | 203 | −3 | +0.4737 | +0.4884 | +0.0146 | [−0.3182, +0.3329] |
| S on his ladder only | 44 | −3 | −0.0164 | +0.4226 | +0.4390 | [**−0.0412**, +0.9552] |
| nearest, 1–2 bars back only | 82 | −2 | +0.4571 | +0.5811 | +0.1240 | [−0.3345, +0.5965] |
| **1–2 bars back AND S on his ladder** | **17** | −2 | **−0.0416** | **+0.6730** | **+0.7146** | **[+0.1833, +1.3136]** |

**The headline arm is a null.** "Take the earlier candidate" is worth +0.0337 R
with a CI 20× wider than the effect. Austin's *"it has the data to figure out
itself"* is, on the blanket reading, **not supported**: the engine's own earlier
candidates are on average no better than the entry it took.

The last row is the only one whose CI excludes zero, and it is **n = 17** and the
**fifth cut of the same 203 rows** — the multiple-comparison discount applies with
full force. Take it as a hypothesis, not a result. What makes it worth keeping is
that its two halves point the same way as everything else in this track: on those
17 rows the engine's own entry books **−0.0416 R** while the S-graded candidate it
already had, two bars earlier, books **+0.6730 R**. The selector is not the clock,
it is **his ladder**.

---

## 4. The held-out cross-check: T1's "+0.0 bars" splits in two

`research/marks/probe_s_sweep_2026-08-28.jsonl` — his 2026-08-28 blind pass, 34
cards graded **S** with an exact entry minute typed on every one. Replayed on the
current ratified engine through `research/t4_engine_recall.run_day`, the same
harness T0 and T1 use. Marks read, never written.

`research/t1_entry_minute_autopsy.md` reports **median +0.0 bars, mean +0.13**, and
`DIRECTION.md` quotes it as *"its timing is exact."* **The number survives — for
DETECTION. It is false for the entries the engine actually takes.**

| what is measured | n | median | mean | late / exact / early | sign test |
|---|---:|---:|---:|---|---|
| nearest **SIGNAL** to his minute, ±2 bars | 17 | **+0.0** | −0.35 | 1 / 9 / 7 | p = 0.070 |
| nearest **SIGNAL**, ±6 bars | 21 | +0.0 | +0.10 | 4 / 9 / 8 | p = 0.388 |
| nearest **FIRED** entry, ±2 bars | 9 | **+1.0** | **+1.22** | **7 / 2 / 0** | **p = 0.0156** |
| nearest **FIRED** entry, no window | 23 | +2.0 | +11.61 | 18 / 2 / 3 | p = 0.0015 |

**Zero early.** Not one of the nine entries the engine took near a minute he typed
landed before it. T1's +0.0 held because T1 pooled FIRED and DETECTED rows; split
them and the two halves say opposite things.

**And the mechanism is arithmetic, not statistical.** On the 9 days the engine both
SAW his setup (a signal within ±2 bars of his minute) and TRADED it, the bar it
entered on minus the bar it first saw it on:

```
+1  +3  +1  +1  +2  +2  +2  +2  +2      median +2.0, mean +1.78, positive 9 of 9
```

Sign test, 9 non-ties, **p = 2 × (1/2)⁹ = 0.0039**.

### What the engine wrote on the candle he named

| sym | day | his bar | every signal within ±2 bars (bar : grade : status) |
|---|---|---:|---|
| CRM | 2025-09-19 | 10 | 10 : **X** : skipped_d |
| SMCI | 2025-11-17 | 36 | 35 : **X** : skipped_d |
| TSM | 2026-02-02 | 6 | 5 : **X** : skipped_d |
| BABA | 2025-02-05 | 11 | 10 : **X** : skipped_d |
| PLTR | 2024-03-11 | 13 | 13 : **X** : skipped_d · **15 : B : fired** |
| HOOD | 2024-11-06 | 49 | 48 : **X** : skipped_d |
| MSFT | 2025-03-13 | 19 | 17 : **X** : skipped_d · 19 : **X** : skipped_d |
| AVGO | 2025-10-10 | 17 | 16 : **X** : skipped_d · 19 : **X** : skipped_d |
| QQQ | 2025-09-23 | 9 | 9 : **X** : skipped_d |

**Twelve near-signals over nine days. Eleven are `X`.** The single non-X is PLTR
bar 15 — two bars after his 13 — and that is the one the engine traded. `X` is not
a grade; it means the engine should not have fired.

**Colour attribution.** `omen_bot.PriceActionAnalyzer._grade_pa:261` opens with
`if not candle.is_bullish: return TradeGrade.D` for a long, mirrored at `:274` for
a short. **6 of those 12 near-signals are `D` on candle colour alone.** The candle
that pokes down into a level on a long is usually red; the candle that confirms is
green and arrives one to two bars later. That is the lag, in one branch. The other
six are `D` from the HTF-bias veto (`omen_bot.py:242`) or the at-key-level test —
the same split `research/g4_dropped_s.md` measured book-wide (HTF 3,525 · colour
2,120 · B&R min-stop 1,385 · OCR 174).

---

## 5. Is the offset symbol-, setup-, or time-specific?

**No, on all three — and that is the finding, not a failure to find one.**

| slice | spread at k = −1 | reading |
|---|---|---|
| setup | B&R +0.8174 (n 1901) · OCR +0.2427 (n 377) · 84%-reentry +0.6566 (n 123) | all positive; B&R largest because its entry bar is the biggest confirmation candle |
| side | long +0.6924 · short +0.7492 | symmetric |
| time of day | 09:30 +0.8350 · 10:00 +0.6285 · 10:30 +0.5221 | decays with the hour, exactly as 1-minute bar range does |
| entry bar | 5–14 +0.9318 · 15–29 +0.7819 · 30–44 +0.6242 · 45–59 +0.6357 · 60+ +0.5221 | same decay, same cause |
| symbol | 24 of 24 positive (n ≥ 40), IWM +0.2518 → AMD +1.0003 | tracks per-symbol bar range, nothing else |
| Austin ladder | C +0.8016 · A +0.5623 · S +0.5448 | no selectivity |
| month | 25 of 25 positive | no regime |

Every gradient in that table is a **volatility** gradient — early bars, wide names
and B&R confirmations have big candles, and a big confirmation candle is a big
free +R when you enter before it. There is no residual timing structure once that
is accounted for. **There is no systematic offset to correct, because the engine is
not late by its own information — it fires on the first bar its own rules are
satisfied. It is late relative to Austin because his rules are satisfied one candle
earlier: he enters as the candle forms, and this engine cannot.**
`backtest_week.py:216` already states that outright — *"this engine is bar-CLOSE
driven. It cannot take an entry 'intrabar' in the sense Austin means."*

---

## 6. The rule that falls out — and it is not a timing rule

**In his language.** *"You're not late. You're looking right at my candle and
writing X on it, then buying the one two candles after. The problem isn't when you
enter, it's what you throw away."*

There is **no** honest version of *"enter on the close of the retest candle, not
the next open"* — §2 shows the engine already enters on the retest candle and that
moving it back only buys look-ahead. **No detector diff is proposed.**

The one arm the data supports is a **selection** rule on his own ladder, and it is
`research/t12_earlier-entry-gap.md`'s recommendation 2 with a price on it for the
first time:

> On a symbol-day where a candidate the engine already emitted sits **1–2 bars
> before** the entry it took, and that candidate grades **S on Austin's ladder**
> while the taken row does not, take the **earlier** one.

**Sizing: 17 of 2,401 rows (0.7%), +0.7146 R/trade, +12.1 R total, 95% CI
[+0.1833, +1.3136], n = 17.** That is one trade every seven weeks and it is the
fifth cut of one dataset. **It does not clear the bar for shipping**, and it must
not be flagged behind a default-ON switch on this evidence. The diff below exists
so the arm is measurable, defaults OFF, and changes no shipped number:

```diff
--- a/backtest_week.py
+++ b/backtest_week.py
@@
 STOP_ON_CLOSE = os.getenv("STOP_ON_CLOSE", "1") not in ("0", "false")
 
+# ---- G71/timing: prefer an EARLIER candidate that grades S on Austin's ladder
+# Austin, 7.1: "8 percent of the book was a candle late or early, but it has the
+# data to figure out itself."  research/g71_timing.md prices that sentence.
+#
+# The blanket reading is a NULL: swapping every traded row to the nearest earlier
+# candidate the engine already had is worth +0.0337 R/trade, 95% CI
+# [-0.3051, +0.3516] over 203 rows.  The ONE arm whose interval excludes zero is
+# narrow -- the earlier candidate must be within 2 bars AND grade S on
+# downgrade.py's ladder while the taken row does not -- and it is n=17,
+# +0.7146 R/trade, 95% CI [+0.1833, +1.3136], +12.1 R over two years.
+#
+# DEFAULT OFF, and it must stay off until n grows.  n=17 is the fifth cut of one
+# dataset; the project's standing rule is to gate on held-out recall, not on a
+# mean-R arm this thin (see research/g71_timing.md section 3).
+PREFER_EARLIER_S = os.getenv("PREFER_EARLIER_S", "0").strip().lower() \
+    in ("1", "true", "yes", "on")
+PREFER_EARLIER_S_BARS = int(os.getenv("PREFER_EARLIER_S_BARS", "2"))
+
```

The implementation site is `simulate_day`'s signal loop
(`backtest_week.py:822-880`), where the candidate is created: hold a per
`(signal_type, direction, idea)` key the last `PREFER_EARLIER_S_BARS` bars of
suppressed candidates with their `downgrade.score` grade, and on a fire, take the
earliest held candidate whose sgrade is `S` when the firing row's is not. **It is
not written here** because this is a diagnosis pass and because the evidence does
not yet justify the code.

**What to do instead, and it is already on the board.** The lever this track keeps
landing on is `PHASES.md` **P4 — wire `downgrade.py` into detection**. Every
mechanism above routes through the legacy ladder writing `X` on a candle Austin
graded S: 11 of 12 near-signals in §4, 92.1% of T12's near-earlier candidates, and
the only positive swap arm in §3 is *defined* by his ladder disagreeing with the
engine's. Timing is a symptom. **The engine's clock is fine; its opinion is wrong.**

---

## 7. Method, error bars, and what did NOT run

**The identity gate.** Every number rests on re-managing the book's own trades
through the shipped `backtest_week._ladder_bar`. At k = 0 that must reproduce the
book exactly, and it does:

```
match index: 2436 bound, 1 unbound
k=0 identity: 2436/2437 exact, 0 mismatched, 1 unbuildable
```

The published book rounds `entry`/`stop`/`target` to 2 dp; on a $0.11 risk that is
a 4% error in R, so every row is bound back to the engine's own `SimTrade` floats
by `build_match_index`. The binding is collision-safe — three INTC rows share bar
32 on 2025-08-22 with three different broken levels, and an earlier cut that keyed
on the bar alone handed all three the same trade and produced 33 false mismatches.

**The 84% re-entry is held fixed.** `_arm_84` writes only `runner.session.*`, and
this replay never calls `detect_signals`, so no shifted entry invents a re-entry
that the book does not have. The signal population is the book's, deliberately.

**Look-ahead, stated.** k < 0 is an **oracle** — the engine did not have the signal
at bar *i−1*. §2 is the measurement of exactly how much that foreknowledge is
worth (+0.7974 R) and why the surface's peak is it. k > 0 is causal, and is worth
nothing.

**Error bar.** The project's standing bar is ±1.5799 R and every A/B it has run
moves less than that (`omen-error-bar-exceeds-arms`). Every CI here is on the
**paired** delta — the same trades on both sides of every arm — which is the right
bar for this comparison, because the between-trade variance that produces ±1.5799 R
cancels in the pairing. Under that bar, §3's headline swap arm (+0.0337 R) is a
null by any reading, and §1's k = ±1/±2 arms are nulls too.

**What did not run.**
- The 34 held-out cards are the only place a human minute exists. n = 9 for the
  FIRED comparison and n = 17 for the DETECTED one. Direction is unambiguous
  (9 of 9, same sign); the magnitudes are soft.
- Arm S's k = −2 row reads +2.0534 mean R at a **33.70%** win rate. That is the
  denominator shrinking, not an edge, and its CI is [+0.0170, +3.7184] — 200× the
  effect it brackets. It is printed for completeness and should not be quoted.
- No intrabar data. Austin's actual fill is *"as the candle is forming"*, which
  this engine structurally cannot take (`backtest_week.py:216`). Whether a
  tick-level fill closes the 1–2 bar gap is unmeasurable on 1-minute bars and is
  not claimed either way here.
- `PREFER_EARLIER_S` is specified, not implemented, and not measured as an A/B
  over the full book — only as the 17-row swap in §3.
