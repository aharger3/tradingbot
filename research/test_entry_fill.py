"""Entry-fill selftest — the gate on `entry_fill.py`, the ONE entry price.

`stop_rule.stop_fill_price` is the one STOP fill. Until 2026-08-30 there was no
equivalent for the ENTRY, and the price the book paid came from
`signal_runner.fill_price`, which clamps the LEVEL into the signal bar's own
range. The signal does not exist until that minute closes, so on most trades the
book paid a price the minute had already traded before there was anything to
react to. Measured: only **105 of 4,508 trades (2.3%)** are obtainable at the
book's price, and **53.8% of the intrabar fills sit at the bar's own extreme with
the level outside the bar**, where a resting order fills nothing at all
(`research/g80_lookahead_refute.md`).

This file is the guard on the replacement. It covers all five modes, the no-fill
case, and the one that has already gone wrong once: a resting limit may NEVER
rest before the signal exists. Last night's verifier found exactly that bug —
5,472 of 5,714 fills landed ahead of the signal bar, median 3 minutes early, and
it turned a +$92/day arm into a fabricated -$252/day.

It also asserts the SHIPPED DEFAULT is `close`, in an isolated child process with
`ENTRY_FILL` popped from the environment — the same trick
`test_runner_stop._shipped_default_probe` uses, and for the same reason: a
module-level constant latched at import time will happily report whatever the
host process was started with.

Synthetic bars, no archive, no network. Run:

    python research/test_entry_fill.py
"""

from __future__ import annotations
import json
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import entry_fill as ef                                          # noqa: E402

EPS = 1e-9


class C:
    """The least a bar has to be. `omen_bot.Candle` satisfies this, and so does
    a loose DXLink bar with the same four attribute names."""

    def __init__(self, o, h, l, c, ts=""):
        self.open, self.high, self.low, self.close = o, h, l, c
        self.timestamp = ts

    def __repr__(self):
        return "C(%s o=%.2f h=%.2f l=%.2f c=%.2f)" % (
            self.timestamp or "?", self.open, self.high, self.low, self.close)


# The signal bar, long side. It CLOSES at 100.80, inside the top 25% of its own
# range — the exact shape `signal_runner.bar_extreme_veto` calls a bad fill, and
# therefore the shape on which the published book back-dates to the level.
SIG = C(100.20, 100.90, 100.05, 100.80, "09:45:00")
LEVEL = 100.10          # inside the bar: the published clamp returns it untouched
LOW_LEVEL = 99.00       # OUTSIDE the bar: the published clamp invents a fill here

# The short mirror.
SIG_S = C(99.80, 99.95, 99.10, 99.20, "09:45:00")
LEVEL_S = 99.90


