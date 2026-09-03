"""G7.1 / drawdown — what the GRAPH actually shows, in pixels.

Austin: "you say max drawdown is not an issue but i still see it in the graph."

g71_drawdown_audit.py answers "how deep". This answers "why does it look like
that". The equity <svg> in research/build_bt2y_report.py:506 is 720x260 with a
34px pad, y auto-scaled to [min(0,min eq), max(0,max eq)], x = TRADE INDEX (not
time). So this reproduces the exact pixel geometry and reports:

  * how many pixels deep each drawdown episode actually draws,
  * the longest UNDER-WATER stretch (time, not depth — a long flat run reads to
    the eye as "drawdown" even when the depth is trivial),
  * per-month R, since the months panel is the other chart on the page,
  * and the same numbers under the filters a person is most likely to click,
    because filtering shrinks the curve and blows the dip up proportionally.

Read-only. No engine file touched.

Usage: python research/g71_drawdown_visual.py
"""
from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RISK = 1000.0

# geometry copied from build_bt2y_report.py:507-512
W, H, P = 720, 260, 34
PLOT_H = H - P - 14          # usable pixel height of the plot area


def usd(x):
    return ("-$" if x < 0 else "$") + format(abs(x), ",.0f")


def curve(rs):
    eq, out = 0.0, []
    for r in rs:
        eq += r
        out.append(eq)
    return out


def episodes(eq):
    """(depth, peak_i, trough_i, rec_i) for every peak-to-trough episode."""
    eps = []
    peak_v, peak_i = 0.0, -1
    tro_v, tro_i = 0.0, -1
    live = False
    for i, v in enumerate(eq):
        if v >= peak_v:
            if live:
                eps.append((peak_v - tro_v, peak_i, tro_i, i))
                live = False
            peak_v, peak_i = v, i
            tro_v, tro_i = v, i
        else:
            if not live or v < tro_v:
                tro_v, tro_i = v, i
            live = True
    if live:
        eps.append((peak_v - tro_v, peak_i, tro_i, None))
    return eps


def px_per_r(eq):
    mn, mx = min(0.0, min(eq)), max(0.0, max(eq))
    if mx == mn:
        mx = mn + 1
    return PLOT_H / (mx - mn), mn, mx


def report(name, tr):
    rs = [t["r"] for t in tr]
    if not rs:
        print("  %s: empty" % name)
        return
    eq = curve(rs)
    scale, mn, mx = px_per_r(eq)
    eps = sorted(episodes(eq), key=lambda e: -e[0])
    days = sorted({t["day"] for t in tr})
    d0 = eps[0]
    # longest under-water stretch, in trades and in sessions
    longest = max(eps, key=lambda e: ((e[3] if e[3] is not None else len(eq)) - e[1]))
    lo_end = longest[3] if longest[3] is not None else len(eq) - 1
    dl = sorted({t["day"] for t in tr[max(0, longest[1]):lo_end + 1]})
    print("  %-34s n=%-5d totalR=%+9.1f  y-range %.0f..%.0fR  %.3f px/R"
          % (name, len(rs), sum(rs), mn, mx, scale))
    print("      maxDD %6.2fR = %-9s = %5.1f px  (%.2f%% of the plot height)"
          % (d0[0], usd(d0[0] * RISK), d0[0] * scale, 100 * d0[0] * scale / PLOT_H))
    print("      longest under water: %d trades / %d sessions (%s .. %s), depth %.2fR"
          % (lo_end - longest[1], len(dl), dl[0] if dl else "?",
             dl[-1] if dl else "?", longest[0]))


def main():
    d = json.loads((ROOT / "research/bt2y_trades.json").read_text(encoding="utf-8"))
    meta = d["meta"]
    all_tr = [t for t in d["trades"] if t.get("traded")]
    all_tr.sort(key=lambda t: (t["day"], t["et"]))

    print("=" * 78)
    print("EQUITY CHART GEOMETRY  (build_bt2y_report.py:506 drawEquity)")
    print("  svg %dx%d, pad %d -> %d px of plot height; x = trade index, not time"
          % (W, H, P, PLOT_H))
    print("  book %s  (%d traded)" % (meta["generated"], meta["traded"]))
    print()
    print("== THE DEFAULT VIEW (what the page opens on) ==")
    report("book = traded  [DEFAULT]", all_tr)

    print()
    print("== THE SAME CURVE UNDER FILTERS A PERSON ACTUALLY CLICKS ==")
    views = [
        ("year = 2024", lambda t: t["yr"] == "2024"),
        ("year = 2025", lambda t: t["yr"] == "2025"),
        ("year = 2026", lambda t: t["yr"] == "2026"),
        ("setup = one_candle_rule", lambda t: t["setup"] == "one_candle_rule"),
        ("Austin grade = S", lambda t: t["sgrade"] == "S"),
        ("Austin grade = C", lambda t: t["sgrade"] == "C"),
        ("engine grade = A", lambda t: t["grade"] == "A"),
        ("symbol = TSLA", lambda t: t["sym"] == "TSLA"),
        ("symbol = IREN", lambda t: t["sym"] == "IREN"),
        ("symbol = QQQ", lambda t: t["sym"] == "QQQ"),
        ("class = etf (index)", lambda t: t["cls"] == "etf"),
        ("vs HTF bias = counter", lambda t: t["aligned"] == "counter"),
    ]
    for lab, f in views:
        report(lab, [t for t in all_tr if f(t)])

    # ---- monthly panel
    print()
    print("== MONTHS PANEL (build_bt2y_report.py:559 drawMonths) ==")
    bym = OrderedDict()
    for t in all_tr:
        bym[t["ym"]] = bym.get(t["ym"], 0.0) + t["r"]
    months = sorted(bym)
    green = sum(1 for m in months if bym[m] > 0)
    print("  %d months, %d green (%.0f%%), worst %s %+.2fR, best %s %+.2fR"
          % (len(months), green, 100 * green / len(months),
             min(months, key=lambda m: bym[m]), min(bym.values()),
             max(months, key=lambda m: bym[m]), max(bym.values())))
    print("  every month:")
    for m in months:
        bar = "#" * max(1, int(abs(bym[m]) / 5))
        print("    %s %+8.2fR %-10s %s" % (m, bym[m], usd(bym[m] * RISK), bar))

    # ---- rolling underwater profile at day level
    byd = OrderedDict()
    for t in all_tr:
        byd[t["day"]] = byd.get(t["day"], 0.0) + t["r"]
    days = list(byd)
    eqd = curve([byd[x] for x in days])
    peak, uw, runs = 0.0, 0, []
    for i, v in enumerate(eqd):
        if v >= peak:
            peak = v
            if uw:
                runs.append(uw)
            uw = 0
        else:
            uw += 1
    if uw:
        runs.append(uw)
    runs.sort(reverse=True)
    frac = sum(1 for i, v in enumerate(eqd)
               if v < max(eqd[:i + 1])) / len(eqd)
    print()
    print("== TIME UNDER WATER (EOD equity) ==")
    print("  %.1f%% of the %d trading sessions closed below a prior peak"
          % (100 * frac, len(days)))
    print("  longest under-water runs (sessions): %s" % runs[:8])


if __name__ == "__main__":
    main()
