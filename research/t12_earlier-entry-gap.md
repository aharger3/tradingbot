# T12 — the earlier-entry gap

Script: `research/t12_earlier_entry_gap.py` (`python research/t12_earlier_entry_gap.py all`).
Engine: the ratified book, `research/bt2y_trades.json` (2,595 traded / 75,953 signals,
2024-08-21 → 2026-08-21), on top of T0's `9edd2ba7`. Read-only on every mark file.

---

## The headline

**Both halves of the contradiction are true, and the cause splits almost exactly in
half.** When Austin picks the day and the minute, the engine finds that minute — median
**+0.0 bars**, and inside ±6 bars it is *early* 7 times to 2. When the **engine** picks the
minute and he reviews it, he says the good trade is earlier on **51 of 60** cards
(**85.0%**, 95% Wilson 73.9–91.9%, exact binomial p = 3.1×10⁻⁸), by a **median 2 bars**
(mean −1.95, 95% bootstrap −3.59 to −0.26 — the bar excludes zero, so this is **not** a
null result).

On the 33 cards where he names a bar count and the card's own entry bar is recoverable,
the engine had **already emitted a candidate within 1 bar of the entry he named on 16 of
33 (48%)** — and killed it with the legacy grade (`X` on 12 of those 16). On the other
17 (52%) the detector never produced anything there at all.

**The split is a function of distance.** At the offset he names most often — **one bar** —
the engine already has the setup **8 times out of 9 (89%)**. That is a grader problem, not
a detector problem. Only at ≥3 bars does the detector go genuinely blind (29% hit).

So the spec's prediction — *"if there is a systematic lead, it is a detector fix worth more
than any grader arm"* — is **half right**. The lead is systematic and large. But the near
half of it, which is also the majority of what he complains about, is sitting in the
engine's own output right now with an `X` on it.

---

## 1. The offset corpus

Every mark corpus is scanned for entry-timing prose (218 notes across 21 files), and each
hit is adjudicated once, in a table inside the script that carries his exact words next to
the verdict. A note is only counted when it names an alternative **ENTRY** — not a stop,
not a piece of structure, not a remark about time of day.

| | count |
|---|---:|
| notes mentioning entry timing | 218 |
| adjudicated rows after de-duplicating across corpora | 158 (30 marked DUP) |
| **ENTRY** — he names an alternative entry | **84** |
| STOP / structure | 11 |
| CONTEXT (no offset) | 27 |
| ELSEWHERE (a different setup, different time) | 2 |
| AMBIG (self-contradictory or truncated) | 4 |

**Reachability (method rule 3).** 84 of 128 live notes (65.6%) are genuine entry offsets —
comfortably between the 1% and 85% bands, so the finding is about the population, not the
filter. The scan is also a tripwire: it re-runs on every invocation and prints any timing
note that is not adjudicated, and any adjudicated key that no corpus contains is dropped
loudly. Nothing in the table can rest on a mark row that is not there.

### P-ENGINE — the card in front of him showed an engine-proposed entry

Sources: `probe_master_2026-08-29.jsonl` (his 2026-08-28 verdicts on engine vetoes and
runners), `probe_master_homework_2026-08-26.jsonl` (`cal_` engine calibration cards),
`probe_omen_test1_2026-08-27.jsonl` (100 engine cards carrying `entry_i`/`entry_t`),
`recovered_reviews.jsonl` (engine trades he reviewed in chat), and the
`austin_marks_v7.jsonl` rows whose prose addresses a second person — *"your entry"*,
*"you missed"*, *"yours a fail"* — which is what tells you the entry on the card was not
his.

| | value |
|---|---|
| n with a stated direction | **60** |
| earlier / later | **51 / 9** |
| fraction earlier | **85.0%** (95% Wilson 73.9 – 91.9) |
| exact binomial sign test, p₀ = 0.5 | **p = 3.09 × 10⁻⁸** |
| n with a stated bar count | 49 |
| **mean signed offset** | **−1.95 bars** (95% bootstrap **−3.59 to −0.26**) |
| **median signed offset** | **−2.0 bars** (95% bootstrap −4.0 to −1.0) |

