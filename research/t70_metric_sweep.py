"""OMEN 6 T70 -- the widest honest cut of the backtest.

T60 answered "does the engine make money" and got one number. T70 asks the
question that number cannot answer: **where does that number come from, and
where does it come from NOT.**

Every trade in the engine's own ledger (``backtest_charts.json``, corpus B --
the same corpus T60 scores) is labelled on ten dimensions, then sliced by every
single dimension and every PAIR of dimensions, and every one of those slices is
re-measured under all six exit policies. That is the whole of the report: no
tuning, no filter search, no policy selection. Report only.

Dimensions
----------
    symbol          the ticker
    pool            equity / index / other, via ``universe.pool_for``
    month           YYYY-MM. Austin's durability gate is EVERY MONTH GREEN
                    (2026-08-23), not every quarter -- 3x as many chances to
                    fail, which is the point. Quarter is reported alongside it
                    only so the older quarterly numbers stay comparable.
    quarter         YYYY-Qn
    setup           the ledger's ``setup`` field
    grade           the ledger's ``grade`` field (A+/A/B/C)
    alert_only      whether the engine flagged the row as alert-only
    trend_qqq       whether QQQ was moving the SAME direction as the trade at
                    the entry bar -- Austin's own first instinct for regime.
                    aligned / opposed / flat, at the 5bps margin that
                    ``research/trend_gate.py`` already uses for its index
                    component. Causal: 09:30 QQQ open -> QQQ close at entry_i,
                    nothing after the entry is read.
    session_third   09:30-10:00 / 10:00-10:30 / 10:30-11:00, from entry_i
    side            long / short

Exit policies
-------------
All six, per ``research/v52_scaleout_run.POLICY_IDS``: the five in
``exit_lab.POLICIES`` plus ``adaptive``, which picks 30_30_30_10 when
``trend_gate.is_trending`` and 50_20_20_10 otherwise. Austin asked for both
ladders backtested rather than one picked, so nothing here is preferred --
30_30_30_10 is called the reference policy only because T60's headline used it.

The thin-slice rule
-------------------
Any slice with N < 20 is written to the CSV with ``thin=1`` and is excluded
from every ranking in the markdown. A 3-trade slice with mean +2.5R is noise,
and presenting it as a finding is the exact failure mode this report exists to
avoid.

FVG and FLAG are retired
------------------------
Austin, 2026-08-24: "I don't trade FVG or FLAG. Those are not setups anymore."
Rows whose setup is ``fair_value_gap`` or ``flag`` are marked ``retired=1`` in
the CSV and excluded from every headline figure and every ranking. See the
generated report's caveat section for what that does and does not achieve on
THIS corpus -- the honest answer is: almost nothing, and the reason matters.
Nothing is deleted from the engine here; that is a different ticket.

    python research/t70_metric_sweep.py

Writes research/t70_metric_sweep.csv and research/t70_metric_sweep.md.
"""

from __future__ import annotations
import csv
import itertools
import json
import os
import statistics
import sys
from collections import defaultdict

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import research.levels as levels  # noqa: E402

# Bars are read once per symbol-day and reused. Pure caching -- the policies
# never mutate a bar list, and trend_gate imports the loader inside its own
# function body, so patching it here is picked up there too.
_BAR_CACHE = {}
_load_rth_bars_uncached = levels.load_rth_bars


def _cached_load_rth_bars(symbol, day):
    key = (symbol, day)
    if key not in _BAR_CACHE:
        _BAR_CACHE[key] = _load_rth_bars_uncached(symbol, day)
    return _BAR_CACHE[key]


levels.load_rth_bars = _cached_load_rth_bars

import research.exit_lab as exit_lab  # noqa: E402
import research.trend_gate as trend_gate  # noqa: E402
import research.sizing as sizing  # noqa: E402
from research.v52_scaleout_run import corpus_b_trades, bars_for  # noqa: E402
from universe import pool_for  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_CSV = os.path.join(HERE, "t70_metric_sweep.csv")
OUT_MD = os.path.join(HERE, "t70_metric_sweep.md")

# All six, in the order v52_scaleout_run publishes them.
POLICY_IDS = ["flat_1r", "flat_2r", "hod_only", "30_30_30_10", "50_20_20_10", "adaptive"]
REFERENCE_POLICY = "30_30_30_10"  # T60's headline ladder, for comparability only

# Austin, 2026-08-24: "I don't trade FVG or FLAG. Those are not setups anymore."
RETIRED_SETUPS = {"fair_value_gap", "flag"}

THIN_N = 20  # below this a slice is noise and is ranked nowhere

TRADING_DAYS_PER_YEAR = 252  # same annualisation basis as T60
R_DOLLARS = sizing.R_DOLLARS  # 1R = $1,000, settled 2026-08-23

