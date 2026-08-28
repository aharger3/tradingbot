# X8 — strategy filters and time blocks on the 2-year book

**Question (Austin):** *"2yr backtest need strategy filters, time blocks to see if 9:30–9:45
outperforms."*

**Answer in one line:** it does — **09:30–09:45 runs +1.1619R at 60.7% win against the book's
+0.9551R at 53.2%**, and it is the **only** 15-minute block that beats its own baseline in
*both* halves of the two years — but the edge (+0.2749R) sits **inside its own ±0.3232R
sampling bar**, and buying it costs **765 of 1017 trades**, 37 trades surrendered per +0.01R
of mean.

Script: `research/x8_time_blocks.py` (run it for the full 360-line dump).
Substrate: `research/g3_arm_ow1.json`, 2024-08-21…2026-08-21, 500 sessions, 28 symbols,
45,193 signals, 1,017 traded. Repo HEAD at measurement: `c089b26b`.

---

## 0. Conventions, and one correction to the brief

| thing | what I used | why |
|---|---|---|
| win rate | wins / (wins + losses) | matches the standing 53.2%; the 5 scratches are out of the denominator |
| months green | months with sum(R) > 0, out of the months the slice actually occupies | a 92-trade slice does not get 25 months for free |
| slice CI | 1.96·sd/√n on the mean | n < 30 printed but not read as evidence |
| **judging bar** | **Welch 95% CI on (slice − complement)** | the ±0.0095R house bar comes from an A/B where both arms share nearly every trade. A **disjoint** slice has a far wider sampling bar. ±0.0095R is a *floor* on what counts as signal, not the bar a slice has to clear. Every slice below reports both. |
| survival | beats **its own half's** baseline in both halves, n ≥ 15 each | H1 is +0.8382R and H2 is +1.0364R. Judging H1 slices against the pooled +0.9551R would fail them for free. |

**Two required slices are look-ahead and cannot be filters.** `scaled` is *"the trade reached
the scale-out"* — i.e. it won: `scaled=True` is n=538 at **+2.6690R and 100.0% win**, `False`
is **−0.9698R and 0.0%**. `bars held` is trade duration, known only at exit. Both are reported
as **descriptive only** and are excluded from every arm. They are the reason a naive
"AND the survivors" pass produced a fantasy book; that pass is not in the final script.

Baseline reproduced: **n=1017, +0.9551R, 53.2% win, 23/25 months green, +971.4R total,
sd 2.3200.** H1 (417 trades) +0.8382R · H2 (600 trades) +1.0364R.

---

## 1. Time blocks — the direct answer

### 15-minute blocks

| block | n | mean R | 95% CI | win% | mgreen | Δ vs rest | clears own bar? |
|---|---:|---:|---:|---:|---:|---:|---|
| **09:30–09:45** | 252 | **+1.1619** | ±0.2773 | **60.7%** | 23/25 | +0.2749 ±0.3232 | **no** |
| 09:45–10:00 | 312 | +0.9840 | ±0.2504 | 58.7% | 24/25 | +0.0416 ±0.3046 | no |
| 10:00–10:15 | 195 | +0.9759 | ±0.3532 | 49.2% | 22/25 | +0.0257 ±0.3859 | no |
| 10:15–10:30 | 118 | +0.8407 | ±0.4212 | 44.8% | 18/25 | −0.1295 ±0.4477 | no |
| 10:30–10:45 | 77 | +0.9458 | ±0.5493 | 45.3% | 15/21 | −0.0101 ±0.5688 | no |
| **10:45–11:00** | 63 | **+0.1466** | ±0.4844 | **32.3%** | 9/23 | **−0.8619 ±0.5065** | **YES (negative)** |

The mean-R ranking is not monotone and mostly noise. **The win-rate ranking is monotone and
is not**: 60.7 → 58.7 → 49.2 → 44.8 → 45.3 → 32.3. The first half hour wins; the last quarter
hour is where the book bleeds.

