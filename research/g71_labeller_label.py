"""G7.1 / labeller -- the setup labeller Austin asked for.

Austin, 2026-08-29:
  "so in homework also tell me what setup you think it is"
  "remember BR and OCR is also a setup when both of them are together."

For any signal, three answers:

  setup      break-and-retest | one-candle-rule | BR+OCR | other
  level      the level it broke, named, out of HIS SIX (PDH PDL PMH PML ORH ORL)
             -- or the honest label when it broke something he does not watch
  timeframe  entry timeframe, and the timeframe the LEVEL came from

NOTHING here is a new measurement. Every field already exists inside the engine
and is thrown away at one boundary. This script reads them back out of
`research/bt2y_trades.json` so the diff in research/g71_labeller.md can be
judged before it is applied.

  setup   ->  row["setup"] (SimTrade.signal_type)  +  "brocr" in row["tags"]
              The [brocr] tag is stamped by
              signal_runner.OMENSignalRunner._label_confluence:2421-2423, which
              calls research/downgrade.py::has_confluence -- the ONE definition
              of BR+OCR confluence. `sig["setup_type"]` already holds exactly the
              answer; backtest_week.py:861-868 does not copy it onto SimTrade, so
              the book only keeps the tag's shadow of it.

  level   ->  row["level"], which backtest_2y.py:153,187 re-derives with a regex
              over the reason prose. That regex cannot see an order block, so
              EVERY one-candle-rule row in the book is filed as "other". The
              signal itself carries `stop_level_name` (signal_runner.py:2819,
              2912, 3090, 3163) and `level_price` (SimTrade.level_price, already
              plumbed). This script resolves the OCR rows by snapping the broken
              price onto the six-level roster.

  timeframe-> a CONSTANT the book never states: entries are 1-minute bars
              (polygon_feed.rth), HTF bias is 1-hour (backtest_12mo
              .hourly_from_1m). What varies per signal is the timeframe the LEVEL
              was drawn on, and that is a pure function of the level's name.

Snapping tolerance is signal_runner.PIVOT_DEDUPE_FRAC (0.001), NOT a new number:
the engine already rules that "a pivot within PIVOT_DEDUPE_FRAC of a named level
is that level having a second name, not a new one" (signal_runner.py:2703-2706).
The same rule is what makes an order block sitting at ORH an ORH break.

Usage:
    python research/g71_labeller_label.py                 # summary + 20-row sample
    python research/g71_labeller_label.py --resolve       # snap OCR rows (needs archive)
    python research/g71_labeller_label.py --out research/g71_labeller_sample.json
"""
import argparse, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import signal_runner as sr                      # PIVOT_DEDUPE_FRAC, nothing else

BOOK = ROOT / "research" / "bt2y_trades.json"

# Austin, 2026-08-29: "you know the 6 levels i watch thats it."
# (Projects/omen-rulebook.md -- "The six levels are closed".) Engine name on
# the left, his name on the right.
HIS_SIX = {"PDH": "PDH", "PDL": "PDL", "PMH": "PMH", "PML": "PML",
           "OR high": "ORH", "OR low": "ORL"}

# The timeframe each level is DRAWN on. Entry timeframe is 1m for all of them.
LEVEL_TF = {"PDH": "1D (prior session)", "PDL": "1D (prior session)",
            "PMH": "1m premarket 04:00-09:30", "PML": "1m premarket 04:00-09:30",
            "ORH": "5m opening range (first 5x1m)",
            "ORL": "5m opening range (first 5x1m)",
            "pivot high": "1m intraday swing (lookback 30)",
            "pivot low": "1m intraday swing (lookback 30)",
            "order block": "1m single candle",
            "prior entry": "1m (the failed entry price)"}


def label_setup(row):
    """{break-and-retest, one-candle-rule, BR+OCR, other} for one book row.

    BR+OCR wins over its own base whenever downgrade.has_confluence held on the
    entry bar -- that is Austin's third setup class, not two overlapping
    detections. reentry_84_rule is deliberately NOT eligible: it is excluded
    from signal_runner.CONFLUENCE_BASE_SETUPS:852 because it is a second bite at
    an idea that already fired, not a fresh break-and-retest."""
    base = row["setup"]
    brocr = "brocr" in row.get("tags", ())
    if base in ("break_and_retest", "one_candle_rule") and brocr:
        return "BR+OCR"
    if base == "break_and_retest":
        return "break-and-retest"
    if base == "one_candle_rule":
        return "one-candle-rule"
    return "other (%s)" % base


def _kind(row):
    return {"one_candle_rule": "order block",
            "reentry_84_rule": "prior entry"}.get(row["setup"], "other")


def broken_price(row):
    """The price of the level this signal broke and retested.

    B&R: the stop IS the level (BNR_STOP_MODE='level', signal_runner.py:2727).
    OCR: the stop is the FAR side of the block; the level broken is the block's
         near edge, which the fill sits on
         (entry = order_fill(block.high, ...), signal_runner.py:2885).
         SimTrade.level_price already holds it exactly; the book does not carry
         that column, so `entry` stands in and is within one tick of it.
    84%: the reclaimed prior entry price."""
    return row["stop"] if row["setup"] == "break_and_retest" else row["entry"]


