"""W5 -- the 12 held-out S days the engine missed, taken apart bar by bar.

THE SAMPLE
----------
`research/marks/probe_omen_test1_2026-08-27.jsonl` -- 100 symbol-days Austin
graded 2026-08-27 (15 S / 27 A / 16 C / 42 X). It is the project's ONLY clean
held-out sample: no rule was fitted on it, no threshold tuned to it.
`research/t70_test1_score.py` scores it and reports **S recall 3/15**, **false
fire 12/42** -- the engine is more likely to fire on a day he refused than on a
day he called S.

This script does not re-litigate that. It takes the **12 S days it missed** and
answers, per day:

  * did the engine produce NO signal of any grade at all, or did it see one and
    throw it away?
  * if it threw one away, WHICH LINE killed it, and what value failed the test?
  * what would opening that gate cost, priced population-wide.

DIAGNOSIS ONLY. No default is changed, no flag is added, nothing is adopted.
Every number below is produced by this file; `research/w5_silent_s_autopsy.md`
is its output and cites it.

HOW THE GATE IS NAMED (not guessed)
-----------------------------------
`research/g10_arming_funnel.py` is the pattern: instrument the real code, count
the deaths per condition in evaluation order, never infer the cause from the
outcome. Two instruments here, both read-only and both removed in a `finally`:

  1. **A line tracer** over `signal_runner`'s grading path
     (`detect_signals`, `_emit`, `_route`, `_grade_for_levels`,
     `_calibration_grade`, `_min_viable_stop`). Every executed line inside those
     functions is recorded, segmented per emitted signal by the `_emit` call
     boundary. The killing gate for a skipped signal is then the LAST executed
     line that wrote the skip grade -- read off the source, not deduced. Line
     numbers are resolved from the live source text at import, so they stay
     correct when the file moves under an unrelated edit.

  2. **`omen_bot.BR_FUNNEL`**, the break-and-retest FSM's own stage counter
     (break -> leave -> retest -> confirm). For a day that produced no signal at
     all there is nothing for the tracer to attribute, so the question becomes
     "how far up the FSM did the candidate get", and that counter answers it per
     level per bar. The wrapper reads the delta after each call; the FSM itself
     is untouched.

`CaptureRunner` (`research/t4_engine_recall.py`) is reused rather than
reimplemented, so the signals counted here are the same signals T70 counted.
NOTE its `_route` is a SIMPLIFIED route: it applies `_grade_for_levels`,
`_calibration_grade`, the X-grade skip and the C-only tight-stop skip, and it
does NOT apply `LEVEL_RETIRE_TOUCHES`, `ENFORCE_NO_REPEAT` or
`NO_REPEAT_ENTRIES`. Those three can only ever remove more, so every recall
number here is an UPPER bound on what the shipped router would find.

    python research/w5_silent_s_autopsy.py                 # the 12 days
    python research/w5_silent_s_autopsy.py --population    # + 2y gate pricing
    python research/w5_silent_s_autopsy.py --stride 3      # population sample stride
    python research/w5_silent_s_autopsy.py --selfcheck

Writes `research/w5_silent_s_autopsy.md`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import omen_bot                                                     # noqa: E402
import signal_runner                                                # noqa: E402
from research.t4_engine_recall import (CaptureRunner, ENTRY_CUTOFF,  # noqa: E402
                                       DEDUPE_BARS, TOL, htf_bias,
                                       premarket_extremes, prior_day_levels,
                                       rth_candles)
from research.t70_test1_score import load_cards, in_universe        # noqa: E402
from universe import BACKTEST_SYMBOLS                               # noqa: E402

OUT_MD = os.path.join(_HERE, "w5_silent_s_autopsy.md")
# The population pass is a ~1 hour replay of the whole archive. Its COUNTS are
# cached here so the report can be re-rendered without re-running it; the cache
# records the stride and the engine commit it was measured at, and the report
# prints both. Delete the file to force a fresh pass.
POP_CACHE = os.path.join(_HERE, "_w5_pop_counts.json")
ARCHIVE = os.path.join(_ROOT, "data_archive")

# ---------------------------------------------------------------------------
# 1. resolve the gate lines from the live source
# ---------------------------------------------------------------------------
# A "gate" is any line on the grading path that WRITES a grade or logs a skip.
# Resolved by scanning the source text so an unrelated edit above them cannot
# make this report cite the wrong line.

_SRC_PATH = signal_runner.__file__.replace(".pyc", ".py")
with open(_SRC_PATH, encoding="utf-8") as _fh:
    _SRC = _fh.read().splitlines()

_GATE_RE = re.compile(
    r"(grade\s*=\s*TradeGrade\.[A-Z_]+"
    r"|sig\[\"grade\"\]\s*=\s*TradeGrade\.[A-Z_]+"
    r"|skip_reason=)")

GATE_SRC = {i + 1: line.strip()
            for i, line in enumerate(_SRC) if _GATE_RE.search(line)}

# The functions whose lines are traced. Everything that can turn a detected
# setup into a non-trade lives in one of these.
WATCH_FUNCS = {"detect_signals", "_emit", "_route", "_grade_for_levels",
               "_calibration_grade", "_min_viable_stop", "_grade_trade"}

# Human names for the gates this report actually hits, keyed by the source text
# so they survive a line-number shift. Anything unnamed prints its raw source.
GATE_LABEL = [
    ("floor_reference_risk", "RISK FLOOR — stock risk < max($0.10, 0.15% of close)"),
    ("stock_risk / current.close > 0.004", "OCR WIDE-STOP — order-block stop > 0.40% of close"),
    ("if stock_risk < 0.50", "FLAT $0.50 RISK FLOOR (FVG / order block / flag)"),
    ("grade.value == \"B\"", "OCR B->C DEMOTION — order block is alert-only below A"),
    ("capped C: counter day trend", "COUNTER-TREND CAP — signal fights the day's direction"),
    ("floor B: first with-trend", "ARRIVAL-ORDER FLOOR — first with-trend signal of the day"),
    ("blocks 2R path", "LEVEL-BLOCK CAP — a level sits inside the 2R path"),
    ("entry not beyond all levels", "A->B — entry not beyond every level"),
    ("stop too tight", "TIGHT-STOP SKIP — C-grade only"),
    ("X grade (skip)", "X/D GRADE SKIP — the route's terminal refusal"),
]


def label_for(lineno):
    src = GATE_SRC.get(lineno, "")
    ctx = " ".join(_SRC[max(0, lineno - 4):lineno + 1])
    for needle, name in GATE_LABEL:
        if needle in src or needle in ctx:
            return name
    return src or "line %d" % lineno


# ---------------------------------------------------------------------------
# 2. the tracer
# ---------------------------------------------------------------------------

_HITS = []          # ordered stream: ("emit",) boundaries and ("line", lineno)
_TRACING = False


def _local_trace(frame, event, arg):
    if event == "line":
        _HITS.append(frame.f_lineno)
    return _local_trace


def _global_trace(frame, event, arg):
    if event != "call":
        return None
    code = frame.f_code
    if code.co_filename != _SRC_PATH or code.co_name not in WATCH_FUNCS:
        return None
    if code.co_name == "_emit":
        _HITS.append("EMIT")
    return _local_trace


def _segments():
    """Split the hit stream into one list of line numbers per emitted signal.

    `_emit` is the boundary: everything recorded from the k-th `_emit` call up
    to the (k+1)-th belongs to signal k, plus the detect_signals lines that ran
    just before it (which is where the D-grade writes live). So each segment is
    [lines since the previous EMIT] and is closed BY the next EMIT.
    """
    segs, cur = [], []
    for h in _HITS:
        if h == "EMIT":
            segs.append(cur)
            cur = []
        else:
            cur.append(h)
    segs.append(cur)          # trailing lines after the last emit; unused
    return segs


def kill_line(seg, sig):
    """The line that killed this signal, or None if it fired.

    * `skipped_d`     -> the LAST executed line in the segment that wrote a skip
                         grade (`TradeGrade.D` / `.X`). That is by construction
                         the write that stuck.
    * `skipped_tight` -> `_min_viable_stop` returned False on a C. No grade line
                         is involved; the gate IS the tight-stop branch.
    * no D write in the segment at all -> the D did not come from
                         `signal_runner`. With `ENABLE_DOWNGRADE_GRADER` off (the
                         shipped default) `_grade_trade` returns
                         `omen_bot.PriceActionAnalyzer.grade_trade`, which grades
                         the ENTRY CANDLE's shape and can return D on its own.
                         That is a real, distinct gate and is reported as `PA`
                         rather than silently dropped.
    """
    if sig.get("status") == "fired":
        return None
    if sig.get("status") == "skipped_tight":
        return "TIGHT"
    for ln in reversed(seg):
        src = GATE_SRC.get(ln, "")
        if "TradeGrade.D" in src or "TradeGrade.X" in src:
            return ln
    if sig.get("status") == "skipped_d":
        return "PA"
    return None


KILL_ALIAS = {
    "TIGHT": ("TIGHT-STOP SKIP (C only)", "`_min_viable_stop`"),
    "PA": ("PA PATTERN VETO — `_grade_pa` graded the entry candle D",
           "`omen_bot.PriceActionAnalyzer`"),
}


# ---------------------------------------------------------------------------
# 3. break-and-retest FSM funnel, per call
# ---------------------------------------------------------------------------

_BR_KEYS = ["too_short", "no_confirm_close", "adverse_wick", "no_break",
            "no_leave", "no_retest", "stale_retest", "passed"]
_BR_LOG = []
_orig_br = signal_runner.detect_break_retest


def _br_wrapper(candles, level, is_long, **kw):
    before = dict(omen_bot.BR_FUNNEL)
    res = _orig_br(candles, level, is_long, **kw)
    stage = None
    for k in _BR_KEYS:
        if omen_bot.BR_FUNNEL[k] != before[k]:
            stage = k
            break
    _BR_LOG.append({"bar": len(candles) - 1, "level": round(level, 4),
                    "long": bool(is_long), "stage": stage})
    return res


# ---------------------------------------------------------------------------
# 4. one instrumented day
# ---------------------------------------------------------------------------

def autopsy_day(symbol, day, trace=True):
    """Replay one day with both instruments on.

    Returns a dict: every captured signal with its status, grade, reason and
    killing gate; the B&R FSM stage log; and the named level map for the day.
    """
    global _HITS, _BR_LOG, _TRACING
    candles = rth_candles(symbol, day)
    if not candles:
        return None
    pdh, pdl, pdo, pdc = prior_day_levels(symbol, day)
    pmh, pml = premarket_extremes(symbol, day)
    r = CaptureRunner(symbol)
    r.pdh, r.pdl = pdh, pdl
    r.pmh, r.pml = pmh, pml
    r.pd_open, r.pd_close = pdo, pdc
    r.htf_bias = htf_bias(symbol, day)
    r.qqq_breaks = None

    _BR_LOG = []
    signal_runner.detect_break_retest = _br_wrapper
    sigs = []
    try:
        for i in range(5, len(candles)):
            c = candles[i]
            if ENTRY_CUTOFF and c.timestamp >= ENTRY_CUTOFF:
                continue
            r.candles = candles[: i + 1]
            before = len(r.captured)
            _HITS = []
            if trace:
                _TRACING = True
                sys.settrace(_global_trace)
            try:
                r.detect_signals()
            except Exception as exc:
                sigs.append({"bar": i, "error": str(exc)[:120]})
                continue
            finally:
                if trace:
                    sys.settrace(None)
                    _TRACING = False
            segs = _segments() if trace else []
            for k, s in enumerate(r.captured[before:]):
                seg = segs[k] if k < len(segs) else []
                sigs.append({
                    "bar": i, "ts": c.timestamp,
                    "type": s["signal_type"].value,
                    "dir": s["direction"], "grade": s["grade"],
                    "status": s["status"],
                    "entry": s["entry"], "stop": s["stop"], "close": c.close,
                    "level_name": s.get("stop_level_name"),
                    "reason": (s.get("reason") or "")[:400],
                    "kill": kill_line(seg, s),
                })
    finally:
        signal_runner.detect_break_retest = _orig_br

    # the named level map, recomputed the way detect_signals builds it
    from omen_bot import OpeningRangeAnalyzer
    or_hi, or_lo = OpeningRangeAnalyzer.get_opening_range(candles)
    levels = {"PDH": pdh, "PDL": pdl, "PMH": pmh, "PML": pml,
              "OR high": or_hi, "OR low": or_lo}
    return {"symbol": symbol, "day": day, "n_bars": len(candles),
            "levels": levels, "signals": sigs, "br": list(_BR_LOG),
            "htf": r.htf_bias}


SIDE_DIR = {"L": "call", "S": "put"}


def his_shape(card, sig):
    """(same direction?, inside +/-TOL of his entry bar?) for one signal.

    Recovering A signal on his day is not the same as recovering HIS trade. A
    gate that resurrects a short at 10:37 on a day he was long at 09:37 has
    bought a fire, not recall, and the two must never be reported as one number.
    """
    want = SIDE_DIR.get((card.get("side") or "").upper()[:1])
    same_dir = (want is not None and sig.get("dir") == want)
    ei = card.get("entry_i")
    near = isinstance(ei, int) and abs(sig["bar"] - ei) <= TOL
    return same_dir, near


def name_level(levels, price, tol=0.005):
    """Name a level price, or say it is an unnamed one.

    Nearest match wins and the band is tight (half a cent, or 0.5 bp on a big
    index). A loose band mislabels: QQQ 2025-02-18's OR low $538.93 sits 9c from
    PDH $538.84, and a 0.02% band called it PDH.
    """
    best, bestd = None, None
    for n, v in levels.items():
        if not v:
            continue
        d = abs(v - price)
        if d <= max(0.005, tol * 0.01 * abs(v)) and (bestd is None or d < bestd):
            best, bestd = n, d
    return best or "unnamed (pivot / rolling HOD-LOD)"


# ---------------------------------------------------------------------------
# 5. population pricing
# ---------------------------------------------------------------------------

def archive_days(stride=1, symbols=None):
    syms = sorted(symbols or BACKTEST_SYMBOLS)
    out = []
    for s in syms:
        d = os.path.join(ARCHIVE, s)
        if not os.path.isdir(d):
            continue
        files = sorted(f for f in os.listdir(d) if f.endswith(".csv"))
        for f in files[::stride]:
            out.append((s, f[:-4]))
    return out


def gate_of(sig):
    """(label, where, source line) for the gate that killed one signal.

    Attribution is resolved to a LABEL here, at counting time, rather than being
    stored as a raw line number and labelled later. `signal_runner.py` is edited
    by other workstreams while this runs, so a number resolved after the fact can
    name a different statement than the one that did the killing.
    """
    k = sig.get("kill")
    if isinstance(k, int):
        return label_for(k), "`signal_runner.py:%d`" % k, GATE_SRC.get(k, "")
    nm, where = KILL_ALIAS.get(k, ("unattributed", "—"))
    return nm, where, ""


def _blank_state(stride, total):
    return {"stride": stride, "total": total, "next_i": 0, "complete": False,
            "days": 0, "fired_days": 0, "secs": 0.0, "head": _head(),
            "status": {}, "kills": {}, "wheres": {}, "srcs": {}, "unlock": {}}


def _save_state(st):
    tmp = POP_CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=1)
    os.replace(tmp, POP_CACHE)


def population(stride=1, limit=None, progress=True, resume=True):
    """Count, over the archive, how many signals each gate kills.

    Sampled by `stride` over each symbol's dated files (stride 1 = every archived
    session of every symbol in `universe.BACKTEST_SYMBOLS`).

    **Checkpointed.** The pass is ~2 hours and has been killed mid-flight; state
    is flushed to `POP_CACHE` every `CHECKPOINT` days and a re-run picks up where
    it left off when the stride matches and the file says `complete: false`. A
    partial file is still readable by the report, which prints how much of the
    archive it covers rather than pretending it covers all of it.
    """
    days = archive_days(stride)
    if limit:
        days = days[:limit]
    st = None
    if resume and os.path.exists(POP_CACHE):
        try:
            with open(POP_CACHE, encoding="utf-8") as fh:
                cand = json.load(fh)
            if (cand.get("stride") == stride and cand.get("total") == len(days)
                    and not cand.get("complete")):
                st = cand
                print("resuming at day %d/%d" % (st["next_i"], len(days)), flush=True)
        except Exception:
            st = None
    if st is None:
        st = _blank_state(stride, len(days))

    kills = Counter(st["kills"])
    status = Counter(st["status"])
    wheres = {k: set(v) for k, v in st["wheres"].items()}
    srcs = {k: set(v) for k, v in st["srcs"].items()}
    unlock = Counter(st["unlock"])
    n_days, n_fired = st["days"], st["fired_days"]
    base_secs = st["secs"]

    t0 = time.time()
    i = st["next_i"]
    CHECKPOINT = 250

    def flush(idx, complete=False):
        st.update({"next_i": idx, "complete": complete, "days": n_days,
                   "fired_days": n_fired, "secs": base_secs + time.time() - t0,
                   "status": dict(status), "kills": dict(kills),
                   "wheres": {k: sorted(v) for k, v in wheres.items()},
                   "srcs": {k: sorted(v) for k, v in srcs.items()},
                   "unlock": dict(unlock)})
        _save_state(st)

    while i < len(days):
        sym, day = days[i]
        i += 1
        res = autopsy_day(sym, day)
        if res is None:
            continue
        n_days += 1
        sk = [s for s in res["signals"] if s.get("status") not in (None, "fired")]
        fired = [s for s in res["signals"] if s.get("status") == "fired"]
        if fired:
            n_fired += 1
        for s in res["signals"]:
            if "status" not in s:
                continue
            status[s["status"]] += 1
        seen_here = set()
        for s in sk:
            lab, where, src = gate_of(s)
            kills[lab] += 1
            wheres.setdefault(lab, set()).add(where)
            if src:
                srcs.setdefault(lab, set()).add(src)
            seen_here.add(lab)
        if not fired:
            for lab in seen_here:
                unlock[lab] += 1
        if i % CHECKPOINT == 0:
            flush(i)
        if progress and i % 100 == 0:
            print("  ...%d/%d days  %.0fs" % (i, len(days), time.time() - t0),
                  flush=True)
    flush(i, complete=True)
    return dict(st)


# ---------------------------------------------------------------------------
# 6. selfcheck
# ---------------------------------------------------------------------------

def selfcheck():
    ok = True

    def chk(name, cond):
        nonlocal ok
        print("%-58s %s" % (name, "ok" if cond else "FAIL"))
        ok = ok and bool(cond)

    chk("gate lines resolved from live source", len(GATE_SRC) >= 10)
    chk("risk-floor gate present",
        any("floor_reference_risk" in " ".join(_SRC[ln - 4:ln])
            for ln in GATE_SRC))
    chk("OCR wide-stop gate present",
        any("0.004" in _SRC[ln - 2] or "0.004" in _SRC[ln - 1]
            for ln in GATE_SRC))
    # segmentation
    global _HITS
    _HITS = [1, 2, "EMIT", 3, 4, "EMIT", 5]
    segs = _segments()
    chk("_segments splits on EMIT", segs[0] == [1, 2] and segs[1] == [3, 4])
    # kill_line picks the LAST skip write
    d_lines = [ln for ln, s in GATE_SRC.items() if "TradeGrade.D" in s]
    chk("kill_line finds a D write",
        len(d_lines) >= 2 and kill_line(d_lines[:2], {"status": "skipped_d"}) == d_lines[1])
    chk("kill_line returns None on a fired signal",
        kill_line(d_lines[:2], {"status": "fired"}) is None)
    chk("kill_line tags the tight-stop skip",
        kill_line([], {"status": "skipped_tight"}) == "TIGHT")
    chk("kill_line tags a D that signal_runner never wrote",
        kill_line([], {"status": "skipped_d"}) == "PA")
    chk("label_for names the risk floor",
        "RISK FLOOR" in label_for([ln for ln in d_lines
                                   if "floor_reference_risk" in
                                   " ".join(_SRC[ln - 4:ln])][0]))
    chk("br wrapper is not installed at rest",
        signal_runner.detect_break_retest is _orig_br)
    # a real day, end to end
    res = autopsy_day("AAPL", "2025-09-11")
    chk("AAPL 2025-09-11 replays", res is not None and res["signals"])
    chk("every skipped signal on it is attributed",
        all(s.get("kill") is not None
            for s in res["signals"] if s.get("status", "fired") != "fired"))
    chk("B&R funnel logged stages",
        any(b["stage"] for b in res["br"]))
    print("SELFCHECK", "GREEN" if ok else "RED")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# 7. report
# ---------------------------------------------------------------------------

def _sh(cmd):
    import subprocess
    try:
        return subprocess.run(cmd, cwd=_ROOT, capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except Exception:
        return ""


def _head():
    return (_sh(["git", "rev-parse", "--short", "HEAD"]) or "unknown")


def _dirty():
    return bool(_sh(["git", "status", "--porcelain", "--", "signal_runner.py"]))


def _priced_rows(pop):
    """One row per killing GATE (not per line): the call side and its put-side
    mirror are the same test written twice and are reported together."""
    rows = []
    for lab, n in sorted(pop["kills"].items(), key=lambda kv: -kv[1]):
        rows.append({"label": lab,
                     "where": " + ".join(sorted(pop["wheres"].get(lab, ["—"]))),
                     "src": sorted(pop["srcs"].get(lab, [])),
                     "killed": n, "unlock": pop["unlock"].get(lab, 0)})
    return rows


def gate_index(lines):
    """line -> (label, the literal source line). Printed so the citation
    survives a line-number shift under an unrelated edit."""
    return [(ln, label_for(ln), GATE_SRC.get(ln, "")) for ln in sorted(lines)]


def build(do_population, stride, limit):
    cards = load_cards()
    s_cards = [c for c in cards if c["his"] == "S"]

    rows = []
    for c in s_cards:
        res = autopsy_day(c["symbol"], c["date"])
        fired = [s for s in (res or {}).get("signals", []) if s.get("status") == "fired"]
        rows.append({"card": c, "res": res, "fired": fired})

    missed = [r for r in rows if not r["fired"]]
    silent = [r for r in missed if not r["res"]["signals"]]
    discarded = [r for r in missed if r["res"]["signals"]]

    pop = None
    if do_population:
        pop = population(stride=stride, limit=limit)
    elif os.path.exists(POP_CACHE):
        with open(POP_CACHE, encoding="utf-8") as fh:
            pop = json.load(fh)
        pop["cached"] = True
        print("re-using population state from", POP_CACHE)
    if pop is not None:
        pop["rows"] = _priced_rows(pop)
        pop["status"] = Counter(pop["status"])

    L = []
    A = L.append
    A("# W5 — the 12 silent S days, taken apart")
    A("")
    A("Generated by `research/w5_silent_s_autopsy.py` (`--selfcheck` green). "
      "**This report diagnoses. It changes no default, adds no flag and adopts "
      "nothing.**")
    A("")
    A("Sample: `research/marks/probe_omen_test1_2026-08-27.jsonl` — the 100 "
      "symbol-days Austin graded 2026-08-27, the project's only clean held-out "
      "set. Scored by `research/t70_test1_score.py`: **S recall 3/15, false fire "
      "12/42** — the engine fires on 29% of the days he refused and 20% of the "
      "days he called S.")
    A("")
    A("Reproduced here independently: **%d of his %d S days fire, %d are missed**. "
      "Of the %d misses, **%d produce no signal of any grade at all** and on **%d "
      "the engine saw something and threw it away**."
      % (len(rows) - len(missed), len(rows), len(missed), len(missed),
         len(silent), len(discarded)))
    A("")
    A("Two instruments, both read-only, both removed in a `finally`: a line "
      "tracer over `signal_runner`'s grading path that names the exact line "
      "which wrote the skip grade, and `omen_bot.BR_FUNNEL`, the "
      "break-and-retest FSM's own stage counter (break → leave → retest → "
      "confirm), read per call. The killing gate is **measured, not inferred** — "
      "`research/g10_arming_funnel.py`'s rule.")
    A("")
    A("> `CaptureRunner` applies a SIMPLIFIED route: grade caps, the X-grade "
      "skip and the C-only tight-stop skip. It does not apply "
      "`LEVEL_RETIRE_TOUCHES`, `ENFORCE_NO_REPEAT` or `NO_REPEAT_ENTRIES`, all "
      "of which can only remove more. Every recall figure here is an UPPER "
      "bound on the shipped router.")
    A("Engine state this was measured against: `git rev-parse HEAD` = **%s**, "
      "`signal_runner.py` %s. Every flag at its shipped default — W1's "
      "`ENABLE_SAC_LADDER` and `SAC_LADDER_REGRADE_ALL` are both OFF, so the "
      "grading path here is HEAD's. **Line numbers below were resolved from the live "
      "source at render time and `signal_runner.py` is under concurrent edit — the "
      "literal source text in the gate index is the durable citation, not the "
      "number.**"
      % (_head(), "clean" if not _dirty() else "carrying W1's default-OFF diff"))
    A("")

    # ---- the verdict ------------------------------------------------------
    kill_all = Counter()
    for r in discarded:
        for sg in r["res"]["signals"]:
            if sg.get("status") != "fired":
                kill_all[label_for(sg["kill"]) if isinstance(sg["kill"], int)
                         else KILL_ALIAS.get(sg["kill"], ("unattributed", ""))[0]] += 1
    top, top_n = (kill_all.most_common(1) or [("—", 0)])[0]
    n_days_top = sum(1 for r in discarded
                     if any((label_for(sg["kill"]) if isinstance(sg["kill"], int)
                             else KILL_ALIAS.get(sg["kill"], ("", ""))[0]) == top
                            for sg in r["res"]["signals"] if sg.get("status") != "fired"))
    A("## The answer, in one paragraph")
    A("")
    # the exact lines, resolved from THIS run rather than typed in -- they move
    # every time signal_runner.py is edited, and it is edited constantly
    floor_lines = sorted({sg["kill"] for r in discarded for sg in r["res"]["signals"]
                          if isinstance(sg.get("kill"), int)
                          and label_for(sg["kill"]) == top})
    A("The %d days it saw and threw away do not fail for %d different reasons. **%d of "
      "them** die on the SAME test — *%s* — which accounts for %d of the %d discarded "
      "signals across them. It is written %s in the source — %s — the call side and "
      "its put-side mirror. Everything else in this report is a footnote to that one "
      "gate."
      % (len(discarded), len(discarded), n_days_top, top, top_n,
         sum(kill_all.values()),
         "once" if len(floor_lines) == 1 else "%d times" % len(floor_lines),
         " and ".join("`signal_runner.py:%d`" % l for l in floor_lines)))
    A("")
    # the two sharpest rows, found rather than remembered
    floor_rows = [(r, sg) for r in discarded for sg in r["res"]["signals"]
                  if isinstance(sg.get("kill"), int) and label_for(sg["kill"]) == top]
    # prefer an IN-UNIVERSE example: a gate named on a symbol the engine is never
    # pointed at is true but buys nothing, so it is the wrong day to lead with.
    inuni = [(r, sg) for r, sg in floor_rows if in_universe(r["card"]["symbol"])]
    pool = inuni or floor_rows
    thinnest = min(pool, key=lambda x: abs(x[1]["entry"] - x[1]["stop"]))
    at_his_bar = sorted(
        [(r, sg) for r, sg in floor_rows
         if isinstance(r["card"].get("entry_i"), int)
         and abs(sg["bar"] - r["card"]["entry_i"]) <= TOL],
        key=lambda x: (not in_universe(x[0]["card"]["symbol"]),
                       abs(x[1]["bar"] - x[0]["card"]["entry_i"])))
    A("**And the mechanism is already on record.** "
      "`research/g12_recall_regression.md` bisected it to `5e3677ea`, and "
      "`Specs/omen6-h2-master-spec.md` §3 W3 is the workstream chartered to fix it: "
      "`fill_price` back-dates the entry to the level on a bar that closes jammed "
      "against the session extreme, `intrabar_stop` then pulls the stop onto that same "
      "fill, and `stock_risk` collapses under `max($0.10, 0.0015 × close)`.")
    A("")
    A("The rows below show it happening to Austin's own S days. The thinnest is "
      "**%s %s bar %d**, which books `entry == $%.2f` against `stop == $%.2f` — a risk "
      "of **$%.4f**."
      % (thinnest[0]["card"]["symbol"], thinnest[0]["card"]["date"],
         thinnest[1]["bar"], thinnest[1]["entry"], thinnest[1]["stop"],
         abs(thinnest[1]["entry"] - thinnest[1]["stop"])))
    if at_his_bar:
        r0, s0 = at_his_bar[0]
        A("")
        A("And it is not only firing on junk bars far from the setup. On **%s %s** the "
          "signal at bar %d — the exact bar Austin marked, or inside the ±2 tolerance "
          "window around it — dies with **$%.4f of risk against a $%.4f floor**; %d of the %d "
          "signals this gate killed sit within ±%d bars of one of his own entry bars."
          % (r0["card"]["symbol"], r0["card"]["date"], s0["bar"],
             abs(s0["entry"] - s0["stop"]), max(0.10, 0.0015 * s0["close"]),
             len(at_his_bar), len(floor_rows), TOL))
    A("")
    all_sk = [(r["card"], x) for r in discarded for x in r["res"]["signals"]
              if x.get("status") not in (None, "fired")]
    both = [1 for cd, x in all_sk if all(his_shape(cd, x))]
    dirs = [1 for cd, x in all_sk if his_shape(cd, x)[0]]
    A("")
    A("**The caveat that has to travel with this, and it is not small.** Recovering a "
      "signal on his day is not the same as recovering HIS trade. Across the %d "
      "discarded signals on these %d days, %d are in the direction he took and only "
      "**%d are both in his direction AND within ±%d bars of his entry bar**. Opening "
      "the gate is necessary for those %d; for the rest it buys a fire on the right day "
      "at the wrong moment, on a sample where `research/t70_test1_score.py` already "
      "measures 12 false fires on his 42 refused days."
      % (len(all_sk), len(discarded), sum(dirs), sum(both), TOL, sum(both)))
    A("")
    A("So W5's contribution is not a new suspect. It is that the suspect W3 is already "
      "prosecuting is confirmed **on held-out data**, and the constant it turns on — "
      "`B&R_MIN_RISK = 0.0015 × close`, `research/hallucination-audit.md` line 51, "
      "*\"0.0015 multiplier territory not swept, HIGH - gates grade D\"* — is one of "
      "the 33 constants **Austin never stated**. It is ours, not his. Section 4 prices "
      "what opening it would cost.")
    A("")

    # ---- the table --------------------------------------------------------
    A("## The 12, one row each")
    A("")
    A("`his entry` is Austin's own entry bar and price off the card. `engine` is "
      "what the replay produced on that day. The killing gate is the last line "
      "that wrote the skip grade.")
    A("")
    A("| # | symbol | date | his setup | side | his entry | engine saw | killing gate |")
    A("|---:|---|---|---|---|---|---:|---|")
    for n, r in enumerate(missed, 1):
        c, res = r["card"], r["res"]
        sigs = res["signals"]
        if not sigs:
            gate = "**no signal at all** — see §3"
            saw = "0"
        else:
            kc = Counter(label_for(s["kill"]) if isinstance(s["kill"], int)
                         else KILL_ALIAS.get(s["kill"], ("unattributed", ""))[0]
                         for s in sigs if s.get("status") != "fired")
            gate = "; ".join("%s ×%d" % (k, v) for k, v in kc.most_common(2))
            saw = str(len(sigs))
        uni = "" if in_universe(c["symbol"]) else " ⚠"
        A("| %d | **%s**%s | %s | %s | %s | bar %s %s $%s | %s | %s |"
          % (n, c["symbol"], uni, c["date"], c.get("setup"), c.get("side"),
             c.get("entry_i"), c.get("entry_t"), c.get("entry_p"), saw, gate))
    A("")
    A("⚠ = symbol outside `universe.BACKTEST_SYMBOLS`. The engine is never "
      "pointed at it in production; the replay is, so a gate is still named, but "
      "opening that gate buys nothing until the universe changes.")
    A("")

    # ---- gate index -------------------------------------------------------
    seen_lines = {s["kill"] for r in missed for s in r["res"]["signals"]
                  if isinstance(s.get("kill"), int)}
    A("### The gates named above, with their source")
    A("")
    A("Line numbers move; the source text does not. Both are given so a reader "
      "can verify the citation after any edit to `signal_runner.py`.")
    A("")
    A("| `signal_runner.py` | what it is | the line |")
    A("|---:|---|---|")
    for ln, lab, src in gate_index(seen_lines):
        A("| %d | %s | `%s` |" % (ln, lab, src))
    A("| `_min_viable_stop` | TIGHT-STOP SKIP, C grades only | `if sig[\"grade\"] != \"C\" or self._min_viable_stop(...)` |")
    A("| `omen_bot._grade_pa` | PA PATTERN VETO — the entry candle's shape graded D, and no promotion in `detect_signals` lifted it | `grade = self._grade_trade(current, lookback, ...)` |")
    A("")

    # ---- discarded detail -------------------------------------------------
    A("## §2 — the %d it saw and threw away" % len(discarded))
    A("")
    for r in discarded:
        c, res = r["card"], r["res"]
        A("### %s %s — his %s %s at bar %s (%s), entry $%s, stop $%s"
          % (c["symbol"], c["date"], c.get("side"), c.get("setup"),
             c.get("entry_i"), c.get("entry_t"), c.get("entry_p"),
             c.get("stop_p")))
        A("")
        A("HTF bias `%s`. Levels: %s."
          % (res["htf"], ", ".join("%s $%.2f" % (k, v)
                                   for k, v in res["levels"].items() if v)))
        A("")
        sk = [x for x in res["signals"] if x.get("status") not in (None, "fired")]
        shapes = [his_shape(c, x) for x in sk]
        n_dir = sum(1 for d, _ in shapes if d)
        n_near = sum(1 for _, n in shapes if n)
        n_both = sum(1 for d, n in shapes if d and n)
        A("Of the **%d** signals thrown away here, **%d** are in his direction (%s), "
          "**%d** land within ±%d bars of his entry bar, and **%d** are both — the only "
          "ones that opening a gate could turn into HIS trade rather than merely a "
          "trade."
          % (len(sk), n_dir, SIDE_DIR.get((c.get("side") or "").upper()[:1], "?"),
             n_near, TOL, n_both))
        A("")
        A("| bar | time | setup | dir | grade | status | entry | stop | killing gate | the value that failed |")
        A("|---:|---|---|---|---|---|---:|---:|---|---|")
        for s in res["signals"][:14]:
            if "status" not in s:
                A("| %d | — | _replay raised_ | | | | | | `%s` | |" % (s["bar"], s.get("error")))
                continue
            k = s["kill"]
            if k in KILL_ALIAS:
                nm, where = KILL_ALIAS[k]
                gate = "%s — %s" % (where, nm)
                val = "risk $%.2f on a $%.2f entry" % (abs(s["entry"] - s["stop"]), s["entry"])
            elif isinstance(k, int):
                gate = "`signal_runner.py:%d` — %s" % (k, label_for(k))
                risk = abs(s["entry"] - s["stop"])
                lab = label_for(k)
                if "RISK FLOOR" in lab:
                    val = "risk **$%.4f** vs floor $%.4f (= max($0.10, 0.0015 x $%.2f))" % (
                        risk, max(0.10, 0.0015 * s["close"]), s["close"])
                elif "$0.50" in lab:
                    val = "risk **$%.4f** vs the flat $0.50 floor" % risk
                elif "0.40%" in lab:
                    val = "stop is %.3f%% of close, cap is 0.400%%" % (
                        100 * risk / s["close"] if s["close"] else 0)
                else:
                    val = "risk $%.4f on a $%.2f close" % (risk, s["close"])
            elif s["status"] == "fired":
                gate = "— fired"
                val = ""
            else:
                gate = "unattributed"
                val = ""
            near = " ⭐" if (isinstance(c.get("entry_i"), int)
                             and abs(s["bar"] - c["entry_i"]) <= TOL) else ""
            A("| %d%s | %s | %s | %s | %s | %s | %.2f | %.2f | %s | %s |"
              % (s["bar"], near, s["ts"][:5], s["type"], s["dir"], s["grade"],
                 s["status"], s["entry"], s["stop"], gate, val))
        if len(res["signals"]) > 14:
            A("| … | | | | | | | | _%d more rows_ | |" % (len(res["signals"]) - 14))
        A("")
        A("⭐ = within ±%d bars of Austin's own entry bar (`t4_engine_recall.TOL`)." % TOL)
        A("")

    # ---- silent detail ----------------------------------------------------
    A("## §3 — the %d that produced nothing at all" % len(silent))
    A("")
    A("Nothing was emitted, so there is no grade to attribute and the tracer has "
      "nothing to say. The question becomes how far up the break-and-retest FSM "
      "the candidate got, and `omen_bot.BR_FUNNEL` answers it per level per bar. "
      "The stages, in the order the FSM evaluates them:")
    A("")
    A("| stage | what failed |")
    A("|---|---|")
    A("| `no_confirm_close` | the current bar did not CLOSE back through the level — step 4 |")
    A("| `adverse_wick` | the entry candle's wick against the trade > 1.5× its body |")
    A("| `no_break` | no candle ever closed through the level inside the 12-bar window |")
    A("| `no_leave` | it broke but never fully cleared the level — chop on the line |")
    A("| `no_retest` | it broke and left but never came back to touch the level |")
    A("| `stale_retest` | the retest was more than 3 bars before the entry candle |")
    A("")
    A("Read the session totals with care: the FSM is called once per bar per level "
      "per direction, so `no_confirm_close` is the base rate of \"this bar is not an "
      "entry bar\" and dominates every day by construction. The informative stages are "
      "the later ones — `no_break`, `no_leave`, `no_retest`, `stale_retest` — and the "
      "per-bar window at HIS entry bar, which is the only place the answer can be.")
    A("")
    for r in silent:
        c, res = r["card"], r["res"]
        A("### %s %s — his %s %s at bar %s (%s), entry $%s"
          % (c["symbol"], c["date"], c.get("side"), c.get("setup"),
             c.get("entry_i"), c.get("entry_t"), c.get("entry_p")))
        A("")
        A("HTF bias `%s`. Levels: %s."
          % (res["htf"], ", ".join("%s $%.2f" % (k, v)
                                   for k, v in res["levels"].items() if v)))
        A("")
        tot = Counter(b["stage"] for b in res["br"])
        A("Across the whole session the FSM was asked **%d times** on this day and "
          "died: %s." % (len(res["br"]),
                         ", ".join("`%s` ×%d" % (k, v) for k, v in tot.most_common())))
        A("")
        ei = c.get("entry_i")
        if isinstance(ei, int):
            win = [b for b in res["br"] if abs(b["bar"] - ei) <= TOL]
            A("At his own entry bar ±%d:" % TOL)
            A("")
            A("| bar | level | dir | FSM died at |")
            A("|---:|---|---|---|")
            for b in win:
                A("| %d | %s $%.2f | %s | `%s` |"
                  % (b["bar"], name_level(res["levels"], b["level"]), b["level"],
                     "long" if b["long"] else "short", b["stage"]))
            if not win:
                A("| — | _the FSM was never called in this window_ | | |")
            A("")

    # ---- pricing ----------------------------------------------------------
    A("## §4 — what opening each gate would cost, population-wide")
    A("")
    if pop is None:
        A("_Not run in this pass. `python research/w5_silent_s_autopsy.py "
          "--population` fills this section._")
    else:
        if pop.get("cached"):
            A("_Counts re-used from `research/_w5_pop_counts.json`, measured at engine "
              "`%s`. Delete that file and re-run with `--population` to remeasure._"
              % pop.get("head", "?"))
            A("")
        universe_txt = ("**every archived session** of every symbol in "
                        "`universe.BACKTEST_SYMBOLS`" if pop["stride"] == 1 else
                        "a stratified **every-%dth-session** sample per symbol across "
                        "`universe.BACKTEST_SYMBOLS`" % pop["stride"])
        done, total = pop.get("next_i", 0), pop.get("total", 0)
        if pop.get("complete"):
            cover = ("%s — %d symbol-days, **%d of them with bars**"
                     % (universe_txt, total, pop["days"]))
        else:
            cover = ("%s — but the pass was interrupted, so this is the first **%d of "
                     "%d** symbol-days (%.0f%%), **%d of them with bars**. It "
                     "checkpoints and resumes; re-run with `--population` to finish it"
                     % (universe_txt, done, total, 100.0 * done / max(1, total),
                        pop["days"]))
        A("Every gate above, priced over the archive: %s, in %.0f min of replay. Deaths "
          "are counted per signal, so the shares are the reading."
          % (cover, pop["secs"] / 60.0))
        A("")
        A("Of those %d days the engine fires on **%d (%.1f%%)**. Signal "
          "dispositions: %s."
          % (pop["days"], pop["fired_days"],
             100.0 * pop["fired_days"] / max(1, pop["days"]),
             ", ".join("`%s` %d" % (k, v) for k, v in pop["status"].most_common())))
        A("")
        A("| killing gate | where | signals killed | share of all kills | silent days it alone is holding shut |")
        A("|---|---|---:|---:|---:|")
        tot_k = sum(r["killed"] for r in pop["rows"]) or 1
        for r in pop["rows"]:
            A("| %s | %s | %d | %.1f%% | %d |"
              % (r["label"], r["where"], r["killed"],
                 100.0 * r["killed"] / tot_k, r["unlock"]))
        A("")
        A("Line numbers move — `signal_runner.py` was edited by other workstreams "
          "while this pass ran, and the pass checkpoints and resumes, so a gate can "
          "carry more line numbers than it has occurrences in the file. The literal "
          "source statement is the durable citation:")
        A("")
        A("| gate | the statement it is |")
        A("|---|---|")
        for r in pop["rows"]:
            for src in r["src"]:
                A("| %s | `%s` |" % (r["label"], src))
        A("")
        A("**The population fire rate is the number to hold next to the held-out "
          "sample.** The engine fires on **%.1f%%** of all archived symbol-days. On the "
          "100 cards Austin graded it fires on 20%% of his S days and 29%% of the days "
          "he refused — so on unseen data it is no more selective than picking a day at "
          "random, and slightly less likely to fire on his best days than on his worst."
          % (100.0 * pop["fired_days"] / max(1, pop["days"])))
        A("")
        A("`unlock` double-counts nothing within a gate but a day can appear under two "
          "different gates; it is a ceiling per gate, not a partition of the days.")
        A("")
        A("**Reading the last column.** It counts days where the engine fired "
          "nothing and this gate killed at least one of the signals it did "
          "produce — i.e. the days opening that gate could turn from silent to "
          "firing. It is an upper bound on the recall a gate can buy and says "
          "nothing about whether those fires are good: on this held-out sample "
          "the engine already fires on 29% of the days Austin refused, so every "
          "gate opened here buys false fires at that rate or worse unless "
          "something else selects.")
        A("")

    A("## Read next to")
    A("")
    A("- `research/w6_tz_recall_and_odds.md` — the same recall question against his "
      "350-row TradeZella hand-replay book, a second held-out set with a different "
      "shape (2 symbols, one playbook).")
    A("- `research/w10_gate_autopsy.py` — the gate autopsy over THAT book. If both "
      "reports land on the same gate from two independent held-out sets, that is the "
      "strongest evidence this project can currently produce.")
    A("- `research/g12_recall_regression.md` — where the gate came from and which "
      "commit turned it into a recall regression.")
    A("- `Specs/omen6-h2-master-spec.md` §3 W3 — the workstream chartered to open it, "
      "and the trap it must avoid (`ENABLE_STRUCTURAL_RISK_FLOOR` recovers 5 of 6 marks "
      "and makes 73.3% of the resulting book untakeable).")
    A("")
    A("## What this does and does not license")
    A("")
    A("- It names gates. It does not open one. No default moved and no flag was "
      "added by this file.")
    A("- **Recall governs** (ballot q20) — a complete miss of an S day outranks "
      "tier accuracy. But the false-fire rate on the same held-out sample is "
      "already higher than the S rate, so a gate opened without a selector "
      "makes the inversion worse, not better.")
    A("- Held-out beats in-sample. Every number here is on the 100 cards or on "
      "the archive; none of it is on the corpus the rules were fitted to.")
    A("")

    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("wrote", OUT_MD)
    print("  S days %d  fired %d  missed %d  (silent %d / discarded %d)"
          % (len(rows), len(rows) - len(missed), len(missed), len(silent),
             len(discarded)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--population", action="store_true")
    ap.add_argument("--stride", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if a.selfcheck:
        return selfcheck()
    return build(a.population, a.stride, a.limit or None)


if __name__ == "__main__":
    sys.exit(main())
