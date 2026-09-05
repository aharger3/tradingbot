# g160 refuter #3 (reproduce from the script) — NOT REFUTED

**What is different now:** I reran `research/g160_tweak_grid.py` from scratch and the regenerated
`research/g160_tweak_grid.json` is byte-identical to the committed one, every one of the 33 rows in
`research/g160_tweak_grid.md` matches the console output, and the operative conclusion — *no arm,
baseline included, is positive in both H1 and H2, so O2 ships defaults unchanged* — **survives two
independent methodology fixes that each should have broken it**. Two supporting sentences in the
report are nonetheless wrong and need correcting.

Fill contract for every number below: book `research/bt2y_trades_retest_on.json`, meta
`entry_fill: "close"` / `entry_misses: 0` (signal-bar CLOSE entry), stops via `stop_rule`
(`STOP_ON_CLOSE=True`, `DISASTER_STOP_R=1.0`), size-gated through
`omen_metrics._row_is_sizeable` → `signal_runner.min_risk_floor`, 1R = $1,000, H1/H2 split at
2025-09-01 (249/249 sessions). Scripts named per claim.

## 1. Reproduction: identical

| check | result |
|---|---|
| `python research/g160_tweak_grid.py` rerun, JSON compared `==` to committed | **IDENTICAL** |
| baseline `first_of_day_arm`: ev_r 0.034 / H1 +0.136 / H2 −0.068, $33.9/day, 13/25 green, 46.4% | **matches** |
| best full-book arm (one_and_done, 09:45, veto1d=on, s_only): 0.064 / +0.236 / −0.062, $11.2/day, 51.1%, 15/23 | **matches** |
| every one of the 32 grid rows' ev_r_H2 negative | **confirmed** |
| `S_CLASSIFIER` moves ≤3 trades per arm (max delta 723→720) | **confirmed** |
| `fire_A_when_no_S_by_10` inert at 09:45 — identical rows | **confirmed**, and sound by construction: `et <= "09:45"` can never satisfy `et >= "10:00"` |

Book: 498 sessions (2024-09-03..2026-09-02), 8,227 eligible candidate rows, `sgrade` C 4,705 /
A 2,115 / S 1,407, `spy_trend` bull 5,399 / bear 2,827 / n-a 1. No missing fields except `close`
(absent on all 8,227 rows, so `_row_is_sizeable` falls back to `close = entry` — correct for this
book, whose fill *is* the close; no effect on the gate).

## 2. Attack A — the grid carries the pick-then-gate bug the baseline does not

`build_arm()` selects on tier/window/veto and lets `ev_r_scoreboard` drop unsizeable rows
*afterward*. `first_of_day_arm` does the opposite: since omen-8 ticket 12a (2026-09-03) it runs
`_row_is_sizeable` **inside** selection and falls through to the next tradeable candidate. So the
baseline loses 0 days to the gate while the report's best arm silently loses **11 of its 99 picks
(11%)** — the exact bug the codebase documents as fixed, reintroduced in the arm it is compared
against.

Rebuilt the whole 32-row grid with the gate inside selection. It moves real numbers — n 151→156,
406→446, 953→1020; ev_r up to +0.010; one arm's green months 8/25→9/25 — and **every single H2
stays negative**. Best arm is unchanged at 0.064 / +0.236 / −0.062.

## 3. Attack B — `VETO_1D` runs on a feature this repo already blacklists

`backtest_2y.spy_context()` sets `spy_trend = "bull" if closes[i] >= fmean(closes[max(0,i-19):i+1])`
— today's close compared against an SMA window that **contains today's close**. At 09:45 ET that is
not knowable. `research/g81_htf_thesis.py:172` names this exact field and this exact line: *"it
knows the answer. That is exactly the bug class this file exists to avoid."* `research/g110_time_of_day.py`
lists `spy_trend` in `EXCLUDED_LOOKAHEAD` per MASTER_SPEC.md sec4. The one lever g160 endorses is
built on it, and g160 does not say so.

Substituted the **prior** session's `spy_trend` (causal; differs from same-day on 55 of 497
sessions, 11.1%) on the report's best cell:

| veto | n | ev_r all | ev_r H1 | ev_r H2 | $/day | win% | green |
|---|---:|---:|---:|---:|---:|---:|---:|
| off | 151 | +0.006 | +0.083 | −0.061 | $2.0 | 45.7% | 14/25 |
| on, same-day (g160 as written, lookahead) | 88 | +0.064 | +0.236 | **−0.062** | $11.2 | 51.1% | 15/23 |
| on, prior-day (causal) | 82 | **+0.108** | +0.275 | **−0.029** | $17.8 | 53.7% | 14/22 |

The lookahead is real and undisclosed, but it is **not** what makes the veto look good — the honest
version is *better*, and its H2 is still negative. The conclusion holds under the correction.

## 4. Multiplicity

32 rows are only **16 distinct arms**, and only **12 distinct results**: `fireA` is inert at the
09:45 window, so 8 rows are exact duplicates of their `fireA=off` twins. Multiplicity inflates false
*positives*; this is a negative result, so sweeping more arms and still finding none positive in both
halves makes the null **stronger**, not weaker. There is no best-of-N selection to correct here
because nothing was selected.

## 5. Residual lookahead, confined and harmless

`first3_loss_halt` halts on `r < 0` of an earlier pick without checking that pick had exited. Using
`et + bars`, **134 of 529 consecutive pick pairs (25%)** enter before the prior trade's exit bar — so
the halt consults an outcome not yet known. This flatters the halt arms only; they all lose anyway,
and the report's highlighted best arm is `one_and_done` (one pick/day), which is clean of it.

## 6. Two sub-claims that are wrong

- **"`VETO_1D=on` beats off on ev_r_all *and win%* in every matched pair"** (g160_tweak_grid.md,
  "Reading it straight"). ev_r_all holds **16/16**. Win% **falls in 8 of the 16 matched pairs** —
  every 11:00-window pair, e.g. 44.1→43.2, 42.4→41.1, 42.1→40.6. The lever helps win% only at the
  09:45 window.
- **"at the cost of roughly a third of the fires"**. Actual spread is **7% to 44%** (433→403 is 7%;
  193→109 is 44%). "~1/3" describes the middle of a wide range, not the range.

## Verdict

**NOT REFUTED.** The claim reproduces exactly, and its conclusion is robust to the pick-then-gate
fix and to replacing the lookahead veto with a causal one. O2 should ship the four flags with
**defaults unchanged**, as g160 recommends. Correct the two sentences above, and add the
`spy_trend` lookahead disclosure to the `VETO_1D` caveat before anyone treats that lever as
measured — the causal prior-day version (+0.108 ev_r, $17.8/day, H2 −0.029) is the number worth
carrying into a real 1D-veto measurement, not the same-day one.

Scripts: `research/g160_tweak_grid.py` (rerun verbatim). Re-tests in this file were run as
throwaway harnesses over the same book and the same `research/omen_metrics` kernel; every figure
above is reproducible from the committed script plus the patches described in §2 and §3.
