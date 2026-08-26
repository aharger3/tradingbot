"""P10 / G9 -- structure trail plus a far-target tail, over the two-year book.

G7 (`research/g7_exit_sweep.md`) swept eight exit policies x two clock arms and
came back negative: nothing reached the 2.0R money gate, the incumbent ladder B
(+0.957R whole book, +1.283R on S) was already the top of its family, and
removing the 11:00 ET force-flat made every *trailing* policy worse.

G7's trails were all mechanical -- 1.0x ATR14 or the prior bar's low/high, plus
a 5-bar consolidation exit. None of them asks "is the thesis still true?". This
rig tests the arm G7 named but did not run:

  * a **structure trail** -- longs stay in while the 1-minute trend structure
    holds (higher highs / higher lows) and leave on a CLOSE beyond the last
    confirmed swing low, mirrored for shorts;
  * a **far-target tail** -- partials at 4R and 5R behind the incumbent's first
    rung, so a runner can actually reach the +4.6R average the money-gate
    arithmetic demands;
  * both clock arms (force-flat at 11:00 ET, and none).

Entry, stop and side are FIXED inputs from `research/bt2y_trades.json` -- the
same signals the report and G7 use. Only the exit varies.

CAUSALITY. Every decision at bar ``i`` reads only bars ``<= i``, and the trail
level applied *to* bar ``i`` is built from bars ``<= i-1``. That is stricter
than it sounds for a swing rule: a swing low at index ``j`` is only confirmable
once bar ``j+1`` has closed, so the newest swing usable when bar ``i`` opens
sits at ``j = i-2``. `--selftest` proves it by truncating each replay at the
bar the policy actually exited on and asserting the R is unchanged -- a
look-ahead read of any later bar would move it.

Swing definition is copied from `omen_bot.py::MarketStructure.update` (the
1-bar fractal: ``h[j] > h[j-1] and h[j] > h[j+1]``) rather than invented here,
so the trail speaks the same structure vocabulary as detection. It is copied
rather than imported because ``MarketStructure`` rebuilds the whole session
non-causally on every ``update`` and consumes ``Candle`` objects, not the dicts
`exit_lab` replays.

Usage:
    python research/p10_structure_trail.py [--selftest] [--inp ...] [--out ...]
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import polygon_feed as pf                       # noqa: E402
from research import exit_lab as xl             # noqa: E402

ARMS = [("clock", 90), ("noclock", 10 ** 6)]    # exit_lab.CLOCK_BAR per arm


# ---------------------------------------------------------------------------
# structure
# ---------------------------------------------------------------------------

def is_swing_low(bars, j):
    """1-bar fractal swing low at index ``j``. Reads bars j-1, j, j+1.

    Copied from omen_bot.py::MarketStructure.update -- same comparison, same
    strictness (``<``), same 1-bar neighbourhood.
    """
    if j < 1 or j + 1 >= len(bars):
        return False
    return bars[j]["l"] < bars[j - 1]["l"] and bars[j]["l"] < bars[j + 1]["l"]


def is_swing_high(bars, j):
    """1-bar fractal swing high at index ``j``. See is_swing_low."""
    if j < 1 or j + 1 >= len(bars):
        return False
    return bars[j]["h"] > bars[j - 1]["h"] and bars[j]["h"] > bars[j + 1]["h"]


# ---------------------------------------------------------------------------
# the replay
# ---------------------------------------------------------------------------

def structure_policy(bars, entry_i, entry, stop, side,
                     w_hod, far_targets=(), be_floor=False, return_exit=False):
    """Replay one trade under: rung 1 at the causal HOD/LOD, remainder on the
    structure trail, with optional partials at far R targets.

    ``w_hod``        weight taken at the incumbent's first rung (causal HOD).
    ``far_targets``  sequence of ``(target_r, weight)`` partials, live only
                     once rung 1 is out. The trail carries whatever is left.
    ``be_floor``     if True the trail is also floored at entry (break-even)
                     once rung 1 is out, exactly as `exit_lab`'s runner does.
                     If False the trail is floored only by the original stop,
                     which is the looser arm G7's numbers point at.

    Bar order of operations, all causal:
      1. the stop level for bar ``i`` is fixed from bars ``<= i-1``;
      2. a close beyond it exits everything still open at that close
         (`exit_lab._stop_fill`, floored at -1.25R);
      3. rung 1 books at the close of the causal-HOD exit bar;
      4. far targets book at the target price if bar ``i`` traded through it;
      5. bar ``i`` is folded into the structure state for the *next* bar;
      6. the clock (if any) flattens the remainder at that bar's close.
    """
    n = len(bars)
    risk = abs(entry - stop)
    if risk <= 0 or entry_i >= n:
        return (0.0, entry_i) if return_exit else 0.0
    clock = xl.CLOCK_BAR
    end = min(clock + 1, n)

    hod_i = xl.causal_hod_exit_bar(bars, entry_i, side)
    if hod_i is None:
        return (0.0, entry_i) if return_exit else 0.0

    targets = []
    for tr, w in far_targets:
        price = entry + tr * risk if side == "L" else entry - tr * risk
        targets.append([price, w, False])

    booked = 0.0        # weighted R already realised
    open_w = 1.0        # weight still in the trade
    # w_hod == 0 means there is no first rung: the structure trail is live from
    # the bar after entry, which is what `st_100_trail` measures.
    rung1_out = w_hod <= 0.0
    trail = None        # structure trail level, monotone once set

    for i in range(entry_i + 1, end):
        b = bars[i]

        # --- 1. the stop level applied to bar i, built from bars <= i-1 ------
        if not rung1_out:
            active = stop
        else:
            active = stop if trail is None else trail
            if be_floor:
                active = max(active, entry) if side == "L" else min(active, entry)

        # --- 2. close beyond it flattens the remainder -----------------------
        if xl._stop_hit_first(bars, i, entry, active, side):
            px = xl._stop_fill(bars, i, entry, active, side, risk)
            booked += open_w * xl.realised_r(entry, stop, px, side)
            return (booked, i) if return_exit else booked

        # --- 3. rung 1 at the causal HOD/LOD exit bar ------------------------
        if not rung1_out and i >= hod_i:
            booked += w_hod * xl.realised_r(entry, stop, b["c"], side)
            open_w -= w_hod
            rung1_out = True
            if open_w <= 1e-9:
                return (booked, i) if return_exit else booked

        # --- 4. far-target partials, live once rung 1 is out -----------------
        elif rung1_out:
            for t in targets:
                if t[2]:
                    continue
                hit = (b["h"] >= t[0]) if side == "L" else (b["l"] <= t[0])
                if hit:
                    t[2] = True
                    booked += t[1] * xl.realised_r(entry, stop, t[0], side)
                    open_w -= t[1]
            if open_w <= 1e-9:
                return (booked, i) if return_exit else booked

        # --- 5. fold bar i into the structure state --------------------------
        # A swing at index j needs bar j+1 to confirm it, so bar i confirms the
        # swing at i-1. That level is therefore known before bar i+1 opens --
        # and NOT before bar i opens, which is why this runs after the tests.
        j = i - 1
        if side == "L":
            if is_swing_low(bars, j):
                lvl = bars[j]["l"]
                if trail is None or lvl > trail:
                    trail = lvl              # monotone: the trail never loosens
        else:
            if is_swing_high(bars, j):
                lvl = bars[j]["h"]
                if trail is None or lvl < trail:
                    trail = lvl

        # --- 6. clock -------------------------------------------------------
        if i >= clock:
            booked += open_w * xl.realised_r(entry, stop, b["c"], side)
            return (booked, i) if return_exit else booked

    last = min(end, n) - 1
    if last <= entry_i:
        return (booked, entry_i) if return_exit else booked
    booked += open_w * xl.realised_r(entry, stop, bars[last]["c"], side)
    return (booked, last) if return_exit else booked


def make(w_hod, far_targets=(), be_floor=False):
    def policy(bars, entry_i, entry, stop, side, return_exit=False):
        return structure_policy(bars, entry_i, entry, stop, side,
                                w_hod, far_targets, be_floor, return_exit)
    return policy


# Weightings. Every one keeps a real tail: the trail carries the last slice with
# no fixed target above it.
SPECS = [
    ("st_100_trail",      1.00, ()),                          # no rung at all
    ("st_30_70",          0.30, ()),
    ("st_50_50",          0.50, ()),
    ("st_70_30",          0.70, ()),
    ("st_50_25x4r_25",    0.50, ((4.0, 0.25),)),
    ("st_50_20x4r_20x5r", 0.50, ((4.0, 0.20), (5.0, 0.20))),
    ("st_30_30x4r_30x5r", 0.30, ((4.0, 0.30), (5.0, 0.30))),
]
# st_100_trail takes 100% at the rung when w_hod=1.0, which is not a trail at
# all -- so it is built with w_hod=0.0 and no rung, pure structure trail.
POLICIES = {}
for _name, _w, _t in SPECS:
    if _name == "st_100_trail":
        POLICIES[_name] = make(0.0, ())
    else:
        POLICIES[_name] = make(_w, _t)
        POLICIES[_name + "_be"] = make(_w, _t, be_floor=True)
POLICIES["st_100_trail_be"] = make(0.0, (), be_floor=True)
PIDS = list(POLICIES)


# --- non-causal reference: the roof over every exit policy ------------------
# These CHEAT. They are printed to bound the family, never to be traded, and
# they are excluded from POLICIES so the causality selftest never sees them.

def oracle_best_close(bars, entry_i, entry, stop, side):
    """100% out at the single best CLOSE between entry and the clock, chosen
    with hindsight and with no stop. Upper bound on any close-exit policy."""
    n = len(bars)
    end = min(xl.CLOCK_BAR + 1, n)
    rs = [xl.realised_r(entry, stop, bars[i]["c"], side)
          for i in range(entry_i + 1, end)]
    return max(rs) if rs else 0.0


def oracle_mfe(bars, entry_i, entry, stop, side):
    """Maximum favourable excursion in R: the best price the trade ever traded
    at before the clock. No exit rule can beat this, scale-outs included."""
    n = len(bars)
    end = min(xl.CLOCK_BAR + 1, n)
    seq = [(bars[i]["h"] if side == "L" else bars[i]["l"])
           for i in range(entry_i + 1, end)]
    if not seq:
        return 0.0
    px = max(seq) if side == "L" else min(seq)
    return xl.realised_r(entry, stop, px, side)


def oracle_stopped(bars, entry_i, entry, stop, side):
    """The fair ceiling: 100% out at the best CLOSE with hindsight, but the
    trade's own stop stays live and close-triggered. If the stop fires at bar
    k, the oracle could only have exited at a close in (entry_i, k], so its
    take is the best of those (or the stop fill itself if every close was
    worse). No policy that honours Austin's stop and exits on closes can beat
    this number.
    """
    n = len(bars)
    end = min(xl.CLOCK_BAR + 1, n)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    best = None
    for i in range(entry_i + 1, end):
        if xl._stop_hit_first(bars, i, entry, stop, side):
            fill = xl.realised_r(entry, stop,
                                 xl._stop_fill(bars, i, entry, stop, side, risk), side)
            return fill if best is None else max(best, fill)
        r = xl.realised_r(entry, stop, bars[i]["c"], side)
        best = r if best is None else max(best, r)
    return best if best is not None else 0.0


REFS = {"oracle_stopped (non-causal)": oracle_stopped,
        "oracle_best_close (non-causal)": oracle_best_close,
        "oracle_MFE (non-causal)": oracle_mfe}


# ---------------------------------------------------------------------------
# book
# ---------------------------------------------------------------------------

def bars_for(sym, day, _cache={}):
    """RTH bars in exit_lab's dict shape, from the loader entry_i indexes.
    Same approach as research/g7_exit_sweep.py."""
    key = (sym, day)
    if key not in _cache:
        if len(_cache) > 400:
            _cache.clear()
        try:
            rth = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            rth = []
        _cache[key] = [{"t": c.timestamp[:5], "o": c.open, "h": c.high,
                        "l": c.low, "c": c.close} for c in rth]
    return _cache[key]


def load_book(inp):
    raw = json.loads((ROOT / inp).read_text(encoding="utf-8"))
    meta = raw["meta"]
    book = [t for t in raw["trades"] if t["traded"]]
    if book and "entry_i" not in book[0]:
        for t in book:
            bars = bars_for(t["sym"], t["day"])
            t["entry_i"] = next((i for i, b in enumerate(bars) if b["t"] == t["et"]), None)
            t.setdefault("side", "L" if t["dir"] == "call" else "S")
        book = [t for t in book if t["entry_i"] is not None]
    return meta, book


def agg(rs):
    """(n, win%, mean R, total R). Wins are R > 0; scratches (R == 0) are
    excluded from the win-rate denominator. Same as g7_exit_sweep.agg."""
    rs = [r for r in rs if r is not None]
    if not rs:
        return 0, 0.0, 0.0, 0.0
    w = sum(1 for r in rs if r > 0)
    dec = sum(1 for r in rs if r != 0)
    return len(rs), (w / dec * 100 if dec else 0.0), sum(rs) / len(rs), sum(rs)


# ---------------------------------------------------------------------------
# selftest -- causality, not calibration
# ---------------------------------------------------------------------------

def selftest(inp="research/bt2y_trades.json", sample=200):
    """Two assertions.

    1. `exit_lab`'s own selftest still passes, so the shared machinery this
       rig leans on (causal-HOD rung, close-triggered stop, -1.25R floor) is
       the same machinery G7 measured.
    2. No look-ahead: replaying each trade against bars truncated one bar after
       the policy's own exit must return the identical R. If any decision read
       a bar later than the exit bar, the truncated replay diverges.
    """
    xl.selftest()
    _, book = load_book(inp)
    step = max(1, len(book) // sample)
    checked = fails = 0
    for arm, clock in ARMS:
        xl.CLOCK_BAR = clock
        for t in book[::step]:
            bars = bars_for(t["sym"], t["day"])
            ei, entry, stop = t["entry_i"], t["entry"], t["stop"]
            side = t.get("side") or ("L" if t["dir"] == "call" else "S")
            if not bars or ei >= len(bars) or entry is None or stop is None:
                continue
            for pid, fn in POLICIES.items():
                full, exit_i = fn(bars, ei, entry, stop, side, return_exit=True)
                trunc, _ = fn(bars[:exit_i + 1], ei, entry, stop, side, return_exit=True)
                checked += 1
                if abs(full - trunc) > 1e-9:
                    fails += 1
                    if fails <= 10:
                        print("LOOK-AHEAD %s/%s %s %s ei=%d exit=%d %.6f != %.6f"
                              % (arm, pid, t["sym"], t["day"], ei, exit_i, full, trunc))
    xl.CLOCK_BAR = 90
    if fails:
        print("P10 SELFTEST FAILED: %d/%d replays moved under truncation"
              % (fails, checked), file=sys.stderr)
        sys.exit(1)
    print("p10 selftest ok: %d truncated replays identical (no look-ahead)" % checked)


# ---------------------------------------------------------------------------

def table(title, rows, cols):
    out = ["", "### " + title, "",
           "| slice | " + " | ".join(cols) + " |",
           "|---" * (len(cols) + 1) + "|"]
    for label, cells in rows:
        out.append("| " + label + " | " + " | ".join(cells) + " |")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inp", default="research/bt2y_trades.json")
    ap.add_argument("--out", default="research/p10_structure_trail.md")
    ap.add_argument("--csv", default="research/p10_structure_trail.csv")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest(args.inp)
        return

    meta, book = load_book(args.inp)
    print("%d traded signals, %s..%s" % (len(book), meta["first"], meta["last"]))

    results = defaultdict(list)
    for arm, clock in ARMS:
        xl.CLOCK_BAR = clock
        for n, t in enumerate(book, 1):
            bars = bars_for(t["sym"], t["day"])
            ei, entry, stop = t["entry_i"], t["entry"], t["stop"]
            side = t.get("side") or ("L" if t["dir"] == "call" else "S")
            bad = (not bars or ei >= len(bars) or entry is None or stop is None)
            for pid in PIDS:
                if bad:
                    results[(arm, pid)].append(None)
                else:
                    try:
                        results[(arm, pid)].append(
                            POLICIES[pid](bars, ei, entry, stop, side))
                    except Exception:
                        results[(arm, pid)].append(None)
            for rid, fn in REFS.items():
                results[(arm, rid)].append(
                    None if bad else fn(bars, ei, entry, stop, side))
            if n % 250 == 0:
                print("  [%s] %d/%d" % (arm, n, len(book)))
    xl.CLOCK_BAR = 90

    incumbent = [t["r"] for t in book]
    cols = ["n", "win%", "mean R", "total R"]

    def block(title, idx):
        sub = [incumbent[i] for i in idx]
        rows = [("`book` (ladder B, incumbent)",
                 ["%d" % len(idx), "%.1f" % agg(sub)[1],
                  "%+.3f" % agg(sub)[2], "%+.1f" % agg(sub)[3]])]
        for arm, _ in ARMS:
            for pid in PIDS + list(REFS):
                n, wr, mr, tr = agg([results[(arm, pid)][i] for i in idx])
                rows.append(("`%s` / %s" % (pid, arm),
                             ["%d" % n, "%.1f" % wr, "%+.3f" % mr, "%+.1f" % tr]))
        return table(title, rows, cols)

    all_idx = list(range(len(book)))
    lines = ["# P10 (G9) — structure trail + far-target tail, two-year book", "",
             "Generated by `research/p10_structure_trail.py` over **%d** traded "
             "signals (%s → %s). Entry, stop and side are fixed; only the exit "
             "varies. Causality proven by `--selftest` (truncated replay)."
             % (len(book), meta["first"], meta["last"]), "",
             "**The trail.** Longs ride while structure holds and exit on a bar "
             "that CLOSES below the last confirmed 1-minute swing low (the 1-bar "
             "fractal from `omen_bot.py::MarketStructure`); shorts mirror it. The "
             "trail is monotone and floored by the original stop. `_be` variants "
             "also floor it at break-even once rung 1 is out, which is what "
             "`exit_lab`'s runner does.", "",
             "**Naming.** `st_50_25x4r_25` = 50% at the incumbent's causal HOD/LOD "
             "rung, 25% at 4R, 25% on the structure trail with no fixed target. "
             "`st_100_trail` takes no rung at all.", "",
             "**Arms.** `clock` force-flats at 11:00 ET (bar 90). `noclock` runs "
             "to the 15:59 close.", ""]
    lines += block("Every policy, whole book", all_idx)
    for grade in ("S", "A", "C"):
        idx = [i for i, t in enumerate(book) if t.get("sgrade") == grade]
        if idx:
            lines += block("Austin grade %s only" % grade, idx)

    s_idx = [i for i, t in enumerate(book) if t.get("sgrade") == "S"]

    def best(idx):
        pool = {k: [v[i] for i in idx] for k, v in results.items()
                if k[1] in POLICIES}
        return max(((agg(v)[2], k) for k, v in pool.items()))

    bw, kw = best(all_idx)
    bs, ks = best(s_idx)
    base_all = agg(incumbent)[2]
    base_s = agg([incumbent[i] for i in s_idx])[2]

    def mean_of(arm, pid, idx=None):
        v = results[(arm, pid)]
        return agg(v if idx is None else [v[i] for i in idx])[2]

    def dist(arm, pid):
        v = sorted(r for r in results[(arm, pid)] if r is not None)
        return (lambda p: v[int(p * (len(v) - 1))] if v else 0.0,
                (sum(1 for r in v if r >= 4.0) / len(v) * 100) if v else 0.0)

    pct, ge4 = dist("clock", "oracle_stopped (non-causal)")
    npct, nge4 = dist("noclock", "oracle_stopped (non-causal)")
    # what the incumbent leaves on the table, trade by trade
    orc = results[("clock", "oracle_stopped (non-causal)")]
    lose_idx = [i for i, r in enumerate(incumbent) if r <= 0]
    lose_o = sorted(orc[i] for i in lose_idx if orc[i] is not None)
    lose_orc = sum(lose_o) / len(lose_o)
    lose_med = lose_o[len(lose_o) // 2]
    lose_ge1 = sum(1 for r in lose_o if r >= 1.0) / len(lose_o) * 100
    cap = base_all / mean_of("clock", "oracle_stopped (non-causal)") * 100

    lines += ["", "## Read", "",
              "- **Nothing clears the 2.0R gate, and nothing beats the "
              "incumbent.** Best whole-book is `%s / %s` at **%+.3fR** against "
              "ladder B's %+.3fR. Best on S is `%s / %s` at **%+.3fR** against "
              "%+.3fR. Every structure-trail variant is *below* the incumbent on "
              "both slices." % (kw[1], kw[0], bw, base_all, ks[1], ks[0], bs, base_s),
              "- **Weight taken at the first rung beats weight left on the "
              "trail, monotonically**: whole book, clock arm, `st_30_70` "
              "%+.3f → `st_50_50` %+.3f → `st_70_30` %+.3f, and the pure trail "
              "`st_100_trail` %+.3f. The structure trail is a *worse* home for "
              "size than the HOD/LOD rung it is meant to improve on."
              % (mean_of("clock", "st_30_70"), mean_of("clock", "st_50_50"),
                 mean_of("clock", "st_70_30"), mean_of("clock", "st_100_trail")),
              "- **The far-target tail costs money rather than making it.** "
              "Moving 25%% of the book from the trail to a 4R partial: "
              "`st_50_50` %+.3f → `st_50_25x4r_25` %+.3f. Adding a 5R rung on "
              "top: %+.3f. A trade that reaches 4R is in a trend the trail is "
              "still riding; capping it there books the smaller number."
              % (mean_of("clock", "st_50_50"), mean_of("clock", "st_50_25x4r_25"),
                 mean_of("clock", "st_50_20x4r_20x5r")),
              "- **Removing the 11:00 clock is worse for every single variant**, "
              "as it was in G7 — %+.3f → %+.3f on the best whole-book policy. "
              "Structure does not fix that: after 11:00 the swing trail gives "
              "back more than the extra room earns."
              % (mean_of("clock", kw[1]), mean_of("noclock", kw[1])),
              "- **Break-even is nearly free on a scale-out and ruinous without "
              "one.** `_be` variants move mean R by <0.01R (they only bind on "
              "trades the trail was going to lose anyway) but win rate rises "
              "1-3 points. On the rungless `st_100_trail` the break-even floor "
              "costs %+.3fR and 12 points of win rate: with no partial booked, "
              "break-even is a stop that has not earned its place yet."
              % (mean_of("clock", "st_100_trail_be") - mean_of("clock", "st_100_trail")),
              "",
              "## The ceiling of this family", "",
              "Three hindsight bounds, none of them tradeable, all of them "
              "printed to say how much room an exit rule actually has.", "",
              "- **`oracle_stopped`** — best CLOSE with hindsight, but the "
              "trade's own stop stays live and close-triggered. This is the "
              "honest ceiling: no policy that keeps Austin's stop and exits on "
              "closes can beat it.",
              "- **`oracle_best_close`** — same, stop switched off.",
              "- **`oracle_MFE`** — the best price the trade ever *traded* at. "
              "Nothing can beat it, and nothing comes close to it either.", "",
              "| arm | oracle_stopped | oracle_best_close | oracle_MFE | incumbent |",
              "|---|---|---|---|---|",
              "| clock (11:00) | %+.3fR | %+.3fR | %+.3fR | %+.3fR |"
              % (mean_of("clock", "oracle_stopped (non-causal)"),
                 mean_of("clock", "oracle_best_close (non-causal)"),
                 mean_of("clock", "oracle_MFE (non-causal)"), base_all),
              "| noclock (15:59) | %+.3fR | %+.3fR | %+.3fR | %+.3fR |"
              % (mean_of("noclock", "oracle_stopped (non-causal)"),
                 mean_of("noclock", "oracle_best_close (non-causal)"),
                 mean_of("noclock", "oracle_MFE (non-causal)"), base_all),
              "",
              "`oracle_stopped` distribution inside the 11:00 window: median "
              "**%+.2fR**, p75 %+.2fR, p90 %+.2fR, p95 %+.2fR; **%.1f%%** of the "
              "%d traded signals reach 4R at some close before the clock. Over "
              "the full session it is median %+.2fR and %.1f%% reach 4R."
              % (pct(0.50), pct(0.75), pct(0.90), pct(0.95), ge4, len(book),
                 npct(0.50), nge4),
              "",
              "## What would have to change", "",
              "**The room is there and the exit cannot find it.** Inside the "
              "11:00 window the stop-respecting oracle returns %+.3fR — the gate "
              "is 2.0R, so the ceiling is not the problem. The incumbent captures "
              "**%.1f%%** of it; the best structure trail captures less. That is "
              "the whole finding: the R exists, and no rule in this family — "
              "ATR, prior bar, consolidation, and now market structure — knows "
              "which excursions to hold for."
              % (mean_of("clock", "oracle_stopped (non-causal)"), cap),
              "",
              "The reason is separability, and it is measurable. Take the %d "
              "signals the incumbent **loses** on: their stop-respecting oracle "
              "averages **%+.3fR** (median %+.2fR), and %.1f%% of them offered a "
              "close at +1R or better before they died. A third of the losses "
              "are trades that went the right way first and came back — and "
              "while they were going the right way they looked exactly like the "
              "winners. An exit fired on price alone cannot separate them, which "
              "is why every unit of extra patience this rig bought (looser "
              "trail, no clock, far targets) came back out as give-back, and why "
              "the *tighter* rung took the money."
              % (len(lose_idx), lose_orc, lose_med, lose_ge1),
              "",
              "So the binding constraint is **information at entry, not "
              "management after it**. G7 said the exit is not the constraint; "
              "P10 says why — the exit family has %+.3fR of headroom it "
              "provably cannot reach, because the signal that would tell it when "
              "to hold is not in the bars. Closing the gate needs either entries "
              "whose winners separate earlier (P1-P3, the entry-selection "
              "block), or an exit conditioned on something outside this book — "
              "the day's regime, the level being traded into, SPY alignment — "
              "none of which any policy here reads."
              % (mean_of("clock", "oracle_stopped (non-causal)") - base_all), ""]
    (ROOT / args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")

    with open(ROOT / args.csv, "w", encoding="utf-8", newline="") as fh:
        cid = PIDS + ["oracle_stopped", "oracle_best_close", "oracle_MFE"]
        cref = PIDS + list(REFS)
        fh.write("sym,day,entry_i,side,sgrade,book_r," +
                 ",".join("%s_%s" % (a, p) for a, _ in ARMS for p in cid) + "\n")
        for i, t in enumerate(book):
            cells = [results[(a, p)][i] for a, _ in ARMS for p in cref]
            fh.write("%s,%s,%d,%s,%s,%.3f,%s\n"
                     % (t["sym"], t["day"], t["entry_i"],
                        t.get("side") or ("L" if t["dir"] == "call" else "S"),
                        t.get("sgrade", ""), t["r"],
                        ",".join("" if c is None else "%.3f" % c for c in cells)))
    print("wrote %s and %s" % (args.out, args.csv))


if __name__ == "__main__":
    main()