### 5-minute blocks, first half hour (there is no 09:30–09:35 trade — earliest entry in the book is 09:35)

| block | n | mean R | win% | Δ vs rest | clears own bar? |
|---|---:|---:|---:|---:|---|
| 09:35–09:40 | 93 | +1.1900 | 64.5% | +0.2585 ±0.4916 | no |
| 09:40–09:45 | 159 | +1.1455 | 58.5% | +0.2256 ±0.3787 | no |
| 09:45–09:50 | 141 | +0.9207 | 57.4% | −0.0400 ±0.3686 | no |
| 09:50–09:55 | 109 | +1.2009 | 66.1% | +0.2752 ±0.4217 | no |
| 09:55–10:00 | 62 | +0.7467 | 48.4% | −0.2220 ±0.7470 | no |

At 5-minute resolution the ordering breaks (09:50–09:55 outranks 09:45–09:50 and nearly
outranks 09:35–09:40). **Nothing at 5-minute resolution is measurable on 1,017 trades.**
Do not tune a 5-minute gate on this book.

### Chronological-half stability, every block, significant or not

| block | n | mean R | H1 n / mean R | H2 n / mean R | beats own half's baseline in both? |
|---|---:|---:|---:|---:|---|
| **09:30–09:45** | 252 | +1.1619 | 102 / **+1.1765** | 150 / **+1.1520** | **YES** |
| 09:45–10:00 | 312 | +0.9840 | 123 / +0.6640 | 189 / +1.1923 | no |
| 10:00–10:15 | 195 | +0.9759 | 84 / +1.0960 | 111 / +0.8850 | no |
| 10:15–10:30 | 118 | +0.8407 | 49 / +0.8560 | 69 / +0.8298 | no |
| 10:30–10:45 | 77 | +0.9458 | 35 / +0.5235 | 42 / +1.2978 | no |
| 10:45–11:00 | 63 | +0.1466 | 24 / −0.1855 | 39 / +0.3510 | no (negative in both) |
| 5m 09:35–09:40 | 93 | +1.1900 | 38 / +1.6331 | 55 / +0.8839 | no |
| **5m 09:40–09:45** | 159 | +1.1455 | 64 / +0.9053 | 95 / +1.3072 | **YES** |
| 5m 09:45–09:50 | 141 | +0.9207 | 51 / +0.8164 | 90 / +0.9799 | no |
| 5m 09:50–09:55 | 109 | +1.2009 | 50 / +0.6864 | 59 / +1.6369 | no |
| 5m 09:55–10:00 | 62 | +0.7467 | 22 / +0.2597 | 40 / +1.0146 | no |

**09:30–09:45 is the most stable slice in the whole study: +1.1765 in year one, +1.1520 in
year two — a 0.024R gap across two years.** That stability, not the size of the edge, is the
reason to believe it. Every other block moves by 0.2R–0.8R between halves.

---

## 2. Arrival order (`seq`) — the requested slice cannot be measured, and here is what can

First, a correction to the brief's framing: **`seq` is arrival order within a
(symbol, day) pair, not within the calendar day.** The book takes up to **8** trades on one
calendar day, one per symbol.

Traded-book histogram: **`{1: 1005, 2: 12}`**. There is no `seq >= 3` row at all. **98.8% of
the book is seq==1**, exactly as `g4_dropped_s.md` §6 predicted — the selector *is*
"first with-trend signal of the symbol-day", so inside the book `seq` is a constant. Its edge
is unmeasurable there by construction (seq==2, n=12, +1.4527R ±1.2904 — noise).

So it has to be measured on the population the selector chose **from**. The 42,375 resolved
non-traded rows split into 41,136 legacy-**X** rows and 1,238 legacy-**C** rows. **The X rows
are not comparable and are excluded**: their stop was never gated by the tight-stop filter
(min `stop_pct` 0.000% against 0.092% in the book), so R runs to **67,169**. Any number that
pools them is garbage.

