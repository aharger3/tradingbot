# OMEN — the morning report
**2026-09-03. Every number below was produced by a run tonight, in this repo, on the committed book `research/bt2y_trades_retest_on.json` (498 sessions, 2024-09-03..2026-09-02, 28 symbols, 4,022 fired-and-traded rows). Entry fills at the signal bar's CLOSE. Stops fill at the level on an intrabar touch, exactly −1.000R (R1 holds: 0 of 4,022 rows worse). Every arm is size-gated on `signal_runner.min_risk_floor`.**

---

## 1. THE ANSWER

**Yes — there is one edge, and it is a subtraction rule, not a setup: stop taking prior-day highs and lows.** Vetoing `level_tf=1D` (PDH/PDL) on the one-trade-a-day arm takes EV per trade from **+0.036R to +0.103R** (n=490 of 498 sessions, honest close fill), and it is the only filter of tonight's ~400 arms that survives family-wise multiplicity correction (FWER p=0.0052 over 53 de-duplicated causal arms), an independent 50,000-draw permutation I ran tonight (**p=0.000040**), both halves of the book, and all three calendar years.

**It passes a $50k prop evaluation on the full-book path — at 0.15%–0.30% risk per trade, in 9.9 months, with a −3.1% peak drawdown against a 4% trail.** But run the honest version of "pass one eval within 12 months" — start on every possible day, 252-session horizon — and it passes **38.7% of all starts and 0.0% of year-2 starts** at that size.

**So: an edge, measured and real, that is not yet a funded account.** The strategy's year-2 EV/R is +0.048R and shrinking; sizing small enough to survive the trailing drawdown is too small to reach 8% in twelve months on recent data. That coupling — not filtering, not exits, not entry timing — is the whole remaining problem.

---

## 2. THE BEST SYSTEM WE CAN BUILD TONIGHT

One configuration. Named end to end. **`B_no1D`.**

| | |
|---|---|
| **Universe** | the committed 28 symbols (`universe.py`). No slice beat the full set on the spec unit; `experimental_tier` "passed" only at trade #444 on 2026-07-10 — ~22 months, a FAIL against your 12-month bar. |
| **Day policy** | **one trade a day.** The **first size-gated candidate of the session**, gate applied *inside* selection — if a candidate is unsizeable or vetoed, substitute the next one, never sit the day out. 490 of 498 sessions trade. |
| **Window** | 09:30–11:00, take the first. Waiting is strictly worse: first-after-09:45 is **−0.0441R** (n=433). Of six disjoint 15-minute buckets across all 6,889 size-gated candidates, **09:30–09:45 is the only positive one (+0.0153R, n=1,234)**; the trough is 10:15–10:30 (−0.0781R, n=976). |
| **Entry** | the **signal bar's CLOSE**. Shipped, unchanged. Every "earlier/better" entry tested tonight was lookahead — see §4. |
| **THE VETO** | **skip the candidate if its retest level is a prior-day level (PDH/PDL, `level_tf=1D`); take the next candidate that session instead.** This is the entire change. |
| **Stop** | the broken level. −1R hard. No candle-structure stop, no fixed-percent stop, no ATR stop — none of them survive an honest fill (§4). |
| **Target** | **flat 2R.** Level-aware snapping to named levels or whole dollars beats it by +0.022R at best; **0 of 11 tolerance arms clear 95%**, best unadjusted p=0.174 over 11 arms. |
| **Exit shape** | single target. The 4-rung ladder is +0.137R vs +0.031R one-shot *in-sample*, but **all 8 shapes collapse H1→H2** (best arm +0.2805R → −0.0057R) and buy exactly **one** green month. Not worth the machinery until the H2 collapse is understood. |
| **Size** | **0.30% of account = $150/trade on $50k.** Derived, not asserted — see §5. |

### What it is worth

| | EV/R | win | avgW | avgL | PF | totR | maxDD | green |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| A_base (shipped) | +0.0356 | 46.3% | 0.898 | 0.710 | 1.09 | +17.6R | −21.58R | 13/25 |
| **B_no1D** | **+0.1033** | 49.4% | 0.898 | 0.672 | 1.30 | **+50.6R** | **−12.49R** | **17/25** |

n=495 and n=490 of 498 sessions. The veto **cuts max drawdown 42%** and adds four green months — which matters more than the EV under a prop bar.

