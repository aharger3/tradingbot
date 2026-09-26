"""propfirm_luck_check.py -- the day-shuffle luck check for the prop-firm gate.

Idea-bank BUILD NEXT #4 (2026-09-26): "add the shuffled-day luck check to the
prop-firm gate." PR #26 (research/propfirm_gate.py, merged) put every firm's
own all-starts pass rate in the nightly report. PR #27
(research/propfirm_overlay_search.py, branch propfirm-overlay-search,
unmerged) found the problem with reading that number at face value: the
start dates it sweeps are heavily overlapping 120-session windows, so a half
of history is really only about two INDEPENDENT draws -- "did this half's
one regime run up before it ran down." A pass rate built out of that many
non-independent starts can look real and just be the luck of which regime
came first. PR #27's own fix, quoting its docstring: two shuffle checks on
N permutations of a half's sessions, "shuffled" (same days, same drift,
random order -- the pass rate a fresh window drawn from this half's day
distribution would have) and "zero-drift" (the same, de-meaned -- what pure
variance buys at this size). This module is that check, wired into every
nightly propfirm_gate.py run instead of PR #27's own one-off search script.

REUSED, NOT REIMPLEMENTED
  * the PASS/FAIL simulator   omen_metrics.evaluate_prop_challenge -- the
                               exact function propfirm_gate.py already calls
                               for every firm, unmodified.

PORTED, not imported -- PR #27's versions thread through its own 3-tuple
(day, pnl_R, low_R) overlay-candidate series, its own stop-at-target
machinery and its own multiprocessing search this module has no use for.
The pieces below are the same idea shrunk to propfirm_gate's plain
(day, dollars) 2-tuple series, the shape research/propfirm_gate.py's
write_gate_report() already builds every night:
  * `_score_windows`   PR #27's `score_windows(..., full_window=True)`
  * `_demean`          PR #27's `_demean()`
  * `_shuffled`        the per-permutation reorder inside PR #27's
                        `_shuffle_job`
  * SPLIT_DAY / HORIZON  PR #27's SPLIT_DAY ("2025-09-01", the same H1/H2
                        split CLAUDE.md and research/g174_funding_ladder.py
                        use) and HORIZON (120 sessions -- Topstep/Apex/
                        MyFundedFutures' own max_days, PR #27's own choice of
                        a bounded common ground so the firms with no day cap
                        -- Vanquish, Alpha Futures, Take Profit Trader --
                        get swept the same way)

THE GATE. Per firm, per half (H1 = day < SPLIT_DAY, H2 = day >= SPLIT_DAY):
`real_pass_pct` is `_score_windows()` on the half's actual chronological
order; `shuffled_pass_pct` and `zero_edge_pass_pct` are each the MEAN of
`_score_windows()` over `n_shuffles` random reorderings of that half's own
sessions (same values; `zero_edge` also de-means them first). A firm earns
`eval_ready: true` only when, in BOTH halves:
  1. `real_pass_pct` >= PASS_FLOOR_PCT (50%) -- the reported number itself
     clears the floor;
  2. `shuffled_pass_pct` >= PASS_FLOOR_PCT (50%) -- a FRESH random window
     drawn from this half's own day distribution (same values, random
     order) would ALSO clear the floor, not just the specific historical
     order. `real_pass_pct` is one draw out of the (n - horizon + 1)
     overlapping windows this half offers -- almost all of them share most
     of their days with their neighbors, so it is not an independent
     sample and can read high purely because of how this one history
     happened to fall. `shuffled_pass_pct` reshuffles the WHOLE half before
     re-slicing into windows, so each shuffled window draws a fresh mix of
     the half's days -- averaged over `n_shuffles` reshuffles, it is the
     honest "how often would a window like this one actually clear the
     bar" number, immune to that one favorable history;
  3. `shuffled_pass_pct - zero_edge_pass_pct` >= EVAL_READY_MARGIN_PTS --
     the same random windows, with the days' P&L de-meaned (zero drift),
     clear the floor much less often -- so the pass rate in (2) is coming
     from real, positive per-day edge, not merely from the variance a
     driftless stream at this position size would already buy on its own.

(Why the margin is checked against `shuffled`, not `real_pass_pct`, and why
`real_pass_pct` gets its own floor instead: `real_pass_pct` and
`shuffled_pass_pct` converge to the same number for a stationary edge with
enough windows to average over -- a real, reproducible per-day edge shows up
just as strongly in a freshly-shuffled window as in the specific historical
one, so requiring `real_pass_pct` itself to clear `shuffled_pass_pct` by 20
points would reject exactly the durable edges this gate exists to find, and
only reward a favorably-ordered history -- the opposite of the point. What
DOES need to clear a margin is whether the edge is real at all, which is a
`shuffled` vs `zero_edge` question -- PR #27's own framing, quoted above:
"shuffled <= zero-drift means the stream's drift is not helping; the pass is
the dice.") This gate is Austin's card, stated plainly: eval-ready only
appears when the pass is real, not a lucky order and not variance passing
itself off as edge.

Must never raise. Every entry point here is called from
research/propfirm_gate.py's write_gate_report(), itself called from
research/nightly_loop.py's run_propfirm_gate() under the same MUST NOT FAIL
THE TASK contract as the rest of that file -- a bad luck check must never
cost the night its PASS/FAIL row. `firm_luck_check()` catches any exception
internally and reports eval_ready=False with the repr in "error" rather than
letting it propagate.
"""
from __future__ import annotations