def label_level(row, roster=None):
    """(his_name_or_None, engine_name, timeframe_the_level_was_drawn_on)."""
    eng = row.get("level", "other")
    if eng in HIS_SIX:
        n = HIS_SIX[eng]
        return n, eng, LEVEL_TF[n]
    px = broken_price(row)
    if roster:
        tol = sr.PIVOT_DEDUPE_FRAC          # 0.001 -- the engine's own dedupe rule
        best, bestd = None, None
        for name in ("PDH", "PDL", "PMH", "PML", "ORH", "ORL"):
            lv = roster.get(name)
            if not lv:
                continue
            d = abs(px - lv) / abs(lv)
            if d <= tol and (bestd is None or d < bestd):
                best, bestd = name, d
        if best:
            return best, "snapped from %s" % (eng if eng != "other" else _kind(row)), LEVEL_TF[best]
    name = eng if eng != "other" else _kind(row)
    return None, name, LEVEL_TF.get(name, "1m intraday")


def label(row, roster=None):
    his, eng, tf = label_level(row, roster)
    return {
        "sym": row["sym"], "day": row["day"], "et": row["et"], "side": row["side"],
        "setup": label_setup(row),
        "level": his or ("not-his: " + eng),
        "level_px": round(broken_price(row), 2),
        "entry_tf": "1m",
        "level_tf": tf,
        "his_six": bool(his),
        # both ladders, side by side, always (CLAUDE.md)
        "legacy": row["grade"], "austin": row["sgrade"],
        "r": row["r"], "out": row["out"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--book", default=str(BOOK))
    ap.add_argument("--all", action="store_true", help="label every signal, not just traded")
    ap.add_argument("--resolve", action="store_true",
                    help="snap non-six levels onto the six using the archive (slow)")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    book = json.loads(Path(a.book).read_text())
    rows = book["trades"]
    if not a.all:
        rows = [r for r in rows if r["traded"]]

    rosters = {}
    if a.resolve:
        from research import p21_target_availability as p21
        for r in rows:
            if r.get("level", "other") in HIS_SIX:
                continue
            k = (r["sym"], r["day"], r["entry_i"])
            if k not in rosters:
                try:
                    rosters[k] = p21.levels_for_entry(*k)
                except Exception:
                    rosters[k] = {}

    out = [label(r, rosters.get((r["sym"], r["day"], r["entry_i"]))) for r in rows]

    print("rows labelled: %d  (%s)" % (len(out), "all signals" if a.all else "traded only"))
    print()
    print("setup:")
    for k, v in Counter(o["setup"] for o in out).most_common():
        print("   %-22s %6d  %5.1f%%" % (k, v, 100.0 * v / len(out)))
    print()
    print("level:")
    for k, v in Counter(o["level"] for o in out).most_common():
        print("   %-34s %6d  %5.1f%%" % (k, v, 100.0 * v / len(out)))
    print()
    print("his six coverage: %d / %d = %.1f%%"
          % (sum(o["his_six"] for o in out), len(out),
             100.0 * sum(o["his_six"] for o in out) / len(out)))
    print()
    print("setup x level-is-his:")
    for k, v in sorted(Counter((o["setup"], o["his_six"]) for o in out).items()):
        print("   %-22s his_six=%-5s %6d" % (k[0], k[1], v))

    print()
    print("--- sample of %d (round-robin across setup classes, oldest first) ---" % a.n)
    classes = sorted({o["setup"] for o in out})
    per = max(1, a.n // max(1, len(classes)))
    ordered = sorted(out, key=lambda x: (x["day"], x["sym"], x["et"]))
    sample, seen, taken = [], Counter(), set()
    for idx, o in enumerate(ordered):
        if seen[o["setup"]] < per and len(sample) < a.n:
            sample.append(o); seen[o["setup"]] += 1; taken.add(idx)
    for idx, o in enumerate(ordered):
        if len(sample) >= a.n:
            break
        if idx not in taken:
            sample.append(o)
    hdr = ("sym", "day", "et", "sd", "setup", "level", "px",
           "entry_tf", "level_tf", "eng", "aus", "R", "out")
    w = (6, 10, 5, 2, 16, 26, 8, 8, 33, 4, 4, 7, 7)
    print("  ".join(h.ljust(x) for h, x in zip(hdr, w)))
    print("  ".join("-" * x for x in w))
    for o in sample[:a.n]:
        cells = (o["sym"], o["day"], o["et"], o["side"], o["setup"], o["level"],
                 "%.2f" % o["level_px"], o["entry_tf"], o["level_tf"],
                 o["legacy"], o["austin"], "%+.3f" % o["r"], o["out"])
        print("  ".join(str(c)[:x].ljust(x) for c, x in zip(cells, w)))

    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1))
        print("\nwrote %s" % a.out)


if __name__ == "__main__":
    main()
