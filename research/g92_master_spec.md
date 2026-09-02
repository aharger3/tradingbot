# OMEN Master Spec — Analytical Core

**Supersedes** `research/g92_master_spec_DRAFT.md`. That draft's header claimed "each adversarially verified (0 REFUTED, 0 QUOTE_INACCURATE, 0 OVERSOLD returned)". The verify phase was broken and checked nothing. The real pass returned, across 9 axes and 78 claims: **8 REFUTED, 1 CARD_NOT_FOUND, ~40 OVERSOLD**. Every surviving item below carries its verdict inline. Three of the draft's eight shortlist entries do not survive, and its ONE CHANGE is measurably money-negative — shown below, not argued.

**Book.** Honest fill = close fill (`ENTRY_FILL=close`), stops via `stop_rule.stop_fill_price()`, `signal_runner.min_risk_floor` on. `research/bt2y_trades.json`, 500 trading days, 25 months. One trade a day = the first fired-and-traded candidate of the session (`g86_honest_ceiling.candidates`, sorted by `(day, et, sym)`). **1R = $1,000 unless a row says otherwise.** Reproduced this session: `python research/g86_honest_ceiling.py` → `first $28/day, best $2948/day, 9322 candidates over 500 days`.

**Baseline being moved.** First-setup-of-day **$28/day, 45.4% win, 11/25 green months**; precision **39.5%** (of 100 days it trades, 60.5 he refused); **18.6** candidates/day against a target of **1–3**; oracle best-of-day **$2,948/day, 25/25 green**; his bar **$397/day, every month green**. g91: index lane QQQ/SPY/IWM **2.3 cand/day, $51/day, 49.0% win, 13/25 green**.

**What is new here.** Nine arms measured on the honest book this session, not forecast. The rig is g86's own candidate stream — it reproduces g86's $28/day and g91's $51/day and $6.59/day funded figures to the dollar, so it is the same ruler.

| arm (one trade/day, honest close fill, 1R=$1,000) | cand/day | days | $/day | win | green | max DD | max 1R inside $2,500 trailing | funded $/day |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL pool, baseline | 18.6 | 500 | $28 | 45.4% | 11/25 | $25,569 | $98 | $2.72 |
| FULL, **retest-required** | 14.2 | 500 | $36 | 46.7% | **15/25** | $19,654 | $127 | $4.58 |
| FULL, **retest-required + no-chase** | 11.2 | 500 | **$73** | 48.3% | 14/25 | $16,671 | $150 | $10.89 |
| INDEX QQQ/SPY/IWM, baseline | 2.3 | 402 | $51 | 49.0% | 13/25 | $19,405 | $129 | $6.59 |
| INDEX, **retest-required** | **1.8** | 402 | **$74** | 49.3% | **16/25** | $13,353 | $187 | $13.86 |
| INDEX, **retest-required + 84% re-entry** | 1.8 | 402 | **$78** | 49.6% | **16/25** | $13,353 | $187 | **$14.66** |
| FULL, gate on the shipped S/A/C ladder (`sgrade=='S'`) | 2.9 | 464 | **−$29** | 44.8% | 11/25 | — | — | — |
| FULL, gate on the shipped displacement tag (`disp`) | 3.6 | 473 | **−$9** | 43.1% | 12/25 | — | — | — |
| FULL, gate on his named levels only (PMH/PML/PDH/PDL) | 4.8 | 490 | **−$17** | 43.5% | 11/25 | — | — | — |

The three negative rows are the draft's shortlist #1, #2 and an implication of the "pivot not levels" mark. They are reported because they were going to be built.

**Caveat binding every row.** These are *selection* results over the book's own recorded, causal `downgrade.score()` fields — they choose which already-detected candidate is taken first. They are not a re-run of detection. Shipping any as a fire gate should reproduce these numbers exactly (detection unchanged; only which candidate is *first* moves), and **that reproduction is the pass test, not an assumption**.

---

## 1. THE SHORTLIST

Ranked by (verified evidence × measured precision/money lift) / build cost.

### 1. Retest-required fire gate — do not fire a break that never retested

| | |
|---|---|
| **What changes** | `research/downgrade.py:296 no_retest()` is a **ratified** variable (`VARIABLES`, 64–73), causal, computed on every row — and it only ever *scores*; nothing suppresses a signal. Add `RETEST_REQUIRED` beside `S_GATE` (`signal_runner.py:384`) / `BNR_DISPLACEMENT_GATE` (:170) / `HTF_BIAS_GATE` (:220), applied in `_route`, capping a tripping candidate to **C (alert-only)** — the convention those three already use. Bars are cached (`_dg_bars_cache`, :2425). |
| **Axis / cards** | `process` c1 — **verdict OVERSOLD** (claimed 5 cards, 3 clean): `HOOD_2025-12-23` "you entered off no break and retest or anything", `TSLA_2025-03-25` "just entering on a break", `QQQ_2024-08-23` "you entered on an overextended break candle". Plus `rule_03`, ballot **yes**. Post-verdict strength: **hint (3/34 timestamp-bearing cards, 4/162 corpus)**. |
| **The correction that makes it shippable** | The draft's codeable form was *"require a confirmed retest bar strictly before an entry can fire"* — that ships entries **later**, and is **REFUTED** by `rule_03` in his own hand ("engine entering late is a bug, should always be entering while the restest is occuring") and by 11 "as candle forming" cards (`entry_timing` c3, OVERSOLD, but its 11/11 and 88/88 counts verify exactly). **Zero of 162 cards ask for an extra confirmation bar.** This gate adds no delay: it refuses only the case where a retest never happened. Break bar ≠ retest bar; the fill stays where it is. |
| **code_status** | ratified variable, **never wired as a gate**. |
| **Build** | **small** — one flag, one call site, one test. |
| **Measured effect** | FULL: $28 → **$36/day**, green **11→15/25**, cand/day 18.6→14.2, max DD $25,569→$19,654. INDEX: $51 → **$74/day**, green **13→16/25**, cand/day **2.3→1.8** (inside his target), max DD −31%. |
| **Why first** | Highest measured money and durability lift per line on the list; his complaint in three separate probe sections; the only item that moves candidates/day toward 1–3 *and* $/day up simultaneously. |