# Austin's own first instinct for regime, at trend_gate's existing index margin.
QQQ_MARGIN_BPS = trend_gate.INDEX_MARGIN_BPS
TREND_INDEX = "QQQ"

DIMENSIONS = ["symbol", "pool", "month", "quarter", "setup", "grade",
              "alert_only", "trend_qqq", "session_third", "side"]


# ---------------------------------------------------------------------------
# stats -- max_consec_losers and summarise are T60's, extended with a CI
# ---------------------------------------------------------------------------

def max_consec_losers(rs):
    worst = run = 0
    for r in rs:
        if r < 0:
            run += 1
            worst = max(worst, run)
        else:
            run = 0
    return worst


def summarise(rows):
    """rows: list of (r_multiple, date), in chronological order.

    T60's summarise plus a 95% CI on the mean. The CI uses the population sd,
    the same estimator T60's headline CI uses, so the two reports agree on the
    overall row rather than differing in the fourth decimal for no reason.
    """
    rs = [r for r, _ in rows]
    if not rs:
        return None
    days = {d for _, d in rows}
    per_year = len(rs) * TRADING_DAYS_PER_YEAR / max(len(days), 1)
    mean = statistics.fmean(rs)
    sd = statistics.pstdev(rs) if len(rs) > 1 else 0.0
    half = 1.96 * sd / (len(rs) ** 0.5) if rs else 0.0
    # Dollars go through the sizing layer rather than being multiplied inline,
    # so the venue assumption lives in exactly one file.
    mean_dollars = sizing.summarise(rs, "shares")["mean_dollars"]
    return {
        "n": len(rs),
        "mean_r": mean,
        "median_r": statistics.median(rs),
        "win_rate": sum(1 for r in rs if r > 0) / len(rs),
        "worst": min(rs),
        "mcl": max_consec_losers(rs),
        "sd": sd,
        "ci_lo": mean - half,
        "ci_hi": mean + half,
        "trading_days": len(days),
        "trades_per_year": per_year,
        "ann_dollars": mean_dollars * per_year,
    }


def month_of(date_str):
    return date_str[:7]


