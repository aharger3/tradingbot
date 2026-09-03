# MASTER SPEC — THE EXIT LADDER (OMEN, lane: exits)

Commit of record for the recon numbers: `b26f4b9c` — `research/g99_rung_recon.py` (written and run for this spec; reproduce with `python research/g99_rung_recon.py`, ~4 min, bars cached). Population is g97's: `research/bt2y_trades_retest_on.json`, first-of-day, size-gated on `signal_runner.min_risk_floor` → **444 rows** (54 dropped by the size gate, 0 missing bars).

## 0. What is already measured, and the one number that decides the shape of this build

| fact | count | source |
|---|---|---|
| book books | **+0.038R/trade ($38)** | `research/g97_mfe.py` |
| available while still alive | **+2.141R** (median +1.015R) | g97 |
| best flat target on this book | **4.0R → +0.153R ($153)** | g97 |
| **today's runner target lands INSIDE the 2R target** | **303 / 444 = 68.2%**, median **1.300R**, 79 rows (17.8%) under 0.5R | g99 §1 |
| runner target's source | whole-dollar fallback on **389/444 (87.6%)**; PDH/PDL/PMH/PML on 55 | g99 §1 |
| PT1 (session extreme at the entry bar) | median **0.495R**; equals entry exactly on **14** rows; ≥2R on **41** | g99 §2 |
| a named level exists beyond PT1 | only **220/444 = 49.5%** — PT2 is ABSENT on half the book | g99 §3 |
| the level the setup is keyed to (`level_px`) is ahead of price | **0 / 444** | g99 §4 |
| MFE while alive, conditional on reaching 2R | n=147, median **4.24R** | g99 §5 |

Two of those rewrite the brief.

**(a) `level_px` is behind price on every single row.** In a break-and-retest the level you retested is the level your stop sits on (`backtest_week.py:353-355`: `level_price == stop` for the default `BNR_STOP_MODE="level"`). So "PT2 = the level the setup is keyed to" cannot be implemented as written — it is a target behind the entry. PT2 is redefined below as *the nearest named level strictly beyond PT1*, and Austin gets a chart question to confirm (§7.1).

**(b) The runner bug is not cosmetic.** It touches 68.2% of the book with a median target of 1.30R. Austin's ".41" is a real band, 79 rows deep. It is ranked #1 in the build order and shipped as its own separable arm.

---

## 1. THE LADDER, precisely

All four rungs are **prices**, all causal at the entry bar, all computed by one pure function that never sees a bar after the entry bar.

### 1.1 The contract (this is the seam between two agents; both can start from it today)

New file `levels_ladder.py` (repo root). Pure, deterministic, no I/O, no `Candle`, no network.

```python
Rung = namedtuple("Rung", "price weight name")   # name is for the book stamp only

def build_rungs(entry, stop, direction, *,
                session_extreme,            # PT1 candidate, as-of entry bar
                named_levels,               # {name: price}, causal, may be empty
                weights=(0.30, 0.30, 0.30, 0.10),
                psych_step=1.00,
                psych_tol=("r", 0.25),      # ("r"|"c"|"pct", value)
                pt4_mode="max",             # "max" | "rmult" | "structure"
                pt4_r=4.0,
                min_gap_r=0.20) -> list[Rung]
```

Returns **1 to 4 rungs**, strictly monotonic in the trade's direction, every rung strictly beyond `entry`, weights summing to 1.0. `named_levels` is supplied by the caller and is exactly the causal pool recon enumerated: PDH/PDL (`backtest_week.py:1369`), PMH/PML (`backtest_week.py:1374`), OR high/low (`backtest_week.py:1377-1378`), pivots (`signal_runner.py:1496-1540`, always called with `as_of`), and — only when `LADDER_HTF_PIVOTS=1` — 1h/4h pivots (§5.4). The function never fetches a level; if the caller passes `{}` it still returns a valid ladder.

### 1.2 The rungs