On the **grade-C candidate pool** — the pool `_calibration_grade` actually picks from:

| seq | n | mean R | 95% CI | win% |
|---|---:|---:|---:|---:|
| 1 | 457 | **+0.6170** | ±0.2537 | 35.1% |
| 2 | 303 | +0.8028 | ±0.3220 | 38.7% |
| 3 | 161 | +0.8824 | ±0.5534 | 32.1% |
| 4+ | 317 | **+1.1639** | ±0.4350 | 35.0% |

**seq 4+ minus seq 1 = +0.5469R ±0.5036 — significant, and it points the wrong way.** The
first signal of the symbol-day is the *worst* bucket in the pool the engine picks it out of.
The same shape holds on the S-graded slice of that pool (seq 1 +1.1645, seq 4+ +3.0475, both
too thin to call).

**This is the finding of the lane that is not about time.** The engine's entry rule is
arrival order, arrival order carries a *negative* measured edge in the pool it selects from,
and the book is nonetheless +0.955R — which means the book's performance is coming from the
other gates, not from being first. G14 is pointed at the right lever.

Caveat, stated plainly: the C pool's rows never actually traded, so survivorship in the
opposite direction is possible (a later signal exists only on days the earlier one behaved a
certain way). This is a **motivating** number for G14, not a licence to flip the selector.

---

## 3. Everything else, ranked, with the bar applied

Only **9 of the ~90 ex-ante slices** clear their own Welch bar. Ranked by mean R:

| slice | n | mean R | 95% CI | win% | mgreen | Δ vs rest | verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| first 15min × long | 136 | +1.4224 | ±0.4003 | 65.4% | 22/24 | +0.5394 ±0.4283 | SURVIVES |
| S-grade × first 30min | 67 | +1.4509 | ±0.4649 | 76.1% | 21/25 | +0.5307 ±0.4882 | SURVIVES (thin) |
| first 15min × big-range day | 170 | +1.3989 | ±0.3701 | 61.8% | 21/25 | +0.5329 ±0.4007 | SURVIVES |
| first 30min × big gap | 298 | +1.3683 | — | 62.3% | — | — | SURVIVES |
| first 15min × confluence yes | 127 | +1.3284 | ±0.3883 | 64.6% | 22/25 | +0.4265 ±0.4173 | SURVIVES |
| first 30min × big-range day | 384 | +1.2648 | — | 60.2% | — | — | SURVIVES |
| with-trend × first 15min | 231 | +1.2358 | ±0.2926 | 62.3% | 24/25 | +0.3632 ±0.3349 | SURVIVES |
| **rangeb = big range** | **704** | **+1.2142** | ±0.1851 | 55.2% | 23/25 | **+0.8417 ±0.2642** | **SURVIVES** |
| **gapb = big gap** | **552** | **+1.2047** | ±0.2139 | 54.6% | 23/25 | **+0.5457 ±0.2780** | **SURVIVES** |
| first 30min × confluence yes | 330 | +1.2035 | ±0.2477 | 63.0% | 22/25 | +0.3676 ±0.3026 | SURVIVES |
| with-trend × first 30min | 525 | +1.0952 | ±0.1948 | 60.0% | 24/25 | +0.2895 ±0.2852 | SURVIVES |
| month = Jul | 92 | +1.5523 | ±0.4999 | 68.1% | 2/2 | +0.6566 ±0.5214 | survives, but **calendar cherry-pick — not a filter** |
| symbol = HOOD | 75 | +1.8421 | ±0.6891 | 61.3% | 18/22 | +0.9576 ±0.7037 | survives, but **name cherry-pick — DIRECTION says <20-trade symbols are noise and 75 is barely above it** |

**Negative in both halves — the real exclude-candidates:**

