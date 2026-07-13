# A/A+ Inversion Audit (B3) — 2026-07-13

**Anomaly:** A/A+ 68 tr, 30.9%W, −$6,393 vs B 693 tr, 36.6%W, +$62,451
(backtest_report_12mo.md 2026-07-12 run, $1k flat risk).

## Verdict

**The inversion is NOT a broken A+ pattern-detector. It is grade laundering:
84%-rule re-entries with no entry-quality gate get floored to B, then promoted
to A by the "clear of all levels" rule. They are 22 of the 68 A-tier trades
(32%) at 22.7%W and account for −$8,395 — more than the entire A-tier loss.
B&R trades graded A are fine (+$3,000, 37%W ≈ B-tier).**

## 1. Decomposition of the 68 A/A+ trades

| Subgroup | n | W/L | Win% | P&L | Reads as |
|---|---|---|---|---|---|
| reentry_84_rule A | 22 | 5/17 | 22.7% | **−$8,395** | THE inverter |
| break_and_retest A | 27 | 10/17 | 37.0% | +$3,000 | ≈ B-tier, healthy |
| break_and_retest A+ | 13 | 4/9 | 30.8% | −$1,000 | n too small, mild negative |
| one_candle_rule A | 6 | 2/4 | 33.3% | $0 | noise |
| **Total** | **68** | | **30.9%** | **−$6,393** | |

Remove the 84% trades → A/A+ = 46 tr, ~35%W, +$2,000. Inversion gone
(A+ still unproven at n=13, but no longer a money-loser headline).

## 2. How a 84% re-entry becomes "A" (the coded path)

1. `signal_runner.py:628` — entry gate: `RULE84_LESSON or self._strong_pa(current)`.
   **`RULE84_LESSON = True` (line 102) → strong-PA gate is BYPASSED.** Any bullish
   candle closing at/above the failed entry qualifies.
2. `omen_bot.py grade_trade()` called with `or_high = or_low = entry_price` — the
   reclaim price is "at key level" by construction (`candle.low <= entry_price`
   almost always true on a reclaim). Hammer → A+, big wick → B, else C.
3. `signal_runner.py:643-644` — `if grade == C: grade = B`. The comment says
   *"strong-PA gate already passed"* — **stale/false under RULE84_LESSON=True.**
   Ungated candles get a free B.
4. `_grade_for_levels()` (`signal_runner.py:287-290`) — B→A when entry is beyond
   every mapped level ("breakout conditions, clear of all levels"). A reclaim of a
   level that was the day's breakout level is usually clear → **B→A promotion.**
   (Hammer reclaims land A+ → demoted to A at :295-297, no `aplus_stack` key.)

Net: the lowest-gated setup in the book exits the pipeline wearing the
second-highest grade. Rulebook says the opposite: **"You need an A+ entry"**
(mastermind-1-0_1453512 00:09:04), "Requires A+ entry. Same setup, same stop,
same profit target" (bonus_1461019 00:09:06), same-thesis required
(trending→consolidating = disqualified). Coded 84% path checks none of that.

## 3. Coded criteria vs rulebook A+ (per-criterion diff)

Rulebook A+ (mastermind §9 + Day 6 boot-camp stack):

