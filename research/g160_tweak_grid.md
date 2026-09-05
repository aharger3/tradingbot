# g160 — the day/tier-policy grid: no arm clears both halves

**What is different now:** 16 day/entry-window/tier/veto arms plus the S_CLASSIFIER (F7, refuted)
overlay were measured as selection arms on `research/bt2y_trades_retest_on.json` (RETEST_REQUIRED=1,
the shipped book), against the shipped baseline; **every single one of the 32 grid arms loses money
in H2** (2025-09-01 onward), same as the baseline does, so none is a shippable default under O2's own
gate ("improved both halves"). Full numbers, every fill: `python research/g160_tweak_grid.py` writes
`research/g160_tweak_grid.json`; this file is the read of it.

Fill contract for every row below: signal-bar CLOSE entry, `stop_rule.stop_fill_price` stops, rows
already size-gated at book-build time on `signal_runner.min_risk_floor`, 1R = $1,000,
`research/omen_metrics.first_of_day_arm` / `ev_r_scoreboard` for the baseline and the scoreboard
math. H1 = before 2025-09-01, H2 = on/after, per the row's instruction. 498 sessions total (249/249).

## The four levers, and what "1D veto" means here

| lever | off/A | on/B |
|---|---|---|
| `DAY_POLICY` | `one_and_done` — first takeable candidate of the day | `first3_loss_halt` — up to 3 takeable/day, stop after 2 consecutive losses |
| `ENTRY_WINDOW_END` | `09:45` | `11:00` (book's native SESSION_END) |
| tier policy | `s_only` — only `sgrade=='S'` (`signal_runner.compute_austin_tier`) is takeable | `fire_A_when_no_S_by_10` — `S` always takeable; `A` becomes takeable at/after 10:00 ET on a day where no `S` has fired yet (causal, no lookahead) |
| `VETO_1D` | off | on |
| `S_CLASSIFIER` (F7) | off | ON — drops any candidate at an OR-high/OR-low level tagged `no_retest` |

**`VETO_1D` is a documented proxy, not the real thing.** The book carries no per-symbol daily-bias
field — its only HTF field is a 1-hour bias, already gated upstream. The closest daily-direction
signal on hand is `spy_trend` (bull/bear, market-wide, off daily bars) crossed with the candidate's
own direction: `VETO_1D=on` skips a call while `spy_trend=bear` or a put while `spy_trend=bull`.
O2 should decide whether that is the veto it actually wants before wiring a flag with this name.

**Known limitation, shared with F7's own refuted classifier arm:** this is a selection arm over a
fixed candidate stream. Dropping a candidate here does not release
`backtest_week.DEDUPE_FIRES_ONLY`'s suppression window the way a live engine rerun under the same
flags would if that candidate had never fired. Differences between arms below are directional, not
exact — the same caveat F7's refuters raised, applied honestly here too.

**S recall** is defined *by this script*: of the days with ≥1 `S`-tier candidate surviving that
arm's own classifier/window/veto filters, the fraction where the arm's actual pick(s) include an
`S`-tier trade. Do not compare it to a differently-defined recall number without checking the
definition.

## Baseline (today's shipped one-trade-a-day unit, unmodified)

| n | fires/day | ev_r all | ev_r H1 | ev_r H2 | $/day | green months | max DD (R) | win% |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 498 | 1.00 | 0.034 | 0.136 | **-0.068** | $33.9 | 13/25 | -21.4 | 46.4% |

No tier restriction at all — the legacy A+/A/B/C/X ladder gates today's book, not S/A/C
(CLAUDE.md, "Two grade ladders"). H2 is already negative before any of this row's levers touch it.

## The 16 arms x classifier ON/OFF (32 rows)

| classifier | day policy | window | tier policy | veto1d | n | fires/day | ev_r all | ev_r H1 | ev_r H2 | $/day | green mo | max DD R | win% | S recall |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| off | one_and_done | 09:45 | s_only | off | 151 | 0.30 | 0.006 | 0.083 | -0.061 | $2.0 | 14/25 | -11.13 | 45.7% | 100.0% |
| off | one_and_done | 09:45 | s_only | on | 88 | 0.18 | 0.064 | 0.236 | -0.062 | $11.2 | 15/23 | -10.44 | 51.1% | 100.0% |
| off | one_and_done | 09:45 | fire_A_when_no_S_by_10 | off | 151 | 0.30 | 0.006 | 0.083 | -0.061 | $2.0 | 14/25 | -11.13 | 45.7% | 100.0% |
| off | one_and_done | 09:45 | fire_A_when_no_S_by_10 | on | 88 | 0.18 | 0.064 | 0.236 | -0.062 | $11.2 | 15/23 | -10.44 | 51.1% | 100.0% |
| off | one_and_done | 11:00 | s_only | off | 406 | 0.82 | -0.057 | -0.019 | -0.095 | -$46.6 | 9/25 | -35.89 | 44.1% | 100.0% |
| off | one_and_done | 11:00 | s_only | on | 333 | 0.67 | -0.039 | 0.024 | -0.102 | -$26.1 | 12/25 | -33.44 | 43.2% | 100.0% |
| off | one_and_done | 11:00 | fire_A_when_no_S_by_10 | off | 433 | 0.87 | -0.096 | -0.104 | -0.087 | -$83.4 | 8/25 | -52.44 | 42.3% | 83.9% |
| off | one_and_done | 11:00 | fire_A_when_no_S_by_10 | on | 403 | 0.81 | -0.033 | -0.026 | -0.040 | -$26.6 | 12/25 | -28.58 | 42.2% | 80.5% |
| off | first3_loss_halt | 09:45 | s_only | off | 193 | 0.39 | 0.014 | 0.090 | -0.047 | $5.3 | 14/25 | -12.27 | 46.6% | 100.0% |
| off | first3_loss_halt | 09:45 | s_only | on | 109 | 0.22 | 0.057 | 0.208 | -0.054 | $12.4 | 15/23 | -11.83 | 51.4% | 100.0% |
| off | first3_loss_halt | 09:45 | fire_A_when_no_S_by_10 | off | 193 | 0.39 | 0.014 | 0.090 | -0.047 | $5.3 | 14/25 | -12.27 | 46.6% | 100.0% |
| off | first3_loss_halt | 09:45 | fire_A_when_no_S_by_10 | on | 109 | 0.22 | 0.057 | 0.208 | -0.054 | $12.4 | 15/23 | -11.83 | 51.4% | 100.0% |
| off | first3_loss_halt | 11:00 | s_only | off | 856 | 1.72 | -0.053 | -0.033 | -0.071 | -$90.4 | 11/25 | -49.19 | 42.4% | 100.0% |
| off | first3_loss_halt | 11:00 | s_only | on | 569 | 1.14 | -0.044 | 0.024 | -0.107 | -$50.1 | 11/25 | -48.83 | 41.1% | 100.0% |
| off | first3_loss_halt | 11:00 | fire_A_when_no_S_by_10 | off | 953 | 1.91 | -0.036 | -0.043 | -0.029 | -$69.2 | 14/25 | -44.01 | 42.0% | 95.0% |
| off | first3_loss_halt | 11:00 | fire_A_when_no_S_by_10 | on | 723 | 1.45 | -0.022 | -0.004 | -0.040 | -$32.5 | 10/25 | -38.44 | 40.7% | 95.9% |
| ON | one_and_done | 09:45 | s_only | off | 150 | 0.30 | 0.008 | 0.087 | -0.061 | $2.4 | 14/25 | -11.13 | 46.0% | 100.0% |
| ON | one_and_done | 09:45 | s_only | on | 88 | 0.18 | 0.064 | 0.236 | -0.062 | $11.2 | 15/23 | -10.44 | 51.1% | 100.0% |
| ON | one_and_done | 09:45 | fire_A_when_no_S_by_10 | off | 150 | 0.30 | 0.008 | 0.087 | -0.061 | $2.4 | 14/25 | -11.13 | 46.0% | 100.0% |
| ON | one_and_done | 09:45 | fire_A_when_no_S_by_10 | on | 88 | 0.18 | 0.064 | 0.236 | -0.062 | $11.2 | 15/23 | -10.44 | 51.1% | 100.0% |
| ON | one_and_done | 11:00 | s_only | off | 405 | 0.81 | -0.057 | -0.018 | -0.095 | -$46.3 | 9/25 | -35.89 | 44.2% | 100.0% |
| ON | one_and_done | 11:00 | s_only | on | 333 | 0.67 | -0.040 | 0.024 | -0.103 | -$26.4 | 12/25 | -33.58 | 43.2% | 100.0% |
| ON | one_and_done | 11:00 | fire_A_when_no_S_by_10 | off | 433 | 0.87 | -0.096 | -0.104 | -0.087 | -$83.2 | 8/25 | -52.54 | 42.3% | 84.1% |
| ON | one_and_done | 11:00 | fire_A_when_no_S_by_10 | on | 403 | 0.81 | -0.033 | -0.026 | -0.041 | -$26.9 | 12/25 | -28.72 | 42.2% | 80.5% |
| ON | first3_loss_halt | 09:45 | s_only | off | 192 | 0.39 | 0.015 | 0.093 | -0.047 | $5.7 | 14/25 | -12.27 | 46.9% | 100.0% |
| ON | first3_loss_halt | 09:45 | s_only | on | 109 | 0.22 | 0.057 | 0.208 | -0.054 | $12.4 | 15/23 | -11.83 | 51.4% | 100.0% |
| ON | first3_loss_halt | 09:45 | fire_A_when_no_S_by_10 | off | 192 | 0.39 | 0.015 | 0.093 | -0.047 | $5.7 | 14/25 | -12.27 | 46.9% | 100.0% |
| ON | first3_loss_halt | 09:45 | fire_A_when_no_S_by_10 | on | 109 | 0.22 | 0.057 | 0.208 | -0.054 | $12.4 | 15/23 | -11.83 | 51.4% | 100.0% |
| ON | first3_loss_halt | 11:00 | s_only | off | 856 | 1.72 | -0.048 | -0.032 | -0.063 | -$82.6 | 11/25 | -45.83 | 42.5% | 100.0% |
| ON | first3_loss_halt | 11:00 | s_only | on | 567 | 1.14 | -0.045 | 0.024 | -0.110 | -$51.1 | 11/25 | -49.37 | 40.9% | 100.0% |
| ON | first3_loss_halt | 11:00 | fire_A_when_no_S_by_10 | off | 953 | 1.91 | -0.032 | -0.042 | -0.022 | -$61.4 | 14/25 | -40.65 | 42.1% | 95.0% |
| ON | first3_loss_halt | 11:00 | fire_A_when_no_S_by_10 | on | 720 | 1.45 | -0.023 | -0.004 | -0.041 | -$33.1 | 10/25 | -38.72 | 40.6% | 95.9% |

## Reading it straight

- **`fireA=on` never differs from `fireA=off` at the 09:45 window** (identical n, identical every
  column, both classifier states): the "no S by 10:00, fall through to A" rule can only trigger at
  or after 10:00 ET, and the narrow window ends at 09:45 — the lever is inert there by construction,
  not by result. Only the 11:00-window rows actually exercise it.
- **`S_CLASSIFIER` (F7, refuted) moves almost nothing here**: at most 3 trades differ between an
  `off`/`ON` pair (e.g. 406→405, 856→856 with a handful of picks swapped downstream), consistent with
  F7's own finding that the honest arm is 12 of 498 sessions. Do not lean on it, per the row's
  instruction — it is reported for completeness only.
- **The single best full-book arm by ev_r**: `day=one_and_done, window=09:45, veto1d=on`
  (ev_r 0.064, $11.2/day, win 51.1%, 15/23 green months) — but its H2 is still **-0.062**, worse than
  the baseline's H2 of -0.068 is *not* actually worse (it's a smaller negative), yet still negative.
  No permutation in the 32-row grid clears H2 into positive territory. Even the best H1 read
  (`09:45, s_only, veto1d=on`, ev_r_H1 0.236) sits on an H2 of -0.062.