| slice | n | mean R | H1 | H2 |
|---|---:|---:|---:|---:|
| 10:45–11:00 | 63 | +0.1466 | −0.1855 | +0.3510 |
| gapb = small gap | 326 | +0.6969 | +0.7729 | +0.6361 |
| gapb = flat | 139 | +0.5698 | +0.2999 | +0.7466 |
| rangeb = normal | 288 | +0.4207 | +0.3546 | +0.4736 |
| month = Sep | 55 | +0.0788 | +0.2715 | −0.0939 |

**Died on the half split** (worked in one year, not the other): `level = other`,
`setup = break_and_retest`, `setup = one_candle_rule`. Note that OCR looked like a clean
−0.5500R ±0.4516 exclude on the pooled book and is **not** one: +0.8736R in H1 against
+0.1841R in H2. This is exactly the trap the half split exists to catch.

**Did not clear the bar at all** — every one of these is noise on 1,017 trades and must not be
turned into a rule: side (L +1.0691 vs S +0.8423, Δ+0.2268 ±0.2850), `sgrade` (S +1.2829 vs
C +0.8735, Δ+0.3750 ±0.3893 — Austin's own ladder does **not** separate on money at this n),
`stopb`, `vol_regime`, `spy_trend`, `aligned`, `bias`, `confluence` alone, `level` (all nine),
day of week (Wed +1.2272 / Thu +0.6962 — Δ+0.3375 ±0.4104, do not build a Wednesday rule),
every tag, and 27 of 28 symbols.

**Look-ahead, descriptive only, never a filter:** `bars held` 1–2 bars +0.0744 / 21+ bars
+2.1121; `scaled` True +2.6690 at 100% win / False −0.9698 at 0%. On Austin's *"the trades be
quicker"*: **the duration table says the opposite** — the longest-held quartile is the best.
But it says nothing causal, because a trade is only still open at bar 21 *because* it has not
stopped out. The honest read is that **the fast trades are the losers, not that being fast
causes loss.** Nothing here supports a time-based exit.

---

## 4. The arms, priced

Ex-ante filters only. `A*` are pure time cuts. `B*` stack conditions on the first 30 minutes.
`C*` keep the whole session and only drop slices negative in **both** halves.

| arm | n | mean R | win% | mgreen | total R | ΔN | H1 mean R | H2 mean R | money gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **A0 incumbent** | **1017** | **+0.9551** | **53.2%** | **23/25** | **+971.4** | 0 | +0.8382 | +1.0364 | FAIL both |
| A1 drop 10:45–11:00 | 954 | +1.0085 | 54.5% | **24/25** | +962.1 | −63 | +0.9007 | +1.0840 | FAIL both |
| A2 first 45 min | 759 | +1.0410 | 56.9% | **24/25** | +790.1 | −258 | +0.9506 | +1.1031 | win ok, R short 0.959 |
| A3 first 30 min | 564 | +1.0635 | 59.6% | **24/25** | +599.8 | −453 | +0.8963 | +1.1745 | win ok, R short 0.937 |
| A4 first 15 min | 252 | +1.1619 | 60.7% | 23/25 | +292.8 | −765 | +1.1765 | +1.1520 | win ok, R short 0.838 |
| B1 A3 + with-trend | 525 | +1.0952 | 60.0% | **24/25** | +575.0 | −492 | +0.9972 | +1.1570 | win ok, R short 0.905 |
| B2 B1 + big-range day | 362 | +1.2863 | 60.2% | 23/25 | +465.6 | −655 | +1.1422 | +1.3739 | win ok, R short 0.714 |
| B3 B2 + not a flat gap | 325 | +1.3401 | 60.0% | 22/25 | +435.5 | −692 | +1.1985 | +1.4274 | win ok, R short 0.660 |
| B4 B3 + confluence yes | 190 | +1.4811 | 63.7% | 21/24 | +281.4 | −827 | +1.1146 | +1.7150 | win ok, R short 0.519 |
| B5 B4 + sgrade S or A | 112 | +1.5663 | 67.9% | 18/21 | +175.4 | −905 | +1.3584 | +1.7113 | win ok, R short 0.434 |
| C1 drop dead slices only | 880 | +1.0515 | 55.0% | 23/25 | +925.3 | −137 | +0.9162 | +1.1460 | FAIL both |
| C2 C1 + drop normal-range | 636 | +1.2761 | 56.2% | 23/25 | +811.6 | −381 | +1.1462 | +1.3609 | win ok, R short 0.724 |
| C3 C2 + drop flat gaps | 576 | +1.2891 | 56.0% | 23/25 | +742.5 | −441 | +1.1813 | +1.3602 | win ok, R short 0.711 |

### The price, stated the way Austin asked for it

| arm | trades given up | mean R bought | **trades surrendered per +0.01R** | total R lost |
|---|---:|---:|---:|---:|
| A1 drop 10:45–11:00 | 63 | +0.0534 | **11.8** | −9.2 |
| C2 drop dead + normal-range | 381 | +0.3210 | **11.9** | −159.7 |
| C3 C2 + drop flat gaps | 441 | +0.3340 | 13.2 | −228.8 |
| C1 drop dead slices only | 137 | +0.0963 | 14.2 | −46.1 |
| B5 the maximum-filter arm | 905 | +0.6112 | 14.8 | −795.9 |
| B4 | 827 | +0.5260 | 15.7 | −690.0 |
| B3 | 692 | +0.3849 | 18.0 | −535.9 |
| B2 | 655 | +0.3311 | 19.8 | −505.8 |
| A2 first 45 min | 258 | +0.0859 | 30.1 | −181.3 |
| B1 | 492 | +0.1401 | 35.1 | −396.4 |
| **A4 first 15 min** | **765** | **+0.2068** | **37.0** | **−678.6** |
| A3 first 30 min | 453 | +0.1084 | 41.8 | −371.6 |

**Three things to read off this table:**

1. **No arm reaches the money gate.** The best possible ex-ante filter combination in this
   study, B5, is **+1.5663R at 67.9%** — the win half of the gate is comfortably passed from
   A2 onward, **but mean R is still 0.434R short of 2.0 while holding only 112 trades**. Every
   filter in this book is a win-rate lever, not an R lever. **You cannot filter your way to
   mean R = 2.0.** That is an exit/target problem, not a selection problem.
2. **The pure time cut Austin asked about is one of the most expensive ways to buy mean R.**
   A4 costs **37.0 trades per +0.01R**, third worst on the board. A1 — just dropping the last
   quarter hour — costs **11.8**, the cheapest, and simultaneously moves durability to
   **24/25 months green** while giving up only **9.2R** of total book.
3. **Every filter destroys total R.** The incumbent's +971.4R is the largest number in the
   table. A1 is the only arm that keeps ~99% of it (+962.1R). This matters because
   1R = $1,000 and Austin trades the whole book, not the mean.

---

## 5. The other direction — Austin wants MORE trades

Filtering is subtraction and every arm above costs him trades. The book's own shadow contains
**1,238 resolved legacy-C signals that were never taken**, at **+0.8370R and 35.6% win**.

| book | n | mean R | win% | mgreen | total R |
|---|---:|---:|---:|---:|---:|
| incumbent | 1017 | +0.9551 | 53.2% | 23/25 | +971.4 |
| **incumbent + all shadow C** | **2255** | **+0.8903** | 43.6% | 23/25 | **+2007.6** |

**+1,238 trades — a 122% larger book — for −0.0648R of mean and +1,036.2R of total.** H1
+0.8329 / H2 +0.9262, so it holds in both halves. Nothing else in this study moves total R
by anything like +1,036R.

**Caveat, and it is a real one: this is an upper bound, not a proposal.** 805 of those 1,238
are `skipped_tight_stop` — the tight-stop gate exists precisely because the fill is not
modelled below it — 377 are `fired` alerts that the trade path declined, and 56 are
`skipped_repeat_entry` competing for the same capital on the same symbol-day. The runnable
subset is smaller and needs its own replay. But the direction is unambiguous and it is the
opposite of every arm in §4.

Excluding the tight-stop rows, by block: 10:30–10:45 is the one expandable block that looks
good (n=102, **+1.0600R**, 38.1% win) — above the incumbent's mean; 09:45–10:00 (n=56,
+0.1132R), 10:15–10:30 (n=99, +0.1279R) and 10:45–11:00 (n=70, +0.2550R) do not.

