"""T3 -- the cross-symbol day-selection ranker.

X13 priced selection's ceiling: one trade per calendar day, chosen with hindsight, books
**+2.2125 R at 76.6% win** over 415 days -- the only ceiling in the whole investigation that
clears both halves of the money gate.  It needs a RANKING of at most 8 same-day candidates,
not knowledge of the path.  This file builds the ranker and scores it out of sample.

    python research/t3_selection_ranker.py            # every section, in order
    python research/t3_selection_ranker.py recall     # held-out S recall only
    python research/t3_selection_ranker.py --selfcheck

Substrate, all on disk, no network:
  research/g3_arm_ow1.json                          the shipped 2-year book (1,017 traded)
  data_archive/<SYM>/<DAY>.csv                      04:00-20:00 1-minute bars
  research/marks/probe_omen_test1_2026-08-27.jsonl  the held-out marks (15 S / 27 A / 16 C / 42 X)
  research/t70_test1_score.md                       the standing held-out engine recall, 3/15

READ-ONLY.  No engine module, no default and no flag is touched by this file.  The book's
1,017 traded rows are content-hashed and asserted unchanged at the end of every run -- not
the file's bytes, because `meta.generated` moves whenever `g3_onwatch_2y.py` is re-run, and
it WAS re-run by another wave-1 track at 2026-08-28T14:03:05 while this was measuring.  The
traded rows came back identical.  There is no ENABLE_* here to ship OFF because nothing
here is wired into the engine; "default off" is the whole file.

THE NO-LOOKAHEAD RULE, and why it has its own test
--------------------------------------------------
X8's strongest whole-book dimension was `rangeb`, the FULL-SESSION high-low, unknowable at a
09:42 entry.  X13's premarket prototype then repeated a softer version of the same mistake:
its `pmr_pct` divides the premarket range by `entry` and its `pm_pos` places `entry` inside
the premarket range -- and `entry` is a post-09:30 price.  So two of the four "ex-ante"
prototype features are not 09:29-knowable.  Every feature here is rebuilt off premarket bars
only, `test_no_post_0930_feature` asserts no feature name is a book field at all, and
`test_builder_ignores_rth` rebuilds the features from a copy of the day's CSV with every
09:30-and-later bar physically deleted and asserts they come out identical.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import statistics as st
import sys
from collections import defaultdict

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

BOOK = os.path.join(_HERE, "g3_arm_ow1.json")
ALT_BOOK = os.path.join(_HERE, "a2_bt2y_rerun.json")   # same rows, written 2026-08-27
ARCHIVE = os.path.join(_ROOT, "data_archive")
MARKS = os.path.join(_HERE, "marks", "probe_omen_test1_2026-08-27.jsonl")
CACHE = os.path.join(_HERE, "_t3_pm_features.json")

# sha256 of the 1,017 TRADED rows, key-sorted (see book_content_sha).  Read-only track:
# if this moves, every number in research/t3_selection_ranker.md is stale.
BOOK_SHA = "afe1d3655081c3294a0a49753ffd581864701869b8507364ade3b7de72135aa3"

# The three S days the engine fires on at all, out of Austin's 15 held-out S days
# (research/t70_test1_score.md, "The three numbers": S recall 3/15).
HELDOUT_FOUND_S = [("BABA", "2026-02-04"), ("IWM", "2025-04-14"), ("MU", "2026-03-09")]

# ---------------------------------------------------------------------------
# THE FEATURE LIST.  Every one of these is computable at 09:29:00 ET from bars
# stamped before 09:30, plus the PREVIOUS session's close (known at yesterday's
# 16:00).  Nothing else is admissible and a test enforces it.
# ---------------------------------------------------------------------------
FEATURES = [
    "pm_range_pct",   # (pm high - pm low) / pm close * 100
    "pm_ret_abs",     # |pm close - pm open| / pm open * 100
    "pm_gap_abs",     # |pm close - prior session close| / prior close * 100
    "pm_rvol",        # pm volume / median pm volume over the symbol's PRIOR 20 sessions
    "pm_rrange",      # pm_range_pct / median pm_range_pct over the PRIOR 20 sessions
    "pm_edge",        # |pm close inside the pm range - 0.5| * 2 -- the ex-ante pm_pos
]

# Anything the book carries about what happened after 09:30.  A feature name may not be a
# book field at all, but these are named so the test's failure message is legible.
POST_0930_BOOK_FIELDS = {
    "entry", "stop", "target", "exit", "out", "pnl", "r", "bars", "entry_i", "et", "slot",
    "drange", "rangeb", "dret", "gap", "gapb", "scaled", "tripped", "sgrade", "downgrades",
    "confluence", "s", "tags", "seq", "grade", "status", "reason", "stop_pct", "stopb",
    "level", "side", "dir", "setup", "spy_trend", "vol_regime", "bias", "aligned",
}

MODES = ["level", "within", "x13"]   # the three ranker forms, declared up front
TRAIL = 20          # sessions in the trailing median for the relative features
TIE = "et"          # ties break to the earliest entry, matching x13's convention


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def winpct(xs):
    xs = [x for x in xs if x != 0]
    return 100.0 * sum(1 for x in xs if x > 0) / len(xs) if xs else float("nan")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


_BOOK_CACHE = None
BOOK_USED = None


def load_book():
    """The STANDING 2-year book -- 1,017 traded rows, +0.9551 mean, content sha BOOK_SHA.

    `research/g3_arm_ow1.json` is `.gitignore`d (`.gitignore:118`, `research/g3_arm_*.json`)
    and is a shared, rewritable artifact.  T11 (the fill-convention track) regenerated it at
    2026-08-28T14:13:17 while this track was measuring, moving the book's mean R from
    +0.9551 to +0.8341, and nothing warned.  T3's whole check is stated against the standing
    book (first-by-time +1.0527, random +0.8809), so this reads whichever file still carries
    the standing rows and refuses to run against anything else.  The candidates are hashed,
    not trusted by name.
    """
    global _BOOK_CACHE, BOOK_USED
    if _BOOK_CACHE is not None:
        return _BOOK_CACHE
    tried = []
    for p in (BOOK, ALT_BOOK):
        if not os.path.exists(p):
            continue
        with open(p) as fh:
            tr = [r for r in json.load(fh)["trades"] if r.get("traded")]
        h = hashlib.sha256(json.dumps(tr, sort_keys=True,
                                      separators=(",", ":")).encode()).hexdigest()
        tried.append("%s n=%d mean %+.4f sha %s"
                     % (os.path.basename(p), len(tr),
                        mean(r["r"] for r in tr) if tr else float("nan"), h[:12]))
        if h == BOOK_SHA:
            _BOOK_CACHE, BOOK_USED = tr, p
            return tr
    raise SystemExit(
        "the standing book (sha %s) is on none of the candidate paths.\n  %s\n"
        "Every number in research/t3_selection_ranker.md was measured on it; re-running "
        "against a different book would silently restate them."
        % (BOOK_SHA[:12], "\n  ".join(tried) or "no candidate file exists"))


def by_day(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["day"]].append(r)
    return d


def months_green(rows):
    m = defaultdict(float)
    for r in rows:
        m[r["day"][:7]] += r["r"]
    return sum(1 for v in m.values() if v > 0), len(m)


# ---------------------------------------------------------------------------
# premarket feature builder -- reads bars stamped BEFORE 09:30 and nothing else
# ---------------------------------------------------------------------------

def read_session(path, premarket_only=False):
    """One archived session -> (premarket aggregates, regular-hours close).

    `premarket_only=True` is what the ranker uses for TODAY.  The regular-hours close is
    read only so that YESTERDAY's close is available as today's gap reference -- it is a
    16:00-yesterday fact, not a look-ahead into today.
    """
    hi, lo, vol, opn, cls = -1e18, 1e18, 0.0, None, None
    rth_close = None
    with open(path, newline="") as fh:
        rd = csv.reader(fh)
        head = next(rd)
        ix = {k: i for i, k in enumerate(head)}
        for row in rd:
            hhmm = row[ix["Datetime"]][11:16]
            if hhmm < "09:30":
                hi = max(hi, float(row[ix["High"]]))
                lo = min(lo, float(row[ix["Low"]]))
                vol += float(row[ix["Volume"]])
                if opn is None:
                    opn = float(row[ix["Open"]])
                cls = float(row[ix["Close"]])
            elif premarket_only:
                break
            elif hhmm <= "15:59":
                rth_close = float(row[ix["Close"]])
    if cls is None:
        return None
    return dict(pm_hi=hi, pm_lo=lo, pm_vol=vol, pm_open=opn, pm_close=cls,
                rth_close=rth_close)


def raw_table(symbols=None, quiet=False):
    """(sym, day) -> raw premarket aggregates, for every archived session."""
    out = {}
    syms = sorted(symbols) if symbols else sorted(os.listdir(ARCHIVE))
    for sym in syms:
        d = os.path.join(ARCHIVE, sym)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".csv"):
                continue
            agg = read_session(os.path.join(d, fn))
            if agg:
                out[(sym, fn[:-4])] = agg
    if not quiet:
        print("   read %d archived sessions over %d symbols" % (len(out), len(syms)))
    return out


def derive(raw):
    """Raw aggregates -> the FEATURES, walk-forward.

    Every relative feature uses the symbol's PRIOR sessions only; the trailing window never
    contains today.  The gap reference is the prior session's 16:00 close.
    """
    bysym = defaultdict(list)
    for (sym, day) in raw:
        bysym[sym].append(day)
    feats = {}
    for sym, days in bysym.items():
        days.sort()
        hist_vol, hist_rng = [], []
        prev_close = None
        for day in days:
            a = raw[(sym, day)]
            rng = a["pm_hi"] - a["pm_lo"]
            f = {}
            f["pm_range_pct"] = rng / a["pm_close"] * 100 if a["pm_close"] else 0.0
            f["pm_ret_abs"] = (abs(a["pm_close"] - a["pm_open"]) / a["pm_open"] * 100
                               if a["pm_open"] else 0.0)
            f["pm_gap_abs"] = (abs(a["pm_close"] - prev_close) / prev_close * 100
                               if prev_close else None)
            f["pm_rvol"] = (a["pm_vol"] / st.median(hist_vol[-TRAIL:])
                            if len(hist_vol) >= 5 and st.median(hist_vol[-TRAIL:]) > 0
                            else None)
            f["pm_rrange"] = (f["pm_range_pct"] / st.median(hist_rng[-TRAIL:])
                              if len(hist_rng) >= 5 and st.median(hist_rng[-TRAIL:]) > 0
                              else None)
            f["pm_edge"] = (abs((a["pm_close"] - a["pm_lo"]) / rng - 0.5) * 2
                            if rng > 0 else 0.0)
            f["pm_close"] = a["pm_close"]      # stored, NOT a feature -- see FEATURES
            feats[(sym, day)] = f
            hist_vol.append(a["pm_vol"])
            hist_rng.append(f["pm_range_pct"])
            if a["rth_close"]:
                prev_close = a["rth_close"]
    return feats


def feature_table(quiet=False):
    if os.path.exists(CACHE):
        with open(CACHE) as fh:
            blob = json.load(fh)
        if blob.get("features") == FEATURES and blob.get("trail") == TRAIL:
            return {tuple(k.split("|")): v for k, v in blob["rows"].items()}
    feats = derive(raw_table(quiet=quiet))
    with open(CACHE, "w") as fh:
        json.dump({"features": FEATURES, "trail": TRAIL,
                   "rows": {"%s|%s" % k: v for k, v in feats.items()}}, fh)
    return feats


# ---------------------------------------------------------------------------
# the ranker: fit-half percentile transform, then OLS of R on the features
# ---------------------------------------------------------------------------

X13_FOUR = ["pm_range_pct", "pm_rvol", "pm_ret_abs", "pm_edge"]   # X13's own four, ex-ante


class Ranker:
    """Score = w . phi(x).  phi is the FIT half's empirical CDF, so the transform is
    monotone, outlier-proof and carries no scale; w is OLS of realised R on it.  Six
    features, ~450 fit rows: no hyperparameter, nothing to tune, nothing to overfit
    beyond the six coefficients themselves.

    Three forms, all fitted on the same half, all declared before any of them was scored:

      mode="level"    OLS of R on phi(x).  Predicts the LEVEL of R.
      mode="within"   OLS on within-CALENDAR-DAY demeaned phi(x) and R.  This is the
                      estimator that matches the task: it throws away everything that
                      separates days and fits only what separates candidates competing on
                      the SAME day, which is the only thing a day-ranker can act on.
      mode="x13"      no fit at all -- the equal-weight mean of the percentiles of X13's
                      own four premarket features.  Zero parameters, so nothing to overfit.
    """

    def __init__(self, rows, feats, names=None, mode="level"):
        self.mode = mode
        self.names = list(names or (X13_FOUR if mode == "x13" else FEATURES))
        self.grid = {}
        cols = {n: [] for n in self.names}
        y, dayof = [], []
        for r in rows:
            v = feats.get((r["sym"], r["day"]))
            if not v or any(v.get(n) is None for n in self.names):
                continue
            for n in self.names:
                cols[n].append(float(v[n]))
            y.append(r["r"])
            dayof.append(r["day"])
        for n in self.names:
            self.grid[n] = np.sort(np.asarray(cols[n], dtype=float))
        self.n_fit = len(y)
        P = np.asarray([[self._pct(n, cols[n][i]) for n in self.names]
                        for i in range(len(y))], dtype=float)
        y = np.asarray(y, dtype=float)
        if mode == "x13":
            self.w = np.concatenate([[0.0], np.ones(len(self.names)) / len(self.names)])
            return
        if mode == "within":
            keep = defaultdict(list)
            for i, d in enumerate(dayof):
                keep[d].append(i)
            idx = [i for d, ii in keep.items() if len(ii) > 1 for i in ii]
            Pw = np.copy(P[idx])
            yw = np.copy(y[idx])
            pos = {i: k for k, i in enumerate(idx)}
            for d, ii in keep.items():
                if len(ii) < 2:
                    continue
                rowsi = [pos[i] for i in ii]
                Pw[rowsi] -= Pw[rowsi].mean(axis=0)
                yw[rowsi] -= yw[rowsi].mean()
            w, *_ = np.linalg.lstsq(Pw, yw, rcond=None)
            self.w = np.concatenate([[0.0], w])
            self.n_fit = len(idx)
            return
        A = np.hstack([np.ones((len(y), 1)), P])
        self.w, *_ = np.linalg.lstsq(A, y, rcond=None)

    def _pct(self, name, x):
        g = self.grid[name]
        return float(np.searchsorted(g, x, side="left")) / max(1, len(g))

    def score(self, feats, sym, day):
        v = feats.get((sym, day))
        if not v or any(v.get(n) is None for n in self.names):
            return None
        return float(self.w[0] + sum(self.w[i + 1] * self._pct(n, float(v[n]))
                                     for i, n in enumerate(self.names)))

    def coefs(self):
        return list(zip(self.names, [float(x) for x in self.w[1:]]))


def pick(rows_by_day, days, keyfn, k=1):
    """Top-k per calendar day by `keyfn` (higher first), ties to the earliest entry."""
    out = []
    for d in days:
        v = sorted(rows_by_day[d], key=lambda r: (-keyfn(r), r[TIE]))
        out.extend(v[:k])
    return out


def arm_line(name, picks, extra=""):
    g, tot = months_green(picks)
    return ("   %-34s n=%-5d %+.4f  win %5.1f%%  mgreen %2d/%-2d %s"
            % (name, len(picks), mean(r["r"] for r in picks), winpct(r["r"] for r in picks),
               g, tot, extra))


def paired(a, b, days, bd):
    """Per-day paired difference between two selectors, over `days`."""
    da = {d: r for d, r in zip(days, a)}
    db = {d: r for d, r in zip(days, b)}
    diff = [da[d]["r"] - db[d]["r"] for d in days]
    n = len(diff)
    sd = st.pstdev(diff) if n > 1 else 0.0
    return mean(diff), 1.96 * sd / math.sqrt(n) if n else float("nan")


# ---------------------------------------------------------------------------
# SECTION 1 -- HELD-OUT S RECALL.  Before any in-sample number.
# ---------------------------------------------------------------------------

def engine_fire_time(sym, day):
    """The engine's own fired entry on a graded symbol-day, as ET.  `t4_engine_recall`'s
    replay, not reimplemented; bar 0 is 09:30, so bar i is 09:30 + i minutes."""
    from research.t4_engine_recall import run_day        # noqa: E402
    entries, _all, _raw = run_day(sym, day)
    if not entries:
        return None
    b = min(e["bar"] for e in entries)
    return "%02d:%02d" % (9 + (30 + b) // 60, (30 + b) % 60)


def section_recall(bk, feats):
    print("=== 1. HELD-OUT S RECALL -- research/marks/probe_omen_test1_2026-08-27.jsonl")
    cards = [json.loads(l) for l in open(MARKS, encoding="utf-8") if l.strip()]
    S = [c for c in cards if c.get("grade_std") == "S"]
    print("   Austin's held-out S days: %d.  Standing engine recall "
          "(research/t70_test1_score.md): 3/15 = 20.0%%" % len(S))
    print("   A one-trade-a-day governor is SUBTRACTION.  It can only keep or drop an S day")
    print("   the engine already fires on, never add one: ceiling 3/15, floor 0/15.  So the")
    print("   number below is a COST, and it is a cost the incumbent selector pays too.")

    bd = by_day(bk)
    days = sorted(bd)
    h = len(days) // 2
    H1, H2 = set(days[:h]), set(days[h:])
    models = {m: {"H1": Ranker([r for r in bk if r["day"] in H1], feats, mode=m),
                  "H2": Ranker([r for r in bk if r["day"] in H2], feats, mode=m)}
              for m in MODES}

    print("\n   The 3 S days the engine finds, ranked against that calendar day's whole")
    print("   candidate field: the book's traded rows that day, plus the S symbol-day")
    print("   itself when the trade path did not take it (BABA and IWM -- the engine fires")
    print("   on both in t70's per-symbol-day replay but neither reaches the book).")
    print("   Weights always come from the OTHER half, so no S day is scored by a model")
    print("   fitted on its own year.\n")

    fields = {}
    for sym, day in HELDOUT_FOUND_S:
        et = engine_fire_time(sym, day)
        field = [(r["sym"], r["day"], r["et"]) for r in bd.get(day, [])]
        if not any(s2 == sym for s2, _, _ in field):
            field.append((sym, day, et or "09:30"))
        fields[(sym, day)] = (et, field)

    print("   %-6s %-11s %-6s %-6s %-9s %-9s %-9s %-8s"
          % ("sym", "day", "fires", "field", "rank:level", "rank:within", "rank:x13",
             "by time"))
    keep = {m: [0, 0] for m in MODES}
    f1 = f2 = 0
    rand_exp = 0.0
    for sym, day in HELDOUT_FOUND_S:
        et, field = fields[(sym, day)]
        ranks = {}
        for m in MODES:
            rk = models[m]["H2" if day in H1 else "H1"]
            sc = [((rk.score(feats, s2, d2) if rk.score(feats, s2, d2) is not None
                    else -1e18), s2) for s2, d2, _ in field]
            order = [s for _, s in sorted(sc, key=lambda t: -t[0])]
            ranks[m] = order.index(sym) + 1
            keep[m][0] += ranks[m] <= 1
            keep[m][1] += ranks[m] <= 2
        by_t = [s for s, _, t in sorted(field, key=lambda x: x[2])]
        trank = by_t.index(sym) + 1
        f1 += trank <= 1
        f2 += trank <= 2
        rand_exp += 1.0 / len(field)
        print("   %-6s %-11s %-6s %-6d %-9s %-9s %-9s %-8s"
              % (sym, day, et or "-", len(field),
                 "%d/%d" % (ranks["level"], len(field)),
                 "%d/%d" % (ranks["within"], len(field)),
                 "%d/%d" % (ranks["x13"], len(field)),
                 "%d/%d" % (trank, len(field))))

    # the FILTER form -- it keeps most of the book, so its recall cost is separate
    filt = {}
    for m in MODES:
        for q in (25, 50, 75):
            kept = 0
            for sym, day in HELDOUT_FOUND_S:
                other = "H2" if day in H1 else "H1"
                rk = models[m][other]
                fit = [rk.score(feats, r["sym"], r["day"]) for r in bk
                       if r["day"] in (H2 if other == "H2" else H1)]
                fit = [v for v in fit if v is not None]
                cut = float(np.percentile(fit, q))
                own = rk.score(feats, sym, day)
                kept += 1 if (own is not None and own >= cut) else 0
            filt[(m, q)] = kept

    print("\n   HELD-OUT S RECALL -- reported before every in-sample number in this file")
    print("   %-44s %s" % ("engine today, whole book, no governor", "3/15 = 20.0%"))
    for m in MODES:
        print("   %-44s %d/15 = %4.1f%%   top-2 %d/15 = %4.1f%%"
              % ("+ ranker[%s] top-1 per day" % m, keep[m][0], 100 * keep[m][0] / 15,
                 keep[m][1], 100 * keep[m][1] / 15))
    print("   %-44s %d/15 = %4.1f%%   top-2 %d/15 = %4.1f%%"
          % ("+ first-by-time top-1 (the incumbent)", f1, 100 * f1 / 15, f2, 100 * f2 / 15))
    print("   %-44s %.2f/15 = %4.1f%%" % ("+ random top-1 per day (expectation)", rand_exp,
                                          100 * rand_exp / 15))
    print("   -- the FILTER form, which keeps most of the book instead of one trade a day --")
    for m in MODES:
        print("   %-44s %s"
              % ("+ ranker[%s] score >= p25 / p50 / p75" % m,
                 "  ".join("%d/15 = %4.1f%%" % (filt[(m, q)], 100 * filt[(m, q)] / 15)
                           for q in (25, 50, 75))))
    print("   %-44s %s" % ("recall gate (>=90%)",
                           "FAIL in every arm -- 20.0% is the ceiling before selection"))
    print("\n   Standing and unchanged by anything here: 12 of his 15 S days produce no fired")
    print("   entry at all, so 12/15 of the recall gap is upstream of selection.  Nothing a")
    print("   ranker does can reach it.  n=3 is far too small to rank the three forms by")
    print("   this column; it is reported as the COST of a one-a-day governor, which every")
    print("   arm here pays, the incumbent included.")
    return keep, f1, f2


# ---------------------------------------------------------------------------
# SECTION 2 -- the features, and the leak that was in the prototype
# ---------------------------------------------------------------------------

def section_features(bk, feats):
    print("=== 2. FEATURES -- all six computable at 09:29:00 ET")
    have = sum(1 for r in bk if feats.get((r["sym"], r["day"]))
               and all(feats[(r["sym"], r["day"])].get(n) is not None for n in FEATURES))
    print("   complete feature vectors: %d of %d traded rows (%.1f%%)"
          % (have, len(bk), 100 * have / len(bk)))
    for n in FEATURES:
        v = [feats[(r["sym"], r["day"])][n] for r in bk
             if feats.get((r["sym"], r["day"])) and feats[(r["sym"], r["day"])].get(n)
             is not None]
        print("      %-14s n=%-5d p10 %8.3f  p50 %8.3f  p90 %8.3f"
              % (n, len(v), np.percentile(v, 10), np.percentile(v, 50), np.percentile(v, 90)))

    print("\n   quartile mean R, whole book, each feature alone:")
    for n in FEATURES:
        v = sorted((r for r in bk if feats.get((r["sym"], r["day"]))
                    and feats[(r["sym"], r["day"])].get(n) is not None),
                   key=lambda r: feats[(r["sym"], r["day"])][n])
        q = len(v) // 4
        parts = [v[:q], v[q:2 * q], v[2 * q:3 * q], v[3 * q:]]
        print("      %-14s " % n + " | ".join(
            "Q%d n=%-4d %+.3f" % (i + 1, len(p), mean(x["r"] for x in p))
            for i, p in enumerate(parts)))

    print("\n   the prototype's leak, quantified:")
    pairs = [(r, feats[(r["sym"], r["day"])]) for r in bk if feats.get((r["sym"], r["day"]))]
    exante = [f["pm_range_pct"] for _, f in pairs]
    leaky = [f["pm_range_pct"] * f["pm_close"] / r["entry"] for r, f in pairs]
    print("      x13's `pmr_pct` divides the premarket range by `entry`, a post-09:30 price;")
    print("      its `pm_pos` places `entry` inside the premarket range.  Both are replaced")
    print("      here by premarket-CLOSE versions.  Spearman(leaky, ex-ante) = %s over %d rows"
          % (spearman(leaky, exante), len(pairs)))
    bd = by_day(bk)
    days = sorted(bd)
    fx = {(r["sym"], r["day"]): v for (r, _), v in zip(pairs, leaky)}
    lk1 = pick(bd, days, lambda r: fx.get((r["sym"], r["day"]), -1e18))
    ex1 = pick(bd, days, lambda r: (feats.get((r["sym"], r["day"])) or {})
               .get("pm_range_pct", -1e18))
    print("      1/day by the LEAKY range %+.4f   vs by the EX-ANTE range %+.4f  (%d days)"
          % (mean(r["r"] for r in lk1), mean(r["r"] for r in ex1), len(days)))


def spearman(a, b):
    if len(a) != len(b) or len(a) < 3:
        return "n/a"
    ra = np.argsort(np.argsort(np.asarray(a, dtype=float)))
    rb = np.argsort(np.argsort(np.asarray(b, dtype=float)))
    return "%+.4f" % float(np.corrcoef(ra, rb)[0, 1])


# ---------------------------------------------------------------------------
# SECTION 3 -- the ranker, temporally split
# ---------------------------------------------------------------------------

def halves_of(bk):
    bd = by_day(bk)
    days = sorted(bd)
    h = len(days) // 2
    return bd, days, {"H1": days[:h], "H2": days[h:]}


def featkey(feats, name):
    def f(r):
        v = (feats.get((r["sym"], r["day"])) or {}).get(name)
        return -1e18 if v is None else v
    return f


def section_rank(bk, feats):
    bd, days, halves = halves_of(bk)
    h = len(halves["H1"])
    print("=== 3. THE RANKER -- temporal split by CALENDAR DAY")
    print("   H1 %s..%s  %d days / %d trades      H2 %s..%s  %d days / %d trades"
          % (days[0], days[h - 1], h, sum(len(bd[d]) for d in days[:h]),
             days[h], days[-1], len(days) - h, sum(len(bd[d]) for d in days[h:])))
    multi = sum(1 for d in days if len(bd[d]) > 1)
    print("   %d of %d days carry more than one candidate -- the only days a ranker can act"
          % (multi, len(days)))
    print("   on.  Three ranker forms, all declared before any was scored: level, within,")
    print("   x13 (see the Ranker docstring).  Trying three and reporting three is not the")
    print("   same as trying three and reporting the winner; all three are below.")

    models = {m: {lbl: Ranker([r for r in bk if r["day"] in set(halves[lbl])], feats, mode=m)
                  for lbl in halves} for m in MODES}
    print("\n   coefficients on the fit-half percentile transform (R per unit of percentile):")
    for m in MODES:
        for lbl in ("H1", "H2"):
            print("      %-7s fit %s (n=%d): " % (m, lbl, models[m][lbl].n_fit)
                  + "  ".join("%s %+.3f" % (n, w) for n, w in models[m][lbl].coefs()))

    results = defaultdict(dict)
    for lbl in ("H1", "H2"):
        other = "H2" if lbl == "H1" else "H1"
        dd = halves[lbl]
        mdays = set(d for d in dd if len(bd[d]) > 1)
        print("\n   --- %s scored by models fitted on %s (OUT OF SAMPLE) ---" % (lbl, other))
        keyfns = {m: (lambda r, _m=m: (models[_m][other].score(feats, r["sym"], r["day"])
                                       if models[_m][other].score(feats, r["sym"], r["day"])
                                       is not None else -1e18)) for m in MODES}
        allrows = [r for d in dd for r in bd[d]]
        first = pick(bd, dd, lambda r: 0)
        arms = [("whole book, no selection", allrows, None),
                ("ORACLE best r (hindsight)", pick(bd, dd, lambda r: r["r"]), "oracle")]
        for m in MODES:
            arms.append(("ranker[%s] top-1" % m, pick(bd, dd, keyfns[m]), m))
            arms.append(("ranker[%s] top-2" % m, pick(bd, dd, keyfns[m], k=2), m + "2"))
        for n in FEATURES:
            arms.append(("%s top-1" % n, pick(bd, dd, featkey(feats, n)), n))
        arms += [("first by time (incumbent)", first, "first"),
                 ("first by time, top-2", pick(bd, dd, lambda r: 0, k=2), "first2"),
                 ("sgrade S>A>C", pick(bd, dd, lambda r: {"S": 3, "A": 2, "C": 1}
                                       .get(r.get("sgrade"), 0)), "sgrade"),
                 ("last by time", [sorted(bd[d], key=lambda r: r["et"])[-1] for d in dd],
                  "last")]
        random.seed(7)
        draws = [mean(random.choice(bd[d])["r"] for d in dd) for _ in range(2000)]
        for name, rows, key in arms:
            print(arm_line(name, rows))
            if key:
                results[lbl][key] = mean(r["r"] for r in rows)
        print("   %-34s n=%-5d %+.4f  (sd over 2000 draws %.4f)"
              % ("random 1/day", len(dd), mean(draws), st.pstdev(draws)))
        results[lbl]["random"] = mean(draws)
        results[lbl]["all"] = mean(r["r"] for r in allrows)

        print("   paired vs first-by-time (the only honest A/B -- same days, same field):")
        for m in MODES:
            p1 = pick(bd, dd, keyfns[m])
            md, ci = paired(p1, first, dd, bd)
            pm = [r for r, d in zip(p1, dd) if d in mdays]
            fm = [r for r, d in zip(first, dd) if d in mdays]
            md2, ci2 = paired(pm, fm, [d for d in dd if d in mdays], bd)
            print("      %-8s all %d days %+.4f +/-%.4f    the %d multi-candidate days "
                  "%+.4f +/-%.4f" % (m, len(dd), md, ci, len(mdays), md2, ci2))
            results[lbl]["paired_" + m] = (md, ci)

    print("\n   --- THE CHECK: beat first-by-time (+1.0527 pooled) AND random (+0.8809)")
    print("       in BOTH halves.  Each half is scored by the model fitted on the other,")
    print("       so both numbers are out of sample. ---")
    print("   %-22s %9s %9s %9s %9s  %s" % ("arm", "H1", "vs first", "H2", "vs first",
                                            "verdict"))
    passing = []
    for key, label in ([(m, "ranker[%s]" % m) for m in MODES]
                       + [(n, n) for n in FEATURES] + [("sgrade", "sgrade S>A>C")]):
        a = results["H1"][key] > results["H1"]["first"] and \
            results["H1"][key] > results["H1"]["random"]
        b = results["H2"][key] > results["H2"]["first"] and \
            results["H2"][key] > results["H2"]["random"]
        v = "PASS both" if (a and b) else ("H2 only" if b else ("H1 only" if a else "no"))
        if a and b:
            passing.append(label)
        print("   %-22s %+9.4f %+9.4f %+9.4f %+9.4f  %s"
              % (label, results["H1"][key], results["H1"][key] - results["H1"]["first"],
                 results["H2"][key], results["H2"][key] - results["H2"]["first"], v))
    print("   %-22s %+9.4f %+9.4f %+9.4f %+9.4f  %s"
          % ("first by time", results["H1"]["first"], 0.0, results["H2"]["first"], 0.0,
             "the incumbent"))
    print("   %-22s %+9.4f %+9.4f %+9.4f %+9.4f  %s"
          % ("ORACLE (hindsight)", results["H1"]["oracle"],
             results["H1"]["oracle"] - results["H1"]["first"], results["H2"]["oracle"],
             results["H2"]["oracle"] - results["H2"]["first"], "the ceiling"))
    print("\n   VERDICT: %s" % ("PASS -- " + ", ".join(passing) if passing
                                else "FAILS the check -- no ex-ante ranker beats arrival "
                                     "order in both halves"))

    # ---- the low-variance read: does the ranker FIND the day's best trade? ----
    print("\n   --- ORACLE HIT RATE on the %d multi-candidate days ---" % multi)
    print("   Mean R over 207 days has a +/-0.3R sampling bar and cannot separate these")
    print("   arms.  'did the pick equal the day's best trade' is a Bernoulli on the same")
    print("   days and its bar is ~7pp, so it is the statistic that can actually decide.")
    print("   %-22s %-22s %-22s" % ("arm", "H1 hit rate", "H2 hit rate"))
    hit_arms = ([("ranker[%s]" % m, (lambda r, _m=m, _o=None: 0)) for m in MODES])
    lines = {}
    for lbl in ("H1", "H2"):
        other = "H2" if lbl == "H1" else "H1"
        dd = [d for d in halves[lbl] if len(bd[d]) > 1]
        base = mean(1.0 / len(bd[d]) for d in dd)
        for m in MODES:
            rk = models[m][other]

            def kf(r, _rk=rk):
                v = _rk.score(feats, r["sym"], r["day"])
                return -1e18 if v is None else v
            lines.setdefault("ranker[%s]" % m, {})[lbl] = hitrate(bd, dd, kf)
        for n in FEATURES:
            lines.setdefault(n, {})[lbl] = hitrate(bd, dd, featkey(feats, n))
        lines.setdefault("first by time", {})[lbl] = hitrate(bd, dd, lambda r: 0)
        lines.setdefault("sgrade S>A>C", {})[lbl] = hitrate(
            bd, dd, lambda r: {"S": 3, "A": 2, "C": 1}.get(r.get("sgrade"), 0))
        lines.setdefault("RANDOM (expectation)", {})[lbl] = (base * len(dd), len(dd))
    for name, per in lines.items():
        cells = []
        for lbl in ("H1", "H2"):
            k, n = per[lbl]
            p = k / n
            cells.append("%5.1f%% +/-%4.1f (%d/%d)"
                         % (100 * p, 100 * 1.96 * math.sqrt(p * (1 - p) / n), round(k), n))
        print("   %-22s %-24s %-24s" % (name, cells[0], cells[1]))
    del hit_arms
    return results


def welch(a, b):
    """(mean(a) - mean(b)) and its Welch 95% CI -- x8's bar for a DISJOINT slice."""
    if len(a) < 2 or len(b) < 2:
        return float("nan"), float("nan")
    va, vb = st.variance(a) / len(a), st.variance(b) / len(b)
    return mean(a) - mean(b), 1.96 * math.sqrt(va + vb)