def quarter_of(date_str):
    y, m, _ = date_str.split("-")
    return "%s-Q%d" % (y, (int(m) - 1) // 3 + 1)


def session_third_of(entry_i):
    """RTH bar index -> which half-hour of the 09:30-11:00 window it entered in."""
    if entry_i < 30:
        return "09:30-10:00"
    if entry_i < 60:
        return "10:00-10:30"
    return "10:30-11:00"


def trend_qqq_of(date, entry_i, side):
    """Was QQQ moving the trade's way at the entry bar?

    Causal by construction: QQQ's 09:30 open versus QQQ's close at ``entry_i``.
    Nothing after the entry bar is read, so this is a label the engine could
    have known at the moment it fired. `aligned` = QQQ moved >= 5bps in the
    trade's favour, `opposed` = >= 5bps against, `flat` = inside the band.
    """
    bars = _cached_load_rth_bars(TREND_INDEX, date)
    if not bars or entry_i >= len(bars):
        return "unknown"
    o = bars[0]["o"]
    if o <= 0:
        return "unknown"
    bps = (bars[entry_i]["c"] - o) / o * 1e4
    if abs(bps) < QQQ_MARGIN_BPS:
        return "flat"
    qqq_up = bps > 0
    trade_long = side == "L"
    return "aligned" if qqq_up == trade_long else "opposed"


# ---------------------------------------------------------------------------
# build the labelled trade table
# ---------------------------------------------------------------------------

def labelled_corpus_b():
    """``corpus_b_trades()`` rows, re-joined to the ledger fields it drops.

    ``v52_scaleout_run.corpus_b_trades`` normalises the ledger down to what the
    exit lab needs (symbol/date/side/entry_i/entry/stop/candles) and throws
    ``setup``, ``grade`` and ``alert_only`` away -- three of this sweep's ten
    dimensions. It reads ``backtest_charts.json`` in order and filters nothing,
    so the two lists are positionally 1:1; that is asserted rather than
    assumed, because a silent misalignment here would mislabel every row.
    """
    norm = corpus_b_trades()
    raw = json.load(open(os.path.join(_REPO_ROOT, "backtest_charts.json"),
                         encoding="utf-8"))
    assert len(norm) == len(raw), (
        "corpus_b_trades() no longer maps 1:1 onto backtest_charts.json "
        "(%d vs %d) -- re-join on keys before trusting setup/grade labels"
        % (len(norm), len(raw)))
    for n, r in zip(norm, raw):
        assert n["symbol"] == r["symbol"] and n["date"] == r["day"], (
            "positional re-join drifted at %s %s" % (n["symbol"], n["date"]))
        n["setup"] = r.get("setup")
        n["grade"] = r.get("grade")
        n["alert_only"] = r.get("alert_only")
    return norm


def build_rows():
    """One dict per ledger trade: every dimension label, plus R under all six
    policies. Rows the exit lab cannot price at all are skipped and counted."""
    rows, skipped = [], 0
    for t in labelled_corpus_b():
        bars = bars_for(t)
        if not bars or t["entry"] is None or t["stop"] is None or t["entry_i"] >= len(bars):
            skipped += 1
            continue
        entry_i, entry, stop, side = t["entry_i"], t["entry"], t["stop"], t["side"]
        rs = {}
        for pid in POLICY_IDS:
            if pid == "adaptive":
                sub = ("30_30_30_10"
                       if trend_gate.is_trending(t["symbol"], t["date"], entry_i, side)
                       else "50_20_20_10")
                rs[pid] = exit_lab.POLICIES[sub](bars, entry_i, entry, stop, side)
            else:
                rs[pid] = exit_lab.POLICIES[pid](bars, entry_i, entry, stop, side)
        setup = (t.get("setup") or "unknown")
        rows.append({
            "symbol": t["symbol"],
            "date": t["date"],
            "entry_i": entry_i,
            "pool": pool_for(t["symbol"]),
            "month": month_of(t["date"]),
            "quarter": quarter_of(t["date"]),
            "setup": setup,
            "grade": (t.get("grade") or "unknown"),
            "alert_only": "alert_only" if t.get("alert_only") else "actioned",
            "trend_qqq": trend_qqq_of(t["date"], entry_i, side),
            "session_third": session_third_of(entry_i),
            "side": "long" if side == "L" else "short",
            "retired": 1 if setup in RETIRED_SETUPS else 0,
            "r": rs,
        })
    rows.sort(key=lambda x: (x["date"], x["symbol"], x["entry_i"]))
    return rows, skipped


# ---------------------------------------------------------------------------
# the sweep
# ---------------------------------------------------------------------------

def sweep(rows):
    """Every policy x (overall, each dimension, each PAIR of dimensions).

    Live rows (retired=0) and retired rows are aggregated separately and never
    mixed: a retired slice can only ever be compared with another retired
    slice, which is what keeps the historical numbers comparable without
    letting them into a headline.
    """
    out = []

    def emit(policy, dim, slice_val, bucket, retired):
        s = summarise(bucket)
        if not s:
            return
        out.append({
            "policy": policy,
            "dim": dim,
            "slice": slice_val,
            "retired": retired,
            "thin": 1 if s["n"] < THIN_N else 0,
            **s,
        })

    pairs = list(itertools.combinations(DIMENSIONS, 2))

    for retired in (0, 1):
        subset = [r for r in rows if r["retired"] == retired]
        if not subset:
            continue
        for policy in POLICY_IDS:
            pairs_of = [(r["r"][policy], r["date"]) for r in subset]
            emit(policy, "ALL", "all trades", pairs_of, retired)

            for dim in DIMENSIONS:
                g = defaultdict(list)
                for r, src in zip(pairs_of, subset):
                    g[src[dim]].append(r)
                for k in sorted(g):
                    emit(policy, dim, str(k), g[k], retired)

            for d1, d2 in pairs:
                # A pair against a dimension that takes only one value in this
                # corpus is a byte-for-byte duplicate of the other dimension's
                # own row (session_third is single-valued here -- every entry is
                # before 09:56). Emitting it would let one finding appear ten
                # times in a ranking, which is the presentation version of the
                # thin-slice error.
                if len({src[d1] for src in subset}) < 2:
                    continue
                if len({src[d2] for src in subset}) < 2:
                    continue
                g = defaultdict(list)
                for r, src in zip(pairs_of, subset):
                    g[(src[d1], src[d2])].append(r)
                for k in sorted(g, key=lambda kk: (str(kk[0]), str(kk[1]))):
                    emit(policy, "%s|%s" % (d1, d2), "%s|%s" % (k[0], k[1]),
                         g[k], retired)
    return out


CSV_FIELDS = ["policy", "dim", "slice", "n", "mean_r", "median_r", "win_rate",
              "worst", "max_consec_losers", "sd", "ci_lo", "ci_hi",
              "trading_days", "trades_per_year", "ann_dollars", "thin", "retired"]


def write_csv(sweep_rows):
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_FIELDS)
        for s in sweep_rows:
            w.writerow([
                s["policy"], s["dim"], s["slice"], s["n"],
                "%.6f" % s["mean_r"], "%.6f" % s["median_r"], "%.6f" % s["win_rate"],
                "%.6f" % s["worst"], s["mcl"], "%.6f" % s["sd"],
                "%.6f" % s["ci_lo"], "%.6f" % s["ci_hi"],
                s["trading_days"], "%.3f" % s["trades_per_year"],
                "%.2f" % s["ann_dollars"], s["thin"], s["retired"],
            ])


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

