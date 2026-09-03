"""G7.2 track `sixlevels` -- held-out S recall under Austin's six levels.

Same three changes as research/g72_sixlevels_book.py, scored on judgement
instead of money:

    hodlod    HODLOD_PAIR = True
    noor      OR high / OR low out of the GATING set
    nopivot   PIVOT_LEVELS = 0
    sixlevels all three = his roster (PDH PDL PMH PML HOD LOD)

Two recall reads per arm, both replayed through research.t4_engine_recall.run_day
(the same harness t0_heldout_recall.py and the regression gate use -- untouched):

  1. the published held-out sample: the 34 S cards inside
     research/marks/probe_s_sweep_2026-08-28.jsonl (100 blind cards), with
     precision on the same 100 beside it.
  2. the WHOLE judged corpus: every Austin-graded symbol-day with archived bars
     listed in research/g71_samplesize_corpus.json. The board's own finding is
     that 34 cards buys +/-15 points and the full pile buys a real read
     (research/g71_ssverify_power.py); this scores both so the two can be
     compared card for card.

Marks are read, never written. No shipped file is edited -- the opening-range
change is made by an asserted one-line substitution on a copy of
signal_runner.py's source, exec'd into sys.modules before anything imports it.

Usage:
    python research/g72_sixlevels_recall.py --arm base      --out research/g72_recall_base.json
    python research/g72_sixlevels_recall.py --arm sixlevels --out research/g72_recall_sixlevels.json
"""
from __future__ import annotations
import argparse, json, os, sys, time, types
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

ap = argparse.ArgumentParser()
ap.add_argument("--arm", required=True,
                choices=["base", "hodlod", "noor", "nopivot", "sixlevels", "sixfast", "hodfast"])
ap.add_argument("--out", required=True)
ARGS = ap.parse_args()

WANT_HODLOD = ARGS.arm in ("hodlod", "sixlevels", "sixfast", "hodfast")
WANT_NOOR = ARGS.arm in ("noor", "sixlevels", "sixfast")
WANT_NOPIVOT = ARGS.arm in ("nopivot", "sixlevels", "sixfast")
# `sixfast` = his roster with F3's two staleness gates relaxed -- see the
# same block in research/g72_sixlevels_book.py for why.
WANT_HODFAST = ARGS.arm in ("sixfast", "hodfast")

if WANT_NOPIVOT:
    os.environ["PIVOT_LEVELS"] = "0"

SR_PATH = os.path.join(ROOT, "signal_runner.py")
OR_LINE = '        level_pairs = [("OR high", "OR low", or_high, or_low)]'
OR_REPLACEMENT = (
    '        level_pairs = []  # G72 sixlevels: the opening range is NOT one of\n'
    '        # Austin\'s six. or_high/or_low are still computed and still sit in\n'
    '        # _active_levels -- they gate nothing.'
)

DUP_LINE = ("            dup = lambda v: any(abs(v - l) / l < 0.001 "
            "for l in self._active_levels)")
DUP_REPLACEMENT = """\
            # G72 sixlevels: dedupe HOD/LOD against the OTHER FOUR levels
            # Austin watches, not against the opening range. Left as shipped,
            # a session high that was set in the first five minutes is thrown
            # away as "the OR high again" -- and that is exactly the HOD he
            # says he watches.
            _six4 = [l for l in (self.pdh, self.pdl, self.pmh, self.pml) if l]
            dup = lambda v: any(abs(v - l) / l < 0.001 for l in _six4)"""

AGE_LINE = "        if HODLOD_PAIR and len(self.candles) >= 43:"
AGE_REPLACEMENT = "        if HODLOD_PAIR and len(self.candles) >= 20:"
OLD_LINE = """\
            hod_lv = hi_val if hi_age >= 30 and not dup(hi_val) else None
            lod_lv = lo_val if lo_age >= 30 and not dup(lo_val) else None"""
OLD_REPLACEMENT = """\
            hod_lv = hi_val if hi_age >= 12 and not dup(hi_val) else None
            lod_lv = lo_val if lo_age >= 12 and not dup(lo_val) else None"""

_src = open(SR_PATH, encoding="utf-8").read()
if WANT_HODFAST:
    for _o, _new in ((AGE_LINE, AGE_REPLACEMENT), (OLD_LINE, OLD_REPLACEMENT)):
        assert _src.count(_o) == 1, "F3 staleness gate moved"
        _src = _src.replace(_o, _new)
if WANT_NOOR:
    _n = _src.count(OR_LINE)
    assert _n == 1, ("expected exactly 1 copy of the OR level_pairs line in "
                     "signal_runner.py, found %d" % _n)
    _src = _src.replace(OR_LINE, OR_REPLACEMENT)
    assert _src.count(DUP_LINE) == 1, "HOD/LOD dedupe line moved"
    _src = _src.replace(DUP_LINE, DUP_REPLACEMENT)

