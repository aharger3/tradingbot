# G71 adversarial verify — track `symbols`, claim "NVDA is the most SPY-redundant name; AAPL is the most orthogonal"

**Verdict: REFUTED.** Every cited number reproduces to 3 decimals. Three of the
claim's four load-bearing assertions do not survive: the "most orthogonal" half is
plainly false, the "most redundant" half is not separable from three other names, and
the "disqualifies" inference is contradicted by the claimant's own trio file.

Scripts: `research/g71_symbolsV_corr.py`, `g71_symbolsV_seps.py`,
`g71_symbolsV_predict.py`, `g71_symbolsV_bookredun.py`.

## 0. What reproduces

Independent re-implementation over every archived symbol (not the hand-picked 16):

| pair | claim | mine | n |
|---|---:|---:|---:|
| SPY–NVDA | 0.62 | 0.617 | 654 |
| QQQ–NVDA | 0.73 | 0.727 | 658 |
| SPY–TSLA | 0.48 | 0.478 | 654 |
| SPY–AAPL | 0.39 | 0.386 | 654 |
| TSLA–AAPL | 0.17 | 0.169 | 658 |
| TSLA–NVDA | 0.37 | 0.366 | 658 |

sd of the window return: SPY 0.43% / AAPL 1.04% / NVDA 1.71% / TSLA 2.04%. Exact.
No look-ahead: the script reads raw archived bars, computes a contemporaneous
09:30→11:00 return, touches no book and no forward information.

## 1. "AAPL is the most orthogonal available" — FALSE

`research/g71_symbols_corr.py:24-25` hardcodes `CANDIDATES` = 16 names. The archive
holds **24** symbols with ≥300 window days. The 8 never looked at:
`ACHR, ARM, BABA, HOOD, MSTR, NFLX, ORCL, SPCX`.

**SPCX beats AAPL on both axes of the claim, separably:**

| | r to SPY | r to TSLA | window days |
|---|---:|---:|---:|
| AAPL | 0.386 | 0.169 | 658 |
| **SPCX** | **0.060** | **0.080** | 373 |
| BABA | 0.321 | 0.195 | 437 |
| INTC | 0.391 | 0.230 | 655 |

Paired bootstrap of r(SPY,SPCX) − r(SPY,AAPL) = **−0.323, 95% CI [−0.490, −0.145]**,
n=369 common days. SPCX is in `MAJOR_15` (`universe.py:31`), is one of the book's 28
symbols (`bt2y_trades.json` meta), and clears the script's own `MIN_DAYS = 300`. It was
excluded by a literal, not by a rule. AAPL is 5th-lowest of 24 and is not separable from
INTC (+0.004), ACHR (+0.014), NFLX (+0.014) or BABA (−0.072).

## 2. "the most SPY-redundant single name" — point estimate holds, ranking does not

NVDA IS top of the full 24-symbol rescan (0.617), so widening the candidate set does not
flip it. But correlations must be ranked with a paired test, and it fails:

| vs | r_NVDA − r_X | 95% CI | separable? |
|---|---:|---|---|
| AMZN (0.598) | +0.019 | [−0.057, +0.113] | **no** |
| META (0.566) | +0.052 | [−0.014, +0.115] | **no** |
| AVGO (0.582) | +0.064 | [−0.010, +0.129] | **no** |
| HOOD (0.562) | +0.079 | [+0.010, +0.149] | yes |
| TSLA (0.478) | +0.140 | [+0.053, +0.218] | yes |
| AAPL (0.386) | +0.231 | [+0.152, +0.308] | yes |

"The most" is a four-way tie. Robust to window choice (09:30–10:30: NVDA 0.561, still
top single name, still not separable). And **r² = 0.381** — 62% of NVDA's window variance
is idiosyncratic; "a levered SPY" (β = 2.44) overstates a 38%-explained relationship.

## 3. "which disqualifies it as SPY's companion" — refuted by the claimant's own file