**Year split** (2025-09-01, run tonight): A_base **+0.140 → −0.070**. B_no1D **+0.159 → +0.048**. The baseline dies out of sample. The veto does not.

### Prop-eval verdict, $50k, 8% target / 4% trailing / 2% daily / 5 min days

**Full-book path: PASS at 0.15%, 0.20%, 0.25% and 0.30%.** At 0.25% ($125/trade): PASS on 2025-07-02, 9.9 months, +8.58% final, −3.12% max drawdown.

**Rolling-start (every possible start day, 252-session horizon): 38.7% at 0.25%, 37.1% at 0.35%, 47.8% at 0.50%. From a year-2 start: 0.0% / 0.0% / 18.2%.**

### The rule that breaks if it fails

**The 4% trailing drawdown.** At 0.35% and above, B_no1D fails on `trailing_drawdown`, every time, at every larger size. At 0.10% it fails the other way — `profit_target_not_reached`. The pass band is 0.15%–0.30% and it is 15 basis points wide.

Second failure mode, and the one I'd actually bet on: **year-2 decay**. +0.048R in the last twelve months is a third of its first-year rate. If it decays again, the arm fails on `profit_target_not_reached` and the veto is a 2024–25 phenomenon.

---

## 3. WHAT HIS MARKS SAY

Corpus verified tonight: `marks_pool.canonical_pool()` → **1,263 judged symbol-days**, `{none 607, S 347, A 237, C 58, B 14}`, 70 contested.

### RULES — measured, adequate n, reproducible from a committed script

**1. Your refusals are worth money.** On the 146 symbol-days you refused that the engine traded anyway (168 trades), engine EV/R is **−0.3008R (n=137 after size gate)** against the book's +0.038R. Restricted to explicit day-level refusals: −0.2625R (n=87). On the identical one-trade-a-day policy, refused days **−0.1665R (n=24)** vs not-refused **+0.0493R (n=420)**. *The n=24 cut is thin; the n=137 cut is the rule.* This is the single strongest thing your marks establish, and no code currently reads it.

**2. Chop is the discriminator — its absence, not any positive tag.** Chop appears in **6 of 295** S-day notes (2.0%) and **91 of 453** non-S notes (20.1%). A 10x inverse. No positive setup tag comes close.

**3. Time is real, and both signals agree.** Your S-rate is **81.9% before 10:00** (136 S / 30 refusals, n=166) and **55.2% after** (53 S / 43 refusals, n=96). The engine's own EV/R over the same bins: **−0.018R early (n=2,316) vs −0.093R late (n=1,086)**. Your intuition and the P&L point the same way. R3 confirmed.

**4. The engine cannot see two-thirds of your S days.** Of 347 canonical S days, **227 (65.4%) have no traded candidate anywhere in the book.** The breakdown matters: 11 are off-universe, 44 are outside the 498-session window, and **172 are in the book with candidates that existed and never cleared the engine's own gate.** That 172 is the recall problem, stated exactly, and it is a gating problem, not a detection problem.

**5. BR+OCR confluence is the one structural family that agrees with you.** In your prose, BR and OCR named together: **22 of 295 S days (7.5%) vs 5 of 499 non-S (1.1%)** — lift 6.8. In the engine, BR+OCR confluence is its only non-negative family on your S days (**+0.0314R, n=91**) while plain break-and-retest loses (**−0.1738R, n=28**). One-candle-rule and 84%-reentry fire as traded on **zero** of your S days.

### HINTS — real, but too thin to build on

- **Order block is your highest-conviction claimed setup** (75.0% S-rate, 9 of 12 tagged cards) — and the engine has **no order-block family at all**. Zero traded rows match. Unmeasurable, not small — this is a coverage hole, not a weak signal.
- **Wick over level for stops**: 29 of 295 S-day notes mention wicks (9.8%) vs 15 of 453 non-S (3.3%). Your own AMZN_2026-01-14 note: *"if its tight and you have to chose the wick or the level, choose the wick."*
- **Your S label predicts, weakly.** `research/g96_does_his_S_predict.json`, as committed: **gap_r 0.1652, p 0.0266, n_S=201 vs n_non=482.** (The header number circulating tonight — 0.157 / p=0.037 / n=466 — is stale against the JSON.)
- **"As candle forming" is not an S rule.** It appears on 23 S and 22 non-S days, and the composed correction splits A:9 / S:7 / C:4 across 20 days. It is a timing correction you apply at every grade, not a discriminator.