| # | Rulebook criterion | Coded? | Where / gap |
|---|---|---|---|
| 1 | Strong momentum/displacement on break | PARTIAL | `_aplus_stack` requires `_bnr_displacement` (1.5× body — OUR quantification, source is qualitative). Only consulted for A+, not A |
| 2 | QQQ/SPY structure aligned | **NO (grade path)** | Only a +1 S-score input via Rule-4 level-break proxy (`_qqq_aligned`). Videos: real leg = moment-to-moment RELATIVE STRENGTH at entry, not level-break. Grade never sees QQQ at all |
| 3 | Entry level is a HTF level (4H/1H pivot) | **NO — coded as its near-opposite** | `_grade_for_levels` :281-290 requires entry BEYOND all levels for A ("clear road"). Source wants entry AT an HTF level; bot rewards being past every level. Measured effect: promoted B&R As perform exactly like B (37% vs 36.6%) — the promotion adds zero edge, it just relabels |
| 4 | Clean retest w/ preferred candle (hammer) | YES | `_grade_pa` hammer→A+ — matches audit #13 |
| 5 | Clear stop, known immediately | PARTIAL | min-stop + structural-stop checks exist (S input), not a grade criterion |
| 6 | R:R ≥ 1.85, ~2R target | YES (blind 2R sim) | n/a |
| — | HTF thesis (daily/4h/1h) | WEAK PROXY | `htf_bias` = SMA20-of-hourly ±0.1% band (backtest_week.py:270). Opposed→D, neutral caps→B — direction right, but a 0.1% band is not "thesis on daily/4h/1h" |
| — | Day 6 stack: gap up, first 5-min all green, first pullback of day | **NO** | none coded anywhere |
| — | A+ = gradient, 1-2×/month | NO | bot fires 13 A+/yr ≈ 1/mo — frequency actually plausible; but A is minted by level-promotion, not confluence count |

## 4. Hypothesis list → verdicts

| Hypothesis | Verdict | Evidence |
|---|---|---|
| H1: 84% C→B floor + B→A promotion launders ungated re-entries into A | **CONFIRMED — primary inverter** | 22 tr 22.7%W −$8,395 = 131% of total A-tier loss; `RULE84_LESSON=True` bypasses the only PA gate; :643 comment stale |
| H2: "clear of all levels" B→A promotion selects bad trades | REFUTED as inverter, CONFIRMED as non-signal | B&R A = 37.0%W ≈ B 36.6%. Promotion doesn't hurt, it just doesn't mean anything (Austin's 30d 67%-win observation didn't generalize to 12mo) |
| H3: A+ hammer-stack misses rulebook legs (QQQ RS, HTF pivot, gap/first-pullback) | PLAUSIBLE, UNDERPOWERED | 13 tr 30.8% −$1k; two missing legs are exactly the sourced ones (§3 rows 2-3). Can't confirm at n=13 — B4's corrected definition is the test |
| H4: mis-grading real A+ setups as B (hidden confluence in B pile) | UNTESTABLE HERE, CONSISTENT | B pile carries all profit; per Day 6, confluence (QQQ RS, gap, first pullback) is invisible to grade_trade, so genuine A-quality trades necessarily sit in B today |

**Which coded criterion inverts: the C→B floor at `signal_runner.py:643` (and its
twin :824 put-side) operating without the strong-PA gate it assumes
(`RULE84_LESSON=True`), compounded by `_grade_for_levels` B→A promotion at :287-290.**

## 5. Handoff to B4 (encode corrected A+ behind flag)

1. **84% re-entries: cap grade at B** (or C) unless the reclaim candle itself
   passes an A-quality gate — rulebook wants A+ entry on re-entries, coded floor
   grants B for free. Cheapest single change; removes ~130% of the inversion.
   Overlaps C9 (strict-spec 84%: A+ entry + same-thesis) — B4 flag should share it.
2. Corrected A+ = mastermind §9 stack: displacement + QQQ relative strength at
   entry (NOT Rule-4 level-break proxy — that one measured inverted twice) +
   entry AT an HTF/PD level + hammer. Encode behind flag, A/B 12mo.
3. Drop or demote the "clear of all levels" B→A promotion in the A/B — it
   contributes nothing (H2) and contradicts source criterion #3.
4. Fix stale comment at :643/:824 whatever else happens.
5. Note for tier sizing: 84% signals carry no S score, so the current
   S≥4+[hammer] tier is NOT contaminated by this — the inversion blocks
   grade-based sizing (GRADE_SIZE_PCT: A+ 1.0 / A 0.8 / B 0.6 would oversize
   the 22.7%-win group), which stays unjustified until B4's A/B lands.