Let `risk = abs(entry - stop)`, `sign = +1` for a call and `-1` for a put, and `R(px) = sign * (px - entry) / risk`.

**PT1 — the near session extreme.** `session_extreme`: `max(c.high for c in candles[:i+1])` for a call, `min(c.low ...)` for a put — the value the engine already computes at `backtest_week.py:1034` / `:1039`. Causal by construction. *Unavailable:* `R(PT1) < min_gap_r` (measured: 14 rows sit exactly at entry, 208 more inside 0.5R). Then PT1 is dropped, not clamped.

**PT2 — the structural level.** The named level with the **smallest** `R` among those strictly beyond PT1 in the trade's direction. *Unavailable on 224/444 rows (50.5%)* — then PT2 is simply absent and the weights renormalize (§1.3). Note from the data: OR high/low **never wins** this slot, because the session extreme at any entry after 09:35 subsumes the opening range by construction. Do not spend code on it beyond including it in the pool.

**PT3 — 2R.** `entry + sign * 2 * risk`, subject to the precedence substitution in §2. Always available. This is the rung that makes the ladder honest: it exists on 444/444 rows, which is why it, not PT2, is the backbone.

**PT4 — the runner.**
- `"rmult"`: `entry + sign * pt4_r * risk` (default `pt4_r = 4.0`).
- `"structure"`: the nearest named level strictly beyond PT3; falls back to `rmult` when there is none.
- `"max"` (**default**): the further of the two.

Why 4.0R is the default and not a guess: among the 147 rows that reached 2R at all, the **median** MFE-while-alive is **4.24R** (g99 §5), and the best flat arm on the same book is 4.0R (g97). Rounded down to 4.0 so the rung is reachable rather than aspirational. Why `"max"` and not `"structure"`: a structure-only PT4 is missing on at least half the book, and a rule that cannot fire is this repo's recurring bug class.

### 1.3 Ordering — enforced, monotonic, and it never crashes

1. Build the candidate set `{PT1, PT2, PT3, PT4}`, dropping any that is unavailable.
2. Drop every candidate with `R <= 0`.
3. Sort ascending by `R`. **The sort is authoritative; the PT labels are cosmetic** and survive only into the book stamp. PT1 ≥ 2R happens on 41/444 rows — after the sort, 2R is simply the first rung on those trades. That is the correct answer, not an error.
4. Coalesce: walk the sorted list and keep a rung only if its `R` exceeds the last kept rung's `R` by at least `min_gap_r`. Ties and near-ties resolve in favour of the **nearer** rung (a target that fills beats one that does not).
5. **Renormalize** the first `k` weights to sum to 1.0, where `k` is the number of survivors. `30/30/30/10` with k=2 becomes 50/50; k=1 becomes 100%. Do *not* dump the leftover into the last rung — that would make the runner the largest tranche, which is the opposite of every one of his sentences.
6. `k == 0` is impossible: PT3 always exists and is always ≥ `min_gap_r` from entry (2.0 > 0.20). Assert it.

---

## 2. THE PRECEDENCE RULE

His words: *"2r level is trumped by HTF levels and whole psych number if one is close"* and *"when 2r falls between a whole psych number target that instead."*

**Rule.** PT3 starts at the 2R price. Collect substitutes: every multiple of `psych_step` (default `1.00`) and every entry in `named_levels`. Keep those whose distance from the 2R price is `<= tol`. If any qualify, **PT3 becomes the qualifying substitute nearest the 2R price** — on either side of it, which is what "falls between" means. Ties: a named level beats a whole dollar (his sentence puts HTF levels first); still tied, the one nearer entry wins. If none qualify, PT3 stays exactly 2R.

**"Close" is a parameter, default `0.25r`, and HE HAS NEVER QUANTIFIED IT.** Not once, in any mark corpus. 0.25R is a placeholder chosen because it is the repo's existing tolerance idiom (`BAR_EXTREME_FRAC`, 25% of the prior candle's range) — that is a reason to write it down, not a reason to believe it. **It must be swept, and the sweep must include the null arm.**

