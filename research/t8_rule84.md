# T8 — the 84% re-entry candidates the card deck can never show

> Source deck input: `research/rule84_candidates.jsonl` — the candidate set this row produces. It is the input for the two-bar 84% grading deck Austin asked for: each line is a losing break-and-retest / one-candle-rule entry, its stop-out, and the bar that reclaimed the original entry price — the three bars a single-bar grading card physically cannot hold.

## Metrics

```
rule84_candidates: 2843
rule84_win_rate: 43.5
rule84_avg_R: 0.021
```

- scanned **15785** archived sessions across 33 symbols; 5396 fired break-and-retest / one-candle-rule entries the engine would take.
- 1847 originals hit target (or never stopped before EOD) -> a winner never arms the re-entry.
- 706 stopped out but never reclaimed the entry price later that session -> no re-entry to take.
- outcome mix: {'loss': 1543, 'win': 1238, 'scratch': 62}  (setup: {'break_and_retest': 2620, 'one_candle_rule': 223}  grade: {'B': 2119, 'C': 654, 'A': 50, 'A+': 20}  dir: {'put': 1363, 'call': 1480})

## What the 84% rule is, in plain English

The 84% rule is a do-over for a trade that already failed. You take a break-and-retest or one-candle-rule entry, it stops you out, and then price turns around and closes back at the price you originally got in. The rule says: take the trade again, with the same stop and the same target. The claim is that the first loss was bad timing, not a bad idea — the setup was right, the entry was early — so the second bite works far more often than a cold entry.

## Why it never showed up in the grading decks

Every card the deck has ever shown Austin is one bar: here is a bar, what would you do? The 84% rule is not a one-bar question. It needs the first entry, the bar that stopped it out, and the later bar that closed back through the original entry price — three bars tied together by a loss in between. A grading card that shows a single bar has no way to ask about that, so the deck has never put one in front of him, and nothing in the archive has ever reported how often the pattern is even there. This scan is the first time that set exists.

## Are these candidates worth arming?

The 2843 candidates ran **43.5%** to target (1238 of 2843) at an average of **0.021R**. For context, the rule's own claim is an 84% hit rate. Measured against the engine's actual break-and-retest and one-candle-rule losers in the archive, the re-entry does not land near that — these are the trades the deck was never shown, graded cold by the geometry alone.

The average R and win rate do not clear the bar the rule sets for itself, so on the evidence here there is no case for arming it. This row measures only and does not change any trading gate; the two-bar deck built from this list is what lets Austin see these on his own charts and settle it.

## Method

- Detection: `research/t4_engine_recall.run_day` — the harness's own replay of `signal_runner.SignalRunner.detect_signals` (bar-by-bar, 11:00 entry cutoff, 30-bar per-idea dedupe, archive-reconstructed PDH/PDL/PMH/PML/HTF bias). Every fired break-and-retest and one-candle-rule entry, all grades (not S-only).
- Original trade: entered at the entry bar's close, stop at the setup's own stop, 2R target; walked forward to the first bar that touches the stop before the target (stop wins a same-bar tie, as in the backtest). A trade that hits target first, or is still open at the session close, never stopped out and so never arms — no candidate.
- Reclaim: the first bar from the stop-out bar forward whose CLOSE is at/above the original entry price (at/below for shorts), same session.
- Re-entry R: taken at the reclaim close with the ORIGINAL stop and target, simulated forward to its own stop (-1R), target (+R), or the session close (signed partial R). `rule84_win_rate` is the fraction that hit target; `rule84_avg_R` is the mean signed R over all candidates.
- This row measures only. It does not arm RULE84 and changes no trading gate; `python research/regression_gate.py` is unchanged.
