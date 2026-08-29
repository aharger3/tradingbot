# T11 -- be-on-movement (R11)

Script: `research/t11_be_on_movement.py`. Regenerate the FULL 2-year book with
`python research/t11_be_on_movement.py --days 730` (~28 symbols x ~500 sessions
x 5 arms, ~15-20 min).

**SCOPE OF THE NUMBERS BELOW: a 60-day / 41-session window (`--days 60`), NOT
the full 2-year ratified book.** A `--days 730` run was started and left
running in the background for the full book but did not finish inside this
session's time budget; it was not killed, but its output was not captured
before this report had to be written, so it is not represented here. The
60-day numbers below are real (not fabricated -- see method rule 6) but are a
small, recent-only slice: three trading months (3/3 green here is on 3
months, not the money-gate's 25-month durability bar), and the held-out
recall probes below score 0/34 and 0/40 simply because none of the probe
corpus's marked days fall inside this 60-day window -- that is a coverage
artifact of the short window, not a recall finding. **Re-run with `--days
730` before trusting this table as the money-gate answer**; the lever itself
(the code change in `backtest_week.py`) is complete and correct independent
of which window measures it.

Austin, months ago, never run until now: *"if we dont hit price target 1, we dont raise the stop to BE, but we need to run stats on with enough movement raising to BE"*. Base case kept: *"can still focus on first PT move to BE"* -- that is the `pt1` arm below, and it is what ships.

Only the stop-to-breakeven TRIGGER varies. The PT1 partial scale-out (`backtest_week.py`'s F1 ladder, `hod_then_runner_be`) is unchanged in every arm -- this measures WHEN the runner's stop moves to entry, not whether it scales.

## Money gate

| arm | N | mean R | median R | win rate | worst | best | total R | months green | vs pt1 (mean R) |
|---|---|---|---|---|---|---|---|---|---|
| pt1 | 262 | 0.7049 | -1.0000 | 44.7% | -1.000 | 12.475 | 184.68 | 3/3 | baseline |
| mfe_0.50 | 242 | 0.7100 | -0.1110 | 39.7% | -1.250 | 12.475 | 171.81 | 3/3 | +0.0051 (inside bar (NULL)) |
| mfe_0.75 | 247 | 0.6747 | -0.1200 | 40.1% | -1.250 | 12.475 | 166.66 | 3/3 | -0.0302 (inside bar (NULL)) |
| mfe_1.00 | 251 | 0.6645 | -0.1177 | 41.4% | -1.250 | 12.475 | 166.80 | 3/3 | -0.0404 (inside bar (NULL)) |
| mfe_1.25 | 252 | 0.6434 | -0.1308 | 41.3% | -1.250 | 12.475 | 162.14 | 3/3 | -0.0615 (inside bar (NULL)) |

Error bar carried forward from T0 (±0.1725R, 95%): an A/B narrower than this reported as inside its own bar is a null result per method rule 1. This track did not re-derive its own bar (no bootstrap run here) -- treat any move under ~0.17R as unproven, not as "no effect".

## Where the movement-trigger's breakeven came from (mfe arms)

Of trades whose stop was raised to breakeven, how many got there from the movement threshold BEFORE the PT1 (causal-HOD) rung ever printed, vs. from PT1 itself (same accelerator as the baseline), vs. never got raised at all:

| arm | mfe_before_pt1 | pt1_or_after | never_be |
|---|---|---|---|
| mfe_0.50 | 116 | 96 | 30 |
| mfe_0.75 | 99 | 99 | 49 |
| mfe_1.00 | 77 | 104 | 70 |
| mfe_1.25 | 68 | 104 | 80 |

## Held-out recall (method rule 2)

This lever changes stop MANAGEMENT on trades already entered -- it cannot change which signals fire, their entry, or their stop. Recall is measured once (against the `pt1` arm's fired set) and is identical for every arm by construction; reported here so the gate is not silently skipped, not because it is expected to move.

- Held-out S sweep: 0/34 (0.0%)
- Veto verdicts fired-on, by his verdict: {'a': '0/4', 'no': '0/27', 'c': '0/4', 's': '0/5'}

## Reading the table

**Null result:** every `mfe_*` arm sits inside the ±0.1725R bar against `pt1`. Raising the stop to breakeven earlier, on plain favourable excursion instead of waiting for PT1, does not move mean R on this book by more than noise.

Ships: `pt1` stays the default (`BE_TRIGGER=pt1` in `backtest_week.py`) per R11 -- "can still focus on first PT move to BE". `BE_TRIGGER=mfe` + `BE_MOVE_R=<0.5|0.75|1.0|1.25>` is available as a flag, OFF by default, for whichever arm above clears its bar.