**The sweep (Agent C, `research/ga1_ladder_replay.py --sweep tol`):**

- unit `r` (fraction of risk): `0.00, 0.10, 0.15, 0.20, 0.25, 0.33, 0.50`
- unit `c` (absolute cents): `0.02, 0.05, 0.10, 0.25`
- unit `pct` (percent of entry price): `0.02, 0.05, 0.10, 0.25`
- crossed with `psych_step ∈ {0.50, 1.00}`

**`0.00r` is the null arm and is mandatory.** If it wins, the precedence rule is not real on this book and we say that in one line rather than shipping it.

Every arm reports, alongside mean R: **the number of rows on which the substitution actually changed PT3.** An arm that fires on fewer than 5% of 444 rows cannot have moved the book and must not be reported as "the rule working" — it is noise with a flag on it.

---

## 3. THE RUNNER GUARD

**The bug.** `backtest_week.py:1020-1021` computes `target = entry ± 2*risk`. `backtest_week.py:1032-1043` then computes `runner_tgt` from levels beyond `scale_level` (the session extreme as of entry, which can be a cent away) plus a next-whole-dollar fallback, and **never compares the two**. They are stamped into separate `SimTrade` fields (`:1054`, `:1058`) and never reconciled. `_ladder_bar` exits at `t.runner_target` (`backtest_week.py:735`) with no reference to `t.target`. The 2R target is dead code under any `SCALE_PLAN`.

**How many rows it touches — measured, not assumed:** **303 of 444 first-of-day trades (68.2%)** have `runner_tgt` inside the 2R target. Median runner target **1.300R**. Distribution: 79 rows under 0.5R, 89 in 0.5–1R, 79 in 1–1.5R, 56 in 1.5–2R. The whole-dollar fallback supplies **87.6%** of all runner targets, so this is overwhelmingly a fallback-geometry bug, not a levels bug (`research/g99_rung_recon.py` §1).

**This guard is NOT cosmetic. It is ranked #1 in the build order** — it is a two-line change that touches two thirds of the book, and it is the literal thing Austin complained about (".41 instead of 2.5" — that band contains 79 real trades).

