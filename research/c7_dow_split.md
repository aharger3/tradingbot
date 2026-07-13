# C7 — day-of-week split + Friday deep-dive (12mo baseline)
Baseline: 671 traded / 866 signals incl alert-only  251W 419L 37.5%W $78,190

## Full-pop per weekday (traded A+/A/B only)
day     tr    W    L   win%        P&L   avgPnL
Mon    115   39   75  34.2% $    3,833 $   33.3
Tue    137   47   90  34.3% $    2,412 $   17.6
Wed    160   62   98  38.8% $   23,121 $  144.5
Thu    105   46   59  43.8% $   32,571 $  310.2
Fri    154   57   97  37.0% $   16,253 $  105.5
ALL    671  251  419  37.5% $   78,190

## Tier (S>=4+[hammer], max 2/day, stop-green): 78 tr  42.3%W  $21,000/yr

## Tier per weekday (split of trades the tier accepts)
day     tr    W    L   win%        P&L  %tier
Mon     13    6    7  46.2% $    5,000    17%
Tue     14    4   10  28.6% $   -2,000    18%
Wed     17    7   10  41.2% $    4,000    22%
Thu     12    8    4  66.7% $   12,000    15%
Fri     22    8   14  36.4% $    2,000    28%

## Friday deep-dive (full-pop, n=154)
Friday: 154 tr 37.0%W $16,253  (vs non-Fri 517 tr 37.6%W $61,937)

Friday by entry-time band:
band           tr   W   L   win%       P&L
pre-10:30     132  50  82  37.9% $  18,000
10:30-11:30    22   7  15  31.8% $  -1,747

Friday within tier: 22 tr 36.4%W $2,000 (vs non-Fri tier 56 tr 44.6%W)

## Friday-next-week-contracts rule (DOCUMENT ONLY — D1 not run)
Rulebook hard rule: on Fridays, trade NEXT WEEK's expiry, not same-day /
this-week. Current expiry selection in options_sizer.py (READ-ONLY):
  - default (SCARFACE_CONTRACT=False): nearest_expiration() — 0DTE if before
    14:30 ET on a weekday, else next weekday. On a Friday <14:30 this returns
    TODAY (same-day 0DTE), the opposite of the rule.
  - SCARFACE_CONTRACT=True (D1, not yet measured): weekly_expiration() =
    nearest Friday; on a Friday it returns TODAY (this week's weekly = today),
    also NOT next-week.
Encoding it would require (do NOT encode now — D1 owns SCARFACE_CONTRACT):
  - In weekly_expiration(), if today.weekday()==4 (Fri), return today + 7d
    (next Friday) instead of today. One-line guard.
  - OR a separate FRIDAY_NEXT_WEEK flag layered on whichever path D1 lands,
    so the rule survives even if D1 keeps SCARFACE_CONTRACT=False (then it
    applies to nearest_expiration: on Friday shift to next weekday's weekly).
  - Live: only matters for symbols without daily expirations; TSLA/NVDA 0DTE
    same-day is the measured baseline. Premium/delta shift unmeasured → D1.

## Verdict
Full-pop best day: Thu 105 tr 43.8%W $32,571
Full-pop worst day: Tue 137 tr 34.3%W $2,412
Tier best day: Thu 12 tr 66.7%W $12,000
Tier worst day: Tue 14 tr 28.6%W $-2,000
Friday avg $/trade $106 vs non-Fri $120 (Δ $-14/trade)
Full-pop P&L spread best→worst weekday: $30,160

Friday rulebook question: Friday is NOT materially worse — avg $106/trade vs $120 non-Fri (Δ $-14, within noise). Friday next-week-contract rule is a live-sizing/encoding concern for D1, NOT a win-rate lever — no edge to flag there.

Day-of-week edge: Thu $32,571 / Tue $2,412 spread is large ($30,160) but tier per-weekday n=12-22 is overfit-prone (C6 precedent: n<5 flagged). Skip-Tuesday-at-tier would cut 14 tr −$2k; skip-Thursday would forfeit 12 tr +$12k (66.7%W) — NOT a gate to ship blind.

C10 flag: WATCH only — no weekday gate to live config from this. If C10 wants a weekday rule, walk-forward (F1) MUST validate Thu-good/Tue-bad out-of-sample before trust; treat as same overfit risk class as C6's per-symbol list.
