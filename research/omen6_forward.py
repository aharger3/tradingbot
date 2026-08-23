"""OMEN 6 forward-only clock -- freeze the engine, then score it going forward.

Ticket 13. Every out-of-sample split OMEN has ever claimed is fake: the rules
were fitted on those days. The only honest holdout is to freeze the engine,
stamp the date, and score trades it takes AFTER that date. It cannot be started
retroactively, so every day this waits is a day the honest sample never gets.

    python research/omen6_forward.py freeze          # stamp the manifest (once)
    python research/omen6_forward.py score           # score yesterday..today
    python research/omen6_forward.py score --day 2026-08-22
    python research/omen6_forward.py report          # where the book stands

`freeze` writes research/omen6_frozen.json: the commit, the SHA-256 of every
file on the engine's decision surface, the universe, the exit policy, and the
gates. `score` refuses to run if any of those hashes has moved -- a refit
invalidates the book, and silence about that would be worse than no book at all.

The blind decks stay the fast iteration loop. This is the slow honest one.
"""

from __future__ import annotations
import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
from datetime import date, datetime, timedelta

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import research.exit_lab as exit_lab  # noqa: E402
from research.levels import load_rth_bars  # noqa: E402
from research.t4_engine_recall import run_day  # noqa: E402
import universe  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "omen6_frozen.json")
BOOK = os.path.join(HERE, "omen6_forward_book.jsonl")
REPORT = os.path.join(HERE, "omen6_forward.md")

POLICY = "30_30_30_10"

# The engine's decision surface: everything that can change WHICH trade is taken,
# at WHAT price, with WHAT stop, and HOW it is exited. If any of these move, the
# book is measuring a different engine.
FROZEN_FILES = [
    "signal_runner.py",
    "omen_bot.py",
    "universe.py",
    "research/levels.py",
    "research/exit_lab.py",
    "research/t4_engine_recall.py",
    "research/trend_gate.py",
]

# Sample-size targets. Derived in `freeze` from the baseline's own dispersion
# rather than guessed: N needed for a 95% CI half-width of 0.25R on mean R.
CI_HALF_WIDTH_R = 0.25
Z = 1.96


