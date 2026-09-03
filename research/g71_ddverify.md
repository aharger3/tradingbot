# G7.1 adversarial verify — track `drawdown`, prop-firm claim: **REFUTED**

**Claim under test:** *"At 1R=$1,000 the book busts every trailing-drawdown floor
in Austin's 4-6% range and every real firm floor … Apex $150K EOD 4.0's actual
$4,000 floor is exceeded 4.3x. The book only fits inside 4% at $408/trade EOD or
$350/trade intraday."* (`research/g71_drawdown.md` §4)

**Verdict: refuted.** The drawdown arithmetic reproduces exactly. The prop-firm
conclusion does not, because every floor it names **stops trailing at a stated
buffer**, and the lock is written in the same table row of the same file the
claim cites as its evidence. Model the lock and the book **survives 4%, 5%, 6%,
Topstep, MFF and Vanquish at $1,000/R**. Only Apex's $4,000 fails, and it fails
by touching the floor exactly — not by 4.3x.

Script: `research/g71_ddverify_lock.py` (read-only; no engine, no mark file).
Book: `research/bt2y_trades.json`, generated 2026-08-29T03:14:29, 2,437 traded,
496 trading days, +1,339.09R.

---

## 1. What reproduces

Re-ran `research/g71_drawdown_audit.py` unmodified. Every headline number is exact:

| figure | claim | my re-run |
|---|---:|---:|
| trade-level max DD | 17.13R / $17,132 | **17.13R** (peak 2025-08-22 10:04 TSLA @ +588.60R → trough 2025-09-12 10:05 META) |
| day-level max DD | 14.71R / $14,714 | **14.71R** (2025-08-28 → 2025-09-11, 10 sessions) |
| $408 / $350 at 4% | — | 6000/14.714 = 407.8 ✓; 6000/17.132 = 350.2 ✓ |
| $612 / $525 at 6% | — | 9000/14.714 = 611.7 ✓; 9000/17.132 = 525.3 ✓ |

Book-choice objection does **not** land: the on-disk book is the post-T23
2,437-trade book (`145d564e`), which supersedes the 2,595-trade post-T0 book
(`9edd2ba7`, max DD 32.43R per `research/t0_ratified_rebaseline.md:43`). The claim
used the current book. `DIRECTION.md:20,27` still quotes 2,595 / +1,422R and is the
stale artifact — as the claim itself flags in its §5.

## 2. What refutes it — the DD lock, stated in the cited evidence itself

`research/g4_prop_fit.md:24` is the row literally titled **"DD lock"**:

| firm | floor | **lock (same row, same file)** |
|---|---:|---|
| Apex $150K EOD 4.0 | $4,000 | *"at start bal.; payout safety net = DD+$100 (+$4,100)"* |
| Topstep $150K MLL | $4,500 | *"MLL locks at $0 once +$4,500"* |
| MFF Pro $150K | $4,500 | *"locks at start+$100 once +$4,600"* |

`risk_of_ruin.py:5` — the other cited source — says the same for Vanquish:
*"Funded: floor locks once equity >= start + 5.75% ($8,625 buffer)"*.

None of these is an unconditionally trailing floor. Once the account clears the
buffer the threshold freezes at (near) the start balance, and a peak-to-trough
drawdown taken **at equity +588.60R** cannot bust it. The claim compares a
full-history max drawdown against a floor that stopped trailing 493 sessions
earlier.

**On this book the lock arrives on trading session 3 (2024-08-23) at +15.90R.**
Sessions 1–2 are −2.00R each (the loss halt caps them), so the deepest the curve
goes before locking is **−4.00R, both at day level and at trade level**.

## 3. Re-run with the real rules, $1,000/R

`research/g71_ddverify_lock.py`, trailing floor that stops at each firm's stated buffer:

| floor | claim's verdict | **verdict with the lock** | min headroom |
|---|---|---|---:|
| 4% of $150k ($6,000) | BUST (2.9x) | **SURVIVES** | $2,000 |
| 5% of $150k ($7,500) | BUST (2.3x) | **SURVIVES** | $3,500 |
| 6% of $150k ($9,000) | BUST (1.9x) | **SURVIVES** | $5,000 |
| Apex $150K EOD 4.0 ($4,000) | BUST (4.3x) | **fails — by $0**, session 2, pre-lock | $0 |
| Topstep MLL / MFF Pro ($4,500) | BUST (3.8x) | **SURVIVES** | $500 |
| Vanquish $150k ($7,500) | BUST (2.3x) | **SURVIVES** | $3,500 |

Minimum EOD equity **after** the lock, over the whole two years: **+$15,896**,
i.e. $15,796 of headroom above Apex's locked $100 floor. The 17.13R episode never
comes near any floor.

Largest risk unit surviving each floor on this realized path, lock modelled:

| floor | claim ($/R, EOD / intraday) | **lock-modelled $/R** | ratio |
|---|---|---:|---:|
| 4% $6,000 | $408 / $350 | **$1,475** | 3.6–4.2x |
| 6% $9,000 | $612 / $525 | **$2,225** | 3.6–4.2x |
| Apex $4,000 | $272 / $233 | **$975** | 3.6–4.2x |
| Topstep/MFF $4,500 | $306 / $263 | **$1,100** | 3.6–4.2x |

## 4. Three further defects, independent of the lock

1. **The multipliers are computed off the wrong series.** "2.9x" = 17,132/6,000
   and "4.3x" = 17,132/4,000 both use the **intraday** DD, while the rows are
   labelled EOD and `g4_prop_fit.md:24-25` explicitly **excludes** intraday-trail
   variants for both Apex and MFF ("*Intraday-trail variant … excluded*",
   "*Rapid plan is 4% intraday — excluded*"). The like-for-like EOD figures are
   14,714/6,000 = **2.45x** and 14,714/4,000 = **3.68x**. `g71_drawdown_audit.py`
   prints its BUSTS verdict off `dd_day` but the md table's multipliers off
   `dd_trade` — the two columns of that table are not the same measurement.
2. **"Two independent methods agree" is false.** `g4_prop_fit.md`'s $250–$525 comes
   from `funded_survival()`-style Monte Carlo of **pre-lock** ruin over 20k random
   orderings — explicitly a lock-aware model of the first few thousand dollars.
   The claim's $350–$612 comes from a **lock-blind** full-history max drawdown.
   They measure different quantities; landing in the same decade is coincidence,
   not corroboration.
3. **The stated numbers are not a bound either way.** −4.00R pre-lock is one
   realized ordering, and the book's worst single day is −5.78R (2026-06-26). A
   book that opened on that day would bust Apex at $700/R. The single-path number
   is as unsafe in the permissive direction as the max-DD number is in the
   restrictive one. Monte Carlo over orderings (which `g4_prop_fit.py` already
   does) is the only correct sizing method here; neither this verify nor the claim
   supersedes it.

## 5. What survives of the claim

- 17.13R / $17,132 trade-level and 14.71R / $14,714 day-level max drawdown: **correct**.
- The chart's auto-scaling making dip size uninformative: **untested here, unchallenged**.
- The 18-deep concurrency and 22.50R instantaneous open risk: **untested here**.
- "The risk unit is a few hundred dollars": **may still be true**, but not for the
  reason given — it rests on `g4_prop_fit.md`'s pre-lock RoR, not on this curve's
  max drawdown, and this track supplies no independent support for it.
