# Scoreboard -- EV/R, last 20 sessions vs the prior 20

One-trade-a-day pick stream (size-gated), `bt2y_trades_retest_on.json`, 498 picks total. Same definition every week: `research/omen_metrics.py::ev_r_scoreboard` on `research/omen_metrics.py::first_of_day_arm`.

| window | sessions | ev/R | win % | total R | max DD (R) |
|---|---|---:|---:|---:|---:|
| last 20 | 2026-07-31 .. 2026-09-02 | -0.1140 | 40.0% | -2.28 | -4.66 |
| prior 20 | 2026-07-02 .. 2026-07-30 | +0.1079 | 60.0% | +2.16 | -3.24 |

**Delta (last - prior): -0.2219 ev/R -- RED, not getting better**

But read the delta next to its own history, not alone: **48.6% of every 20-vs-20 comparison in this book's 2-year history is RED**, and the current |delta| sits at only the 42 percentile of magnitude -- typical, not unusual.

## Kill rule (60 sessions at ev/R <= 0 means this approach is dead)

ev/R -0.1491 over the last 60 sessions (2026-06-03 .. 2026-09-02) -- at or below zero.

**Read this next to its own history before treating it as news.** Across all 439 rolling 60-session windows in this book, **42.4% sit at or below zero** (8 separate episodes, one 55 sessions long that fully recovered). The current window is at the 12 percentile (low, but not rare) and -1.13 standard errors from the book's own long-run mean -- inside the range chance alone produces. A single 60-session slice of a process with per-trade sd ~1R and a long-run mean near zero trips this rule constantly by construction -- it is not, on its own, evidence of decay.

## The one signal that IS new: trailing-250-session ev/R

Trailing 250-session ev/R is now **-0.0660**. It first went negative on **2026-05-28** (value -0.0068) and remains negative through the end of the book (current streak: 61 sessions since 2026-06-02; the longest negative streak anywhere else in the book's history is 61 sessions). Unlike the 60-session kill rule, a first-ever sign flip on a 250-session trailing window is not something the book's own history has done before -- this is the more defensible way to argue the edge is decaying, not the 60-session slice above.

| quarter | ev/R | n |
|---|---:|---:|
| 2024 Q3 | +0.0093 | 20 |
| 2024 Q4 | -0.0409 | 64 |
| 2025 Q1 | +0.2032 | 60 |
| 2025 Q2 | +0.2689 | 62 |
| 2025 Q3 | +0.1325 | 64 |
| 2025 Q4 | -0.1075 | 64 |
| 2026 Q1 | +0.0620 | 61 |
| 2026 Q2 | -0.2224 | 62 |
| 2026 Q3 | -0.0273 | 41 |

Adversarial pass, 2026-09-03 night: the raw numbers above (last-20, prior-20, last-60, trailing-250) were independently re-derived and CONFIRMED; the bare 'kill rule tripped' framing this file used to print was found misleading and dropped in favor of the historical-context read above.