`research/g71_symbols_trio.json`, 91 non-QQQ trios (QQQ trios excluded because SPY–QQQ
0.913 is a mechanical outlier that dominates `maxcorr`):

* corr(maxcorr, **green months**) = **−0.074**
* corr(maxcorr, **meanR**) = **−0.218**
* corr(maxcorr, heldout_S) = +0.090

Redundancy predicts nothing the gates measure. Worse, the sign is decorative:

| trio | green | meanR [CI] | n | maxcorr |
|---|---:|---|---:|---:|
| **SPY+NVDA+GOOGL** | **24/25** | **+0.7844** [0.481, 1.100] | 231 | **0.62** |
| SPY+AAPL+ORCL | 24/25 | +0.7242 [0.437, 1.032] | 241 | 0.45 |
| SPY+TSLA+AAPL | 20/25 | +0.7134 [0.479, 0.973] | 306 | 0.48 |
| SPY+TSLA+NVDA | 17/25 | +0.6382 [0.401, 0.891] | 328 | 0.62 |

The best trio in the whole table on **both** durability and money carries `maxcorr = 0.62`
— and that 0.62 *is* NVDA's SPY correlation. The disqualifying number sits on top of the
winner. The two trios the claim contrasts have mean-R CIs that overlap over 80% of their
width; neither reaches the mean R = 2.0 gate, nor within a factor of 2.5.

## 4. Wrong redundancy metric for this book

Window-return correlation measures co-movement of *the tape*. The book is a stop-based
directional engine that trades SPY on **52 of 500 sessions** (55 trades). No companion
shares even 20 traded days with SPY, so `MIN_SAMPLE_N = 20` (`universe.py:181`) cannot be
met for a single SPY-companion pair. Per-day realised-R correlation on the traded book:

| sym | r(day R vs SPY) | co-days |
|---|---:|---:|
| GOOGL | +0.775 | 10 |
| HOOD | +0.345 | 19 |
| AMZN | +0.299 | 13 |
| **NVDA** | **+0.053** | 15 |
| TSLA | −0.016 | 17 |
| **AAPL** | **−0.622** | 11 |

Every n is too small to conclude from — which is the finding. At the level where money is
actually made, SPY–companion redundancy barely exists as a measurable phenomenon, and the
one companion the claim calls redundant scores near zero on it.

## 5. Checks that clear

* **Look-ahead:** none. Raw bars, contemporaneous window, no book, no forward field.
* **Book identity:** the corr claim uses no book at all. The trio evidence uses
  `meta.traded = 2437`, generated 2026-08-29T03:14, the current book superseding the
  2,595-trade T0 book (`research/g71_advscanners.md:13`). Not the stale 1,017 book.
* **Reachability:** measurement only; `FOCUS_3` is a proposed diff, nothing is wired.
* **Window sensitivity:** 09:30–10:30 preserves the top of the ranking.

## The one-line fix

`research/g71_symbols_corr.py:24-25` — stop hardcoding the candidate set.

```diff
--- a/research/g71_symbols_corr.py
+++ b/research/g71_symbols_corr.py
@@
-CANDIDATES = ["SPY", "QQQ", "IWM", "TSLA", "NVDA", "AAPL", "MU", "AMD",
-              "PLTR", "META", "GOOGL", "MSFT", "AMZN", "INTC", "COIN", "AVGO"]
+# Every archived name, so "most/least correlated IN THE UNIVERSE" is a claim the
+# script can actually support. A hardcoded 16 silently dropped ACHR, ARM, BABA,
+# HOOD, MSTR, NFLX, ORCL and SPCX -- and SPCX (0.06 to SPY, 0.08 to TSLA) is more
+# orthogonal than AAPL on both axes.
+from universe import ALL_SYMS, archived_symbols
+CANDIDATES = archived_symbols(sorted(set(ALL_SYMS)), min_days=300)
 MIN_DAYS = 300
```

A ranking of correlations also needs the paired bootstrap in
`research/g71_symbolsV_seps.py::diff_ci` before any "most" is written down.