**The fix**, at `backtest_week.py:1043`, gated by `LADDER_RUNNER_GUARD` (default `"0"` = today's behaviour, byte-identical):

```python
if LADDER_RUNNER_GUARD:
    floor_px = entry + 2 * risk if long else entry - 2 * risk
    # a runner nearer than 2R is only allowed when the precedence rule put it
    # there deliberately (within tol of 2R); otherwise it is the fallback bug.
    if R(runner_tgt) < 2.0 - tol_in_r:
        runner_tgt = floor_px
```

Ship it as its own arm and measure it **alone**, before the four-rung ladder exists, so its effect is separable from everything else in this build. Under `SCALE_PLAN=four_rung` the guard is inert by construction (PT3 = 2R is always a rung), so the flag governs only the legacy two-rung plans — which is where the shipped book lives today.

---

## 4. SIZE PLANS

**The two vectors.** `30/30/30/10` (default) and `50/20/20/10`.

Austin wrote *"30/30/30/10 and 50/20/10/10"*. The second sums to **0.90**. The repo's own constant is `50/20/20/10` (`research/exit_lab.py:410`). We ship `50/20/20/10` and put the missing 10% in front of him as a one-word question (§7.4). We do **not** silently renormalize 50/20/10/10 into 55.6/22.2/11.1/11.1 — that is a different plan wearing his number.

**The trending test: do not wire one into the default.** Recon found three causal candidates and none of them has ever been shown, in this repo, to predict intraday follow-through:

- `daily_trend_bias` — yesterday's daily close vs SMA20 (`signal_runner.py:1913-1920`). Causal. Returns `None` on <20 prior sessions.
- `qqq_breaks` — QQQ's first RTH close through its PD/PM levels, timestamped (`live_scanner.py:229-262`). Causal **only** if compared with a strict `<` against the entry bar's timestamp.
- `regime_state` — SPY SMA / VIX (`regime_detector.py`). Computed once at scan start and **never threaded into entry-time code at all** (`live_scanner.py:340-354` uses only the action, discards the label). Any rule branching on it today is unreachable. **Excluded from this build.**

**Verdict: ship both plans as flag arms, default `30/30/30/10`, and let the sweep choose.** `LADDER_TREND_TEST` ships with arms `off` (default) / `daily` / `qqq` as a *measured option only*.

Arm definitions, exactly:
- `daily`: trending ⟺ `daily_trend_bias` aligns with the trade direction (`"bullish"`→call, `"bearish"`→put). `None` counts as not-trending, and the `None` count is printed.
- `qqq`: trending ⟺ the QQQ break timestamp in the trade's direction exists **and is strictly earlier than the entry bar's timestamp**.
- Mapping, from his sentence *"if day is not trending, we want those HOD exits more money quicker"*: trending → `30/30/30/10`; not trending → `50/20/20/10`.

**Reachability gate (mandatory, this repo's recurring bug class):** each arm prints how often it selects the alternate vector across the 444 rows. An arm that fires on **<15% or >85%** of rows is a dead branch and gets **deleted, not shipped**.

---

## 5. FLAG AND FILE PLAN

### 5.1 Flags — all defined in `backtest_week.py`, all `os.getenv`, all added to `research/book_stamp.py::FLAG_SOURCES` **in the same commit that defines them**

| flag | shipped default | arms |
|---|---|---|
| `OMEN_SCALE_PLAN` | unchanged (`hod_then_runner_be`, via the `LADDER_MODE="B"` alias at `backtest_week.py:169-176`) | new accepted value **`four_rung`** |
| `LADDER_RUNNER_GUARD` | `"0"` | `"1"` |
| `LADDER_WEIGHTS` | `"30/30/30/10"` | `"50/20/20/10"` |
| `LADDER_PSYCH_TOL` | `"0.25r"` | suffix `r` / `c` / `%`, values per §2 |
| `LADDER_PSYCH_STEP` | `"1.00"` | `"0.50"` |
| `LADDER_PT4_MODE` | `"max"` | `"rmult"`, `"structure"` |
| `LADDER_PT4_R` | `"4.0"` | `3.0`, `4.0`, `5.0` |
| `LADDER_MIN_RUNG_GAP` | `"0.20r"` | `0.10r`, `0.33r` |
| `LADDER_TRAIL` | `"be"` | `"prev_rung"` |
| `LADDER_TREND_TEST` | `"off"` | `"daily"`, `"qqq"` |
| `LADDER_HTF_PIVOTS` | `"0"` | `"1"` |

**Byte-identical when off:** with `SCALE_PLAN != "four_rung"` and `LADDER_RUNNER_GUARD=0`, not one line of an existing path executes differently. `_ladder_bar` (`backtest_week.py:650-741`) is **not modified** — the four-rung engine is a new sibling function.

**Decided here, not sent to Austin (the `flag_convention` blocker):** a `SCALE_PLAN` value is a **key**, and the logic lives in `backtest_week.py`. `exit_lab.py` stays research-only and gets no runtime path. Reason: `book_stamp.py` reads the effective flags off `backtest_week` (`research/book_stamp.py:51-75`), and a second runtime mechanism would produce books that cannot say which exit engine made them — the exact failure recorded at `research/book_stamp.py:72-74` on 2026-09-02.

### 5.2 File ownership — **two agents never edit the same file**

| agent | owns (exclusively) | job |
|---|---|---|
| **A** | `backtest_week.py`, `research/book_stamp.py` | flags; `SimTrade` fields; `_ladder_bar_4`; the `pnl` rungs branch; the runner guard; the EOD flush |
| **B** | `levels_ladder.py` (new), `levels_htf.py` (new) | `build_rungs` per §1; the precedence rule per §2; 1h/4h pivot construction for `LADDER_HTF_PIVOTS` |
| **C** | `research/ga1_ladder_replay.py` (new), `research/fixtures/ladder_baseline.json` (new) | the exit replay, the sweeps, the reachability counts, the pass-test table |
| **D** | `research/test_exit_ladder.py` (new) | every test in §5.5, written **from this spec**, not from A's or B's code |

**Sequencing that matters:** Agent C generates `research/fixtures/ladder_baseline.json` from commit `b26f4b9c` **before** Agent A's first edit lands. Without that fixture the byte-identical test has nothing to compare against. A imports B's `build_rungs` behind the signature in §1.1 and can stub it locally until B lands; the signature is frozen by this spec.

`signal_runner.py` is **not edited by anyone in this build.** Detection stays byte-identical, and every level the ladder needs is already in `simulate_day`'s scope or importable.

### 5.3 `SimTrade` and P&L (Agent A)

Add, defaulting to the empty state so nothing existing changes (`backtest_week.py:326-366`):

```python
rungs: tuple = ()                                  # (price, weight, name), set only under four_rung
fills: list = field(default_factory=list)          # (weight, price), appended in bar order
```

`pnl` (`backtest_week.py:377-416`) gets a **new first branch**, ahead of the existing `if self.scaled:`:

```python
if self.rungs:
    sign = 1 if self.direction == "call" else -1
    return round(sum(w * sign * (px - self.entry) / risk
                     for w, px in self.fills) * risk_dollars, 2)
```

`risk` stays `abs(entry - stop)` — the **original** risk, never a raised `runner_stop`. At close, `sum(w for w, _ in self.fills) == 1.0`; asserted by a test.

### 5.4 `_ladder_bar_4` — the per-bar algorithm, exact order (Agent A)

1. `stop_lv = t.runner_stop or t.stop`
2. **Disaster stop** (`_disaster_hit`, intrabar touch), only if `stop_lv == t.stop` — same guard and same reasoning as `backtest_week.py:717`. Remaining weight fills at `dz`; close; `_arm_84` only if **no** rung has ever filled.
3. `touched = [r for r in unfilled rungs if _target_hit(c, r.price, long)]`
4. **Stop on the close** (`_stop_hit`): remaining weight fills at `_stop_fill_px(t, c, long, stop_lv)`, clamped to `t.stop` when `PESSIMISTIC_FILL and touched` — identical to `backtest_week.py:725-731`. **No rung on this bar fills. The stop wins the bar.** Close. `_arm_84` only if `stop_lv == t.stop` and no rung filled on an earlier bar.
5. Otherwise fill every rung in `touched`, in order, each at its own price. After the **first** fill in the trade's life, set `t.runner_stop` per `LADDER_TRAIL`: `"be"` → `t.entry`; `"prev_rung"` → the price of the last filled rung. Under `"prev_rung"`, `stop_lv != t.stop`, so step 2's existing condition correctly disarms the disaster stop.
6. All rungs filled → close; `outcome` by the sign of `t.pnl` (same convention as `backtest_week.py:739`).
7. `BE_TRIGGER == "mfe"` arm last, unchanged, so it takes effect next bar.
8. **EOD** (`backtest_week.py:1078-1079`): extend the flush to append the **remaining weight** at `candles[-1].close` before marking `scratch`.

**The −1.25R floor** stays where it lives — `stop_rule.stop_fill_price()` via `_stop_fill_px` — and applies to the remaining weight only. Total R can never breach it, because every filled rung is at `≥ min_gap_r` in profit. A test asserts it anyway, on synthetic cases *and* on every replayed row.

**HTF pivots (`levels_htf.py`, Agent B, `LADDER_HTF_PIVOTS`, default off).** Build 1h and 4h candles from `candles[:i+1]` only (`backtest_12mo.py:37` is the existing hourly aggregator and matches `htf_bias_for`), run `signal_runner.pivot_levels` on each with `as_of` set, dedupe against the named pool at `PIVOT_DEDUPE_FRAC`. This is the **last** item in the build order: it is the only thing that can fill the 50.5% PT2 hole, and it is also the only piece with no prior art in this repo.

### 5.5 Tests — `research/test_exit_ladder.py` (Agent D), and what each asserts

1. `test_shipped_default_byte_identical` — child process with every `LADDER_*` var **popped** from `os.environ` (the pattern at `research/test_runner_stop.py:296-303`); run `simulate_day` over the fixture symbol-days; assert `(entry, stop, exit_price, exit_idx, outcome, pnl)` matches `research/fixtures/ladder_baseline.json` exactly.
2. `test_rungs_monotonic` — 500 randomized cases: strictly monotonic in the trade's direction, every gap ≥ `min_gap_r * risk`, `1 ≤ len ≤ 4`, weights sum to 1.0 ± 1e-9, every rung strictly beyond entry.
3. `test_pt2_missing_folds` — empty `named_levels` still yields ≥2 rungs and renormalized weights. (Reachable: 224/444 real rows.)
4. `test_pt1_at_entry_dropped` — `session_extreme == entry` yields a ladder starting at PT3, never a zero-distance rung. (Reachable: 14 real rows.)
5. `test_precedence_substitutes` — risk 1.00, 2R at 100.00, whole dollar at 100.05: `tol=0.25r` → PT3 = 100.05; `tol=0r` → PT3 = 100.00; named level and whole dollar equidistant → named level wins.
6. `test_stop_wins_the_bar` — a bar touching rung 2 that closes beyond the stop fills **no** rung and books the remainder at `min(fill, t.stop)`.
7. `test_floor_never_breached` — total R ≥ −1.25 on every synthetic case and every replayed row.
8. `test_weights_sum_to_one` — after each exit path (disaster, stop, all-rungs, EOD scratch), filled weights sum to 1.0.
9. `test_runner_guard_reachable` — with `LADDER_RUNNER_GUARD=1`, the guard changes `runner_target` on **≥ 250** of the 444 first-of-day rows (measured 303; the assert is a floor so a bar refresh cannot turn it red for the wrong reason).
10. `test_trend_arm_reachable` — each `LADDER_TREND_TEST` arm selects the alternate vector on ≥15% and ≤85% of rows, else the arm fails and is deleted.
11. `test_htf_pivots_causal` — a pivot whose confirming bars land at or after the entry bar is never returned.

The repo's own gate — `python research/regression_gate.py && python research/test_runner_stop.py` (the `verify:` line) — must stay green throughout. That is the whole-book proof that "off" means off.

---

## 6. THE PASS TEST

Population: the **444** first-of-day, size-gated rows. Rig: `research/ga1_ladder_replay.py` (Agent C) — bar-ordered from `entry_i + 1`, window ends 11:00, stop wins any tied bar, entries and stops frozen. Metric: **mean R per trade**, 1R = $1,000; one trade a day, so $/trade = $/day.

| arm | mean R | $/trade |
|---|---:|---:|
| the book today | +0.038 | $38 |
| flat 1.5R | +0.048 | $48 |
| flat 2.5R | +0.098 | $98 |
| **flat 4.0R — THE HURDLE** | **+0.153** | **$153** |
| ceiling (MFE while alive) | +2.141 | $2,141 |

**The hurdle is 4.0R, not 2.5R.** The brief said a ladder that cannot beat a flat 2.5R is not worth shipping; the honest version is stricter, because on this book the best flat arm is 4.0R and a flat target is a one-line change. **A four-rung ladder that does not beat +0.153R is a more complicated way to make less money and must not ship.**

**PASS requires all four:**

- **P1** mean ≥ **+0.200R/trade** ($200 — 1.31× the best flat arm).
- **P2** median R ≥ **0.000** — the arm is not carried by three trades.
- **P3** green months ≥ the best flat arm's green-month count, **and ≥ 14/25**.
- **P4** the winning arm re-run end to end through `backtest_2y.py` lands within **±15%** of the replay's mean R. The replay cannot see `loss_halt` (`loss_halt.py:87-115`, applied post-collection at `backtest_2y.py:284`) or the 84% re-entry cascade (`backtest_week.py:548-601`, which arms only on a **loss** — so an exit flip silently deletes downstream candidates). If the two disagree by more than 15%, **the backtest's number is the number** and the replay is wrong.

**FAIL-FAST, and it is an acceptable outcome.** If no arm in the entire sweep clears P1, the answer is "the exits were not the lever". Then ship a single-rung `LADDER_PT4_MODE=rmult` flat 4R target (+$115/trade over today's book on its own), write the one line, and close the lane. Do not iterate the ladder into a win.

**Build order, ranked by measured leverage:**
1. `LADDER_RUNNER_GUARD` alone — 303/444 rows, two lines (Agent A).
2. `levels_ladder.build_rungs` + its tests (B, D).
3. `four_rung` engine + P&L (A).
4. Replay + sweeps + pass table (C).
5. `LADDER_TREND_TEST` arms, kept only if reachable.
6. `LADDER_HTF_PIVOTS` **last**.

---

## 7. HUMAN BLOCKERS — six, each answered by pointing at a line on a chart

Nothing below blocks the start of the build. Each has a stated default that runs until he answers.

1. **What is PT2?** Measured: the level the setup is keyed to is behind price at entry on **444/444** rows, so it cannot be a target. *Ask:* 8 cards, each with PT1 (session extreme) and every named level beyond it drawn and labelled — "circle the line that is your PT2." *Default until answered:* nearest named level beyond PT1.
2. **How close is "close"?** He has never quantified it. *Ask:* 10 pairs where 2R and the nearest whole dollar sit 0.10R / 0.25R / 0.50R apart, both drawn — "on which of these do you take the dollar instead of 2R?" *Default:* `0.25r`, and the sweep runs regardless; his answer only picks between arms that measure inside the noise.
3. **What is a "medium average" (PT4)?** It reads either as a moving average or as a statistical one. *Ask:* one card with three lines drawn — the 1h pivot, the 4h pivot, and a horizontal at +4R (the median of what the book actually offered once it reached 2R, n=147) — "which line is your PT4?" *Default:* `max(structure, 4R)`.
4. **The missing 10%.** 50/20/10/10 sums to 90. *Ask, one word:* "is the last 10% a piece you never close, or a typo for 50/20/20/10?" *Default:* `50/20/20/10`.
5. **What does "the day is trending" mean?** Do **not** ask him to choose between `daily_trend_bias`, `qqq_breaks` and `regime_state` — he cannot see any of them on a chart, and asking would be us outsourcing an engineering choice. *Ask:* 20 day-charts, blind, "trend or chop", and we fit whichever causal signal matches his labels. *Default:* no trend test; both weight vectors ship as arms.
6. **Does a near target ever earn its place?** 303/444 rows carried a runner target inside 2R, median 1.30R, 79 of them under 0.5R. *Ask:* 6 of those 79, each with both the actual runner target and 2R drawn — "was the near one right on any of these?" *Default:* the guard ships **behind a flag, off**, and the arm is measured. If he says "none of them," the flag's default flips ON in a follow-up commit, not in this one.

**Two blockers recon raised that I am answering here rather than sending to him:**

- *Should `runner_target` be guarded against the 2R target, and which wins?* **Yes, guarded; 2R wins** unless the precedence rule of §2 put a level inside it deliberately. 68.2% of the book, median 1.30R, and the whole-dollar fallback supplying 87.6% of runner targets is not a trading opinion — it is a geometry bug. He gets question 6 as confirmation, not as the decision.
- *Should `SCALE_PLAN` carry new plan variants, or should a new mechanism be built?* **`SCALE_PLAN` value is a key; the logic lives in `backtest_week.py`; `exit_lab.py` stays research-only** — see §5.1.