### DELETED tonight — claims that would not re-run

- **Your S-rate by level type** (ORH 57.1%, PMH 14.7%, the 40.6% join rate). No committed script exists; `ls research/ | grep level` returns nothing. **Cannot be quoted.** The engine half of that analysis is fully verified and stands: ORH is the only positive named level (+0.0182R, n=552, 13/25 green), PDH is −0.0883R (n=208) and PDL is −0.0375R (n=180) — which independently corroborates §2's veto.
- **"25 same-candle contradictions across grading passes."** No committed script. What survives is the input: 1,263 pool rows, **70 contested keys**. The 70→38→25 decomposition cannot be re-derived and is struck.
- **"Whole-dollar/psych levels appear on 3 of 4 S days."** Contradicted by its own rig: `_s_prose_mine_out` reads **0 S / 0 non-S** for whole-dollar and **0 S / 1 non-S** for psychological. Struck.
- **The 22 `take: yes` days cannot move any S number.** 22 of 22 are absent from the canonical pool entirely; **0 of 39 take-answered days register as S.** Whatever they are, they are not S recall.

### One live bug in the corpus

`answers.regrade` is never read by `grade_read.py` or `marks_pool.py`. **TSLA_2026-05-21 and QQQ_2026-07-24 both carry `regrade=['to_a']` and both sit in the pool today as grade `S`.** QQQ is additionally `contested=True, raw_grades=['C','S']` — the note that would settle the contest is invisible to every rig. Two of 347 S days are wrong. Twenty-one of the 27 `answers.*` keys in the mark files are read by nothing.

---

## 4. WHAT SURPRISED US

**Every better entry was lookahead.** The retest-touch entry that read **+2.1458R** collapses to **−0.8324R** on a one-line off-by-one fix — its stop was placed on the fill bar's own low, a price not yet printed at the moment of the intrabar fill. Its size gate then kept only bars that wicked past the level and closed back through it (**24 of 24 survivors**). And the honest version inverts the story: a limit resting before the confirm bar decays monotonically — **K=0 bars 0.83R → K=5 0.67 → K=10 0.52 → K=20 0.18 → K=60 0.07** (n=300 to 2,890, stable in both years). **The value is being AT the confirm, not resting early — which is exactly what the shipped engine already does.**

**Stop placement was a fill-convention artifact, not a finding.** The claim that a fixed 0.25% stop beats the level stop by +0.132R depends on triggering the stop on a *close* through it and then filling at the *stop price* — an order that does not exist. Fill the close honestly and it is **+0.026R, 95% CI [−0.025, +0.077]**. Use a real resting stop and it is **−0.004R**. The winner changes with the fill convention, in which case there is no winner. A separate leak: because the stop needed a close but the target only a touch, **6–9% of trades whose low went clean through the stop were scored as full winners.**

**Exits are not the lever, and this is the most useful null of the night.** Seven ladder shapes recompute to a per-row difference of **0.000000R** against an independently written bar-walk. The best shape is +0.137R against a one-shot +0.031R — but **all eight arms collapse H1→H2**, three of the four "4-rung" arms are literally the same arm on **411 of 444 rows** (the weight list truncates when fewer rungs survive), and scaling out buys **one** green month, 12/25 → 13/25. On the metric you made primary, exit shape does nothing.

**The engine's own downgrade variables are anti-predictive as a family.** Trading only candidates with **zero** downgrades — structurally clean setups — books **−0.1152R (n=143)**. Four of the eight solo vetoes are negative. `counter_trend_not_respected` is the worst: vetoing it costs **−0.0822R**, and it is wrong-signed in *both* halves of the book — the only variable that is. It is reliably picking out the good trades. Its sign should be inverted and tested.

**`chase` is not a price-action variable at all.** `downgrade.chase()` reduces to a threshold on `|entry − level| / price`, and for break-and-retest the stop *is* the level — so it is exactly `stop_pct ≥ 0.5%`, confirmed at **0 of 444 mismatches**. It is the size gate cutting from the other end, and it should never have been ranked alongside structural rules.

**Null on runners, and it is clean.** Eighty-five arms tested against "does this trade reach 3R while alive." Under Westfall-Young max-statistic correction over 20,000 shared permutations — strictly more powerful than Bonferroni — **zero survive**; best adjusted p is 0.16. Nothing in this book predicts a runner. But re-label the identical family on EV per trade in R, as your ruling demands, and **one arm survives: the 1D veto, FWER p=0.0047.** The question was being asked in the wrong unit.