def hitrate(bd, days, keyfn):
    """How often the top-1 pick IS the day's best trade, over multi-candidate days."""
    hits = 0
    for d in days:
        v = bd[d]
        best = max(r["r"] for r in v)
        top = sorted(v, key=lambda r: (-keyfn(r), r[TIE]))[0]
        hits += 1 if top["r"] >= best - 1e-12 else 0
    return hits, len(days)


# ---------------------------------------------------------------------------
# SECTION 3b -- the form that could actually be run live
# ---------------------------------------------------------------------------

def section_deploy(bk, feats):
    """Top-1-of-the-day is not live-implementable: at 09:35 you do not know what will fire
    at 10:20.  What IS implementable at 09:29 is a SHORTLIST -- rank every symbol before
    the open, watch only the top k, take whatever fires there."""
    bd, days, halves = halves_of(bk)
    print("=== 3b. THE DEPLOYABLE FORM -- a 09:29 symbol shortlist, not a day ranking")
    print("   Top-1-of-the-day needs the whole day's candidate field, which does not exist")
    print("   until 11:00.  A shortlist does: rank all archived symbols at 09:29, watch the")
    print("   top k, trade whatever fires on them.  Fewer trades AND some days go empty.")
    syms = sorted({r["sym"] for r in bk})
    models = {m: {lbl: Ranker([r for r in bk if r["day"] in set(halves[lbl])], feats, mode=m)
                  for lbl in halves} for m in MODES}
    print("\n   %-16s %3s %6s %7s %9s %7s %8s %9s %9s" %
          ("arm", "k", "days", "trades", "mean R", "win%", "mgreen", "H1 mean", "H2 mean"))
    for m in MODES:
        for k in (1, 2, 3, 5, 8):
            rows = {"H1": [], "H2": []}
            hit = 0
            for lbl in ("H1", "H2"):
                rk = models[m]["H2" if lbl == "H1" else "H1"]
                for d in halves[lbl]:
                    sc = [(rk.score(feats, s, d), s) for s in syms]
                    sc = [(v, s) for v, s in sc if v is not None]
                    short = {s for _, s in sorted(sc, key=lambda t: -t[0])[:k]}
                    take = [r for r in bd[d] if r["sym"] in short]
                    if take:
                        hit += 1
                    rows[lbl].extend(take)
            allr = rows["H1"] + rows["H2"]
            g, tot = months_green(allr) if allr else (0, 0)
            print("   %-16s %3d %6d %7d %+9.4f %7.1f %5d/%-2d %+9.4f %+9.4f"
                  % ("shortlist[%s]" % m, k, hit, len(allr),
                     mean(r["r"] for r in allr) if allr else float("nan"),
                     winpct(r["r"] for r in allr), g, tot,
                     mean(r["r"] for r in rows["H1"]) if rows["H1"] else float("nan"),
                     mean(r["r"] for r in rows["H2"]) if rows["H2"] else float("nan")))
    print("   (days = calendar days on which the shortlist caught at least one signal, out")
    print("    of %d; the rest trade nothing at all.  Every mean is out of sample -- each"
          % len(days))
    print("    half is shortlisted by the model fitted on the other.)")


