# Corpus Recall (corpus 2.0 / T1)

**Overall recall (covered instances, +/-10 min): 0.0% [0.0%, 0.0%]**  (k=0 seen of n=10305 covered instances)

An instance is *seen* when an engine entry exists on the same symbol-day within +/-10 minutes of the instance's `minute_i`. The population is restricted to instances whose symbol-day appears under `data_archive/` (a day with no bars was never offered to the engine and must not count against it).

> **Why recall is ~0%.** This is not a broken join — it is a structural time-of-day mismatch. Every one of the 417 engine entries fires inside the opening range (`minute_i` 5-89, i.e. 09:35-10:59 ET; median 25 ≈ 09:55 ET), because the break-and-retest engine only sets up in the first 90 minutes. The chat corpus is the opposite: instances cluster hard in the afternoon, median `minute_i` 263 (≈13:53 ET), and only 39 of 10,379 instances (0.4%) fall in the first 90 minutes. Even on the 1,261 instances that share a symbol-day with an engine entry, just 6 sit in the opening range and 0 land within +/-10 min of an entry. So the engine and the chat marks almost never describe the same moment of the same day. The miss map below therefore mirrors the overall instance distribution (afternoon-heavy), and the window-sensitivity table confirms widening the window cannot recover misses that are hours, not minutes, apart.

## Population

- Total instances in `corpus_instances.jsonl`: **10379**
- Covered instances (symbol-day in `data_archive/`): **10305**
- Instances dropped by the covered-set restriction: **74** (their symbol-day had no archived bars, so the engine was never run on them)
- Distinct covered symbol-days (from `data_archive/`): **13815**
- Distinct symbol-days touched by instances: **3655**
- Engine entries in `corpus_engine_entries.jsonl`: **417** over **380** symbol-days (all within the covered set)

## 1. Recall (overall, by channel, by author)

Overall: 0.0% [0.0%, 0.0%]  (k=0, n=10305)

### By channel (+/-10 min)

| Channel | instances | seen | recall | Wilson 95% CI |
|---|---:|---:|---:|---|
| scarface-alerts | 4020 | 0 | 0.0% | [0.0%, 0.1%] |
| jdub-alerts | 3080 | 0 | 0.0% | [0.0%, 0.1%] |
| trading-floor | 2718 | 0 | 0.0% | [0.0%, 0.1%] |
| trade-feedback | 235 | 0 | 0.0% | [0.0%, 1.6%] |
| swing-ideas | 110 | 0 | 0.0% | [0.0%, 3.4%] |
| futures-alerts | 106 | 0 | 0.0% | [0.0%, 3.5%] |
| options-trade-reviews | 13 | 0 | 0.0% | [0.0%, 22.8%] |
| pre-market-live | 11 | 0 | 0.0% | [0.0%, 25.9%] |
| backtesting | 9 | 0 | 0.0% | [0.0%, 29.9%] |
| futures-trade-reviews | 1 | 0 | 0.0% | [0.0%, 79.3%] |
| premarket-charts | 1 | 0 | 0.0% | [0.0%, 79.3%] |
| scarface-tips | 1 | 0 | 0.0% | [0.0%, 79.3%] |

### By author (+/-10 min) — top 20 by instance count

| Author | instances | seen | recall | Wilson 95% CI |
|---|---:|---:|---:|---|
| TonyMontana | 4052 | 0 | 0.0% | [0.0%, 0.1%] |
| Jdub | 3103 | 0 | 0.0% | [0.0%, 0.1%] |
| Jatin | 223 | 0 | 0.0% | [0.0%, 1.7%] |
| Benny Stax | 167 | 0 | 0.0% | [0.0%, 2.2%] |
| MambaTrades | 107 | 0 | 0.0% | [0.0%, 3.5%] |
| Viper | 99 | 0 | 0.0% | [0.0%, 3.7%] |
| Lauren (lakatrades) | 98 | 0 | 0.0% | [0.0%, 3.8%] |
| TG | 85 | 0 | 0.0% | [0.0%, 4.3%] |
| Neto Moreno (Performance Coach) | 74 | 0 | 0.0% | [0.0%, 4.9%] |
| Jonathan | 74 | 0 | 0.0% | [0.0%, 4.9%] |
| Markellwhite16 | 72 | 0 | 0.0% | [0.0%, 5.1%] |
| Miguel Licero | 66 | 0 | 0.0% | [0.0%, 5.5%] |
| Rodneficent | 61 | 0 | 0.0% | [0.0%, 5.9%] |
| demchy19 | 46 | 0 | 0.0% | [0.0%, 7.7%] |
| DWC2016 | 41 | 0 | 0.0% | [0.0%, 8.6%] |
| FraggDieb | 38 | 0 | 0.0% | [0.0%, 9.2%] |
| Lord Nava | 36 | 0 | 0.0% | [0.0%, 9.6%] |
| John H | 35 | 0 | 0.0% | [0.0%, 9.9%] |
| Royal191 | 34 | 0 | 0.0% | [0.0%, 10.2%] |
| MDizzy | 32 | 0 | 0.0% | [0.0%, 10.7%] |