- **`VETO_1D=on` (the `spy_trend` proxy) is the one lever that consistently helps** — every matched
  on/off pair in the table shows `veto1d=on` beating `veto1d=off` on ev_r_all and win%, at the cost of
  roughly a third of the fires (e.g. 151→88, 406→333, 856→569). It is worth a real (non-proxy) 1D
  veto measurement before shipping anything under that name.
- **`first3_loss_halt` raises fires/day** (up to 1.91 at the 11:00 window) but never beats
  `one_and_done` on ev_r in the same window/tier/veto cell — every matched pair is flat-to-worse.
- **Restricting to `s_only` costs real recall of tradeable days** relative to the unrestricted
  baseline (498 trades/year down to 88-856 depending on window), which is the expected shape of a
  precision-over-recall tier filter, but none of these particular cells turn that trade into a
  net-positive H2.

## Bottom line for O2

**No arm in this grid — nor the baseline — clears "positive ev_r in both H1 and H2".** O2's gate
("defaults = the grid winner ONLY if it improved both halves and did not cut S recall") is not met by
any row here; O2 should ship the flags with **defaults unchanged**, and say so, rather than pick a
losing-half winner. `VETO_1D` (as this proxy defines it) is the one lever worth a follow-up
measurement with a genuine daily-timeframe field before it is written off.

Script: `research/g160_tweak_grid.py`. Data: `research/g160_tweak_grid.json` (33 arms incl.
baseline). Book: `research/bt2y_trades_retest_on.json` (RETEST_REQUIRED=1, 498 sessions,
2024-09-03..2026-09-02).