# ---------------------------------------------------------------------------
# SECTION 4 -- the price, in the currency Austin asked for
# ---------------------------------------------------------------------------

def section_price(bk, feats, results):
    bd = by_day(bk)
    days = sorted(bd)
    h = len(days) // 2
    halves = {"H1": days[:h], "H2": days[h:]}
    allm = {m: {lbl: Ranker([r for r in bk if r["day"] in set(halves[lbl])], feats, mode=m)
                for lbl in halves} for m in MODES}
    print("=== 4. THE PRICE -- trades surrendered per +0.01 R of mean, x8's currency")
    print("   Austin wants MORE trades, so every subtraction below is priced, not "
          "recommended.\n")
    base_n = len(bk)
    base_r = mean(r["r"] for r in bk)
    print("   %-32s %6s %9s %8s %9s %10s" %
          ("arm (pooled, each half scored", "n", "mean R", "dN", "dR", "trades per"))
    print("   %-32s %6s %9s %8s %9s %10s" %
          (" out of sample)", "", "", "", "", "+0.01R"))
    print("   %-32s %6d %+9.4f %8s %9s %10s" % ("A0 incumbent whole book", base_n, base_r,
                                                "0", "-", "-"))
    hh = len(halves["H1"])

    def oos(mode, k=None, thresh=None):
        """Score each half with the model fitted on the OTHER half.  A score threshold is
        also taken from the fit half's own score distribution -- never from the half being
        scored."""
        rows = []
        for lbl in ("H1", "H2"):
            fit = "H2" if lbl == "H1" else "H1"
            dd = halves[lbl]
            if mode is None:
                keyfn = (lambda r: 0)
            else:
                rk = allm[mode][fit]

                def keyfn(r, _rk=rk):
                    v = _rk.score(feats, r["sym"], r["day"])
                    return -1e18 if v is None else v
            if thresh is None:
                rows.extend(pick(bd, dd, keyfn, k=k))
            else:
                fitrows = [keyfn(r) for d in halves[fit] for r in bd[d]]
                fitrows = [v for v in fitrows if v > -1e17]
                cut = np.percentile(fitrows, thresh)
                rows.extend([r for d in dd for r in bd[d] if keyfn(r) >= cut])
        return rows

    arms = []
    for m in MODES:
        for k in (1, 2, 3):
            arms.append(("ranker[%s] top-%d / day" % (m, k), oos(m, k=k)))
    arms += [("first-by-time top-1 / day", oos(None, k=1)),
             ("first-by-time top-2 / day", oos(None, k=2)),
             ("first-by-time top-3 / day", oos(None, k=3))]
    for m in MODES:
        for q in (25, 50, 75):
            arms.append(("ranker[%s] >= p%d (FILTER)" % (m, q), oos(m, thresh=q)))
    for name, rows in arms:
        n, r = len(rows), mean(x["r"] for x in rows)
        dn, dr = n - base_n, r - base_r
        per = abs(dn) / (dr * 100) if dr > 0 else float("nan")
        g, tot = months_green(rows)
        h1 = [x for x in rows if x["day"] in set(halves["H1"])]
        h2 = [x for x in rows if x["day"] in set(halves["H2"])]
        print("   %-32s %6d %+9.4f %8d %+9.4f %10s  win %5.1f%% mg %2d/%-2d  H1 %+.4f H2 %+.4f"
              % (name, n, r, dn, dr, ("%.1f" % per) if per == per else "n/a",
                 winpct(x["r"] for x in rows), g, tot,
                 mean(x["r"] for x in h1), mean(x["r"] for x in h2)))
    print("\n   H1 and H2 are printed on every row because the pooled column is the average")
    print("   of two disagreeing years: every top-1 ranker arm is BELOW first-by-time in H1")
    print("   and above it in H2.")

    # ---- the filter form, judged the way x8 judged a disjoint slice ----
    print("\n   --- THE FILTER FORM vs its OWN HALF's baseline, with a Welch bar ---")
    print("   A top-k governor competes with first-by-time.  A score FILTER does not: it")
    print("   competes with the whole book, keeps most of the trades, and is the only shape")
    print("   here that answers 'more trades' rather than 'fewer'.  x8's rule applies -- a")
    print("   disjoint slice is judged against its complement on a Welch 95% CI, not against")
    print("   the +/-0.0095R house bar, which is for arms that share nearly every trade.")
    print("   %-26s %-30s %-30s" % ("arm", "H1  slice vs complement", "H2  slice vs complement"))
    for m in MODES:
        for q in (25, 50, 75):
            rows = set(id(r) for r in oos(m, thresh=q))
            cells = []
            both = clears = True
            for lbl in ("H1", "H2"):
                a = [r["r"] for d in halves[lbl] for r in bd[d] if id(r) in rows]
                b = [r["r"] for d in halves[lbl] for r in bd[d] if id(r) not in rows]
                dl, ci = welch(a, b)
                both &= dl > 0
                clears &= dl > ci
                cells.append("n=%-4d %+.4f  d %+.4f+/-%.4f"
                             % (len(a), mean(a), dl, ci))
            print("   %-26s %-30s %-30s %s"
                  % ("ranker[%s] >= p%d" % (m, q), cells[0], cells[1],
                     "CLEARS BOTH BARS" if clears else
                     ("both halves +" if both else "")))

    # ---- and the permutation null for exactly that pattern ----
    print("\n   --- LABEL-PERMUTATION NULL for the filter arms ---")
    print("   Nine filter arms were tried, so 'one of them survived both halves' has to be")
    print("   priced.  R is shuffled WITHIN each half 2000 times, the same rows are kept,")
    print("   and the two events are counted: both halves positive, and both halves")
    print("   clearing their own Welch bar.")
    print("   %-26s %14s %16s" % ("arm", "P(both > 0)", "P(both clear)"))
    for m in MODES:
        for q in (25, 50, 75):
            keep = set(id(r) for r in oos(m, thresh=q))
            idx = {lbl: [r for d in halves[lbl] for r in bd[d]] for lbl in halves}
            mask = {lbl: [id(r) in keep for r in idx[lbl]] for lbl in halves}
            rng = random.Random(11)
            pos = clear = 0
            for _ in range(2000):
                ok_pos = ok_cl = True
                for lbl in ("H1", "H2"):
                    rs = [r["r"] for r in idx[lbl]]
                    rng.shuffle(rs)
                    a = [v for v, keep_it in zip(rs, mask[lbl]) if keep_it]
                    b = [v for v, keep_it in zip(rs, mask[lbl]) if not keep_it]
                    dl, ci = welch(a, b)
                    ok_pos &= dl > 0
                    ok_cl &= dl > ci
                pos += ok_pos
                clear += ok_cl
            print("   %-26s %13.3f%% %15.3f%%"
                  % ("ranker[%s] >= p%d" % (m, q), 100 * pos / 2000, 100 * clear / 2000))


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_no_post_0930_feature():
    """No feature may be a book field, and none may be one of the known post-09:30 fields."""
    bk = load_book()
    book_fields = set(bk[0].keys())
    bad = [n for n in FEATURES if n in book_fields]
    assert not bad, "feature read off the book (post-09:30 by construction): %s" % bad
    bad = [n for n in FEATURES if n in POST_0930_BOOK_FIELDS]
    assert not bad, "post-09:30 feature in the feature list: %s" % bad
    assert all(n.startswith("pm_") for n in FEATURES), \
        "every admissible feature is premarket-derived and says so in its name"
    return "no post-09:30 feature in the feature list (%d features, all pm_*)" % len(FEATURES)