**`break_then_rejection` trips 0 times in all 127,152 rows.** Not rare — unreachable. `_break_bar` returns the most *recent* bar that closed through the level, so any re-break moves the anchor past the rejection it was looking for. This is the repo's known bug class firing again. `stale_retest` is nearly dead for the same reason (179 of 127,152).

**Selection *can* fix sizing — the opposite of what we concluded.** At $250/trade the baseline FAILs on `trailing_drawdown`, but the `level_not_respected` and `no_displacement` vetoes both **PASS**. Sizing alone fails; selection alone fails; sizing and selection together pass.

**There is no hindsight ceiling to chase.** Real best-of-day is **$2,684/day** against a null of **$2,763/day** from random draws of the same size. The "oracle" was max-of-N arithmetic. That number should never be quoted again as a target.

**And the one that invalidated half of tonight's consensus: the EV unit is not one unit.** Three populations run under the same arm names — **444** (`omen_metrics.first_of_day_arm` picks the first candidate, *then* drops the day if it fails the size gate), **495** (`g116`, gate inside selection, halted excluded), **498** (gate inside selection, halted included). The same chase-veto arm reads **+0.0698** and **+0.0632** depending on which. This is not cosmetic: **"every edge tonight is a year-1 artifact" is TRUE on the 444 unit and FALSE for the 1D veto on the correct one.** The pick-then-gate construction silently deleted the exact days that carried the veto's out-of-sample performance. The defect is at `research/omen_metrics.py:470` and it needs one owner and one commit before any two sweeps are combined.

---

## 5. POSITION SIZING AND THE $1,000 QUESTION

### Kelly loses to the drawdown constraint, by an order of magnitude

Kelly computed numerically as the *f* maximising E[log(1+f·R)] on each arm's own empirical R sample:

| arm | full Kelly | quarter Kelly | eval allows | ¼K ÷ eval |
|---|--:|--:|--:|--:|
| A_base | 3.20% | 0.80% | 0.25% | **3.2×** |
| **B_no1D** | **9.91%** | **2.48%** | **0.30%** | **8.3×** |
| C_no1D_noThu | 16.48% | 4.12% | 0.40% | 10.3× |

Kelly is a growth criterion with no drawdown constraint. A 4% trailing drawdown is a hard absorbing barrier, and a barrier always dominates a growth rate. **Trade the eval's number: 0.30% of account. Even one-tenth-Kelly is over the line.**

### The $1,000 question: **No.** The number is **$12,000.**

Priced against **276 real Alpaca 0DTE ATM 1-minute prints** — premium is p10 0.401% / median 0.859% / p90 1.638% of spot, median $1.89 premium on a $206.75 stock. Your one live journal trade agrees exactly (TSLA $358.62, ATM put, $1.79 premium, delta 0.5).

**One contract is the entire sizing grid. There is nothing smaller.** Risk per contract = |entry − stop| × 0.5 × 100:

- **0.0% of B_no1D's trades risk ≤ $2.50** (0.25% of $1,000). Not "few." Zero.
- **10.4% risk ≤ $10** (1% of $1,000).
- Median risk per contract is **$30 — 3.0% of a $1,000 account. p90 is 8.6%. Worst is 34.4%.**

So **1% of a $1,000 account is unbuyable, and any plan built on it is fiction.** A single median loss is 3.0% of the account — **1.5× a 2% daily loss limit on one trade.** A $1,000 account cannot be a prop-eval-shaped account in options; the rules are structurally unreachable at the position floor.

Cost is not the constraint — a contract costs a median $159 and 0% of trades cost over $1,000. **Granularity is.** Contracts are integers and you cannot round down.

Simulated honestly on $1,000 — one contract a trade, real premium, loss capped at premium paid, compounding:

| arm | final | peak | trough | max DD |
|---|--:|--:|--:|--:|
| A_base | $731 | $1,900 | $401 | **63.9%** |
| B_no1D | $1,759 | $2,583 | $451 | **57.8%** |

