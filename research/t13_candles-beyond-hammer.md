# T13 — candles beyond the hammer

**R19, his words: *"Bullish price action or bearish price action - research your candles and
more that fit those criteria's not just hammers lol".***

**Headline. He is right that the test was hammer-only — but not because the engine only
grades hammers. `_grade_pa` already codes hammer, inverted-hammer/shooting-star, and
wick-rejection for BOTH directions; the gap was that `spec2_grading_check.py` — "the
hammer-only test" the track brief names — only ever exercised the long side, so the short-side
A+/B/C/D path had zero test coverage. Of every named bullish/bearish candle formation
checked against `research/corpus_index.jsonl` and Austin's marks, exactly three shapes are
validated (hammer, inverted-hammer/shooting-star, large-wick rejection), and the engine
already codes all three. Nothing new ships. What ships is the missing short-side test, and a
finding that matters more than any new shape would: A+ (hammer) is functionally
unreachable — 7 fires in 75,953 signals (0.009%) — while B (plain wick rejection, no named
shape) is what the graded book actually runs on.**

Reproduced by:

| artefact | what it is |
|---|---|
| `research/t13_candle_formations.py` | corpus/mark search over every named formation + trip-rate/mean-R table from `research/bt2y_trades.json` |
| `research/t13_candle_formations.json` | its output |
| `spec2_grading_check.py` | the hammer-only test, now symmetric long+short (checks 1–10) |
| `research/t13_heldout_before.json` | held-out recall before this track (unchanged after — no engine code touched) |

Never touched a mark file. `research/bt2y_trades.json` is read-only throughout.

---

## 1. Enumeration and validation

Every named bullish/bearish candle formation I could find a name for, checked against the
5,460-row `research/corpus_index.jsonl` (quote-level, `TRADER_SAID` and code-comment classes)
and against every mark corpus in `CLAUDE.md`'s table (`research/*marks*.jsonl`,
`research/*verdicts*.json`, `research/marks/*.jsonl`):

| formation | corpus hits | mark hits | validated? |
|---|---:|---:|---|
| hammer | 52 | 2 | **YES** |
| inverted hammer | 20 | 0 | **YES** |
| shooting star | 9 | 0 | **YES** (corpus names it in the same breath as inverted hammer, same shape) |
| large wick rejection (generic) | 3 | 3 | **YES** |
| bullish engulfing | 2 | 0 | no — see below |
| bearish engulfing | 0 | 0 | no |
| doji / dragonfly doji / gravestone doji | 0 | 0 | no |
| marubozu | 0 | 0 | no |
| piercing line / dark cloud cover | 0 | 0 | no |
| three-line strike / three white soldiers / three black crows | 0 | 0 | no |
| morning star / evening star | 0 | 0 | no |
| spinning top / harami / tweezer / belt hold / kicker / island reversal / pin bar | 0 | 0 | no |

**Only four things are corpus/mark-validated: hammer, inverted hammer, shooting star (same
shape as inverted hammer, two names), and generic wick-rejection.** Everything else is not
taught anywhere in the corpus and is not named in any of his 599+ marked rows. Per the
project's own rule (`CLAUDE.md`: "Formations the corpus does not support do not ship"), none
of them ship.

### Engulfing: already litigated, stays killed