def _rows():
    """(name, ok, detail) for every case. Nothing raises out of here except the
    two cases that are SUPPOSED to raise, which are caught in-place."""
    r = []

    def chk(name, cond, detail=""):
        r.append((name, bool(cond), detail))

    # ---------------- published: kept only for reproducibility -------------
    f = ef.entry_fill_price(LEVEL, SIG, True, close_is_bad_fill=True,
                            mode="published")
    chk("published, extreme close -> the LEVEL (the old clamp)",
        f.filled and abs(f.price - LEVEL) < EPS, "%.4f" % f.price)
    chk("published fills on the signal bar itself", f.bar_offset == 0,
        "offset %s" % f.bar_offset)

    f = ef.entry_fill_price(LEVEL, SIG, True, close_is_bad_fill=False,
                            mode="published")
    chk("published, ordinary close -> the CLOSE",
        f.filled and abs(f.price - SIG.close) < EPS, "%.4f" % f.price)

    f = ef.entry_fill_price(LOW_LEVEL, SIG, True, close_is_bad_fill=True,
                            mode="published")
    chk("published clamps a level BELOW the bar up to the bar's low "
        "(the unobtainable fill, reproduced on purpose)",
        abs(f.price - SIG.low) < EPS, "%.4f" % f.price)

    f = ef.entry_fill_price(LEVEL_S, SIG_S, False, close_is_bad_fill=True,
                            mode="published")
    chk("published, short side -> the LEVEL",
        abs(f.price - LEVEL_S) < EPS, "%.4f" % f.price)

    # ---------------- close: the new default -------------------------------
    for bad in (True, False):
        f = ef.entry_fill_price(LEVEL, SIG, True, close_is_bad_fill=bad,
                                mode="close")
        chk("close ignores the fill-quality gate (bad_fill=%s)" % bad,
            f.filled and abs(f.price - SIG.close) < EPS, "%.4f" % f.price)

    f = ef.entry_fill_price(LEVEL_S, SIG_S, False, mode="close")
    chk("close, short side -> the close",
        abs(f.price - SIG_S.close) < EPS, "%.4f" % f.price)

    # close needs no future bars at all — it is the price on the screen.
    f = ef.entry_fill_price(LEVEL, SIG, True, mode="close", future_bars=())
    chk("close fills with zero future bars", f.filled, "%.4f" % f.price)

    # ---------------- next_open --------------------------------------------
    nxt = C(100.95, 101.20, 100.70, 101.00, "09:46:00")
    f = ef.entry_fill_price(LEVEL, SIG, True, mode="next_open",
                            future_bars=[nxt])
    chk("next_open -> the NEXT minute's open",
        f.filled and abs(f.price - nxt.open) < EPS, "%.4f" % f.price)
    chk("next_open books on the bar AFTER the signal", f.bar_offset == 1,
        "offset %s" % f.bar_offset)

    f = ef.entry_fill_price(LEVEL, SIG, True, mode="next_open", future_bars=[])
    chk("next_open on the session's LAST bar is a NO TRADE",
        (not f.filled) and f.price is None, f.reason)

    # ---------------- chase_once -------------------------------------------
    # The limit rests for one bar. That bar trades down through the level.
    touch = C(100.60, 100.70, 100.00, 100.40, "09:46:00")
    after = C(100.40, 100.50, 100.30, 100.45, "09:47:00")
    f = ef.entry_fill_price(LEVEL, SIG, True, mode="chase_once",
                            future_bars=[touch, after])
    chk("chase_once fills AT the level when the next bar trades to it",
        f.filled and abs(f.price - LEVEL) < EPS, "%.4f" % f.price)
    chk("chase_once's limit books on the bar after the signal", f.bar_offset == 1,
        "offset %s" % f.bar_offset)

    # The bar GAPS through the level: a resting buy limit fills at the open,
    # which is better than the level, never worse.
    gap = C(99.50, 99.80, 99.30, 99.60, "09:46:00")
    f = ef.entry_fill_price(LEVEL, SIG, True, mode="chase_once",
                            future_bars=[gap, after])
    chk("chase_once fills at the OPEN when the bar opens through the level",
        abs(f.price - gap.open) < EPS, "%.4f" % f.price)

    # It never trades to the level -> market at the open of the bar after that.
    miss = C(100.95, 101.10, 100.85, 101.00, "09:46:00")
    mkt = C(101.05, 101.30, 101.00, 101.20, "09:47:00")
    f = ef.entry_fill_price(LEVEL, SIG, True, mode="chase_once",
                            future_bars=[miss, mkt])
    chk("chase_once unfilled -> MARKET at the following open",
        f.filled and abs(f.price - mkt.open) < EPS, "%.4f" % f.price)
    chk("the chase books two bars after the signal", f.bar_offset == 2,
        "offset %s" % f.bar_offset)

    f = ef.entry_fill_price(LEVEL, SIG, True, mode="chase_once",
                            future_bars=[miss])
    chk("chase_once with nothing left to chase into is a NO TRADE",
        (not f.filled) and f.price is None, f.reason)

    # Short side: the limit sits ABOVE, and a bar that only trades DOWN misses.
    up = C(99.30, 99.95, 99.25, 99.90, "09:46:00")
    f = ef.entry_fill_price(LEVEL_S, SIG_S, False, mode="chase_once",
                            future_bars=[up, after])
    chk("chase_once, short side, fills at the level on a bar that trades up",
        f.filled and abs(f.price - LEVEL_S) < EPS, "%.4f" % f.price)

    # ---------------- limit_level ------------------------------------------
    # Rests from the bar AFTER the signal until 11:00. Fills on the first touch.
    b1 = C(100.85, 101.00, 100.50, 100.70, "09:46:00")
    b2 = C(100.70, 100.75, 100.00, 100.20, "09:47:00")
    f = ef.entry_fill_price(LEVEL, SIG, True, mode="limit_level",
                            future_bars=[b1, b2])
    chk("limit_level fills at the level on the first bar that reaches it",
        f.filled and abs(f.price - LEVEL) < EPS, "%.4f" % f.price)
    chk("limit_level waited for the SECOND bar after the signal",
        f.bar_offset == 2, "offset %s" % f.bar_offset)

    # ***THE ONE THAT HAS ALREADY GONE WRONG.*** The signal bar itself traded
    # through the level (low 100.05 < 100.10) — the order must NOT fill there,
    # because it could not have been resting before the signal existed.
    f = ef.entry_fill_price(LEVEL, SIG, True, mode="limit_level",
                            future_bars=[miss, mkt])
    chk("limit_level NEVER fills on the signal bar, even though that bar "
        "traded through the level",
        not f.filled, f.reason)

    # A no-fill is a NO TRADE, and it says so in a way a caller can count.
    chk("a no-fill carries filled=False, price=None and a reason",
        (not f.filled) and f.price is None and bool(f.reason), f.reason)
    chk("a no-fill is falsey so `if not fill:` cannot silently trade it",
        not bool(f), "bool(fill)=%s" % bool(f))

    # Expiry: he does not trade past 11:00, so a touch at 11:03 is not a trade.
    late = C(100.90, 101.00, 99.00, 99.50, "11:03:00")
    f = ef.entry_fill_price(LEVEL, SIG, True, mode="limit_level",
                            future_bars=[miss, late])
    chk("limit_level expires at 11:00 — a touch after it is NOT a fill",
        not f.filled, f.reason)

    early = C(100.90, 101.00, 99.00, 99.50, "10:59:00")
    f = ef.entry_fill_price(LEVEL, SIG, True, mode="limit_level",
                            future_bars=[miss, early])
    chk("...but 10:59 still fills", f.filled and abs(f.price - LEVEL) < EPS,
        "%.4f" % (f.price if f.price is not None else float("nan")))

    f = ef.entry_fill_price(LEVEL_S, SIG_S, False, mode="limit_level",
                            future_bars=[C(99.20, 99.40, 99.15, 99.30, "09:46:00"),
                                         C(99.30, 99.95, 99.28, 99.90, "09:47:00")])
    chk("limit_level, short side, fills at the level on the bar that reaches up",
        f.filled and abs(f.price - LEVEL_S) < EPS, "%.4f" % f.price)

    # ---------------- the look-ahead assert --------------------------------
    for name, bad_ts in (("the signal bar's OWN minute", "09:45:00"),
                         ("a minute BEFORE the signal", "09:42:00")):
        try:
            ef.entry_fill_price(LEVEL, SIG, True, mode="limit_level",
                                future_bars=[C(100.9, 101.0, 99.0, 99.5, bad_ts)])
            chk("look-ahead: a future bar stamped %s must RAISE" % name,
                False, "it returned a fill instead")
        except ef.LookAheadError as e:
            chk("look-ahead: a future bar stamped %s RAISES" % name, True,
                str(e)[:70])

    try:
        ef.entry_fill_price(LEVEL, SIG, True, mode="chase_once",
                            future_bars=[C(100.9, 101.0, 99.0, 99.5, "09:44:00")])
        chk("look-ahead: chase_once is guarded too", False, "no raise")
    except ef.LookAheadError:
        chk("look-ahead: chase_once is guarded too", True, "")

    # ---------------- misuse -----------------------------------------------
    try:
        ef.entry_fill_price(LEVEL, SIG, True, mode="hope")
        chk("an unknown mode raises", False, "no raise")
    except ValueError as e:
        chk("an unknown mode raises", True, str(e)[:60])

    chk("the five modes are exactly the five named in the spec",
        tuple(ef.ENTRY_FILLS) == ("published", "close", "next_open",
                                  "chase_once", "limit_level"),
        str(ef.ENTRY_FILLS))

    return r


