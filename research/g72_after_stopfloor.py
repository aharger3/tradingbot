"""G7.2 verification — why every loss in the two-year book is exactly -1.000R,
and why research/t11_stop_fill_fix.py reads RED while the engine is correct.

THE ALARM. In the freshly rebuilt book (research/bt2y_trades.json) 1,775 of
1,828 losing rows book EXACTLY -1.0000R, nothing is below -1.0R, and the
-1.25R floor never binds on any row. That is the signature CLAUDE.md warns
about: "every loss was -1.000R by construction and the floor was unreachable
code". Taken at face value it would mean the T11 stop-fill fix never landed and
every dollar figure on this board understates the losses.

THE ANSWER. It is not the fill. `backtest_week._stop_fill_px` does route
through `stop_rule.stop_fill_price` (the one definition) and t11 proves it.
What caps the loss first is a DIFFERENT rule: `DISASTER_STOP` (default ON)
rests a stop ORDER at -1R. A resting order that is touched fills AT its price,
so it books exactly -1.0R -- intraday, off the wick, before the candle can
close past 1R and hand the close-fill path anything worse to floor.

So while the resting order is on, -1.25R is unreachable BY DESIGN, not by bug.
The two rules are both real and they compose in that order.

t11_stop_fill_fix.py never sets DISASTER_STOP. It drives backtest_week with the
resting order live and then asserts the close-fill outcomes, so its 12
backtest-side checks fail on a configuration the engine was never asked to
produce. Its live-path (paper_trader) checks pass because that path is
configured separately. This script pins both halves.

Run:
    python research/g72_after_stopfloor.py

Writes research/g72_after_stopfloor.json. 1R = $1,000 (CLAUDE.md).
"""
import collections, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "research" / "bt2y_trades.json"
T11 = ROOT / "research" / "t11_stop_fill_fix.py"


def book_loss_shape():
    """How the shipped book actually books its losses."""
    b = json.load(open(BOOK, encoding="utf-8"))
    traded = [r for r in b["trades"] if r.get("traded")]
    losses = [r["r"] for r in traded if r["r"] < 0]
    c = collections.Counter(round(r, 4) for r in losses)
    return {
        "book_generated": b["meta"].get("generated"),
        "traded_rows": len(traded),
        "losing_rows": len(losses),
        "exactly_minus_1R": c.get(-1.0, 0),
        "worse_than_minus_1R": sum(1 for r in losses if r < -1.0001),
        "at_the_minus_125_floor": sum(1 for r in losses if abs(r + 1.25) < 1e-6),
        "worst_loss_R": min(losses) if losses else None,
    }


def t11(disaster: str):
    """Run t11_stop_fill_fix.py with DISASTER_STOP forced, return (exit, tail)."""
    env = dict(os.environ)
    env["DISASTER_STOP"] = disaster
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run([sys.executable, str(T11)], cwd=str(ROOT), env=env,
                       capture_output=True, text=True, errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    fails = [l.strip() for l in out.splitlines() if l.strip().startswith("- ")]
    return {"disaster_stop": disaster, "exit": p.returncode,
            "failing_checks": len(fails), "last_line": out.strip().splitlines()[-1]
            if out.strip() else ""}


def _verdict(on, off):
    """Read the two t11 runs.

    HISTORY. When this script was written (2026-08-29) t11_stop_fill_fix.py
    never touched DISASTER_STOP, so it inherited whatever the env said: red
    with the resting order on, green with it off. That asymmetry WAS the
    finding. t11 now switches the order itself -- close-fill sections off,
    section 3b on -- so it is green under both, and green/green is the fixed
    state, not a new alarm.
    """
    if on["exit"] == 0 and off["exit"] == 0:
        return ("engine correct, and t11 now controls the resting order itself "
                "(green with it on and off) -- the blind spot is fixed")
    if off["exit"] == 0 and on["exit"] != 0:
        return "engine correct, test blind to DISASTER_STOP"
    return "NOT explained by the resting order -- investigate the fill path"


def main():
    shape = book_loss_shape()
    on, off = t11("1"), t11("0")
    out = {
        "book_loss_shape": shape,
        "t11_with_resting_order_ON": on,
        "t11_with_resting_order_OFF": off,
        "verdict": _verdict(on, off),
    }
    json.dump(out, open(ROOT / "research" / "g72_after_stopfloor.json", "w",
                        encoding="utf-8"), indent=2)

    print("book %s" % shape["book_generated"])
    print("  losing rows            %d" % shape["losing_rows"])
    print("  exactly -1.0000R       %d" % shape["exactly_minus_1R"])
    print("  worse than -1.0R       %d" % shape["worse_than_minus_1R"])
    print("  at the -1.25R floor    %d" % shape["at_the_minus_125_floor"])
    print("  worst loss             %sR" % shape["worst_loss_R"])
    print()
    print("t11_stop_fill_fix.py, resting -1R order ON : exit %d, %d failing checks"
          % (on["exit"], on["failing_checks"]))
    print("t11_stop_fill_fix.py, resting -1R order OFF: exit %d, %d failing checks"
          % (off["exit"], off["failing_checks"]))
    print()
    print("VERDICT: %s" % out["verdict"])


if __name__ == "__main__":
    main()