def sha256(path):
    """Hash the file's CONTENT, with line endings normalised.

    Not the raw bytes: git's autocrlf rewrites CRLF on checkout, so a plain
    byte hash false-alarms on files nobody edited. The guard must fire on a
    refit, never on a checkout.
    """
    p = os.path.join(_REPO_ROOT, path)
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        data = f.read()
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def git(*args):
    try:
        return subprocess.check_output(["git"] + list(args), cwd=_REPO_ROOT,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return None


def baseline_dispersion():
    """sd of R over the baseline corpus, for the sample-size math."""
    try:
        from research.v52_scaleout_run import corpus_b_trades, bars_for
    except Exception:
        return None
    fn = exit_lab.POLICIES[POLICY]
    rs = []
    for t in corpus_b_trades():
        bars = bars_for(t)
        if not bars or t["entry"] is None or t["stop"] is None or t["entry_i"] >= len(bars):
            continue
        rs.append(fn(bars, t["entry_i"], t["entry"], t["stop"], t["side"]))
    return statistics.pstdev(rs) if len(rs) > 1 else None


# ---------------------------------------------------------------------------

def cmd_freeze(args):
    if os.path.exists(MANIFEST) and not args.force:
        raise SystemExit("already frozen: %s (use --force to re-stamp, which "
                         "VOIDS the forward book)" % MANIFEST)

    sd = baseline_dispersion()
    need_n = int(round((Z * sd / CI_HALF_WIDTH_R) ** 2)) if sd else None

    man = {
        "frozen_at": args.date or date.today().isoformat(),
        "commit": git("rev-parse", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "tag": args.tag,
        "policy": POLICY,
        "entry_cutoff": "11:00:00",
        "universe": {
            "ALL_SYMS": universe.ALL_SYMS,
            "CORE_SYMBOLS": universe.CORE_SYMBOLS,
            "BACKTEST_SYMBOLS": universe.BACKTEST_SYMBOLS,
            "INCLUDE_SPY_IN_BACKTEST": universe.INCLUDE_SPY_IN_BACKTEST,
        },
        "hashes": {p: sha256(p) for p in FROZEN_FILES},
        "sample_size": {
            "baseline_sd_r": sd,
            "ci_half_width_r": CI_HALF_WIDTH_R,
            "trades_needed": need_n,
            "note": ("N for a 95%% CI half-width of %.2fR on mean R, using the "
                     "baseline's own dispersion. Quote nothing before this."
                     % CI_HALF_WIDTH_R),
        },
        "what_is_frozen": [
            "detection (signal_runner.detect_signals and everything it calls)",
            "grading (compute_austin_tier)",
            "the exit ladder (%s, incl. the ticket 02 break-even fix)" % POLICY,
            "the traded universe (universe.py, SPY excluded pending Q12)",
            "the 11:00 ET entry cutoff",
        ],
        "what_is_NOT_frozen": [
            "data_archive contents (it grows daily -- that is the point)",
            "deck generation, marks, and anything under research/ that only reports",
        ],
    }
    json.dump(man, open(MANIFEST, "w", encoding="utf-8"), indent=2)
    print("froze at %s  commit %s" % (man["frozen_at"], (man["commit"] or "?")[:12]))
    if need_n:
        print("  baseline sd = %.3fR -> need ~%d forward trades before quoting a mean"
              % (sd, need_n))
    return man


def load_manifest():
    if not os.path.exists(MANIFEST):
        raise SystemExit("not frozen yet -- run: python research/omen6_forward.py freeze")
    return json.load(open(MANIFEST, encoding="utf-8"))


def check_frozen(man):
    """Refuse to score a book against an engine that has moved."""
    moved = [p for p, h in man["hashes"].items() if sha256(p) != h]
    if moved:
        print("REFUSING TO SCORE -- the frozen engine has changed:", file=sys.stderr)
        for p in moved:
            print("    %s" % p, file=sys.stderr)
        print("\nA forward book is only honest if the rules did not move inside it.\n"
              "Either revert the change, or re-freeze (which VOIDS the book so far)\n"
              "with: python research/omen6_forward.py freeze --force", file=sys.stderr)
        sys.exit(2)


def already_scored():
    if not os.path.exists(BOOK):
        return set()
    out = set()
    for line in open(BOOK, encoding="utf-8"):
        line = line.strip()
        if line:
            out.add(json.loads(line)["day"])
    return out


def cmd_score(args):
    man = load_manifest()
    check_frozen(man)
    frozen_at = man["frozen_at"]
    fn = exit_lab.POLICIES[POLICY]

    if args.day:
        days = [args.day]
    else:
        # everything from the freeze date to today that is not already scored
        d0 = datetime.strptime(frozen_at, "%Y-%m-%d").date()
        days = []
        d = d0
        while d <= date.today():
            if d.weekday() < 5:
                days.append(d.isoformat())
            d += timedelta(days=1)

    done = already_scored()
    symbols = man["universe"]["BACKTEST_SYMBOLS"]
    n_new = 0
    with open(BOOK, "a", encoding="utf-8") as out:
        for day in days:
            if day <= frozen_at:
                continue  # the freeze date itself is in-sample
            if day in done and not args.rescore:
                continue
            wrote_any = False
            for sym in symbols:
                bars = load_rth_bars(sym, day)
                if not bars:
                    continue
                try:
                    entries, _sigs, _raw = run_day(sym, day)
                except Exception as e:
                    print("  %s %s: engine error %s" % (sym, day, e))
                    continue
                if not entries:
                    continue
                for e in entries:
                    r = None
                    if e["entry"] is not None and e["stop"] is not None and e["bar"] < len(bars):
                        side = "L" if str(e["direction"]).lower().startswith(("c", "l")) else "S"
                        r = fn(bars, e["bar"], e["entry"], e["stop"], side)
                    out.write(json.dumps({
                        "day": day, "symbol": sym, "bar": e["bar"],
                        "timestamp": e["timestamp"], "signal_type": e["signal_type"],
                        "direction": e["direction"], "grade": e["grade"],
                        "entry": e["entry"], "stop": e["stop"],
                        "policy": POLICY, "r": r,
                        "scored_at": datetime.now().isoformat(timespec="seconds"),
                    }) + "\n")
                    wrote_any = True
                    n_new += 1
            if wrote_any:
                print("  scored %s" % day)
    print("forward book: +%d trades -> %s" % (n_new, BOOK))
    cmd_report(args)


def cmd_report(args):
    man = load_manifest()
    rows = []
    if os.path.exists(BOOK):
        for line in open(BOOK, encoding="utf-8"):
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    rs = [r["r"] for r in rows if r.get("r") is not None]
    need = (man.get("sample_size") or {}).get("trades_needed")

    L = ["# OMEN 6 — the forward-only book", "",
         "The one honest holdout. Frozen **%s** at commit `%s`%s."
         % (man["frozen_at"], (man["commit"] or "?")[:12],
            (", tag `%s`" % man["tag"]) if man.get("tag") else ""),
         "",
         "Generated by `research/omen6_forward.py report`. Scoring refuses to run if any "
         "frozen file's hash has moved, so a silent refit cannot contaminate this book.",
         ""]
    L.append("## Where it stands")
    L.append("")
    L.append("| | |")
    L.append("|---|---:|")
    L.append("| trades booked | %d |" % len(rs))
    L.append("| distinct days | %d |" % len({r["day"] for r in rows}))
    if need:
        L.append("| trades needed before quoting | %d |" % need)
        L.append("| progress | %.1f%% |" % (100.0 * len(rs) / need))
    if rs:
        L.append("| mean R | %+.4f |" % statistics.fmean(rs))
        L.append("| win rate | %.3f |" % (sum(1 for r in rs if r > 0) / len(rs)))
        L.append("| worst | %+.2f |" % min(rs))
    L.append("")
    if need and len(rs) < need:
        L.append("> **Do not quote a number from this book yet.** It holds %d of the ~%d "
                 "trades needed for a 95%% CI half-width of %.2fR. Reading a mean off %d "
                 "trades is exactly the mistake the in-sample numbers already made."
                 % (len(rs), need, CI_HALF_WIDTH_R, len(rs)))
        L.append("")
    L.append("## What is frozen")
    L.append("")
    for w in man["what_is_frozen"]:
        L.append("- %s" % w)
    L.append("")
    L.append("**Not frozen:** " + "; ".join(man["what_is_NOT_frozen"]) + ".")
    L.append("")
    L.append("| file | sha256 |")
    L.append("|---|---|")
    for p, h in sorted(man["hashes"].items()):
        L.append("| `%s` | `%s` |" % (p, (h or "MISSING")[:16]))
    open(REPORT, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("wrote %s  (%d trades booked)" % (REPORT, len(rs)))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("freeze"); f.add_argument("--date"); f.add_argument("--tag")
    f.add_argument("--force", action="store_true")
    s = sub.add_parser("score"); s.add_argument("--day"); s.add_argument("--rescore", action="store_true")
    sub.add_parser("report")
    a = ap.parse_args()
    {"freeze": cmd_freeze, "score": cmd_score, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