import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from omen_metrics import evaluate_prop_challenge  # noqa: E402

# PR #27's own split and horizon (see module docstring for why); duplicated
# here rather than imported so this module has zero dependency on
# propfirm_gate.py or propfirm_overlay_search.py at import time (propfirm_
# gate.py imports THIS module -- a load-time cycle the other way around).
SPLIT_DAY = "2025-09-01"
HORIZON = 120

# Named per the ask: the margin a firm's real pass rate must clear the
# day-shuffle luck check's own (shuffled, zero-edge) baseline by before
# "eval_ready" is allowed to be true.
EVAL_READY_MARGIN_PTS = 20.0
PASS_FLOOR_PCT = 50.0            # the real pass rate's own floor, each half
N_SHUFFLES_DEFAULT = 500
LUCK_SEED_DEFAULT = 1337


def _rule_kwargs(rule: dict) -> dict:
    """The subset of `rule` evaluate_prop_challenge() accepts -- the same
    eight keys propfirm_gate._challenge_kwargs() pulls out, duplicated here
    (not imported) so this module stays a leaf: propfirm_gate.py imports
    propfirm_luck_check, so the reverse import would be a load-time cycle."""
    return {k: rule[k] for k in (
        "account_size", "profit_target_pct", "trailing_dd_pct",
        "daily_loss_limit_pct", "min_trading_days", "consistency_pct",
        "dd_mode", "dd_lock_at_breakeven",
    )}


def _score_windows(daily, rule, horizon=HORIZON):
    """(pass_pct, n_windows) -- every fixed-`horizon`-session window fully
    inside `daily` (a chronological (day, dollars) list), scored by the
    reused simulator. Ported from PR #27's
    `score_windows(..., full_window=True)`, shrunk to propfirm_gate's plain
    2-tuples (no overlay `low` channel or stop-at-target -- this module's
    callers use neither) and pinned to one fixed horizon. (None, 0) if
    `daily` is shorter than `horizon` -- too little history for even one
    full window."""
    kw = _rule_kwargs(rule)
    n = len(daily)
    if n < horizon:
        return None, 0
    starts = range(0, n - horizon + 1)
    passed = sum(1 for s in starts
                 if evaluate_prop_challenge(daily[s:s + horizon], **kw)["passed"])
    ns = len(starts)
    return round(100.0 * passed / ns, 1), ns


def _demean(daily):
    """The zero-edge baseline series: subtract the mean of the TRADED days'
    P&L from each traded day. A day with pnl == 0 is left at 0 so it still
    does not count as a trading day (evaluate_prop_challenge's own rule).
    Ported from PR #27's `_demean()`, shrunk to a 2-tuple (day, dollars)
    series (no `low` channel to carry alongside it)."""
    traded = [p for _, p in daily if p != 0]
    mu = sum(traded) / len(traded) if traded else 0.0
    return [(d, p) if p == 0 else (d, p - mu) for d, p in daily]


def _shuffled(daily, rng):
    """Same days, same P&L values, a fresh random order. Ported from the
    per-permutation reorder inside PR #27's `_shuffle_job`, shrunk to a
    plain (day, dollars) series (no per-day candidate list to remap --
    this module reshuffles the gate's own realized daily P&Ls, not the
    overlay search's tradeable-candidate lists)."""
    days = [d for d, _ in daily]
    vals = [p for _, p in daily]
    order = list(range(len(vals)))
    rng.shuffle(order)
    return list(zip(days, (vals[i] for i in order)))


