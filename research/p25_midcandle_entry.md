# P25 — the mid-candle entry, and why the number is 0% when it should not be

Austin, 2026-08-27: *"im concerned with a lot of my entries all target HOD/LOD and getting
entries on the middle of candles not at candle close. im sure the percentage on that is
high. all that should be reflected and changed in the intricate backtest results."*

Measured with `research/p25_midcandle_entry.py` (`--selfcheck` green) over every mark
corpus that carries a human entry. 117 entries measured, 5 rejected because the recorded
price sits outside the bar it claims, 976 mark rows carry no entry at all (X-grade days
and prose reviews — not missing data).

## The answer is that the instrument cannot record it

| group | n | at close | mid-bar | median pos in bar | slip R mean | slip>0 |
|---|---:|---:|---:|---:|---:|---:|
| ALL | 117 | 62 (53%) | 55 (47%) | 0.82 | +0.133 | 49% |
| **grade S** | **15** | **15 (100%)** | **0 (0%)** | 0.93 | −0.001 | 20% |
| **grade A** | **27** | **27 (100%)** | **0 (0%)** | 0.86 | +0.001 | 18% |
| **grade C** | **14** | **14 (100%)** | **0 (0%)** | 0.85 | +0.004 | 25% |
| setup BR | 58 | 36 (62%) | 22 (38%) | 0.84 | +0.168 | 46% |
| setup OCR | 32 | 18 (56%) | 14 (44%) | 0.85 | +0.059 | 40% |
| setup BR+OCR | 18 | 7 (39%) | 11 (61%) | 0.80 | +0.054 | 65% |

`pos in bar` is oriented so **0.0 is the favourable extreme for his direction** (a long
wants the low) and 1.0 is the adverse one. `slip R` is what waiting for the close would
have done to the fill, over his own stop: positive means entering mid-candle paid.

**Every S, A and C entry from OMEN Test 1 reads 100% at-close, and that is a lie the page
tells.** `research/build_omen_test1.py:696`:

```js
out.entry_p = closes[i];
```

He picks an entry *minute*; the page writes that minute's **close** as the fill price. The
field cannot differ from the close, so the measurement cannot come out any other way. This
is the [[omen-rules-unreachable-in-code]] bug class in a homework instrument instead of the
engine: a real behaviour becomes a field that can never be true.

The 55 genuine mid-bar entries all come from the two 2026-08-19/20 deck files, where
chart-click marking recorded whatever price he clicked.

## He told us anyway, in prose, 14 times

The note fields carry the override the price field could not:

| grade | rows saying *"as candle forming not HOD/LOD"* |
|---|---:|
| S | 2 |
| A | 8 |
| C | 4 |
| **total** | **14 of 58 graded (24%)** |

So the honest floor is **24% of his graded entries are explicitly not at the close**, and
that is a floor, not an estimate — it counts only the times he stopped to type it.

`median pos in bar = 0.82–0.93` says the same thing from the other side. If his marks were
real fills, they sit **at the adverse end of the entry bar** — exactly the *"the candle
closes near/above HOD/LOD and the RR is shot"* complaint, and exactly what you get when the
price is forced to the close.

## Where the close does land

- Entry bar closes within 10% of the session extreme so far: **40/117 (34%)**.
- Median distance close → extreme: **0.157** of the day's range.

So a third of the time the close-fill assumption is buying at the top of the move. That
third is where the backtest's R is most overstated.

## Is it hard to hold in the backtest?

Two halves, and only one is hard.

- **The price half is already built.** ON WATCH (ticket 18) triggers intrabar at 25% of
  the previous bar's range beyond the level — Austin's one tolerance unit. A 1-minute
  archive can answer "did price reach P inside bar *i*" exactly.
- **The time half is undecidable at 1-minute granularity.** If the trigger price *and* the
  stop both sit inside bar *i*'s range, no OHLC bar says which came first. That is the real
  cost, and it is not a modelling choice — the information is not in the data.

The exposure is bounded and countable, and nobody has counted it: for the entries where an
intrabar trigger would fire, how often does the same bar's range also reach the stop? That
is the ambiguity rate, and it is the honest error bar on any intrabar backtest. It is now
**R8**.

Second-tier data (a true tick or second feed) removes the ambiguity and is the only thing
that does. That is a purchase, not a patch.

> **Superseded 2026-08-28 — counted, then answered.** R8 was counted (`research/p26_intrabar_ambiguity.md`): 86.8% of traded intrabar fills sit on a bar whose range also holds the stop, but **790 of those 792 rows are the stop sitting on the entry bar's own extreme**. Then Austin answered the rules question underneath it: *"out on that same close"* — a stop is triggered by a candle CLOSE and by nothing else, the entry candle's own close counts, and one bar has exactly one close, so a stop cannot fire inside the entry bar ahead of the fill. **The residual ambiguity is 2 rows of 913 and the carried error bar is ±0.0095 R, not the ±1.5799 R wide bar, which is retired.** Second-tier tick data is therefore NOT needed to answer this question — it was answered by a sentence, for free. The paragraph above is kept because it framed the question correctly and because tick data may still be worth buying for other reasons; it is no longer "the only thing that does".

## What this changes

1. **The next homework instrument must let him type the fill price.** Deriving it from the
   close makes the corpus unable to answer the question he is asking of it. Until that
   lands, every future test deck adds rows that read 100% at-close.
2. **The 24% is a floor from prose, not a measurement.** Do not quote it as the rate. The
   rate is unknown and will stay unknown until (1) lands.
3. **Nothing in the backtest changes yet.** `slip R mean` on the S/A/C rows is ±0.004R —
   noise around zero, because the numbers are the close by construction. Re-running the
   book against these fills would measure the instrument, not the market.

## Status

**Provenance:** every number above is produced by `research/p25_midcandle_entry.py`, committed at `9d0c2206`, over the mark corpora listed in its `MARK_FILES`. Regenerate with `python research/p25_midcandle_entry.py --json research/p25_midcandle_entry.json`.

- `research/p25_midcandle_entry.py` committed, `--selfcheck` green.
- `research/p25_midcandle_entry.json` is the per-entry table (regenerate with `--json`).
- Queued: **R6** (instrument fix), **R7** (roster), **R8** (intrabar ambiguity rate).
