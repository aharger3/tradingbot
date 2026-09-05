# g208 — vault corrections (OMEN 9.0 wave 2, W8)

Every stale line the morning report's §7 named now carries a dated correction next to it — nothing
was deleted or un-checked, and `CLAUDE.md` gets the precision-footnote decision from W8's row.

## What changed

Nine vault notes touched, one repo file touched, two repos committed.

## Vault: `C:\Users\aharg\Austin's Vault` (git repo)

| file | line(s) touched | what the correction says |
|---|---|---|
| `Projects/omen-next-session.md` | 226 (Alpaca "cleared") | both pairs went dead (401), then fresh keys pasted 01:45 and confirmed working via `broker/test_alpaca_paper.py` |
| `Projects/omen-next-session.md` | §1 "the real-money blocker" (~40-58) | `grade == "A+"` live gate already replaced by `a53c2c93`; section stale |
| `Projects/omen-next-session.md` | T2 "Moves: real money. Blocker." (~136-142) | done — `a53c2c93` closed it |
| `Projects/OMEN.md` | 271-277 (revoke Alpaca) | reversed by Austin's own later call — Alpaca paper is the chosen venue, do not revoke |
| `Projects/OMEN.md` | 679 ("B is the only profitable tier") | pre-honest-fill dollar figure, kill it; also moot, live gate no longer trades that ladder |
| `Projects/omen-blockers.md` | 48-51 (sizing blocker "stands") | closed by `a53c2c93` / L5 |
| `Projects/omen-blockers.md` | 120-127 (R6 sizing blocker) | closed by `a53c2c93` |
| `Projects/omen-blockers.md` | 266-275 (sizing blocker, second half) | closed by `a53c2c93` |
| `Projects/omen-blockers.md` | 94-101 (mid-candle "settled ... Dead") | F9 reports the opposite on a larger book, unrefereed, reopened — points to wave 2 W1's referee result |
| `Projects/omen-blockers.md` | 427 (`floor −1.25R` table row) | no clamp exists; max loss is −1R hard, per `stop_rule.py` and `test_runner_stop.py` |
| `Projects/omen-blockers.md` | 572 (Tastytrade re-auth checkbox) | marked `[x]` done — re-ran the done-signal command directly, `validate_credentials()` returned `True`, 2 accounts |
| `Projects/omen-x-board.md` | 142-144 (`floor −1.25R` cost analysis) | describes a rule (`exit_lab.py`'s −1.25R) that is no longer live |
| `Projects/omen-x-board.md` | ~199-202 (live governor A+/A) | replaced by `a53c2c93` |
| `Projects/omen-x-board.md` | 328 (live-governor decision row) | shipped, `a53c2c93` — per-day cap piece not yet built |
| `Projects/omen-2y-backtest.md` | 88 (A+ "what the live path needs") | live path no longer gates on A+ |
| `Projects/omen-2y-backtest.md` | 150 (A+ fired 7/76,019) | fixed by `a53c2c93`; flagged the note's own denominator mismatch (line 84) plus `CLAUDE.md`'s "twice in two years" as three countings of a retired ladder |
| `Projects/omen-2y-backtest.md` | 184-191 (−1R vs −1.25R open question) | settled 2026-09-03 by Austin: −1R, no clamp; question closed, not open |
| `Projects/omen-brief-2026-09-03.md` | 16 (38.7% prop eval pass rate) | superseded — no rung fundable per tonight's `g174_funding_ladder.py`; futures rolling-window figure separately corrected 0%→12-27%, a different quantity |
| `Projects/omen-brief-2026-09-03.md` | 45 (−1.25R floor deletion reverted) | overtaken — no clamp at all, settled −1R hard |
| `Projects/omen-brief-2026-09-03.md` | 56, 63 (R2 mid-candle "Dead"; R5 caveat) | R2 contradicted by F9, unrefereed, reopened; R5's sizing caveat closed by `a53c2c93` |
| `Projects/omen-brief-2026-09-03.md` | 86-87 (−1.25R clamp question; size map question) | both answered 2026-09-03/since: −1R no clamp; S = flat $1,000 |

Human tasks: the Tastytrade checkbox above is the only one this row owns per the spec (`## Wave 2`
W8 names "the two cleared human tasks close" — Alpaca's task lives in the morning report's §6 item
1 with no checkbox in `omen-blockers.md`; only the Tastytrade item is a tracked checkbox there).

## Repo: `CLAUDE.md`

Added the precision footnote under THE LANE, after the honest-ceiling table: lane precision is
graded-day precision on the one-trade-a-day pick (baseline 30.5%, 18/59,
`research/g156_s_classifier_v0.md`); the 39.5% candidate-level figure stays as the secondary read;
the bar is "materially above 30.5% on the pick" until Austin restates it.

## Verification

`python -c "import tastytrade_feed as t; print(t.TastytradeFeed().validate_credentials())"` printed
`True`, 2 accounts (5WI83217, 5WI77845) — re-run directly before marking the checkbox done, not
taken on the morning report's word alone.