def _half_luck(half, rule, n_shuffles, rng, horizon):
    """One firm, one half -> the real start-date pass rate plus the mean
    pass rate over `n_shuffles` day-shuffles of the same half, both on the
    actual (day, dollars) values and on their zero-edge (de-meaned) twin.
    None fields (not 0.0) when `half` is too short for even one window --
    "not enough data" must never be silently read as "0% pass"."""
    real_pct, n_windows = _score_windows(half, rule, horizon)
    if real_pct is None:
        return dict(real_pass_pct=None, n_windows=0,
                    shuffled_pass_pct=None, zero_edge_pass_pct=None)
    demeaned = _demean(half)
    shuf_rates, zero_rates = [], []
    for _ in range(n_shuffles):
        pct, _ = _score_windows(_shuffled(half, rng), rule, horizon)
        if pct is not None:
            shuf_rates.append(pct)
        zpct, _ = _score_windows(_shuffled(demeaned, rng), rule, horizon)
        if zpct is not None:
            zero_rates.append(zpct)
    shuffled_pct = round(sum(shuf_rates) / len(shuf_rates), 1) if shuf_rates else None
    zero_edge_pct = round(sum(zero_rates) / len(zero_rates), 1) if zero_rates else None
    return dict(real_pass_pct=real_pct, n_windows=n_windows,
                shuffled_pass_pct=shuffled_pct, zero_edge_pass_pct=zero_edge_pct)


def firm_luck_check(daily, rule, n_shuffles=N_SHUFFLES_DEFAULT,
                    seed=LUCK_SEED_DEFAULT, margin_pts=EVAL_READY_MARGIN_PTS,
                    horizon=HORIZON, split_day=SPLIT_DAY) -> dict:
    """One firm, the gate's own full chronological (day, dollars) series ->
    {"eval_ready": bool, "h1": {...}, "h2": {...}, "n_shuffles", "seed",
    "margin_pts", "horizon_sessions", "error"}. `eval_ready` is true only
    when, in BOTH halves, `real_pass_pct` and `shuffled_pass_pct` each clear
    PASS_FLOOR_PCT AND `shuffled_pass_pct` clears `zero_edge_pass_pct` by at
    least `margin_pts` (see module docstring, "THE GATE", for why the
    margin is checked on `shuffled` vs `zero_edge` rather than on
    `real_pass_pct` itself).

    Never raises -- any exception is caught and reported as
    eval_ready=False with the repr in "error", same MUST NOT FAIL THE TASK
    contract as the rest of the gate this feeds."""
    try:
        rng = random.Random(seed)
        h1 = [x for x in daily if x[0] < split_day]
        h2 = [x for x in daily if x[0] >= split_day]
        halves = dict(h1=_half_luck(h1, rule, n_shuffles, rng, horizon),
                     h2=_half_luck(h2, rule, n_shuffles, rng, horizon))

        def _clears(h):
            r, s, z = h["real_pass_pct"], h["shuffled_pass_pct"], h["zero_edge_pass_pct"]
            if r is None or s is None or z is None:
                return False
            return r >= PASS_FLOOR_PCT and s >= PASS_FLOOR_PCT and (s - z) >= margin_pts

        eval_ready = all(_clears(h) for h in halves.values())
        return dict(eval_ready=eval_ready, h1=halves["h1"], h2=halves["h2"],
                    n_shuffles=n_shuffles, seed=seed, margin_pts=margin_pts,
                    horizon_sessions=horizon, error=None)
    except Exception as exc:
        return dict(eval_ready=False, h1=None, h2=None, n_shuffles=n_shuffles,
                    seed=seed, margin_pts=margin_pts, horizon_sessions=horizon,
                    error=repr(exc))


def compute(daily, firms, n_shuffles=N_SHUFFLES_DEFAULT, seed=LUCK_SEED_DEFAULT,
           margin_pts=EVAL_READY_MARGIN_PTS, horizon=HORIZON,
           split_day=SPLIT_DAY) -> dict:
    """Every firm in `firms` -> {firm_name: firm_luck_check() result}. Each
    call is independently guarded inside firm_luck_check(); one firm's
    failure never touches another firm's result."""
    return {name: firm_luck_check(daily, rule, n_shuffles, seed, margin_pts,
                                  horizon, split_day)
           for name, rule in firms.items()}