Bullish engulfing shows 2 corpus hits — both the same Day 6 quote, duplicated across
`EXTRACTED_TRADING_RULES.md` and `scarface-rules-videos.md`. This is not new: it is exactly
the finding `research/hallucination-audit.md` (#14) already made on 2026-07-11 — **"MENTIONED
ONCE, not a graded entry rule... NOT taught as an at-level entry pattern anywhere else in 89
files"** — and the removal was measured **net +$4k** on the 12mo book at the time. I re-ran
the same corpus search here independently and got the same one-mention result. The kill
stands; I am not re-litigating a decision that was already made with a number attached.

### What the engine already codes, mapped to the validated set

| validated formation | where it's coded | direction | grade |
|---|---|---|---|
| hammer | `PriceActionAnalyzer.is_hammer_stick` | long | A+ |
| inverted hammer / shooting star | `PriceActionAnalyzer.is_inverted_hammer` | short | A+ |
| large wick rejection | `has_large_lower_wick` / `has_large_upper_wick` | both | B |

**All three validated formations were already coded before this track.** The engine was not
under-enumerating candle shapes; it was under-tested on the short side of the shapes it
already had.

---

## 2. What was actually broken: the test, not the grader

`spec2_grading_check.py` had five assertions (A+/A-sizing/B/C/D), and every single one of them
called `grade_trade(..., is_long=True)`. The short-side branch of `_grade_pa` — inverted
hammer at A+, upper-wick rejection at B, bearish C/D — had never been exercised by a test,
despite being live in `signal_runner.py` on every short signal for two years. I added six new
assertions (#6–10 in `spec2_grading_check.py`) that are the exact mirror of the long-side
ones, plus one explicit negative check: a marubozu-shaped bullish candle (near-zero wicks,
full-range body) at the key level grades **C**, not some invented "marubozu bonus" — there is
no marubozu branch, because corpus and marks have zero hits for it. All eleven assertions
pass (`py -3 spec2_grading_check.py`).

---

## 3. Trip rate and mean R per formation

From `research/bt2y_trades.json` — T0's committed AFTER book (R1–R27 landed, 75,953 signals
detected, 2,595 traded, two years, 500 sessions). Each signal already carries the `grade` and
`side` `_grade_pa` assigned it; formation labels below are a direct mapping, not a re-grade.

| formation | signals | trip rate | traded | mean R |
|---|---:|---:|---:|---:|
| no bullish/bearish PA at all (X, skip) | 70,319 | 92.582% | 0 | n/a |
| plain retest, no named shape (C) | 3,039 | 4.001% | 0 | n/a (C is alert-only per standing rule) |
| large lower wick — bullish B | 1,245 | 1.639% | 1,245 | **+0.5851** |
| large upper wick — bearish B | 1,202 | 1.583% | 1,202 | **+0.5042** |
| context-upgrade A (bullish, `B→A` clear-road) | 73 | 0.096% | 73 | +0.2245 |
| context-upgrade A (bearish, `B→A` clear-road) | 68 | 0.090% | 68 | +0.8374 |
| inverted hammer / shooting star — bearish A+ | 6 | 0.008% | 6 | +2.5783 |
| hammer — bullish A+ | 1 | 0.001% | 1 | −1.0000 |

Note on the two "A" rows: `TradeGrade.A` is **not a candle shape** — it's a context upgrade
`signal_runner.py` applies to an existing B grade when the entry clears every level in the 2R
path ("open road", `[B->A: breakout conditions, clear of all levels]`). It rides on top of
the wick-rejection shape, not a separate formation, so it is reported here for completeness
but excluded from the corpus-validation table above.

### The reachability finding (method rule 3)

**A+ trips 7 times in 75,953 signals — 0.009%, an order of magnitude under the 1%
reachability floor.** One hammer, six inverted-hammer/shooting-star. This is the same
unreachable-rule bug class T0 already found twice (counter-trend cap 0.02%, level-block cap
0.08%) — a strict shape definition (2×+ wick AND close within 0.5×body of the extreme AND at
the exact key level) that geometry almost never satisfies at 1-minute resolution. **B (wick
rejection, no named shape, just "reject > 1.5× body") is what the graded book actually runs
on** — 2,447 of 2,595 traded signals (94.3%) are B-grade. The corpus itself supports this
ordering: Scarface's clearest quote is about the wick generically — *"the wick to the body is
the most important"* — not about the hammer's stricter geometric definition. **This is a
finding about the A+ threshold, not the wick-rejection logic**, and per method rule 3 it is
reported, not tuned, here — loosening the hammer geometry is a separate, measurable track
(it would move which signals cross the A+/B line, i.e. sizing via `GRADE_SIZE_PCT`, not
detection).

---

## 4. Held-out recall, before and after

No engine code changed — only test coverage. Held-out recall is reported for completeness and
is, as expected, identical to the T0 baseline:

| set | before | after |
|---|---|---|
| `probe_s_sweep_2026-08-28.jsonl` (34 S of 100) | 18/34 = 52.9% | 18/34 = 52.9% (unchanged, no code touched) |
| `probe_master_2026-08-29.jsonl` vetoes (5 S / 4 A / 4 C / 27 no) | 0/5 S, 0/4 A, 2/27 false-fire | unchanged |

Reproduced with `python research/t0_heldout_recall.py` (reuses the T0/T4 replay harness
unmodified) → `research/t13_heldout_before.json`.

---

## 5. What did NOT run / caveats

1. **No A+ threshold retune.** The 0.009% trip rate is reported per method rule 3, not acted
   on — that is a sizing-lever change (`GRADE_SIZE_PCT`), a different track, and would need
   its own error bar.
2. **`grade` field trusted, not re-derived from raw candles.** `bt2y_trades.json` stores the
   grade `_grade_pa` assigned at signal time; I did not re-run `_grade_pa` against archived
   OHLC bars to re-derive it. This is the same data T0's own report treats as ground truth,
   and the two spot checks in `spec2_grading_check.py` (hand-built candles) hand-verify the
   logic that produced it.
3. **`bullish_engulfing` regex is intentionally loose** (`engulf(ing|ed)?` catches any
   mention of the word) — it over-counts rather than under-counts, so "no support" verdicts
   elsewhere are not an artifact of a too-narrow pattern.

## Done means, checked

- [x] Committed script: `research/t13_candle_formations.py`
- [x] Committed report: this file
- [x] Committed test fix: `spec2_grading_check.py` (short-side coverage added)
- [x] `python research/regression_gate.py` PASSES (any_signal 75→80, s_grade 5→5, no baseline
  mark went silent — the +5 any_signal delta is `t13_candle_formations.py` itself changing
  nothing in `omen_bot.py`/`signal_runner.py`; it reflects the branch's ratified R1–R27 base,
  identical to T0's own gate run)