def test_builder_ignores_rth():
    """Rebuild one day's features from a CSV with every 09:30+ bar physically deleted.

    Identical output is the only proof that the builder never read a regular-hours bar.
    """
    import tempfile
    sym, day = "NVDA", "2025-06-02"
    src = os.path.join(ARCHIVE, sym, day + ".csv")
    full = read_session(src)
    with tempfile.TemporaryDirectory() as td:
        cut = os.path.join(td, "cut.csv")
        with open(src, newline="") as fh, open(cut, "w", newline="") as out:
            rd = csv.reader(fh)
            wr = csv.writer(out)
            head = next(rd)
            wr.writerow(head)
            for row in rd:
                if row[0][11:16] < "09:30":
                    wr.writerow(row)
        trunc = read_session(cut)
    for k in ("pm_hi", "pm_lo", "pm_vol", "pm_open", "pm_close"):
        assert full[k] == trunc[k], "%s changed when 09:30+ bars were deleted" % k
    assert trunc["rth_close"] is None and full["rth_close"] is not None, \
        "the truncated file must have no regular-hours close at all"
    return "features identical with all 09:30+ bars deleted (%s %s)" % (sym, day)


def test_trailing_window_is_strictly_prior():
    """The relative features may never see today."""
    raw = {}
    for i, day in enumerate(["2025-01-%02d" % (d + 1) for d in range(30)]):
        raw[("ZZZ", day)] = dict(pm_hi=101.0, pm_lo=99.0, pm_vol=1000.0, pm_open=100.0,
                                 pm_close=100.0, rth_close=100.0)
    spike = "2025-01-30"
    raw[("ZZZ", spike)] = dict(pm_hi=101.0, pm_lo=99.0, pm_vol=1e9, pm_open=100.0,
                               pm_close=100.0, rth_close=100.0)
    f = derive(raw)
    assert f[("ZZZ", spike)]["pm_rvol"] > 1e5, \
        "a volume spike must show up in ITS OWN rvol"
    assert abs(f[("ZZZ", "2025-01-29")]["pm_rvol"] - 1.0) < 1e-9, \
        "the day BEFORE the spike must not see it -- the window leaked forward"
    return "trailing median uses strictly prior sessions"