_(Authors with at least one instance: 491.)_

## 2. Window sensitivity

Recall of covered instances at four match windows. If recall barely moves from +/-3 to +/-20 min, the misses are real misses (the engine never fired on that signal), not timing offsets that a wider window would recover.

| Window (min) | seen | covered instances | recall | Wilson 95% CI |
|---:|---:|---:|---:|---|
| +/-3 | 0 | 10305 | 0.0% | [0.0%, 0.0%] |
| +/-5 | 0 | 10305 | 0.0% | [0.0%, 0.0%] |
| +/-10 | 0 | 10305 | 0.0% | [0.0%, 0.0%] |
| +/-20 | 1 | 10305 | 0.0% | [0.0%, 0.1%] |

Recall moves from 0.0% at +/-3 min to 0.0% at +/-20 min — a spread of 0.0 percentage points. 
Recall barely moves across the window, so the misses are **real misses**: widening the match window does not recover them. The engine simply did not produce an entry on those symbol-days near those times.

## 3. Miss map

Unseen covered instances (at +/-10 min): **10305** of 10305.

### Misses by symbol (top 20)

| Symbol | unseen instances |
|---|---:|
| TSLA | 1990 |
| NVDA | 1955 |
| QQQ | 1361 |
| AMD | 1181 |
| SPY | 1006 |
| AAPL | 941 |
| AMZN | 406 |
| PLTR | 273 |
| META | 227 |
| MU | 213 |
| MSFT | 202 |
| INTC | 154 |
| GOOGL | 109 |
| NFLX | 78 |
| AVGO | 48 |
| HOOD | 42 |
| TSM | 32 |
| ORCL | 28 |
| SOFI | 15 |
| COIN | 12 |

### Misses by hour-of-day (ET, message timestamp)

| Hour (ET) | unseen instances |
|---:|---:|
| 9 | 7 |
| 10 | 31 |
| 11 | 51 |
| 12 | 1708 |
| 13 | 4235 |
| 14 | 2854 |
| 15 | 1419 |

### Misses by weekday

| Weekday | unseen instances |
|---|---:|
| Mon | 1408 |
| Tue | 2023 |
| Wed | 2121 |
| Thu | 1782 |
| Fri | 2971 |
| Sat | 0 |
| Sun | 0 |

### Work-list: `research/corpus_misses.jsonl` (300 misses)

The 300 misses written to `research/corpus_misses.jsonl` are drawn from the symbol-days with the highest covered-instance counts, so a later version has a dense, high-value work-list. Each row carries `symbol, day, ts, minute_i, channel, author, msg_id, text, sd_instance_count`.

## 4. Reverse — engine entries no instance sits near, by grade

An engine entry is *unmatched* if no covered instance falls within +/-10 min on the same symbol-day. These are entries the engine fired that nobody called in chat. An entry nobody called is not automatically wrong — it is reported, not judged.

| Grade | unmatched entries | total engine entries of that grade |
|---|---:|---:|
| A+ | 4 | 4 |
| A | 23 | 23 |
| B | 298 | 298 |
| C | 92 | 92 |
| **total** | **417** | **417** |

Of 417 engine entries, 417 (100.0%) have no covered instance within +/-10 min.

---

*Method:* join on `symbol|day`; instance seen iff an engine entry exists on the same symbol-day with `|minute_i(inst) - minute_i(eng)| <= W`. `minute_i` is minutes from the 09:30 ET open. Population restricted to covered symbol-days (those with archived bars under `data_archive/`). Wilson score 95% intervals (z=1.96) throughout.