B_no1D nearly doubles the account and troughs at $451 on the way. That is not a survivable account; it is a coin toss you happened to win. **And every one of those drawdowns is an underestimate** — the sim uses a flat delta of 0.5, so a −1R stock loss maps to exactly −1R of premium. `research/g80_options_honest.json::floor` measured real contract behaviour and found **106–126 rows past −1.25R on the premium while zero underlying rows were.** Theta and gamma make the contract's losses worse than the stock's R.

**The derived minimum account for this strategy in options is ~$12,000** — where one contract equals the 0.30% the eval tolerates on B_no1D. Below that, the instrument sizes you, not the plan. **The right move is the prop account, not the $1,000 account**, and that is now an arithmetic conclusion rather than a preference.

---

## 6. THE KILL CRITERION

You are owed a cheap way to prove this cannot work. Here it is.

**The test.** The 1D veto is the *only* thing that survived tonight — multiplicity (FWER 0.0052 over 53 arms), an independent 50,000-draw permutation (p=0.000040), both halves, all three years, and the year split. It carries the whole thesis. So test it, and nothing else.

**Run `B_no1D` forward on 60 real sessions** — roughly three months — paper, one trade a day, first size-gated candidate, PDH/PDL vetoed with substitution, level stop, flat 2R, $150/trade on a $50k eval simulator with the 4% trail live.

**Kill condition: if EV/R over those 60 sessions is ≤ 0.00, this approach is dead** and no amount of further sweeping will revive it. Not "needs tuning." Dead. Because if the single arm that survived four independent robustness tests does not hold out of sample, then the other ~400 arms measured tonight — every one of which already failed at least one of those tests — will not either.

**Pass condition to keep going: EV/R ≥ +0.05R with max drawdown under 2% of account.** That is below its measured year-2 rate of +0.048R, so it is a fair bar, not a generous one.

**Cost: $0 in API credits and three months of paper.** No new backtests, no new rigs, no new marks.

**Cheaper still, tonight-cheap, if you want a same-week answer:** hold out calendar-2026 completely, refit nothing, and require the 1D veto's EV/R > 0 on that slice alone. Partial evidence already exists and it is favourable — 1D trades book −0.364R in 2026 specifically — but a clean, nothing-fitted 2026-only run is the honest version and it takes one script.

**What is NOT a kill criterion:** another sweep. Tonight ran roughly 400 arms across twelve sweeps and produced exactly one survivor. The marginal value of arm #401 is zero, and it is where the API credits went.

---

## 7. WHAT ONLY YOU CAN ANSWER

Five questions. Each answerable from a chart, none re-asking a rule you have already given.

1. **Prior-day highs and lows lose money — badly.** n=104 of 495, EV −0.352R, 29.8% win, p=0.000040, never positive in any year. Pull up five of those charts: **is the level wrong, or is the entry late?** If PDH/PDL setups are real and the engine is just arriving 24 minutes behind you on them, the veto is throwing away good trades and we should fix timing instead.

2. **On all 347 of your S days, the engine has fired a traded one-candle-rule setup zero times, and an 84%-reentry zero times.** It only ever fires break-and-retest or BR+OCR. **Are your S setups actually break-and-retest — or is the engine mislabeling your OCR entries as BR?**

3. **172 of your S days are in the book with candidates the engine generated and then graded away.** Two charts each on five of them: **what did you see that the gate killed?**

4. **Wick or level for the stop?** Your own TSLA_2026-06-08 note: *"would the candle be good to use as the stop? the wick is but i dont like the size of the candle… im conflicted here and contradicting myself."* Tonight's measurement says the stop convention moves EV by roughly **2× more than the target choice does**. One answer settles the largest single lever in the system.

5. **Two of your S grades disagree with your own later note.** TSLA_2026-05-21 and QQQ_2026-07-24 both carry `regrade: to_a` and both still sit in the corpus as `S`. **Confirm the downgrade** and I will wire `answers.regrade` into `grade_read.py`.

---

### Housekeeping, so nothing rots

Nine of tonight's twelve adversarial rechecks live in this session's scratchpad (`adv.py`, `adv3.py`, `adv_targets.py`, `zz_tl_adv*.py`, `tgtadv_unique_9f3.py`). **They will not survive the session.** The stop-placement, targets-flat, targets-level, time-windows and day-policy refutations are currently unbacked by committed code, which violates the repo's own rule that every claim routes through a committed script. They need `git add` before this lane closes — and `research/omen_metrics.py:470` needs the pick-then-gate fix, because that one line is why half of tonight's fleet concluded the edge was a year-1 artifact when it is not.