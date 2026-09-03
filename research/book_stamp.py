"""book_stamp.py — a book that says who it is, and a check any report can call.

WHY THIS EXISTS. Four different files have been called `research/bt2y_trades.json`
in four days — a published-fill book, a dedupe-fixed book, a close-fill book — and
nothing on disk said which was which. Reports quoted a figure, the book underneath
them was rebuilt, and the figure silently stopped being reproducible. That is the
same failure shape as `research/g82_artifact_cleanup.md` found in the verdict page
(it hard-read a dated snapshot with no freshness check) and the same shape as the
mark-file trap in `CLAUDE.md`: real work, correct work, invisible to anyone who
looks at the file instead of remembering the session.

So a book now carries its own identity:

    entry_fill   which of the five entry fills priced it (`entry_fill.py`)
    commit       the git commit it was built from, and whether the tree was dirty
    built_at     when
    signals/traded/sessions   how big it is
    flags        the EFFECTIVE value of every behaviour-changing engine flag,
                 read off the modules themselves so defaults are captured too
    book_id      a sha256 fingerprint of the trades — two books with the same id
                 hold the same trades at the same prices

And a report can assert against it before it quotes a dollar:

    from research.book_stamp import assert_book, assert_figure
    assert_book(BOOK, entry_fill="close", traded=4329)
    assert_figure(BOOK, "one_a_day", "per_day", 28)      # raises if the book moved

Both raise `BookMismatch` with the old and new value spelled out. A report that
calls neither is quoting a number it cannot vouch for.

1R = $1,000 (CLAUDE.md). Figures are computed by `research/g72_suppress_price.py`,
imported not re-typed, so "per_day" here means exactly what it meant when the
board was written.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The engine flags that change what the book contains. Read off the modules
# rather than out of os.environ, because most runs set none of them and the
# DEFAULT is what actually priced the book. `(module, [names])`; a module that
# will not import is recorded as unavailable rather than silently skipped.
FLAG_SOURCES = (
    ("entry_fill", ("ENTRY_FILL", "ENTRY_LIMIT_EXPIRE")),
    ("loss_halt", ("LOSS_HALT", "HALT_AFTER_CONSECUTIVE_LOSSES")),
    ("stop_rule", ("MAX_LOSS_R", "DISASTER_STOP_R")),
    ("backtest_week", (
        "RISK_DOLLARS", "DEDUPE_MODE", "DEDUPE_FIRES_ONLY", "DEDUPE_BARS",
        "DEDUPE_CONTIG", "BE_TRIGGER", "BE_MOVE_R", "STOP_ON_CLOSE",
        "PESSIMISTIC_FILL", "DISASTER_STOP", "DISASTER_R", "STOP_ARM",
        "TARGET_ON_CLOSE", "ENTRY_SCRATCH", "SCRATCH_PROBE_ON", "SCALE_PLAN",
        "SSCORE_SIZING", "RULE6_ENABLED",
        # 2026-09-02, the four-rung exit ladder. Eleven flags landed unstamped,
        # which is the same hole the three _route C-cap gates left and the exact
        # confusion this file exists to end -- a book built with the ladder on
        # was indistinguishable from one built without it. SCALE_PLAN alone does
        # not cover them: LADDER_RUNNER_GUARD changes the book while
        # SCALE_PLAN is still the shipped default.
        "LADDER_RUNNER_GUARD", "LADDER_WEIGHTS", "LADDER_PSYCH_TOL",
        "LADDER_PSYCH_STEP", "LADDER_PT4_MODE", "LADDER_PT4_R",
        "LADDER_MIN_RUNG_GAP", "LADDER_TREND_TEST",
        "LADDER_TRAIL", "LADDER_HTF_PIVOTS")),
        # NOT stamped, deliberately: backtest_week.LADDER_TREND_FUNNEL is a
        # Counter that ACCUMULATES during a run (backtest_week.py:266, 335, 343).
        # It is a diagnostic, not a flag. Stamping it would make the stamp -- and
        # anything derived from it -- depend on how much of the book had been
        # simulated when it was read, which is the opposite of a fingerprint.
    ("signal_runner", (
        "ON_WATCH", "OCR_STRICT", "BNR_DISPLACEMENT_GATE", "COUNTER_TREND_CAP",
        "GRADE_FIX", "HTF_BIAS_GATE", "RULE84_OFF", "RULE84_STRICT",
        "RULE84_ARM_SGRADE", "RULE84_ARM_NOGATE", "RULE84_SOURCE",
        "RULE84_MAX_ATTEMPTS", "X_LIFT", "MIN_STOP_PCT", "NO_REPEAT_ENTRIES",
        "SESSION_START", "SESSION_END", "SESSION_EXTREME_FRAC",
        "INTRABAR_STOP_AT_BAR", "STOP_PLACEMENT", "STOP_FILL_ORDER",
        "PIVOT_LEVELS", "PIVOT_STRENGTH", "PIVOT_LOOKBACK",
        "LEVEL_RETIRE_TOUCHES", "LEVEL_RETIRE_COOLDOWN", "MESH_S_VETO",
        "S_PLUS_PER_DAY", "RETEST_TOL_FRAC", "ARRIVAL_LADDER",
        "TRADE_RETIRED_SETUPS", "CONFLUENCE_SETUP_ROUTES", "SAC_LADDER_VARSET",
        # 2026-09-02: the three C-cap gates in _route were all missing from this
        # list, so a book built with any of them on was indistinguishable from
        # one built without — the exact confusion the stamp exists to end.
        "RETEST_REQUIRED", "S_GATE", "RULE_710_ENABLED")),
)

# The figures a report is allowed to assert on, and how far each may drift
# before the assert bites. Dollars are whole dollars; a rerun of the same book
# is bit-identical, so these tolerances only absorb rounding in a quoted figure.
FIGURE_TOL = {"trades": 0, "win_pct": 0.1, "per_trade": 1, "per_day": 1,
              "mean_r": 0.001, "months_green": 0, "weeks_green": 0,
              "worst_drawdown": 1, "total_dollars": 1, "days_traded": 0,
              "green_days_pct": 0.1, "months": 0, "weeks": 0}


class BookMismatch(AssertionError):
    """A published figure no longer matches the book on disk.

    An AssertionError subclass because there is no recovering from it: either
    the report is stale or the book is, and a human has to say which."""


# ------------------------------------------------------------------ the stamp

def engine_flags() -> dict:
    """Effective value of every behaviour-changing flag, defaults included."""
    import importlib
    out = {}
    for mod, names in FLAG_SOURCES:
        try:
            m = importlib.import_module(mod)
        except Exception as e:                       # pragma: no cover
            out[mod] = "UNAVAILABLE: %s" % type(e).__name__
            continue
        for n in names:
            v = getattr(m, n, "<absent>")
            out["%s.%s" % (mod, n)] = v if isinstance(
                v, (str, int, float, bool, type(None))) else repr(v)
    return out


def _git(*args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=str(ROOT), text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              timeout=60).stdout.strip()
    except Exception:                                # pragma: no cover
        return ""


# The modules that actually build a book. A dirty file here means the book on
# disk cannot be rebuilt from the commit it names; a dirty file anywhere else in
# the repo does not change a single trade.
ENGINE_PY = ("signal_runner.py", "backtest_week.py", "backtest_2y.py",
             "backtest_12mo.py", "entry_fill.py", "stop_rule.py", "loss_halt.py",
             "options_sizer.py", "polygon_feed.py", "universe.py",
             "research/downgrade.py", "research/book_stamp.py")


def git_state() -> dict:
    """The commit the book was built from, and whether the ENGINE was dirty.

    Dirty matters: OMEN-7.3 §4 records a night where every published figure sat
    on eight uncommitted engine files and a fresh clone earned half as much."""
    dirty = [ln[3:].strip().strip('"') for ln in _git("status", "--porcelain").splitlines()
             if ln[3:].strip().strip('"').endswith(".py")]
    return {"commit": _git("rev-parse", "HEAD"),
            "commit_subject": _git("log", "-1", "--format=%s"),
            "dirty_engine_py": sorted(p for p in dirty if p in ENGINE_PY),
            "dirty_py_count": len(dirty)}


def book_id(rows) -> str:
    """Fingerprint of the trades: same id == same trades at the same prices."""
    h = hashlib.sha256()
    for r in rows:
        h.update(("%s|%s|%s|%s|%.4f|%.4f|%.4f|%s|%s\n" % (
            r.get("sym"), r.get("day"), r.get("et"), r.get("dir"),
            r.get("entry", 0.0), r.get("stop", 0.0), r.get("pnl", 0.0),
            r.get("status"), r.get("traded"))).encode())
    return h.hexdigest()[:16]


def stamp(rows, **extra) -> dict:
    """The identity block a book writes into its own JSON."""
    out = {"built_at": datetime.now().isoformat(timespec="seconds"),
           "python": sys.version.split()[0],
           "git": git_state(),
           "flags": engine_flags(),
           "book_id": book_id(rows),
           "rows": len(rows)}
    out.update(extra)
    return out


# ------------------------------------------------------------------- the check

def load_book(path):
    b = json.loads(Path(path).read_text(encoding="utf-8"))
    return b["meta"], b["trades"]


def describe(path) -> str:
    """One line naming the book, for the top of any report that quotes it."""
    meta, rows = load_book(path)
    st = meta.get("stamp", {})
    return ("%s — fill %s · %d traded of %d · commit %s%s · built %s · id %s"
            % (Path(path).name, meta.get("entry_fill", "UNSTAMPED"),
               meta.get("traded", 0), meta.get("signals", len(rows)),
               (st.get("git", {}).get("commit", "?") or "?")[:8],
               " (dirty tree)" if st.get("git", {}).get("dirty_py_count") else "",
               st.get("built_at", meta.get("generated", "?")),
               st.get("book_id", "UNSTAMPED")))


def assert_book(path, *, entry_fill=None, traded=None, signals=None,
                book_id_=None, commit=None):
    """Assert the book on disk is still the one a figure was published from."""
    meta, rows = load_book(path)
    st = meta.get("stamp", {})
    got = {"entry_fill": meta.get("entry_fill"), "traded": meta.get("traded"),
           "signals": meta.get("signals"),
           "book_id_": st.get("book_id"),
           "commit": (st.get("git", {}) or {}).get("commit")}
    want = {"entry_fill": entry_fill, "traded": traded, "signals": signals,
            "book_id_": book_id_, "commit": commit}
    bad = ["%s: published %r, book on disk has %r" % (k, want[k], got[k])
           for k in want if want[k] is not None and want[k] != got[k]]
    if bad:
        raise BookMismatch("%s is not the book these figures came from:\n  %s"
                           % (path, "\n  ".join(bad)))
    return meta


_FIG_CACHE = {}


def book_figures(path) -> dict:
    """{'shipped'|'all': {...}, 'one_a_day': {...}} on the committed arithmetic.

    Cached on (path, mtime): a report asserting fourteen figures should not
    re-parse a 130 MB book fourteen times. 'all' is an alias for 'shipped' —
    'take every signal the engine fires' is what both mean."""
    key = (str(path), Path(path).stat().st_mtime_ns)
    if key not in _FIG_CACHE:
        sys.path.insert(0, str(ROOT / "research"))
        from g72_suppress_price import stats, shipped_rows, oneaday_rows  # noqa: E402
        meta, rows = load_book(path)
        nd = meta["sessions"]
        shipped = stats(shipped_rows(rows), nd)
        _FIG_CACHE.clear()
        _FIG_CACHE[key] = {"shipped": shipped, "all": shipped,
                           "one_a_day": stats(oneaday_rows(rows), nd)}
    return _FIG_CACHE[key]


def assert_figure(path, policy, field, expected, tol=None):
    """Assert a published figure still comes out of the book on disk.

    `policy` is 'shipped' (take everything) or 'one_a_day'. Raises BookMismatch
    naming both numbers, so a stale report says what moved instead of lying."""
    got = book_figures(path)[policy].get(field)
    tol = FIGURE_TOL.get(field, 0) if tol is None else tol
    if got is None or abs(got - expected) > tol:
        raise BookMismatch(
            "%s / %s: published %s, book on disk gives %s (tolerance %s)\n  book: %s"
            % (policy, field, expected, got, tol, describe(path)))
    return got


if __name__ == "__main__":
    for p in (sys.argv[1:] or [str(ROOT / "research" / "bt2y_trades.json")]):
        print(describe(p))