Distribution (negative = earlier than the engine's entry):

```
-22 -11 -9 -8 -6 -6 -6 -5.5 -5 -5 -5 -5 -5 -5 -5 -4 -4 -4 -3 -3 -3
 -2 -2 -2 -2 -2 -2 -2 -2 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1
 +1 +4 +7 +8 +12.5 +14 +16.5
```

**The mode is −1 and the second mode is −2.** Twenty-one of 49 numeric offsets are one or
two bars. This is not "he wants a different trade"; it is "he wants the same trade, one
candle sooner".

### P-SELF — control: he was marking his own entry

His blind pass, the `mark_batch_03` regrades, and the silent-day autopsy, where the entry
on the card is his own.

| | value |
|---|---|
| n with a direction | 11 |
| earlier / later | 10 / 1 |
| fraction earlier | 90.9% (95% Wilson 62.3 – 98.4) |
| mean signed offset | −3.14 bars (95% boot −5.00 to −1.43), n = 7 |

He second-guesses his *own* entries in the same direction. That matters for
interpretation: some of the P-ENGINE lead is a standing preference for earlier fills, not
a defect specific to the engine. But the P-SELF n is 11 and its CI is wide; treat it as a
caution, not a discount.

### P-MIXED — reported, in neither headline

`mark_batch_02` is *"40 S-miss bars + 20 unmarked engine entries"* (`research/marks/LEDGER.md`),
so rows from it with no pronoun cannot be assigned. 12 rows, 10 earlier / 2 later, mean
−3.11 bars (95% boot −7.00 to **+1.39** — this one **does** straddle zero).

### Base rate — how often he raises it at all

| corpus | cards | says "earlier" | says "later" |
|---|---:|---:|---:|
| `probe_omen_test1_2026-08-27.jsonl` | 100 | 5 (5.0%) | 1 |
| `probe_master_2026-08-29.jsonl` (veto + rare + runner lanes) | 75 | 5 (6.7%) | 1 |
| `recovered_reviews.jsonl` | 176 | 13 (7.4%) | 2 |

**The 85% is the direction given that he raised it, not the share of all cards that are
late.** He volunteers a timing complaint on 5–7.4% of engine cards. Hold on to that
number — section 4 produces an independent 8.4% from the engine side, and they agree.

---

## 2. What T1's "median +0.0 bars" was conditioned on

`research/t1_entry_minute_autopsy.md` states its own matching rule in its second line:
*"A signal counts as 'his idea' when it lands within 2 bars of the minute he typed."* The
+0.0 median is then taken over exactly the rows that rule admitted.

| | n | median | mean |
|---|---:|---:|---:|
| T1's reported subset (FIRED + DETECTED) | 15 | **+0.0** | +0.13 |
| All 34 days in T1's own published table | 34 | **+2.0** | +12.82 |

Max \|delta\| in the reported subset: **2** — the selection window itself. The statistic
could not have left [−2, +2]. **"+0.0" is a property of the matching rule.** Over all 34
of T1's own rows the engine is late on 20 (59%).

This does not make T1 wrong about what it set out to measure, and section 5 below confirms
its conclusion survives without the window. It makes the *quoted number* unusable as
evidence that the engine's timing is exact.

---

## 3. The obvious mechanism, and its refutation

`omen_bot.detect_break_retest` is a four-step FSM: BREAK → LEAVE → RETEST → **CONFIRM**,
where step 4 requires the current candle to **close** back through the level. Austin's
fill is repeatedly *"as the candle is forming"* / *"as candle closing not lod"*. The
obvious hypothesis is that CONFIRM-on-close costs a bar.

Measured on every traded break-and-retest row in the shipped book — bars from the last
bar whose range touched the broken level (parsed out of the row's own `reason` string) to
the bar the engine entered on:

| | value |
|---|---|
| traded B&R rows | 1,704 |
| level price unparseable | 0 |
| day not in `data_archive` | 59 |
| measured | 1,645 |
| **gap = 0 — the entry bar IS the retest bar** | **1,267 (77.0%)** |
| gap = 1 | 94 (5.7%) |
| gap ≥ 2 | 284 (17.3%) |
| median / mean gap | **0.0 / 0.49 bars** (95% boot 0.45–0.54) |

**Refuted.** Step 4 does not cost a bar. `detect_break_retest`'s loop runs
`for i in range(1, len(w))`, so the retest index may be the current bar itself, and on a
break-and-retest long the confirm bar's low usually reaches the level on its way up. The
engine is already entering on the retest candle three times in four. This is a real
negative result and it kills the cheapest available "fix".

---

## 4. Where the lateness actually comes from

For every traded row, look at the engine's own signal stream on the same symbol / day /
direction and ask whether it had **already emitted** a candidate before the entry it took.

| | value |
|---|---|
| traded rows | 2,595 |
| had **any** earlier candidate | **1,658 (63.9%)** |
| median bars to the nearest earlier candidate | 4 |
| had one **1–6 bars** earlier — Austin's own range | **1,075 (41.4%)** |

Those 1,451 near-earlier candidates, by the grade that actually routes trades:

| legacy grade | n | share | | status | n |
|---|---:|---:|---|---|---:|
| **X** | **1,338** | **92.1%** | | `skipped_d` | 1,338 |
| B | 72 | 5.0% | | `fired` | 84 |
| C | 37 | 2.5% | | `skipped_tight_stop` | 30 |
| A | 4 | 0.3% | | | |
| A+ | 1 | 0.1% | | | |

And the same candidates on **Austin's** ladder, which routes nothing:

| sgrade | n | share |
|---|---:|---:|
| C | 834 | 57.4% |
| **A** | **358** | **24.7%** |
| **S** | **260** | **17.9%** |

> 218 traded rows (**8.4%**) have a candidate 1–6 bars earlier that scores **S on his own
> ladder**. On 139 of them (**5.4%**) the row the engine actually took is *not* S.

**8.4% from the engine side; 5.0–7.4% from his prose.** Two independent counts of the same
thing. The engine takes a worse-graded entry than one it already had in hand, a few bars
earlier, on roughly one traded row in twelve — and that is roughly how often he says so.

---

## 5. The held-out read (method rule 2)

`research/marks/probe_s_sweep_2026-08-28.jsonl`, the 34 cards he graded **S** and typed a
minute for. Engine = the nearest signal that symbol-day emits in the ratified book, **with
no matching window at all**, so the sign is free to move.

| | value |
|---|---|
| cards with a typed minute | 34 |
| engine silent that symbol-day | 9 |
| measured | 25 |
| engine LATE / EXACT / EARLY | **12 / 6 / 7** |
| **median signed delta** | **+0.0 bars** (95% boot +0.0 to +9.0) |
| mean signed delta | +11.88 bars (dragged by far-off signals on other setups) |
| within ±6 bars of his minute | 15 of 25 — of those, LATE **2** / EARLY **7**, median +0.0 |

**T1's conclusion survives without its window.** On the minutes *he* names, the engine is
not systematically late; inside ±6 bars it skews **early**. Held-out recall on this file is
unchanged by this track, because this track changed no engine code.

**This is the resolution of the contradiction.** The two measurements ask different
questions:

- *"When he picks the day and the minute, can the engine find that minute?"* — Yes. Median
  +0.0, and it errs early.
- *"When the engine picks the minute, is it the best minute on that day?"* — No. He says
  earlier 85% of the time, median 2 bars, and the engine usually already had the earlier
  one.

Both can be true at once because the second is a **selection among the engine's own
candidates**, and the first is a **search for one specific candidate**.

---

## 6. The decisive card-level test — detector or grader?

For every P-ENGINE row where he states a bar **count** and the card's own entry bar is
recoverable, ask the shipped book: did the engine emit anything within ±1 bar of the entry
he named?

| | value |
|---|---|
| resolvable named-bar rows | 38 |
| engine silent that whole day | 5 |
| **testable** | **33** |
| **HIT** — engine had it and refused it | **16 (48%)** |
| **MISS** — detector never produced it | **17 (52%)** |
| legacy grades at the named bar (hits) | X 12 · B 6 · C 1 |
| his-ladder grades there (hits) | C 10 · S 4 · A 3 |

**By distance — this is the load-bearing table:**

| how far away the entry he names is | testable | HIT | hit rate |
|---|---:|---:|---:|
| **\|offset\| = 1 bar** | 9 | **8** | **89%** |
| \|offset\| = 2 bars | 7 | 3 | 43% |
| \|offset\| ≥ 3 bars | 17 | 5 | 29% |

At one bar the engine is not blind — it is **refusing**. Eight of nine. His own line on
the clearest of these, `cal_QQQ_2026-06-29_b10`: *"the engine entered one candle late,
thats why it doesn't see the textbook s trade OCR"* — and the engine's own record at the
bar he means is a signal graded **X**, `skipped_d`.

Selected rows (`card` = the engine's bar, `his` = the bar he named, both counted from
09:30):

| sym | day | card | his | off | found | grade / sgrade | his words |
|---|---|---:|---:|---:|---|---|---|
| QQQ | 2026-06-29 | 10 | 9 | −1 | **HIT** | X / C | *the engine entered one candle late* |
| META | 2025-12-22 | 5 | 4 | −1 | **HIT** | X / **S** | *1 candle earlier S* |
| META | 2025-09-18 | 45 | 44 | −1 | **HIT** | X / **S** | *1 candle earlier A entry* |
| NVDA | 2026-02-05 | 48 | 47 | −1 | **HIT** | B,X / A,**S** | *1 candle earlier is your A entry* |
| NVDA | 2025-09-29 | 13 | 12 | −1 | **HIT** | B / C | *1 candle earlier is S entry* |
| INTC | 2025-06-05 | 22 | 21 | −1 | **HIT** | X / C | *on candle earlier is your entry* |
| SPCX | 2026-06-30 | 33 | 32 | −1 | **HIT** | B,C / C | *your entry is wrong one candle late* |
| AMD | 2025-03-28 | 31 | 9 | −22 | **HIT** | X / **S** | *earlier entry at 9:39 as candle forming* |
| MU | 2026-01-09 | 12 | 10 | −2 | miss | — | *2 candles earlier s* |
| HOOD | 2026-03-27 | 9 | 5 | −4 | miss | — | *4 candle earlier may be entry* |
| MU | 2026-01-28 | 13 | 4 | −9 | miss | — | *you missed the entry 9 candles earlier* |

The full 38-row table is printed by `python research/t12_earlier_entry_gap.py named`.

---

## What this says to do — and what it does not

1. **Do not build a "shift the entry back N bars" detector patch.** Section 3 shows the
   FSM already enters on the retest candle 77% of the time; there is no uniform bar to give
   back. A blanket shift would move 1,645 entries to fix ~8%.
2. **The one-bar case is a grading fix and it belongs to T10/T14, not to a detector track.**
   Eight of nine one-bar complaints are signals the engine emitted and graded `X`. `X` is
   not a grade — it means the engine should not have fired — and 17.9% of the near-earlier
   candidates it suppresses are **S on Austin's own ladder**. The concrete arm: on a
   symbol-day where two candidates sit within 1–2 bars of each other, prefer the **earlier**
   one when its Austin-ladder grade is **equal or better**. Sizing: 218 traded rows (8.4%)
   have such a candidate; 139 (5.4%) currently take a strictly worse-graded entry.
3. **The ≥3-bar case is a genuine detection gap and it is the smaller half.** 12 of 17
   misses are ≥3 bars out; several of his notes for those name a *different* setup at the
   earlier bar (*"thats a one candle rule"*, *"break and retest of pivot structure"*), which
   makes them T2 (the OCR detector) and T13 (candle shapes), not a timing fix.
4. **T1's number should be re-stated, not retracted.** Section 5 re-runs it with no
   matching window on the ratified book and it holds. The `+0.0` figure should carry its
   condition wherever it is quoted.

---

## Error bar, and what did not run

**Error bar (method rule 1).** This track ran no A/B and produced no R figure, so there is
nothing to compare against the project's ±1.5799 R band. Its own bars:

- fraction earlier, P-ENGINE: 85.0%, 95% Wilson **73.9 – 91.9%**; exact binomial
  p = 3.09 × 10⁻⁸. Excludes 50%.
- mean signed offset, P-ENGINE: −1.95 bars, 95% bootstrap (20,000 reps, seed 12)
  **−3.59 to −0.26**. Excludes 0.
- P-MIXED's mean (−3.11, 95% boot −7.00 to **+1.39**) **does** straddle zero and is
  reported as inconclusive, which is why it is not in the headline.
- section 3's mean gap 0.49 bars, 95% boot 0.45–0.54.
- section 6's 48% hit rate rests on **33 cards**. The by-distance split (89% / 43% / 29%)
  rests on 9 / 7 / 17. Direction is clear; the percentages are soft.

**What did not run.**

1. **No engine change and no re-run of the two years.** Nothing here moves held-out recall;
   section 5's 25 measurable cards are a re-read of the ratified book, not an arm.
2. **The adjudication is human judgement.** 84 prose notes were classified by hand into
   ENTRY / STOP / CONTEXT / ELSEWHERE / AMBIG. The table is in the script with his verbatim
   words beside every call, so it can be re-checked line by line, but a different reader
   would move some rows. The four AMBIG rows (including `t1_UBER_2025-09-18`, where he
   writes *"earlier entry at 10:52"* on a card whose entry is 09:58) are excluded rather
   than guessed at.
3. **"few" / "a couple" are counted as direction only, never as a number.** 11 of the 60
   P-ENGINE rows have a direction but no magnitude and are in the sign test only.
4. **P-ENGINE membership inside `austin_marks_v7` is inferred from second-person prose**,
   because the `<sym>_<day>_<a>_<b>` batch05 ids carry no provenance field. Rows where that
   tell is absent are in P-MIXED, not silently assigned.
5. **Section 3 uses "the last bar whose range contained the level" as a proxy for the FSM's
   `retest_idx`.** It is not the FSM's own index — `detect_break_retest` does not persist
   one into the book — so it is an upper bound on how close the retest was. 59 of 1,704
   rows had no archived day.
6. **Section 4 treats `research/bt2y_trades.json`'s 75,953 rows as the engine's candidate
   stream.** That is what the engine emitted under the shipped configuration; a different
   configuration would emit different earlier candidates.
7. **Section 6's 5 SILENT days** (AAPL 2024-01-02, AAPL 2024-03-28, MSTR 2024-08-08,
   MSTR 2025-12-12, SPY 2026-04-29) are days the ratified engine takes no signal at all, so
   they are neither HIT nor MISS. They are excluded from the 48%, not counted as misses.
8. **No options, contracts, spreads or futures.** Every bar count here is the underlying.