---

## 6. Held out — the one number here that is not in-sample

The chronological split is out-of-sample *in time* but same-corpus. The genuinely held-out
check comes from the 100 unseen cards in
`research/marks/probe_omen_test1_2026-08-27.jsonl`, using **Austin's own entry block**
(`eblock`, 0 = 09:30–09:45). It takes four distinct values, so it is not a stuck default.

| Austin's grade | n with an entry | in 09:30–09:45 | in the first 30 min | histogram |
|---|---:|---:|---:|---|
| **S** | 15 | **9 (60.0%)** | **14 (93.3%)** | `{0:9, 1:5, 2:1}` |
| A | 27 | 12 (44.4%) | 20 (74.1%) | `{0:12, 1:8, 2:4, 3:3}` |
| C | 16 | 2 (12.5%) | 9 (56.2%) | `{0:2, 1:7, 2:1, 3:6}` |
| none | 42 | — | — | a refusal has no entry |

**60.0% of held-out S days have Austin's own entry inside 09:30–09:45, against 12.5% of C
days; 93.3% of S days are inside the first 30 minutes.** This is a corpus the engine has
never scored, and it independently corroborates the block finding — the first 15 minutes is
where his *best* setups are, and the grade gradient across blocks is steep.

**It does not, however, license a hard time gate.** 1 of the 15 held-out S days (6.7%) sits
in 10:00–10:15, and 6 of 15 (40.0%) sit outside 09:30–09:45. The recall gate is ≥90%: a hard
cut at 10:00 forfeits 6.7% of held-out S recall before the detector even runs, and a cut at
09:45 forfeits 40.0%, against a standing held-out recall of 3-of-15. **No recall gain is
claimed in this report; the held-out number is reported here only because the standing rules
require it beside any in-sample claim.**