### 2. Chase fire gate — refuse the overextended break candle

| | |
|---|---|
| **What changes** | `research/downgrade.py:444 chase()` with `ENABLE_CHASE_DOWNGRADE = True` (:153) is **shipped and ratified as a downgrade**; `signal_runner` already tags rows `[chase]`. Same one-line treatment as #1. |
| **Axis / cards** | `exit_scale_out_ladder` c2 (**verdict HOLDS**, corrected *hint*) supplies the only direct card: `QQQ_2024-08-23`, "you entered on an overextended break candle". Post-verdict strength: **single-card**. |
| **code_status** | ratified, scoring only, not a gate. |
| **Build** | **trivial** — same flag block, second predicate. |
| **Measured effect** | Stacked on #1, FULL: $36 → **$73/day**, win 46.7→48.3%, cand/day 14.2→**11.2**, max DD →$16,671, funded $4.58→**$10.89/day**. On INDEX it is a **no-op** (identical rows). |
| **Honest label** | **The money is the argument, not the marks.** One card. Ranked second because it is one flag from #1's code and +$37/day with lower drawdown on a ratified variable is not free to leave. If his eye says the chased entries were fine, kill this first. |

### 3. Narrow the *fired* universe to QQQ / SPY / IWM; keep scanning the full pool

| | |
|---|---|
| **What changes** | `live_scanner.py:67 DEFAULT_SYMBOLS` = 29 names; fire only on the three index names, log the rest. **Not** `universe.CORE_SYMBOLS` — see drops. |
| **Axis / cards** | **Not a mark finding.** `mentor_ballot` rule_11 is **verdict OVERSOLD**: he wrote "10 tickers is a good sample size" and **named none**; the draft's mapping to `CORE_SYMBOLS` is contradicted by his own session — **39 of the 60 cards he graded positively are on non-core symbols**, across 16 names. Evidence for *this* item is `research/g91_lane_slice.py` plus the demand read: S-rate **27.8% over 1,246 judged symbol-days**, **38.1% on QQQ/SPY/IWM (83/218)** — with g91's stated confound (deck cards were selected by `build_deck`, not randomly sampled). |
| **code_status** | config only. **Build:** trivial. |
| **Measured effect** | Alone: 18.6→**2.3 cand/day**, $28→$51/day, green 11→13/25, funded $2.72→$6.59/day. With #1: **1.8 cand/day, $74/day, 16/25 green, funded $13.86/day**. Cost: **98 of 500 days have no index candidate** (402/500); forfeits the equities oracle ($2,317/day best-of-day on the 15 equity names). |
| **Why not #1** | It buys the *count* target, not accuracy, and it is a lane decision with a real cost — §3 states the fork rather than assuming it. |

### 4. Reconcile the two S/A/C ladders — and keep the grader out of the fire path

| | |
|---|---|
| **What changes** | `signal_runner.py:1759–1767` (`compute_austin_tier`, T11(a)) hard-caps a no-displacement B&R to **C**, skipping A entirely; `BNR_DISPLACEMENT_GATE` defaults **"1"/ON** (:170), so this is shipped behaviour, not an arm. `research/downgrade.py::score()` — the ratified ladder — makes one trip an **A**. Two implementations, one live, disagreeing on his most-discussed variable. Fix: T11(a) demotes to **A**. |
| **Axis / cards** | Corpus says **A**, not C, and not a kill. `a_vs_s_boundary` c1 (**OVERSOLD** → *hint*): 5 of **17** A-naming chart cards cite no-displacement — `AVGO_2025-03-28`, `MSFT_2026-07-28` ("9:50 a trade no displacement"), `AMZN_2025-10-07`, `AMZN_2025-11-21` ("both A trades because of no displacement"), `ACHR_2025-06-27` ("9:39 A entry no displacement, S entry at 10"). And S survives it when a substitute is named: `NVDA_2025-06-03`, `PLTR_2025-07-17`, `SPY_2025-07-16`. |
| **What it must NOT become** | **Do not wire `downgrade.score()` as the fire gate.** Measured: first `sgrade=='S'` of the day is **−$29/day against $28**, 11/25 green, and on the index lane it **drops 255 of 402 days** for −$19/day. The `sgrade` column **is** `downgrade.score()`'s grade (`backtest_2y.py:267`, `backtest_week.py:531 _sgrade_84`), so this tests the exact proposal. The draft's ONE CHANGE fails its own "$/day ≥ $28" threshold before it is built. |
| **code_status** | **two implementations disagree — confirmed bug**; the ratified one should stay measurement-only. **Build:** small. |
| **Measurable effect** | Not money. Precondition for any classifier work: today half the engine says no-displacement is a kill and half says it is one downgrade. Metric: book rows where `austin_tier` and `sgrade` disagree — target **0**. |

### 5. Guard the runner target: it must sit beyond 2R, or be logged as a cap

| | |
|---|---|
| **What changes** | `backtest_week.py:1032–1043` computes `runner_tgt` as the nearest PDH/PMH or next whole dollar beyond the scale point and **never compares it to `target`**, the 2R price computed 12 lines earlier (1020–1021). `pnl()` (396–402) never checks the distance. `scale_level` is the session extreme as of the entry bar, so it can sit cents from entry and the runner lands *inside* 2R. |
| **Axis / cards** | `process` c5 — **verdict HOLDS** (2/8 trade_anatomy, corrected *hint*). `QQQ_2025-02-25`: "runner always the last one why is it in between 2 r?" — the ordering bug, on **one** card. `QQQ_2024-08-26` says something adjacent but different. **Do not restate his "we shouldnt be targeting .41" as a realized R-multiple** — it is a target, and `exit` c8 was marked **OVERSOLD** partly for that swap, in the project whose honest-fill reset exists to police it. |
| **code_status** | implemented and unguarded — **live arithmetic bug in the rig producing every published dollar figure**. **Build:** small for the guard; the policy is his (§4 q6). |
| **Measurable effect** | Count of trades whose runner was capped inside 2R, and by how much. $/day cannot fall — the guard only moves the runner out. |