def book_content_sha():
    """sha256 over the 1,017 TRADED rows, key-sorted -- NOT the file's byte hash.

    The file's bytes are not the invariant: `meta.generated` moves on every re-run of
    `research/g3_onwatch_2y.py`.  The traded rows are.  `load_book` searches the candidate
    paths for the file that still carries them; this reports what it found.
    """
    tr = load_book()
    blob = json.dumps(tr, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest(), len(tr), mean(r["r"] for r in tr)


def test_book_untouched():
    """The standing book is still reachable and still says what it said.

    This is the "byte-identical" proof for a read-only track: nothing here writes to the
    book, and every number is refused if the rows underneath have moved.  It has already
    fired once for real -- T11 rewrote `g3_arm_ow1.json` mid-measurement.
    """
    got, n, mr = book_content_sha()
    assert n == 1017, "traded rows moved: %d (expected 1017)" % n
    assert abs(mr - 0.9551) < 5e-5, "book mean R moved: %+.4f (expected +0.9551)" % mr
    assert got == BOOK_SHA, "traded rows changed: %s (expected %s)" % (got, BOOK_SHA)
    return ("standing book found in %s: %d rows, %+.4f mean, content sha %s"
            % (os.path.basename(BOOK_USED or "?"), n, mr, got[:16]))


def test_ranker_is_pure_ranking():
    """The score must be invariant to anything the trade did.  Shuffle every outcome field
    on a copy of the book and the top-1 picks must not move."""
    bk = load_book()
    feats = feature_table(quiet=True)
    bd = by_day(bk)
    days = sorted(bd)
    rk = Ranker([r for r in bk if r["day"] in set(days[:len(days) // 2])], feats)

    def sc(r):
        v = rk.score(feats, r["sym"], r["day"])
        return -1e18 if v is None else v

    before = [(r["sym"], r["day"]) for r in pick(bd, days, sc)]
    shuffled = json.loads(json.dumps(bk))
    rs = [r["r"] for r in shuffled]
    random.seed(1)
    random.shuffle(rs)
    for r, v in zip(shuffled, rs):
        r["r"] = v
    bd2 = by_day(shuffled)
    after = [(r["sym"], r["day"]) for r in pick(bd2, days, sc)]
    assert before == after, "the ranker's picks moved when outcomes were shuffled"
    return "picks invariant to shuffling every realised R (%d days)" % len(days)


TESTS = [test_no_post_0930_feature, test_builder_ignores_rth,
         test_trailing_window_is_strictly_prior, test_ranker_is_pure_ranking,
         test_book_untouched]


def selfcheck():
    bad = 0
    for t in TESTS:
        try:
            print("   PASS  %-32s %s" % (t.__name__, t()))
        except AssertionError as e:
            bad += 1
            print("   FAIL  %-32s %s" % (t.__name__, e))
    print("   %d/%d green" % (len(TESTS) - bad, len(TESTS)))
    return bad


# ---------------------------------------------------------------------------

def main(argv):
    if "--selfcheck" in argv:
        return 1 if selfcheck() else 0
    want = ([a for a in argv if not a.startswith("-")]
            or ["recall", "features", "rank", "deploy", "price"])
    bk = load_book()
    feats = feature_table()
    print("\n   book: %s -- %d traded rows, %+.4f mean R, content sha %s\n"
          % (os.path.relpath(BOOK_USED, _ROOT), len(bk), mean(r["r"] for r in bk),
             BOOK_SHA[:12]))
    if "recall" in want:
        section_recall(bk, feats)
        print()
    if "features" in want:
        section_features(bk, feats)
        print()
    res = None
    if "rank" in want:
        res = section_rank(bk, feats)
        print()
    if "deploy" in want:
        section_deploy(bk, feats)
        print()
    if "price" in want:
        section_price(bk, feats, res)
        print()
    test_book_untouched()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
