# P12 / G6 — sample floor for report tables

## The floor: 20 trades, reusing `SCAN_MIN`

`research/build_bt2y_report.py`'s edge scanner already refused to rank any slice under 20
trades (`SCAN_MIN = 20`, in place before this change). This task extends that same constant
to the breakdown table instead of inventing a second number. 20 is defensible on its own
terms too: at ~50% win rate and R outcomes in the -1.25..+3 range, a slice's mean R has a
standard error around 1/sqrt(n) of its per-trade spread; below n=20 that error is large
enough that one extra trade can swing the mean by several tenths of an R, which is the same
order of magnitude as the money-gate threshold (2.0R) itself. Above ~20 the swing per
additional trade is small enough that the number starts meaning something. It also matches
what the traded-book histogram in the task actually shows: GOOGL (n=21) clears it, CRM
(n=18) doesn't — the floor lands exactly where the real distribution has a gap, not at an
arbitrary round number.

No second constant was introduced. Both the edge scanner and the breakdown table read the
one `SCAN_MIN`.

## What changed

Before: the edge scanner silently dropped any slice under 20 trades (a documented behaviour,
but still a delete). The breakdown table had no floor at all — every dimension, including
per-symbol, rendered every slice at equal visual weight regardless of n.

After, in both tables:
- Every slice still renders — nothing is hidden.
- A slice under 20 trades gets a `low n` badge (tooltip: "fewer than 20 trades -- too few
  for this number to mean anything") and its row is dimmed (`opacity:.55`, class
  `lowsample`).
- Sub-threshold rows always sort after every trustworthy row, regardless of which column is
  clicked (breakdown table) or how large the slice's delta-R looks (edge scanner) — a
  2-trade slice can no longer top a leaderboard on a lucky mean.
- The scanner's old "no slice reaches 20 trades" empty-state text was replaced with "no
  trades in selection", since slices no longer disappear at the floor.
- Both sections gained a plain-language note explaining what the badge means, and the page
  footer gained one line doing the same.
- All new colour is the existing `--warn` token (used via `color-mix`), no raw hex added;
  the badge and dimmed-row styles are defined once at `:root` scope like everything else, so
  both themes pick them up automatically.

## Before / after on the current corpus

Traded-book symbol breakdown (27 symbols): **9 of 27** now carry the `low n` badge and sort
to the bottom — SPCX, CRM, AAPL, BABA, QQQ, IWM, SPY, ACHR, SOFI. The other 18 (HOOD, MU,
COIN, PLTR, TSLA, AMD, ORCL, IREN, AVGO, META, INTC, NVDA, UBER, NFLX, TSM, MSFT, AMZN,
GOOGL) render as before. Verified with a Node DOM-stub harness (see below) run against the
real embedded dataset, sorting the symbol breakdown by total R: every trustworthy row
appears before every low-n row in the rendered HTML, confirming the sort guarantee holds
against real data, not just a hand-built fixture.

## Verification performed

- `python research/build_bt2y_report.py` — writes clean, no traceback.
- Output size: 6.3 MB (`research/omen-2y-backtest.html`), well under the 16 MB artifact cap.
- A throwaway DOM-stub harness (Node, fake `document`, kept out of the repo per the task's
  instructions — scratchpad only) `eval`'d the page's inline script against the real
  embedded JSON and confirmed: the script completes with no thrown error, the breakdown and
  scanner tables both render `class="badge low"` / `class="lowsample"` markup, and the
  symbol breakdown's row order (sorted by Total R, the default) has all 9 low-n symbols
  strictly after all 18 trustworthy ones.