_mod = types.ModuleType("signal_runner")
_mod.__file__ = SR_PATH
sys.modules["signal_runner"] = _mod
exec(compile(_src, SR_PATH, "exec"), _mod.__dict__)
if WANT_HODLOD:
    _mod.HODLOD_PAIR = True
assert _mod.PIVOT_LEVELS == (not WANT_NOPIVOT)
assert _mod.HODLOD_PAIR == WANT_HODLOD

import research.t4_engine_recall as t4  # noqa: E402

SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
CORPUS = os.path.join(HERE, "g71_samplesize_corpus.json")


def jl(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def top_austin(r):
    """Highest grade Austin gave the day, S first. Same reader as
    research/g71_samplesize_full_recall.py::top_austin."""
    for g in ("S", "A", "C", "none"):
        if r["austin"].get(g):
            return g
    return None


def main():
    # ---- every symbol-day either read needs, replayed exactly once ----------
    cards = [r for r in jl(SWEEP) if r["answers"].get("s")]
    corpus = [r for r in json.load(open(CORPUS, encoding="utf-8"))["rows"]
              if r["bars"] and r["austin"]]

    days = {(r["symbol"], r["date"]) for r in cards}
    days |= {(r["symbol"], r["day"]) for r in corpus}

    t0 = time.time()
    rep = {}
    for i, (sym, day) in enumerate(sorted(days)):
        try:
            entries, sigs, _raw = t4.run_day(sym, day)
        except Exception as e:
            rep[(sym, day)] = {"error": type(e).__name__ + ": " + str(e)[:100]}
            continue
        if entries is None:
            rep[(sym, day)] = {"error": "no archived bars"}
            continue
        rep[(sym, day)] = {"entries": len(entries), "signals": len(sigs)}
        if i % 200 == 0:
            print("  %d/%d  %.0fs" % (i, len(days), time.time() - t0), flush=True)
    elapsed = time.time() - t0

    def fired(sym, day):
        return bool(rep.get((sym, day), {}).get("entries"))

    # ---- read 1: the published 100-card held-out sweep ----------------------
    his_s = [r for r in cards if r["answers"]["s"] == ["s"]]
    his_no = [r for r in cards if r["answers"]["s"] != ["s"]]
    tp = [r for r in his_s if fired(r["symbol"], r["date"])]
    fp = [r for r in his_no if fired(r["symbol"], r["date"])]
    sweep = {
        "set": "probe_s_sweep_2026-08-28 (100 blind cards)",
        "n_S": len(his_s), "n_no": len(his_no),
        "fired_on_S": len(tp), "fired_on_no": len(fp),
        "recall_pct": round(len(tp) / len(his_s) * 100, 1) if his_s else 0.0,
        "precision_pct": (round(len(tp) / (len(tp) + len(fp)) * 100, 1)
                          if (tp or fp) else 0.0),
        "hit_S": sorted(r["card_id"] for r in tp),
        "missed_S": sorted(r["card_id"] for r in his_s
                           if not fired(r["symbol"], r["date"])),
    }

    # ---- read 2: the whole judged corpus, by his grade ----------------------
    by = defaultdict(lambda: {"n": 0, "fired": 0})
    hit_keys = defaultdict(list)
    miss_keys = defaultdict(list)
    for r in corpus:
        g = top_austin(r)
        if g is None:
            continue
        d = rep.get((r["symbol"], r["day"]), {})
        if "error" in d:
            continue
        by[g]["n"] += 1
        if d.get("entries"):
            by[g]["fired"] += 1
            hit_keys[g].append(r["key"])
        else:
            miss_keys[g].append(r["key"])
    full = {g: {"n": v["n"], "fired": v["fired"],
                "recall_pct": round(v["fired"] / v["n"] * 100, 1) if v["n"] else 0.0}
            for g, v in sorted(by.items())}

    out = {
        "arm": ARGS.arm,
        "flags": {"HODLOD_PAIR": WANT_HODLOD,
                  "OR_in_gating_set": not WANT_NOOR,
                  "PIVOT_LEVELS": not WANT_NOPIVOT},
        "replayed_days": len(days),
        "replay_errors": sum(1 for v in rep.values() if "error" in v),
        "seconds": round(elapsed, 1),
        "sweep_100": sweep,
        "full_corpus_by_his_grade": full,
        "full_corpus_S_hits": sorted(hit_keys["S"]),
        "full_corpus_S_misses": sorted(miss_keys["S"]),
    }
    with open(ARGS.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({k: v for k, v in out.items()
                      if k not in ("full_corpus_S_hits", "full_corpus_S_misses")},
                     indent=1)[:2000])
    print("wrote", ARGS.out)


if __name__ == "__main__":
    main()