HEAD = ("| slice | policy | N | mean R | 95% CI | median R | win | worst | MCL | ann $ |\n"
        "|---|---|---:|---:|---|---:|---:|---:|---:|---:|")


def md(text):
    """Escape a slice label for a markdown table cell.

    Pair slices are joined with `|` in the CSV because that is unambiguous for a
    machine. Unescaped, that same character ends the markdown cell and silently
    shreds the table.
    """
    return str(text).replace("|", "\|")


def row(label, s, with_policy=True):
    return ("| %s | %s | %d | %+.4f | %+.3f … %+.3f | %+.4f | %.3f | %.2f | %d | %s |"
            % (md(label), s["policy"] if with_policy else "—", s["n"], s["mean_r"],
               s["ci_lo"], s["ci_hi"], s["median_r"], s["win_rate"], s["worst"],
               s["mcl"], format(round(s["ann_dollars"]), "+,")))


def label_of(s):
    return "`%s` = %s" % (s["dim"].replace("|", " x "), s["slice"])


def main():
    rows, skipped = build_rows()
    sweep_rows = sweep(rows)
    write_csv(sweep_rows)

    live = [r for r in rows if r["retired"] == 0]
    n_retired = len(rows) - len(live)

    rankable = [s for s in sweep_rows
                if s["thin"] == 0 and s["retired"] == 0 and s["dim"] != "ALL"]

    # Collinear dimensions produce slices holding the IDENTICAL trades under
    # different names. Ranked side by side they read as several independent
    # findings when they are one. They stay in the CSV; the ranked tables here
    # show the first (shortest-named, i.e. simplest) description of each set.
    def dedupe(rows_in):
        seen, out = set(), []
        for s in sorted(rows_in, key=lambda s: (len(s["dim"]), s["dim"])):
            key = (s["policy"], s["n"], round(s["mean_r"], 9), round(s["worst"], 9))
            if key in seen:
                continue
            seen.add(key)
            out.append(s)
        return out

    by_mean = sorted(dedupe(rankable), key=lambda s: s["mean_r"])
    worst10 = by_mean[:10]
    best10 = list(reversed(by_mean[-10:]))

    # Which dimension pairs are collinear, and on which values -- reported, not
    # silently collapsed. `grade=C` and `alert_only=alert_only` being the same
    # 273 trades is a fact about the engine, not a bookkeeping detail.
    collinear = []
    for d1, d2 in itertools.combinations(DIMENSIONS, 2):
        m = defaultdict(set)
        for r in rows:
            m[r[d1]].add(r[d2])
        exact = sorted(str(k) for k, v in m.items()
                       if len(v) == 1
                       and sum(1 for r in rows if r[d2] == next(iter(v))) ==
                       sum(1 for r in rows if r[d1] == k))
        if exact:
            collinear.append((d1, d2, exact))

    unique = by_mean  # rankable, collinear duplicates collapsed
    decisive_pos = [s for s in unique if s["ci_lo"] > 0]
    decisive_neg = [s for s in unique if s["ci_hi"] < 0]
    # The slices that survive BOTH tests that matter: a clean interval and
    # enough trades that the interval is not a coincidence of the N>=20 cutoff.
    big_decisive = sorted([s for s in unique
                           if s["n"] >= 100 and (s["ci_lo"] > 0 or s["ci_hi"] < 0)],
                          key=lambda s: -s["n"])

    L = []
    L.append("# T70 — the metric sweep: where the edge is, and where it is not")
    L.append("")
    L.append("Generated by `research/t70_metric_sweep.py`. Machine-readable companion: "
             "`research/t70_metric_sweep.csv` (%d rows)." % len(sweep_rows))
    L.append("")
    L.append("Corpus B — the engine's own trade ledger, `backtest_charts.json`, the same "
             "corpus T60 scores. **%d trades** over **%d sessions**, %s to %s. "
             "%d ledger rows were skipped (no bars, or entry beyond the session)."
             % (len(rows), len({r["date"] for r in rows}),
                min(r["date"] for r in rows), max(r["date"] for r in rows), skipped))
    L.append("")
    L.append("Every slice is measured under **all six** exit policies (`%s`). Austin asked "
             "for both ladders backtested rather than one picked, so no policy is preferred "
             "here; `%s` is called the reference only because T60's headline used it."
             % ("`, `".join(POLICY_IDS), REFERENCE_POLICY))
    L.append("")
    L.append("**Nothing in this file is tuned.** No threshold was searched, no filter was "
             "fitted, no policy was selected. It is a census.")
    L.append("")

    # ---- read this first -------------------------------------------------
    L.append("## 0. Read this before any number below")
    L.append("")
    L.append("### The thin-slice rule")
    L.append("")
    L.append("Any slice with **N < %d** carries `thin=1` in the CSV and is excluded from "
             "every ranking here. Of %d slice rows, **%d are thin (%.0f%%)** — the sweep is "
             "mostly noise by row count, and that is the honest shape of a %d-trade corpus "
             "cut ten ways. A 3-trade slice with mean +2.5R is not a finding."
             % (THIN_N, len(sweep_rows), sum(1 for s in sweep_rows if s["thin"]),
                100 * sum(1 for s in sweep_rows if s["thin"]) / max(len(sweep_rows), 1),
                len(rows)))
    L.append("")
    L.append("### FVG and FLAG are retired — and this corpus cannot show it")
    L.append("")
    L.append("Austin, 2026-08-24: *\"I don't trade FVG or FLAG. Those are not setups "
             "anymore.\"* Rows with setup `fair_value_gap` or `flag` are marked `retired=1` "
             "and excluded from every headline and every ranking.")
    L.append("")
    L.append("**That exclusion removed %d trades, because this ledger has none.** The "
             "ledger's `setup` field only ever takes the values %s. The reason is in "
             "`omen_bot.py`'s own comment on `SignalType`: until the omen-3.7 T5 split, "
             "*\"the FVG and flag entries used to hide behind other labels (FVG under "
             "BREAK_AND_RETEST, flag under ONE_CANDLE_RULE)\"*. `backtest_charts.json` "
             "predates that split."
             % (n_retired, ", ".join("`%s`" % s for s in
                                     sorted({r["setup"] for r in rows}))))
    L.append("")
    L.append("So: **`break_and_retest` and `one_candle_rule` below still contain the retired "
             "setups, and there is no committed data that can separate them.** Every "
             "per-setup figure in this report is contaminated by trades Austin no longer "
             "takes, in an unknown proportion. Fixing that needs a fresh engine run under "
             "the post-split labels — a different ticket, not a re-run of this script. "
             "Treat the setup dimension as the least trustworthy in the sweep.")
    L.append("")
    L.append("### Dimensions that are the same dimension")
    L.append("")
    if collinear:
        L.append("Some of these ten labels are not independent — a value of one implies a "
                 "value of another, so the two slices contain the **identical trades** and "
                 "report identical numbers. Ranked naively that makes one finding look like "
                 "several. Both rows stay in the CSV; the ranked tables in §1 keep only the "
                 "first (simplest-named) description of each identical set.")
        L.append("")
        L.append("| dimension | value | is exactly | note |")
        L.append("|---|---|---|---|")
        for d1, d2, vals in collinear:
            for v in vals:
                other = {r[d2] for r in rows if str(r[d1]) == v}
                note = ""
                if {d1, d2} == {"grade", "alert_only"}:
                    note = ("**the engine's C grade and its alert-only flag are one "
                            "switch.** Whatever §1 says about one is a statement about "
                            "the other.")
                L.append("| `%s` | `%s` | `%s` = `%s` | %s |"
                         % (d1, v, d2, next(iter(other)), note))
        L.append("")
    else:
        L.append("_None: no value of any dimension exactly implies a value of another._")
        L.append("")
    L.append("### What the dimensions mean")
    L.append("")
    L.append("| dimension | values | note |")
    L.append("|---|---|---|")
    for d in DIMENSIONS:
        vals = sorted({str(r[d]) for r in rows})
        shown = ", ".join("`%s`" % v for v in vals[:6])
        if len(vals) > 6:
            shown += ", … (%d total)" % len(vals)
        note = ""
        if d == "trend_qqq":
            note = ("QQQ 09:30 open → QQQ close at `entry_i`, ±%.0fbps band. Causal — "
                    "nothing after the entry bar is read." % QQQ_MARGIN_BPS)
        elif d == "month":
            note = "**the durability gate: every month green**"
        elif d == "quarter":
            note = "reported only so older quarterly numbers stay comparable"
        elif d == "session_third":
            note = ("entry_i in this ledger runs %d–%d, i.e. **every trade enters before "
                    "09:56**. This dimension is degenerate on this corpus and proves "
                    "nothing about the later two thirds."
                    % (min(r["entry_i"] for r in rows), max(r["entry_i"] for r in rows)))
        elif d == "setup":
            note = "**contaminated — see above**"
        L.append("| `%s` | %s | %s |" % (d, shown, note))
    L.append("")
    L.append("Slices are cut on every dimension **and every pair of dimensions** "
             "(%d pairs), under each of the six policies. The pair rows live in the CSV; "
             "the rankings below draw from single and pair rows alike."
             % len(list(itertools.combinations(DIMENSIONS, 2))))
    L.append("")

    # ---- headline: best and worst ---------------------------------------
    L.append("## 1. The headline — both halves of it")
    L.append("")
    L.append("Ranked by mean R across **every non-thin, non-retired slice** in the sweep, "
             "single and paired, under every policy. The two tables are the same finding "
             "seen from two ends; neither outranks the other.")
    L.append("")
    L.append("A mean-R ranking is dominated by the smallest slices that clear the N=%d "
             "cutoff — that is arithmetic, not signal, and it is why the CI column is "
             "printed next to the mean instead of underneath it. Median N in these twenty "
             "rows: **%d**, against %d trades in the corpus. §1e is where to look for what "
             "actually holds up."
             % (THIN_N,
                statistics.median([s["n"] for s in (best10 + worst10)] or [0]),
                len(rows)))
    L.append("")
    L.append("### 1a. WHERE THE EDGE IS NOT — the ten worst non-thin slices")
    L.append("")
    L.append(HEAD)
    for s in worst10:
        L.append(row(label_of(s), s))
    L.append("")
    L.append("### 1b. Where the edge is — the ten best non-thin slices")
    L.append("")
    L.append(HEAD)
    for s in best10:
        L.append(row(label_of(s), s))
    L.append("")
    L.append("**Read the CI column, not the mean.** A slice is only a finding if its whole "
             "95%% interval sits on one side of zero. Of %d distinct rankable slices, **%d are "
             "decisively positive** (CI entirely above 0) and **%d are decisively "
             "negative** (CI entirely below 0); the remaining %d — %.0f%% — are "
             "indistinguishable from zero at this sample size."
             % (len(unique), len(decisive_pos), len(decisive_neg),
                len(unique) - len(decisive_pos) - len(decisive_neg),
                100 * (len(unique) - len(decisive_pos) - len(decisive_neg))
                / max(len(unique), 1)))
    L.append("")

    if decisive_pos:
        L.append("### 1c. Decisively positive slices (95% CI entirely above zero)")
        L.append("")
        L.append(HEAD)
        for s in sorted(decisive_pos, key=lambda s: -s["mean_r"])[:25]:
            L.append(row(label_of(s), s))
        if len(decisive_pos) > 25:
            L.append("")
            L.append("_… %d more in the CSV (`thin=0`, `retired=0`, `ci_lo>0`)._"
                     % (len(decisive_pos) - 25))
        L.append("")
    else:
        L.append("### 1c. Decisively positive slices (95% CI entirely above zero)")
        L.append("")
        L.append("**None.** Not one non-thin slice anywhere in this sweep — no symbol, "
                 "no month, no grade, no regime, no policy, no pair of those — has a mean R "
                 "whose whole 95% interval sits above zero. That is the single most "
                 "important line in this report.")
        L.append("")

    if decisive_neg:
        L.append("### 1d. Decisively negative slices (95% CI entirely below zero)")
        L.append("")
        L.append("These are the ones that are *actually* established. A losing slice with a "
                 "clean interval is a real finding and is worth as much as a winning one.")
        L.append("")
        L.append(HEAD)
        for s in sorted(decisive_neg, key=lambda s: s["mean_r"])[:25]:
            L.append(row(label_of(s), s))
        if len(decisive_neg) > 25:
            L.append("")
            L.append("_… %d more in the CSV (`thin=0`, `retired=0`, `ci_hi<0`)._"
                     % (len(decisive_neg) - 25))
        L.append("")

    L.append("### 1e. What survives at size — decisive slices with N ≥ 100")
    L.append("")
    L.append("A clean 95% interval on 20 trades and a clean 95% interval on 300 are not the "
             "same claim. These are the only slices in the whole sweep that have both a "
             "one-sided interval **and** enough trades that the interval is not an artifact "
             "of sitting just above the thin cutoff. Sorted by N, largest first — the top "
             "of this table is the most defensible statement this corpus can make.")
    L.append("")
    if big_decisive:
        L.append(HEAD)
        for s in big_decisive[:30]:
            L.append(row(label_of(s), s))
        L.append("")
        atoms = set()
        for s in big_decisive:
            atoms.update(s["dim"].split("|"))
        absent = [d for d in DIMENSIONS if d not in atoms]
        L.append("**Every large decisive slice in the corpus is built from %s.**"
                 % ", ".join("`%s`" % d for d in DIMENSIONS if d in atoms))
        if absent:
            # Two different reasons a dimension is missing here, and conflating
            # them would overclaim. Either it has a slice big enough to have
            # shown something and did not (a real null), or its slices are all
            # smaller than 100 trades and the question was never asked.
            null, untested = [], []
            for d in absent:
                biggest = max([x["n"] for x in rankable
                               if d in x["dim"].split("|")] or [0])
                (null if biggest >= 100 else untested).append((d, biggest))
            L.append("")
            if null:
                L.append("**No large decisive slice exists on %s — and the sample was "
                         "there.** Slices on those labels reach %s trades and still "
                         "straddle zero: cutting the book that way does not separate "
                         "winners from losers. That is a negative finding and it is as "
                         "real as anything in §1b."
                         % (", ".join("`%s`" % d for d, _ in null),
                            " / ".join(str(n) for _, n in null)))
            if untested:
                L.append("")
                L.append("**None on %s either — but the sample never was.** The largest "
                         "non-thin slice there holds only %s trades, so N ≥ 100 was "
                         "unreachable by construction. Read that as *unmeasured at this "
                         "resolution*, not as *no effect*."
                         % (", ".join("`%s`" % d for d, _ in untested),
                            " / ".join(str(n) for _, n in untested)))
    else:
        L.append("**None.** Every decisive slice in this sweep sits near the thin cutoff. "
                 "There is no large, clean slice anywhere in the corpus.")
    L.append("")

    # ---- overall per policy ---------------------------------------------
    L.append("## 2. Overall, per exit policy")
    L.append("")
    L.append("Every live trade in the corpus, one row per ladder. This is the number T60 "
             "reports, re-derived, plus the five ladders it did not print.")
    L.append("")
    L.append(HEAD)
    for s in [x for x in sweep_rows if x["dim"] == "ALL" and x["retired"] == 0]:
        L.append(row("all trades", s))
    L.append("")

    # ---- durability: every month green -----------------------------------
    L.append("## 3. The durability gate — every month green")
    L.append("")
    L.append("Austin's gate, tightened from quarterly on 2026-08-23. A policy passes only "
             "if **every** month is green. Thin months are shown but a thin month cannot "
             "rescue a policy either — it just means the month is unmeasured.")
    L.append("")
    L.append("| policy | months | green | red | thin | verdict |")
    L.append("|---|---:|---:|---:|---:|---|")
    for policy in POLICY_IDS:
        ms = [s for s in sweep_rows
              if s["dim"] == "month" and s["policy"] == policy and s["retired"] == 0]
        green = [s for s in ms if s["mean_r"] > 0]
        red = [s for s in ms if s["mean_r"] <= 0]
        thin = [s for s in ms if s["thin"]]
        L.append("| `%s` | %d | %d | %d | %d | %s |"
                 % (policy, len(ms), len(green), len(red), len(thin),
                    "**PASS**" if not red else "**FAIL** (%s)"
                    % ", ".join(s["slice"] for s in sorted(red, key=lambda x: x["slice"]))))
    L.append("")

    # ---- per-dimension tables --------------------------------------------
    L.append("## 4. Per-dimension tables")
    L.append("")
    L.append("Every single-dimension slice, every policy. `thin` rows are kept visible here "
             "(marked) so the reader can see how much of each dimension is unmeasured — "
             "they are still excluded from the rankings in §1.")
    L.append("")
    for dim in DIMENSIONS:
        rowsd = [s for s in sweep_rows
                 if s["dim"] == dim and s["retired"] == 0]
        if not rowsd:
            continue
        L.append("### 4.%d `%s`" % (DIMENSIONS.index(dim) + 1, dim))
        L.append("")
        L.append(HEAD)
        for s in sorted(rowsd, key=lambda s: (s["slice"], POLICY_IDS.index(s["policy"]))):
            lab = s["slice"] + (" _(thin)_" if s["thin"] else "")
            L.append(row(lab, s))
        L.append("")
        nonthin = [s for s in rowsd if not s["thin"]]
        if nonthin:
            spread_lo = min(nonthin, key=lambda s: s["mean_r"])
            spread_hi = max(nonthin, key=lambda s: s["mean_r"])
            L.append("**Spread (non-thin only):** worst `%s` under `%s` at %+.4fR, best "
                     "`%s` under `%s` at %+.4fR."
                     % (spread_lo["slice"], spread_lo["policy"], spread_lo["mean_r"],
                        spread_hi["slice"], spread_hi["policy"], spread_hi["mean_r"]))
            neg = sorted({s["slice"] for s in nonthin if s["mean_r"] < 0})
            L.append("")
            L.append("**Non-thin slices negative under at least one policy:** %s"
                     % (", ".join("`%s`" % v for v in neg) if neg else "_none_"))
        else:
            L.append("**Every slice on this dimension is thin.** Nothing here is measured.")
        L.append("")

    # ---- retired rows -----------------------------------------------------
    L.append("## 5. Retired setups (FVG / FLAG)")
    L.append("")
    if n_retired:
        L.append(HEAD)
        for s in [x for x in sweep_rows
                  if x["retired"] == 1 and x["dim"] == "setup"]:
            L.append(row(s["slice"] + (" _(thin)_" if s["thin"] else ""), s))
        L.append("")
        L.append("Kept for historical comparability only. Excluded from every figure above.")
    else:
        L.append("**Zero rows.** As set out in §0, the ledger predates the FVG/FLAG label "
                 "split, so there is nothing to segregate — which is not the same as there "
                 "being no FVG or FLAG trades in it. There are; they are wearing other "
                 "labels, and this corpus cannot tell you which ones.")
    L.append("")

    # ---- caveats ----------------------------------------------------------
    L.append("## 6. Caveats that ride with every number here")
    L.append("")
    L.append("- **In-sample.** Corpus B is the engine's own trade ledger; the rules were "
             "fitted on these days. Every slice below is an in-sample slice, and slicing "
             "in-sample data ten ways is exactly how a spurious \"edge\" is manufactured. "
             "The thin-slice rule and the CI columns are the only defence in this file, and "
             "neither is a substitute for the forward clock (ticket 13).")
    L.append("- **Multiple comparisons.** %d slice rows were computed. At a 95%% CI, "
             "roughly %d of them would clear the bar by chance alone even if the engine had "
             "no edge whatsoever. No correction is applied here; none is claimed. Any single "
             "slice from §1b that has not been checked forward is a hypothesis, not a "
             "finding." % (len(sweep_rows), round(0.05 * len(sweep_rows))))
    L.append("- **The break-even stop fills exactly at entry**, so the runner cannot lose. "
             "Mean R is a ceiling on every scale-out policy (T60 / ticket 02, Q9).")
    L.append("- **Dollars are a sizing skin.** 1R = $%s via `research/sizing.py` at the "
             "`shares` venue — exact passthrough. Austin trades **options**, and "
             "`sizing.dollars_options` is explicitly an approximation with "
             "`confidence: \"low\"`. R is the result; the `ann $` column is an indication."
             % format(int(R_DOLLARS), ","))
    L.append("- **Annualisation** projects each slice's own trade rate onto %d trading days, "
             "assuming every trade is taken at full risk with no capital constraint, no "
             "commissions and no options spread. On a narrow slice that rate is itself an "
             "extrapolation from very few days — read `ann $` on any slice with few "
             "`trading_days` as arithmetic, not a forecast." % TRADING_DAYS_PER_YEAR)
    L.append("- **SPY is absent**, per `universe.INCLUDE_SPY_IN_BACKTEST = False`, and the "
             "corpus predates the flag so it never contained SPY at all.")
    L.append("- **`session_third` is degenerate** on this corpus: every entry is before "
             "09:56. The dimension is swept and reported, but it says nothing about "
             "10:00-11:00 because the engine never traded there.")
    L.append("- **`setup` is contaminated** by the retired FVG/FLAG entries hiding under "
             "`break_and_retest` and `one_candle_rule` (§0).")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

    # ---- console ----------------------------------------------------------
    print("wrote %s (%d rows)" % (OUT_CSV, len(sweep_rows)))
    print("wrote %s" % OUT_MD)
    print("trades=%d skipped=%d retired=%d  thin_rows=%d  rankable=%d"
          % (len(rows), skipped, n_retired,
             sum(1 for s in sweep_rows if s["thin"]), len(rankable)))
    for s in [x for x in sweep_rows if x["dim"] == "ALL" and x["retired"] == 0]:
        print("  ALL %-12s N=%4d mean=%+.4fR CI %+.3f..%+.3f win=%.3f ann=$%s"
              % (s["policy"], s["n"], s["mean_r"], s["ci_lo"], s["ci_hi"],
                 s["win_rate"], format(int(s["ann_dollars"]), ",")))
    if best10:
        b = best10[0]
        print("  BEST  %s | %s | N=%d mean=%+.4fR CI %+.3f..%+.3f"
              % (label_of(b), b["policy"], b["n"], b["mean_r"], b["ci_lo"], b["ci_hi"]))
    if worst10:
        w = worst10[0]
        print("  WORST %s | %s | N=%d mean=%+.4fR CI %+.3f..%+.3f"
              % (label_of(w), w["policy"], w["n"], w["mean_r"], w["ci_lo"], w["ci_hi"]))
    print("  decisive: %d positive, %d negative, of %d distinct rankable (%d raw)"
          % (len(decisive_pos), len(decisive_neg), len(unique), len(rankable)))
    for s in big_decisive[:4]:
        print("  N>=100  %s | %s | N=%d mean=%+.4fR CI %+.3f..%+.3f"
              % (label_of(s), s["policy"], s["n"], s["mean_r"], s["ci_lo"], s["ci_hi"]))


if __name__ == "__main__":
    main()