---

## 7. What survives, and the one thing to do

**Survives both halves and is a legitimate ex-ante filter:** `rangeb = big range` (704,
+1.2142), `gapb = big gap` (552, +1.2047), `with-trend × first 30 min` (525, +1.0952),
`first 30 min × big range` (384, +1.2648), `first 30 min × big gap` (298, +1.3683), and the
first-15-minute interactions.

**Does not survive:** every 5-minute block, `level`, `setup` (both), `side`, `sgrade` on money,
`stopb`, `vol_regime`, `spy_trend`, `bias`, day of week, every tag. `month = Jul` and
`symbol = HOOD` survive numerically and are cherry-picks — do not ship them.

**Recommended single move — A1: drop the 10:45–11:00 block.** It is the only slice in the
study that is *significantly negative* (−0.8619R ±0.5065), it is negative in both halves, and
removing it costs **63 trades and 9.2R** to buy **+0.0534R of mean, +1.3pp of win rate, and
23/25 → 24/25 months green.** It is the cheapest lever on the board at 11.8 trades per
+0.01R, and it is the only filter here that improves durability without materially shrinking
the book. **It needs Austin**, because it changes what trades and re-freezing the forward
book voids it.

**Do not ship a 09:30–09:45-only gate.** It is the most stable slice in the book and the
held-out marks back it, but it costs 75% of the book to buy +0.207R, it still fails the money
gate by 0.838R, and it would forfeit held-out S recall the project cannot spare.
