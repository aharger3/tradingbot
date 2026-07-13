# C3 — [disp]/[nodisp]/[chase]/[vwap-] tag split + skip-tag stacking

**Date:** 2026-07-13 · **Source:** `research/c1_off_charts.json` (= `b4_baseline_charts.json`, 671 traded / 866 signals incl. alert-only) · **Script:** `research/c3_tag_split.py` · **Analysis only — no new backtest.**

## Verdict (one line)

**Stacking skip-tags does NOT meaningfully beat S-score alone** — only `tier + skip-[chase]` beats the S>=4+[hammer] baseline on BOTH win% (44.3% vs 42.3%) and $/yr ($23k vs $21k), and that win is marginal (+2pp, +$2k) and drops trade count 78→70. Every other stack loses on $/yr or on both. **[vwap-] is absent from data** (removed 2026-07-11, `signal_runner:354`) so `skip-[vwap-]` is a no-op. Recommendation: skip-[chase] is a plausible live add-on (+$2k, +2pp) but not a real edge gain — it's just filtering 8 bad chase-tier trades; defer to C10, don't ship standalone.

## Data note

- `[disp]` + `[nodisp]` partition **all 671 traded** signals (every B&R card carries exactly one, per OPUS-SPEC #1 at `signal_runner:550/741`): 238 disp / 337 nodisp.
- `[chase]` is a subset tag (86 traded, overlaps disp/nodisp).
- `[vwap-]` = **0 occurrences** — removed 2026-07-11 per `signal_runner:354`. Reported as no-op, no split possible.

## Per-tag split — full population (traded A+/A/B only)

| tag | trades | W | L | win% | P&L |
|---|---|---|---|---|---|
| [disp] | 238 | 85 | 153 | 35.7% | $17,000 |
| [nodisp] | 337 | 129 | 207 | 38.4% | $52,489 |
| [chase] | 86 | 24 | 61 | 28.2% | −$11,511 |
| [vwap-] | 0 | — | — | — | — (removed) |

**Read:** [nodisp] is the money tag full-pop (+$52k, 38.4%W); [chase] is the loser (28.2%W, −$11.5k, matches the `signal_runner:92` comment "chase 28.0%W −$14.5k"); [disp] is middling (35.7%W, +$17k). [disp] vs [nodisp]: nodisp wins on both axes — displacement is *not* a positive selector here (consistent with C1 verdict that the displacement gate hurts).

## Per-tag split — within tier (S>=4+[hammer], n=78)

| tag | of-tier | W | L | win% | P&L |
|---|---|---|---|---|---|
| [disp] | 35 | 13 | 22 | 37.1% | $4,000 |
| [nodisp] | 43 | 20 | 23 | 46.5% | $17,000 |
| [chase] | 8 | 2 | 6 | 25.0% | −$2,000 |
| [vwap-] | 0 | — | — | — | — |

**Read:** Within the tier the split sharpens — [nodisp] tier trades are 46.5%W (+$17k, 43/78 trades = the tier's core), [disp] tier trades dilute to 37.1%W (+$4k), [chase] tier trades are 25.0%W (−$2k, only 8 of 78). The tier's 42.3%W is a blend; nodisp-only would be 46.5%.

## Stacking test — tier (S>=4+[hammer]) vs tier + skip-tag

| config | tr/yr | win% | $/yr |
|---|---|---|---|
| **tier baseline (S-score alone)** | 78 | 42.3% | $21,000 |
| tier + skip-[nodisp] | 36 | 36.1% | $3,000 |
| tier + skip-[disp] | 43 | 46.5% | $17,000 |
| **tier + skip-[chase]** | 70 | 44.3% | $23,000 |
| tier + skip-[vwap-] (no-op, removed) | 78 | 42.3% | $21,000 |
| tier + skip-[nodisp]+[chase] | 31 | 38.7% | $5,000 |
| tier + skip-[disp]+[chase] | 40 | 47.5% | $17,000 |
| tier + skip-[nodisp]+[disp] (=kill B&R) | 0 | — | $0 |

**Beats baseline on BOTH win% and $/yr:**
- `tier + skip-[chase]` — 70 tr, 44.3%W (+2.0pp), $23k (+$2k). ✅ only winner.

**Beats baseline on win% only (loses $/yr):**
- `tier + skip-[disp]` — 46.5%W but $17k (−$4k); cuts 35 trades to drop the disp dilution but the disp tier trades were net +$4k, so skipping them costs money.
- `tier + skip-[disp]+[chase]` — 47.5%W (highest win%) but $17k (−$4k).

**Loses on both / collapses:**
- `skip-[nodisp]` nukes the tier's core (nodisp = 43 of 78 trades, +$17k) → 36 tr, 36.1%W, $3k. Disaster.
- `skip-[nodisp]+[disp]` = no B&R trades left → 0 trades.

## Conclusion

1. **No stack meaningfully beats S-score alone.** The only both-axes winner (`skip-[chase]`) is +2pp win% / +$2k on 8 fewer trades — filtering 8 bad chase trades, not a new edge. Not worth shipping as a standalone config change; candidate for C10's combined-config run if it composes cleanly, but the gain is within noise of a 78-trade sample.
2. **[chase] is a real loser tag** (28.2%W full-pop, 25.0%W in-tier, −$11.5k/−$2k) — the only skip that helps at all. Matches the `signal_runner:92` comment verdict ("chase 28.0%W −$14.5k"). It already stays as TAG-ONLY by decision; skipping it at the tier gate is the cheap lift.
3. **[disp]/[nodisp] are not stackable skip-tags** — [nodisp] carries the tier (+$17k of $21k), skipping it collapses the tier; [disp] dilutes win% but is net-positive, so skipping it raises win% while losing money. Displacement split is non-predictive as a skip filter (echoes C1: keep displacement gate OFF).
4. **[vwap-] is dead** — removed 07-11, 0 occurrences. Remove from future task framing.