_DEFAULT_DRIVER = r"""
import json, sys
sys.path.insert(0, %r)
import entry_fill as ef
import signal_runner as sr


class C:
    def __init__(s, o, h, l, c, ts=""):
        s.open, s.high, s.low, s.close, s.timestamp = o, h, l, c, ts


bar = C(100.20, 100.90, 100.05, 100.80, "09:45:00")
print(json.dumps({
    "mode": ef.ENTRY_FILL,
    # the engine's own entry, through the two functions every emit site calls
    "fill_price": sr.fill_price(100.10, bar, True),
    "order_fill": sr.order_fill(100.10, bar, True),
}))
"""


def _probe(**env_over):
    env = dict(os.environ)
    env.pop("ENTRY_FILL", None)
    env.pop("STOP_FILL_ORDER", None)
    env.update({k: v for k, v in env_over.items() if v is not None})
    res = subprocess.run([sys.executable, "-c", _DEFAULT_DRIVER % _REPO],
                         cwd=_REPO, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError("child failed (%s):\n%s"
                             % (env_over, res.stderr[-1500:]))
    return json.loads(res.stdout.strip().splitlines()[-1])


def _default_rows():
    """The loud half: what a fresh process ACTUALLY ships, and whether
    `signal_runner` really delegates instead of keeping its own copy."""
    r = []
    d = _probe()
    r.append(("SHIPPED DEFAULT is `close`, not the unobtainable clamp",
              d["mode"] == "close", "ENTRY_FILL=%r" % d["mode"]))
    r.append(("the shipped engine's entry IS the signal minute's close",
              abs(d["fill_price"] - 100.80) < EPS, "%.4f" % d["fill_price"]))
    r.append(("...and every emit site (order_fill) pays the same price",
              abs(d["order_fill"] - d["fill_price"]) < EPS,
              "%.4f" % d["order_fill"]))

    p = _probe(ENTRY_FILL="published")
    r.append(("ENTRY_FILL=published restores the old clamp exactly",
              abs(p["fill_price"] - 100.10) < EPS, "%.4f" % p["fill_price"]))
    r.append(("the default and the published fill really are DIFFERENT prices "
              "on a bar that closes at its extreme",
              abs(p["fill_price"] - d["fill_price"]) > 0.01,
              "%.4f vs %.4f" % (p["fill_price"], d["fill_price"])))

    n = _probe(ENTRY_FILL="next_open")
    r.append(("a forward-looking mode still returns a usable price inside "
              "signal_runner, which has no future bars",
              n["fill_price"] is not None, "%.4f" % n["fill_price"]))
    return r


def main():
    rows = _rows() + _default_rows()
    width = max(len(n) for n, _, _ in rows)
    for name, ok, detail in rows:
        print("%-*s  %s  %s" % (width, name, "ok  " if ok else "FAIL", detail))
    bad = [n for n, ok, _ in rows if not ok]
    print()
    if bad:
        print("ENTRY-FILL SELFTEST FAILED: %d of %d checks are wrong."
              % (len(bad), len(rows)))
        for n in bad:
            print("  " + n)
        sys.exit(1)
    print("entry-fill selftest ok: %d checks, five modes, no-fill is a NO TRADE, "
          "and no limit ever rests before its signal." % len(rows))


if __name__ == "__main__":
    main()