### 6. Give `path_target` a consumer — targets are structural, R is the fallback

| | |
|---|---|
| **What changes** | `signal_runner.py:2052–2060` computes `blocking_levels(sig, levels)` and stamps `sig["path_levels"]` / `sig["path_target"]`, naming the target policy that would consume it. Grep of the tree: **written, read nowhere**. Build the consumer: the ladder is a list of real levels from entry outward, and **2R is inserted only where no level sits nearby**. |
| **Axis / cards** | The completeness critic's merge **M1** — best-supported finding in the corpus once joined, **9 cards**, currently shattered across four axes at 1–2 cards each and every fragment labelled *hint*: `QQQ_2024-08-26` ("when 2r falls between a whole psych number target that instead"), `QQQ_2025-02-25` ("2r level is trumped by HTF levels and whole psych number if one is close"), `PLTR_2024-09-20`, `GOOGL_2024-10-15`, `NVDA_2024-09-03`, `UBER_2026-08-04` ("theres major levels it needs to break for good rr"), `MARA_2025-10-01` ("hod is a consolidation wall and too hard to target"), `TSM_2026-07-24`, `rule_08` (ballot **skip**, counter-proposal: 1h/4h pivot structures as scaling targets — **verdict HOLDS**). |
| **What the verdicts removed** | The **specific 4-leg ordering** is **OVERSOLD → single-card**: only `PLTR_2024-09-20` gives it; `GOOGL_2024-10-15` gives "OCR PT HOD, 2r, median, best average for runner" — 2R at leg **two**, no "next structural level" leg. Build the principle; do not hard-code a leg order. |
| **code_status** | **partial** — data computed on every signal, consumer absent. A dead *field*, sibling of the CLAUDE.md unreachable-branch bug class. **Build:** medium. |
| **Measurable effect** | $/day and green months against whichever of #1–#3 has shipped, plus a new read: **distance from entry to the first real level** as a setup-quality variable. |

### 7. Fix the measurement unit: the 84% re-entry is unrepresentable in "one trade a day"

| | |
|---|---|
| **What changes** | `research/g86_honest_ceiling.py::candidates()` takes the **first traded row of the day**. Verified this session against `research/bt2y_trades.json`: **635 armed re-entries, 83 traded (13.1%), mean −0.117R, 32.5% win, −$9,707 over two years, on 73 of 500 days — and 0 of 500 days has an 84% re-entry as its first traded row**, necessarily, since a re-entry is the second trade of an idea. Every headline figure in THE LANE is measured on a book that structurally cannot contain one of "the three setups Austin trades" (`SignalType.REENTRY_84_RULE`, `signal_runner.py:1306`). |
| **Axis / cards** | **Owned by no axis — 5 cards, 0 claims.** Two are **S grades whose stated plan includes being stopped out**: `GOOGL_2025-09-15` "9:46 because of all those green candles, i would do a stop out and 84 percent reclaim at 9:56-57"; `MU_2026-04-29` "9:52 - stop out and 84 reclaim wouldve worked out but only for LOD". One counts a stopped-out multi-entry day as a take: `AVGO_2025-03-28` "9:38 long, stopped out by 84 once so two Ls, then another channel". One gives the arming condition: `SOFI_2025-11-21` "a lot of chop happened so if lost on trade, 84 percent likely should not be considered". Plus `rule_02`. Five cards beats every claim in the decode except the chop tally. |
| **What the measurement says, against the critic's framing** | Measured, not asserted: appending the armed re-entry is **+$1/day full pool ($28→$29, green 11→12)** and **+$4/day on the index lane ($74→$78, green stays 16/25)**. It is **not** a money lever. Its value is making his verdicts *representable*: `AVGO_2025-03-28` is a four-entry, two-loss, stopped-and-re-entered day he marked **take=yes**, scored today on its first dot alone. An unknown share of "62 refusals per 100 days traded" is days where he accepted the **sequence**. |
| **code_status** | shipped detector, absent from the measurement rig. **Build:** small — one file. |
| **Measurable effect** | The precision denominator itself. Print both books; nothing ships off it. |

### 8. Promote `strong_pa` to a measured 9th downgrade variable

| | |
|---|---|
| **What changes** | `signal_runner.py:102 STRONG_PA_MULT = 1.5` exists and is used **only** to gate the 84% reclaim (:2335). `downgrade.VARIABLES` (64–73) has no `strong_pa`. Add it, default OFF, measure only. |
| **Axis / cards** | `rule_02`, ballot **yes**, asking for exactly this: these "are for 84 percent rules really, **but can help as the downgrade too**". The two-sided spec in the same note — "not entering stong PA when copping on levels, **or level clean but strong PA never comes**". `AVGO_2025-02-20` separates the ingredients: "it looks like displacement **and weak PA**". Post-verdict **single-card** (`mentor_ballot` rule_02 **OVERSOLD**, but only for a fabricated code citation — "failed three implementations" appears nowhere in `research/downgrade.py`; **strike that phrase**. The ballot fact and his words verify byte-exact). |
| **code_status** | the measure ships; the *use* he ratified is absent. **Build:** trivial. |
| **Measurable effect** | Report only: does `strong_pa=False` correlate with his `no` grades, and does gating on it move $/day? If flat or wrong-signed, kill it — that is what happened to `level_not_respected`. |

### Dropped, and why

| Dropped | Reason |
|---|---|
| **Wire `downgrade.score()` as the fire gate** (the draft's ONE CHANGE) | **Measured negative.** First `sgrade=='S'` of the day = **−$29/day vs $28**, 11/25 green; on the index lane it kills 255 of 402 days for −$19/day. Testable on the existing book because `sgrade` **is** `downgrade.score()`'s grade (`backtest_2y.py:267`). Ship #4 instead. |
| **Swap displacement from body-size to separation** (the draft's #2) | Not dropped for being wrong — dropped for being **unmeasurable today**, and its shipped proxy is money-negative: filtering to the `disp` tag (which *is* the shipped body check, `signal_runner.py:2009`, body ≥ 1.5× avg body of prior 10) gives **−$9/day full, −$29/day index**. Evidence the shipped check is worthless, **not** that separation is. `research/g81_displacement.py`'s `separation_atr()` has never run against the honest book. → §4 q3. |
| **His named levels only (PMH/PML/PDH/PDL)** — from `MU_2026-03-18` "i didnt like the Br of pivot not levels" | **Measured negative:** −$17/day (vs $28), 11/25 green; the *not-his* levels carry **+$82/day**. His mark is real and uncovered by any axis; as a fire gate it is amputation. → §6 c3. |
| **Chop as a veto** (15/22 coded refusals, `veto_vocabulary` c1 **OVERSOLD** → *strong*) | The wired analogue `downgrade.level_not_respected` is wrong-signed, re-measured here: first candidate **not** tripping it is **−$58/day, 7/25 green**. Over all 47 refusals the chop rate is **15/47 = 32%**, not 68%. `CRM_2025-10-09` is chop-tagged and graded **yes**. Highest card count in the corpus; dropped anyway. |
| **Intrabar / "as candle forming" entry** | His clearest ask (11/11 cards; `entry_timing` c3 **OVERSOLD** only for a claimed link to the g87 tolerance result). Unbuildable honestly: `entry_fill._assert_causal` raises on any bar at or before the signal bar, and g88 found **89.6%** of the closest attempt's fills landed before it. Honest version **$275/day vs the shipped $33** — 27% win, 15/25 green. → §4 q5. |
| **A confirmation bar before entry** (the draft's #3, `max_confirm_gap` 3→1) | **REFUTED in direction** by `rule_03` and 13 cards demanding an *earlier* entry. Zero of 162 ask for delay. Cutting the gap is a *lateness* fix, and it is blocked on §4 q2 — we do not know what minute to close to. |
| **4-leg PT ladder as a fixed order** | **OVERSOLD → single-card**; the two cited cards give different orders. #6 buys the principle. |
| **Trend-conditional scale split (30/30/30/10 vs 50/20/10/10)** | **OVERSOLD → single-card**, and *he never states which split goes with which condition* — that mapping was the decoder's. `backtest_week.pnl()` hardcodes a 2-leg 50/50 (396–402). N-way split model + trending classifier for zero stated direction. |
| **`SCARFACE_CONTRACT` (rule_12)** | Dead: `research/d1_scarface_ab.py` — no-op on P&L by construction; the realized path never imports `options_sizer`, and the sizer normalizes max loss to a flat $1,000, so A == B bit-identical. |
| **Weekly/4H HTF trend + liquidity zones (rule_07, ballot yes)** | **No 4h data is fetched anywhere in the repo.** And his note is a **question to us**: "all of this alligns with me, but how would we shape it into day trading?" |
| **Surface {S, A} instead of S-only** | `a_vs_s_boundary` c6 **OVERSOLD**: 4 of 7 cited cards carry his own negation, loss report, or question mark, and on every card with both grades he names the **S** as the entry (`INTC_2025-02-24`, `PLTR_2026-02-05`, `ACHR_2025-06-27`). `TSM_2026-07-24`: "were looking for **1 and done S trades a day**." → §4 q8, never shipped silently. |
| **`sequence_gate` as a predictor** | Exists (`downgrade.py:427`), `ENABLE_SEQUENCE_GATE = False` (:137), points the **opposite** way. Underlying claim **REFUTED**: `IWM_2026-05-05` has the S at 9:34 and the A at 10:06, and `INTC_2025-02-24` calls the ordering **rare** in the sentence used as proof. |
| **`reject_entry_if entry_bar == break_bar`** | Nothing to gate: `omen_bot.py:615–724`'s FSM makes them different by construction. → §6 c1. |

---

## 2. THE ONE CHANGE

**Ship #1: the retest-required fire gate.** One flag, one call site, one test.

It is the only item that is simultaneously (a) his most-repeated engine complaint across three probe sections, (b) a **ratified, causal, already-computed** variable, (c) measured positive on money, win rate, green months **and** drawdown, and (d) a move toward 1–3 candidates/day rather than away.

**The change.** In `signal_runner.py`, beside `S_GATE` (:384):

```
RETEST_REQUIRED = os.getenv("RETEST_REQUIRED", "0") in ("1","true","yes","on")
```

applied in `_route`, capping any candidate for which `downgrade.no_retest(bars, i, level, is_long)` is True to **C (alert-only)** — the convention `BNR_DISPLACEMENT_GATE` (:170) and `HTF_BIAS_GATE` (:220) already use. Bars from the existing `_dg_bars_cache` (:2425).

**The falsifiable test.** Honest book only, one trade a day, 500 days, 25 months:

```
python backtest_2y.py                     # regenerate bt2y_trades.json with the flag ON
python research/g86_honest_ceiling.py     # $/day, win, green months
python research/g91_lane_slice.py         # cand/day, max DD, funded sizing
python research/regression_gate.py && python research/test_runner_stop.py
```

**PASS requires all five.** The gate run must **reproduce** the selection numbers, because the gate does by suppression what the filter did by selection. A material miss means detection moved and the arm is not what it claims.

| metric | baseline | PASS threshold | measured (selection proxy) |
|---|---:|---:|---:|
| first-setup-of-day $/day, honest close fill | $28 | **≥ $34** | $36 |
| green months | 11/25 | **≥ 14/25** | 15/25 |
| candidates/day | 18.6 | **≤ 15.0** | 14.2 |
| max drawdown at 1R = $1,000 | $25,569 | **≤ $21,000** | $19,654 |
| S-day recall (his S days the engine still fires on) | current | **≥ current − 5.0pp** | **unmeasured — this is the gate** |

**FAIL on any one → the flag stays off and the run is committed as a measurement, not shipped.**

The fifth row can still kill this. Money up with recall down is a ranker sneaking in the back door, and the corpus holds at least one card where he wants an entry with no retest visible (`ACHR_2025-06-27`, graded **S**). Run `research/t61_onwatch_ab.py` on `RETEST_REQUIRED` over the graded day-cards before the default flips.

**Explicitly not the pass bar: $397/day.** One gate will not carry $28 to $397. This week's honest question is "did the engine stop taking the trades he says are not trades, without going blind".

---

## 3. THE LANE CALL

**Yes — fire only QQQ/SPY/IWM, and keep scanning all 29 for data.** The reason is g91's measurement, not the mentor ballot, and the prop-firm premise underneath the question does not hold as stated.

**What it buys** (honest close fill, one trade a day, 1R = $1,000):
- **2.3 candidates/day → 1.8 with the retest gate** — inside his 1–3 target. Nothing else gets there; the full pool with both gates is still 11.2/day.
- **$51/day alone, $74/day with #1, $78/day with the 84% re-entry appended**, against $28.
- **16/25 green months** against 11/25 — the durability number CLAUDE.md gates on.
- **Max drawdown $19,405 → $13,353** (−31%) — the only number a funded account is judged on.
- **Funded pay $6.59/day → $13.86–$14.66/day** at the largest 1R fitting a $2,500 trailing drawdown ($187 vs the full pool's $98).
- His S-rate is **38.1% on QQQ/SPY/IWM (83 of 218)** vs **27.8% baseline (347 of 1,246)**.

**What it costs, plainly:**
- **98 of 500 days have no index candidate at all.** The lane trades 402 days, not 500.
- It forfeits the equities headroom — best-of-day is **$2,317/day on the 15 equity names** vs **$437/day** on the three index names. If the eventual answer is a *ranker* on equities, this throws away most of the ceiling. THE LANE says classifier, so that ceiling is not the plan — but name the cost.
- The S-rate confound is **unresolved**: `build_deck` selected the cards he was shown. 38.1% vs 27.8% is a hint about the deck as much as about the market.
- **`QQQ` alone is −$66/day** and SPY+QQQ is $43/day. The lane is the *three*, not "the index".

**The prop-firm fork, honestly.** The mainstream firms — Topstep, Apex, MyFundedFutures, TakeProfit — are **futures desks** (ES/NQ/RTY/CL/GC). **They do not fund equity-options traders.** "We need to do prop firms" and "those stocks, lots of options" are two lanes wearing one sentence.

- **Fork A — futures prop.** The instrument is NQ/ES/RTY; QQQ/SPY/IWM is the *research proxy*, not the trade. Everything downstream of `options_sizer.py` becomes wrong: contract selection, the 1R = $1,000 skin, `DEFAULT_RR`. The objective changes too — a trailing max drawdown scores the **path**, and most firms void a payout if one day exceeds 20–30% of total profit, which the "best setup of the day" oracle arm would fail outright.
- **Fork B — his own options account.** The full pool stays available and 1R = $1,000 stays honest. The index lane is still the better book here, but as a preference, not a constraint.

**Narrowing the fired universe is correct under both forks** — under A it is the instrument, under B it is the measured better book. Nothing else about prop firms needs deciding this week.

**What is premature:**
1. **Choosing a firm, an account size, or a payout plan.** No number here is a funded-account number; `max_r_for_dd` is sizing arithmetic, not a cleared evaluation.
2. **Converting these dollars to a funded target.** At the index lane's $187 max 1R, **$397/day requires 2.12R/day sustained**; the measured arm is **0.078R/day** — **27× away**. $397/day is an own-account number. Never present the funded column and the $397 bar in one sentence again without that ratio attached.
3. **Rewriting `options_sizer.py` for futures.** Fork A is not chosen, and the sizer is provably a no-op on realized P&L today.
4. **Flipping the live default.** Ship #1 first and re-measure; a lane cut and a detection change in the same run cannot be attributed.

---

## 4. WHAT THE MARKS CANNOT SETTLE

Ranked by how much an answer unblocks. Every one is answered by **marking a chart**. None asks him to restate a rule he has already given.

**1. "Circle the retest. If there wasn't one, write NONE."** 12 cards where `downgrade.no_retest` tripped and the engine fired anyway, plus 6 where it did not, shuffled. → **Directly gates §2.** The whole ONE CHANGE rests on 3 clean cards (`HOOD_2025-12-23`, `TSLA_2025-03-25`, `QQQ_2024-08-23`, post-verdict *hint*) plus one ballot line. If his eye says those rows did retest, `no_retest` is mis-implemented and the money lift is an artefact.

**2. "Mark the candle you would have entered on."** 12–15 cards, engine entry candle in one colour, **nothing else marked**. He clicks a candle. → Today all we have is a signed gap that does not survive its own denominator: `entry_timing` c1 is **OVERSOLD** (7/7 verifies, but the honest denominator is 85 rows, not 34, and in the omitted pool 9 are earlier and 9 later), and c5's "the engine is never early" is **REFUTED** by `ACHR_2025-06-27` — engine 09:39, graded **S**, S entry at 10:00. We do not know which direction to move the entry, let alone how far.

**3. "Which of these eight is displaced?"** Four cards with a **big body that stays inside** the prior cluster; four with a **small body that separates cleanly**. Yes/no, no notes. → The only way the dropped displacement swap comes back. **The last probe was not broken** — `Displacement` c1 is **REFUTED**: `g82_master_homework.py::pick_displacement` draws from `DISP_BUCKETS` = tiny(2)/boundary(3)/clear(1)/big(2), so 3 of 8 charts had separation ≥ 1.25 ATR and contrast cases *were* shown. His 8 "no"s are deliberate presses rejecting charts the metric scored as displaced — **a finding about the metric.** What was missing is the definition: `COIN_2026-07-24`, "these past 8 make me anxious **you cant remember what it means**". Commit his definition to the card, then re-serve.

**4. "You were stopped out here. Take the 84% re-entry, or done for the day?"** 10 charts of the `AVGO_2025-03-28` shape. Take/skip. → Unblocks #7 and tells us whether "62 refusals per 100 days" counts the wrong object. His arming condition is on record (`SOFI_2025-11-21`) and is not coded.

**5. "The engine can be honest or it can be early — pick."** Two charts of the same trade: entry at the signal bar's close (**$33/day**, shipped) and a limit resting strictly after the signal bar (**$275/day**, 27% win, 15/25 green). Which fill would he actually get? Frame as two marked charts, never as a question about look-ahead. **Do not quote $469/day** — g88 killed it.

**6. "Where does the runner come off?"** Six charts with the 2R price as one line and the nearest real level (PDH/PMH/whole dollar) as another — sometimes inside 2R, sometimes beyond. He marks the exit. → Unblocks #5's policy and #6's consumer.

**7. "Same setup, two days: which would you take?"** `AMZN_2025-11-21` (his "range chop day of hell") against a trend day of the same shape. → Whether displacement needs a day-regime term; `downgrade.py:188 no_displacement` is a flat boolean reading no day state. **Note:** the draft's partner card `t1_AMZN_2025-08-22` is **CARD_NOT_FOUND** in the corpus files of record (it lives in `research/marks/probe_omen_test1_2026-08-27.jsonl`). Use an in-corpus partner.

**8. "You marked these seven take. The engine would not fire on any of them."** The 7 A-naming cards among the 22 `take==yes` rows. Keep/drop per card. → The scope question. `a_vs_s_boundary` c6 is **OVERSOLD** and the corpus reads the other way, so this is a decision only he can make.

**9. "Two stops are drawn. Circle one, or write NO TRADE."** Start with `META_2024-09-30` ("not respecting level, 2 stop losses to choose from"), then 15 from `g82_master_homework.py:706–725 stop_candidates()`'s all-four-disagree filter. → **Not worth his time until deck bug #2 lands**: on the last stop-pick section **5 of 6 notes voice entry/setup doubt** and both `none` answers read as entry refusals, so the section measured the deck.

---

## 5. NEXT DECK BUILD LIST

| # | Bug | Location | Fix | Evidence |
|---|---|---|---|---|
| 1 | **`deep_is_s` has no structured `why_not`.** 25 of 25 refusals in the file's largest refusal pool carry zero coded reasons. | `research/g84_one_page.py`: the `why_not` block is emitted only at ~863 (`is_this_an_s`) and ~1074 (`take_the_trade`); the `deep_is_s` builder (~1110) has none. | Add `question("why_not", …)` with `hb.NO_REASONS` to `render_deep`. | `veto_vocabulary` c10, **OVERSOLD** — instrument fact confirmed in source, but "all reasoning lives in free text" is false for **9 of 25**, which are a bare "no" with empty `notes.entry`: `META_2026-08-06`, `AVGO_2025-06-04`, `INTC_2025-01-29`, `QQQ_2024-11-08`, `MSFT_2025-06-13`, `HOOD_2024-10-23`, `AAPL_2026-01-06`, `COIN_2026-03-09`, `CRM_2025-08-28`. **36% has no reasoning in any form.** |
| 2 | **`stop_pick` has no quality pre-filter.** He had to editorialise that the trade was bad before answering. | `where_is_the_stop` card builder | Pre-filter to cards grading ≥ A; add an explicit **"bad setup, skip"** button so a refusal records as a refusal. | `process` c8, **HOLDS** — understated: **4 of 6** rows editorialise (`MU_2024-10-09` "i dont see a OCR or the level its referencing", `NFLX_2025-07-28` "not an entry too late in the day", `BABA_2025-11-21` "this is a low grade trade in case you didnt know", `SOFI_2025-11-07`). |
| 3 | **Entry, stop, level and OCR are not drawn on the cards.** | `trade_anatomy` / `where_is_the_stop` builders | Draw entry and stop as marked lines, render the level and the OCR candle, zoom the entry candle. Static SVG per the homework contract. | `process` c6, **HOLDS**: `QQQ_2024-08-26` "cant critique entry and stop because cant see"; `MU_2024-10-09`; `ORCL_2025-04-02`. Undercounted — `SPCX_2026-08-03` is a fourth. |
| 4 | **Cards assert facts he can see are wrong.** | card context strip | Show the source of any asserted market fact, or drop it. | `SPCX_2026-08-03`: "indices were in a major downtrend, **but that doesn't make sense**." He is disputing the card, not the chart. |
| 5 | **Term definitions are not on the card.** 8 cards served a word we never wrote down for him. | probe page shell | Put his committed definition in the section header: displacement is a candle that "displaced and closed into the levels at 9:45", separating from the immediately preceding cluster (`COIN_2026-07-24`). Commit it; do not re-derive. | `Displacement` c1 **REFUTED** (sampler was fine — `DISP_BUCKETS` filled all four buckets); `process` c7 **OVERSOLD**. The bug is the missing definition, not the deck. |
| 6 | **Checkbox wording collapses two answers into one.** "level not respected — closing on it / chopping on it" makes chop and level_not_respected near-synonyms on the page. | `research/g71_homework_build.py:222`, `research/g75_deck2_build.py:154` | Split into disjoint wording, or drop one. | `veto_vocabulary` c2, **HOLDS** (8 of 9 co-occur; exception `CRM_2026-04-15`). `downgrade.py:243`'s docstring already merges them. **The 8/9 co-occurrence cannot be interpreted until this is fixed.** |
| 7 | **Build the ON WATCH deck he volunteered.** | new | `TSM_2026-07-24`: "9:40 as candle forming — **for on watch if we need help with that**." Unprompted offer, at exactly the point where the intrabar-fill defect lives. Take it. | Offered once; the scarcest resource in the project volunteering at the site of the biggest known bug. |
| 8 | **No before/after diff harness for level computation.** `regression_gate.py` gates detections, not level values. | new | Dump PDH/PDL/PMH/PML across a fixed day sample; diff before vs after. Required before any level-code edit. | Process gap, not a mark. |

---

## 6. CONTRADICTIONS

**1. The engine enters on the break — and the engine is late.**
- `PLTR_2024-09-20`: *"you seem to enter on breaks which is a halucination we never trade that and you know it."*
- `rule_03` (ballot **yes**): *"engine entering late is a bug, should always be entering while the restest is occuring."*

Both cannot describe the same code. `omen_bot.py:615–724`'s FSM (`seek_break → seek_leave → seek_retest → confirm`) makes break index and entry index different **by construction**. **Adjudication: the symptom is real, the mechanism is misnamed.** He is seeing the *confirm gap* plus a close-only fill, not break-candle anchoring — and the sentence reconciling every card is: **the break bar and the retest bar must be different bars, and the fill happens intrabar on the retest bar.** Do not build `reject_entry_if entry_bar == break_bar`; it is already true. `process` c1 is **OVERSOLD** (3 clean cards) and its fix is **REFUTED in direction** by `rule_03` and 13 cards asking for an earlier entry.

**2. Displacement is required — and displacement is not required.**
- `rule_03`: *"just always need that displacement for S trades."*
- `NVDA_2025-06-03`, graded **S**: *"9:46 as candle forming above ORH, no displacement but 9:30 ocr wick confluence with pmh."*
- `PLTR_2025-07-17`, graded **S**: *"10:04 no displacement but holding ocr."*
- `SPY_2025-07-16`: *"could be considered as an S 9:43 even though no displacement because its early and there could be HTF bias."*

Three axes gave three answers off the same ~20 cards (`Displacement` c6 **OVERSOLD**, `WHAT MAKES AN S` c7 **OVERSOLD**, `a_vs_s_boundary` c1 **OVERSOLD**). **Adjudication: displacement is one member of a substitutable confluence set — {displacement, OCR hold, wick reclaim of the level, strong PA, early + HTF bias}. S if ≥1 member present and no veto; A if none present and no veto; refused when a *second* defect co-fires** (`MU_2026-03-18` + pivot-not-level, `HOOD_2024-11-15` + chop + level, `ACHR_2026-06-30`, `AMD_2025-12-23`). The live engine states neither — `signal_runner.py:1759–1767` caps to **C**, skipping A, with `BNR_DISPLACEMENT_GATE` defaulting **ON**. → #4.

**3. Pivots are not levels — and pivots are levels.**
- `MU_2026-03-18`, refused: *"almost opportunity but i didnt like the Br of pivot not levels and no displacement."*
- `IWM_2026-05-12`, graded **S**: *"that entry candle wicked back into the pivot structure."*
- `rule_08` (ballot **skip**, counter-proposal): major levels and *"pivot structures at 1h and 4h for scaling targets."*

**Adjudication: a pivot is legitimate as a target and as HTF structure, and he rejects it as the *break reference*.** Nobody checked this — `bt2y_trades.json`'s largest reason bucket is pivot-referenced break-and-retest. Measured: his named levels only is **−$17/day against $28**; the not-his levels carry **+$82/day**. Real mark, uncovered by any axis; as a fire gate it is amputation. Unresolved, not shipped.

**4. Two stops in one plan, and each axis saw one.**
- `MSFT_2026-08-10`: *"this and last one have been stop below the candle entered on."*
- `QQQ_2024-08-23`: *"stop either BE, and/or stop held … stopping rest BE."*
- `NVDA_2024-09-03`: *"a little farther up stop wouldve allowed you to stay in trade."*

`stop` c2 ("always structural, never a bare price/fixed distance") is **OVERSOLD** — and its denominator was wrong (claimed 2 of 6 `where_is_the_stop` cards; only 1 is in that section). **Adjudication: the initial stop is structural** — "below the candle entered on", "the upper body of the opening range candle" (`IWM_2026-05-05`), "stop body of opening range" (`GOOGL_2024-10-15`) — **and the post-first-target stop is breakeven, anchored to entry.** Nobody modelled the transition, which is what all three "be" complaints are about (`exit` c7, **OVERSOLD**, and an entry finding, not an exit one: BE fires off the entry price).

**5. "I don't like bodies" — and the stop goes at the body.**
- `NVDA_2024-09-03`: *"those 3 green candles even though i dont like bodies that wouldve been a better stop."*
- `IWM_2026-05-05`: *"the stop which woudlve been at the upper body of the opening range candle."*
- `GOOGL_2024-10-15`: *"9:43 OCR stop body of opening range OCR."*

`stop` c4 is **REFUTED**: it asserted the body-anchored routine lives outside the assigned files. It is inside them twice, and `MARA_2026-06-16` bears on it (*"its above all the bodies and is in the territory of the Wicks"*). Shipped code is not in tension either way — every `placed_stop` mode (`signal_runner.py:1536–1568`) uses `candle.low`/`candle.high`, never open or close. Unresolved: which anchor he wants. → §4 q9.

**6. Late is a veto — and late is a downgrade.**
- `BABA_2025-03-14`, accepted at **10:40**: *"late in day."*
- `UBER_2026-08-11`, refused: *"10:34 **c trade** because its been too long."*
- `META_2025-05-16`: *"A opportunity 10:30."*

`veto_vocabulary` c9 is **REFUTED**: it claimed every late-tagged refusal sits at 10:34 or after. Exactly 4 cards carry `late` in `why_not`; **three have no time anywhere**, and the one that does reads **10:30** — below the asserted floor. Structurally every g84 row has `et = None`, so every clock time in that claim was scraped from prose. **Adjudication: late is never a veto in his prose. It is a downgrade unit that walks S → A → C with the clock, and it produced a refusal only once it reached C.** The "10:40 latest accepted" half holds.

**7. Chop is his most-used refusal — and chop is not a veto.**
- `CRM_2025-10-09`, chop checked, graded **yes**: *"so maybe downgrade but i do see the s your getting at."*
- `AMD_2025-07-09`, accepted: *"10:05 S option in my opinion but a lot of chop."*
- `MU_2026-03-18`, refused with `why_not = ['chop']` — but his text blames *"the Br of pivot not levels and no displacement"*.

15 of 22 coded refusals check chop (`veto_vocabulary` c1 **OVERSOLD** → *strong*; over all 47 refusals it is 32%, not 68%). **Five accepted cards describe chop** (`CRM_2025-10-09`, `AMD_2025-07-09`, `SOFI_2025-11-21`, `AAPL_2024-10-23`, `PLTR_2026-02-05`), the checkbox absorbs non-chop failures (`MU_2026-03-18`), and the wired analogue measures **−$58/day, 7/25 green**. Chop and `level_not_respected` are **one variable presented as two checkboxes** — his own name is `rule_02`'s *"copping on levels"*, and `downgrade.py:243`'s docstring already says so. Deck bug #6 first.

**8. Retest tolerance: "a few cents give or take" — and zero.**
- `rule_01` (ballot **yes**): *"it doesn't follow the 25 percent candle unit, its just if its close but didnt actually touch, within a few cents give or take"* … *"you stress test and find the best metric yourself."*
- `research/g87_retest_tol.py`: the best tolerance is **zero**. Shipped default `OMEN_RETEST_TOL_FRAC=0.0` (`signal_runner.py:1290`, `DETECT_WIDE=False` at 409).

**Resolved on detection in favour of zero; not resolved on execution.** Do not present the zero result as confirming his words — `process` c2 is **OVERSOLD** for exactly that, and his sentence describes a strictly *nonzero* tolerance for a level he says was never touched. The delegation half stands. **Do not quote $469/day**: g88 killed it (89.6% of those fills landed before the signal bar). The honest pair is **$33/day** shipped and **$275/day** for the strictly-after-signal limit.

**9. Bookkeeping corrections — published wrong, not contradictions.**
- The mentor-ballot census is **9 yes / 6 skip**, not 10/5 (**REFUTED**): yes on 1, 2, 3, 5, 6, 7, 9, 12, 14; skip on 4, 8, 10, 11, 13, 15. The per-rule lists were right; the summary integers were not, and the draft's headline repeated the error.
- **"failed three implementations"** is **not** in `research/downgrade.py` in any form — it is the ballot page's own blurb from `g82_master_homework.py`, re-attributed to engine source. Strike it wherever quoted.
- **`ENABLE_CHASE_DOWNGRADE = True`** (`downgrade.py:153`) — chase is **ratified and ON**, unlike `large_counter_body` / `multi_level_confluence` / `sequence_gate` (all False). It must not be cited as precedent for adding an unratified variable, and it is why #2 is a flag, not a feature.
- **Prior scale-IN work exists**: `research/w13_scaling.py:208 scale_in_leg()`, called at 315 and 549. `rule_14`'s claim that it does not is **OVERSOLD** and would have got the wheel reinvented.
- **`_confirm_candle`** (`signal_runner.py:82`) tests lower wick ≥ body and a close in the upper half of range. It **never tests whether the body respects the level**, which is the half of rule_09 his note is about, and at two of its four call sites it is a **+2 scoring term, not a gate**. Rule 9 is not "already shipped" — and `rule_09` grants permission for new code: *"if neto has an explanation of good bullish candles for cleaner code, then use it."*

---

## Appendix — open instructions and questions from him, filed nowhere

| card | his words | what it actually is |
|---|---|---|
| `rule_07` (ballot **yes**) | "all of this alligns with me, **but how would we shape it into day trading?**" | An open request for a proposal on weekly/daily/4H trend — booked as a ratified rule. |
| `AMZN_2025-10-07` | "these are ones **we got to figure out if odds in out favor** to delegate as S trades" | An explicit assignment to measure no-displacement early entries. |
| `MARA_2025-10-01` | "**you wanted 10:28 entry i bet** but hod is a consolidation wall and too hard to target" | He models the engine and pre-labels a false positive **with its cause** — precision training data. |
| `rule_05` (ballot **yes**) | "**you said easy to measure**, but i dont want it to mess up my main levels" | A constraint on an experiment, on a row recorded **yes**. `process` c9 is **OVERSOLD** for reading it as rejection. |
| `NFLX_2025-05-07` (**S**) | "two candle distraction at 9:33-34 but **those break rejection patterns like that are forgivable**" | He names a shipped variable — `downgrade.break_then_rejection` (:284, `REJECT_BARS = 2`) — and gives its tolerance. No axis touched it. |
| `MARA_2026-06-16` (only `htf: agrees` card) | "it was at a **sweet spot** … **above all the bodies and is in the territory of the Wicks**" | A testable definition of a good HTF starting condition. Zero coverage. |
| `QQQ_2024-08-26` / `QQQ_2025-02-25` | "if we know our mean RR is 2.5" … "average in the **higher quartile** of trades. **3-4r?**" | His stated RR distribution, against CLAUDE.md's mean-R = 2.0 gate and `options_sizer.py:37 DEFAULT_RR = 2.5`. |
| `TSM_2026-04-21` (**S**) | "10:03 **hod scalp**" | A second trade type. A scalp cannot carry a multi-leg ladder. |
| `NVDA_2025-11-21` | "**double fakeout**" | A named pattern, zero coverage. |
| `IWM_2026-05-12` (S) vs `MSFT_2026-01-05` (refused) | "bear flag to start the day" vs "higher highs in range **after bear flag** to start day" | The same phrase to opposite verdicts. That pair separates a variable from a slogan; no axis paired them. |