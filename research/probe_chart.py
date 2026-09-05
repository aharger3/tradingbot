"""probe_chart.py -- static SVG candle charts for the OMEN 6 elicitation probes.

Why static and not the deck's canvas renderer: these instruments ship as claude.ai
Artifacts with the `artifact` capability, which is a LIVE DOC -- only markup that is
IN the served HTML is the document, and only DOM changes made by a viewer gesture are
saved. A chart painted by JS on load is not part of the document. So the chart is
rendered to SVG here, in Python, and the page ships it as markup.

Chart-click interaction (H2, 2026-09-05): `tappable=True` adds pointer/touch tap
marking directly on the served SVG -- entry, stop and up to three price targets --
for decks where a chip-based capture (OMEN Test 1's block+minute chips) is the
wrong shape for the question. The 2026-08-22 note above ("entry-marking by
pointer does not work on a phone") was about `<canvas>`-style drag interaction;
plain `pointerdown` on markup that is already in the served SVG works fine on a
phone and is what `tappable` uses. It stays off by default so every existing
caller's SVG is byte-identical.
"""
from __future__ import annotations

import json

W, H = 720, 330
PAD_L, PAD_R, PAD_T, PAD_B = 4, 56, 10, 24

# G7.2 (2026-08-29): HOD/LOD added. Austin named his six levels the same day --
# PDH, PDL, PMH, PML, HOD, LOD -- and this renderer could not draw two of them,
# so every card built on it was silently missing the level the engine misses most
# (HOD, 413 symbol-days). ORH/ORL stay in the table because other pages draw the
# opening range; a caller that does not want a level simply omits its key from
# the `levels` dict, so every existing caller's SVG is byte-identical.
#
# NOT to be confused with downgrade.CONFLUENCE_LEVELS = (PDH, PDL, PMH, PML, ORH,
# ORL). That is a different set for a different job -- the confluence tally, which
# uses only levels fixed at or before the open so it cannot leak hindsight
# (research/p18_p19_new_variables.md:53). Two sets, two jobs. Never merge them.
#
# HOD/LOD are RUNNING levels: the caller owns the anchor and must pass a value
# computed from bars that had already closed, never from the whole session.
LEVELS = [
    ("pdh", "PDH", "lvl-pd"), ("pdl", "PDL", "lvl-pd"),
    ("pmh", "PMH", "lvl-pm"), ("pml", "PML", "lvl-pm"),
    ("orh", "ORH", "lvl-or"), ("orl", "ORL", "lvl-or"),
    ("hod", "HOD", "lvl-hl"), ("lod", "LOD", "lvl-hl"),
]


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def render(candles, levels, marks=None, label="", interactive=False,
           hlines=None, vlines=None, dots=None, xfmt=None, tappable=False):
    """candles: [{t,o,h,l,c,v}]  levels: {pdh:..}  marks: [{i,price,stop,side,tag}]

    ``hlines`` / ``vlines`` (H2 three-lane deck, 2026-08-28) are optional
    overlays that carry no market semantics of their own: a horizontal price
    rail (the give-back lane's 2R target) and a vertical bar marker (the 11:00
    clock step). They default to empty, so every existing caller gets byte-
    identical SVG. Shape:

        hlines = [{"price": 128.44, "label": "2R", "cls": "tgt"}]
        vlines = [{"i": 90, "label": "11:00", "cls": "clk"}]

    The page owns the colours via ``.chart .tgt`` / ``.chart .clk``. An hline may
    also carry ``"at": bar_index``, which moves its label off the right-hand
    gutter and onto the plot above that bar -- four labelled candidate stop lines
    on one chart collide in the gutter and read fine when they are spread out.

    ``dots`` (master homework, 2026-08-30) marks a bar with a small labelled
    circle and NOTHING else -- no price rail, no arrow, no stop. It exists for
    the questions that must point at a bar without telling him where the entry
    or the stop goes: "which of these two setups is the trade" and "does the
    higher timeframe agree with this one". Shape:

        dots = [{"i": 14, "price": 128.44, "label": "A"}]

    ``xfmt`` overrides the x-axis label. The default reads a clock out of a
    1-minute timestamp; a daily chart needs its date instead, and passing
    ``xfmt=lambda t: t[5:10]`` gives ``09-08``. Both default to off, so every
    existing caller's SVG is byte-identical.

    ``interactive=True`` (OMEN Test 1) adds two things and changes nothing else:

    * the plot's own scale, as data-* attributes on the <svg>, so a page can map
      a bar index to an x and a price to a y without re-deriving the framing;
    * an empty ``<g class="usermark">`` holding placeholder entry/stop lines the
      page positions when Austin taps. The chart stays static SVG rendered here
      in Python -- the page only moves elements that are already in the markup,
      which is what keeps it phone-safe and pointer-free.

    The frame (lo/hi) is computed from the bars and the levels, so a mark placed
    later can fall outside it. The page clamps rather than rescaling: rescaling
    would move every candle under his finger mid-tap.

    ``tappable=True`` (H2, 2026-09-05) is the pointer-driven sibling of
    ``interactive``: it emits the same scale attributes (so it also sets
    ``data-w``/``data-h``, needed either way), plus ``data-ohlc`` -- a compact
    JSON array of ``[o,h,l,c]`` per bar, which is how the page turns a stop tap
    on a candle into "that candle's extreme in the trade direction" without a
    second fetch -- a transparent ``<rect class="taphit">`` over the plot and a
    ``<rect class="railhit">`` over the price-rail gutter to catch taps, and a
    ``<g class="tapmark">`` of hidden entry/stop/PT1-3 placeholders the page
    moves. Nothing here decides what a tap means; that state machine lives in
    probe_page.py so every tappable chart shares it.
    """
    marks = marks or []
    hlines = hlines or []
    vlines = vlines or []
    dots = dots or []
    n = len(candles)
    if not n:
        return '<div class="chart-missing">no bars</div>'

    lo = min(c["l"] for c in candles)
    hi = max(c["h"] for c in candles)
    for k, _lab, _cls in LEVELS:
        v = levels.get(k)
        # A level far off-screen would flatten the candles into a ribbon. Only let a
        # level widen the frame by a quarter of the session's own range.
        if v is not None and lo - (hi - lo) * 0.25 <= v <= hi + (hi - lo) * 0.25:
            lo, hi = min(lo, v), max(hi, v)
    for m in marks:
        for v in (m.get("price"), m.get("stop")):
            if v is not None:
                lo, hi = min(lo, v), max(hi, v)
    for h in hlines:
        # A 2R rail the tape never reached still has to be ON the chart, or the
        # card asks him to judge a target he cannot see. Same for a candidate
        # stop that sits under the session low.
        if h.get("price") is not None:
            lo, hi = min(lo, h["price"]), max(hi, h["price"])
    for d in dots:
        if d.get("price") is not None:
            lo, hi = min(lo, d["price"]), max(hi, d["price"])
    span = (hi - lo) or 1.0
    lo -= span * 0.04
    hi += span * 0.04
    span = hi - lo

    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    def x(i):
        return PAD_L + (i + 0.5) * plot_w / n

    def y(p):
        return PAD_T + (hi - p) * plot_h / span

    bw = max(1.6, plot_w / n * 0.62)
    scale = ""
    if interactive or tappable:
        scale = (' data-n="%d" data-padl="%d" data-padt="%d" data-plotw="%.2f"'
                 ' data-ploth="%.2f" data-lo="%.4f" data-hi="%.4f" data-w="%d"'
                 ' data-h="%d"'
                 % (n, PAD_L, PAD_T, plot_w, plot_h, lo, hi, W, H))
    if tappable:
        ohlc = [[round(c["o"], 4), round(c["h"], 4), round(c["l"], 4), round(c["c"], 4)]
                for c in candles]
        scale += ' data-ohlc="%s"' % _esc(json.dumps(ohlc, separators=(",", ":")))
        scale += ' data-tappable="1"'
    out = ['<svg class="chart" viewBox="0 0 %d %d" role="img" aria-label="%s" '
           'preserveAspectRatio="xMidYMid meet"%s>'
           % (W, H, _esc(label or "session chart"), scale)]

    # session grid: a faint line every 15 bars, i.e. every 15 minutes
    for i in range(0, n, 15):
        out.append('<line class="grid" x1="%.1f" y1="%d" x2="%.1f" y2="%.1f"/>'
                   % (x(i), PAD_T, x(i), PAD_T + plot_h))
        raw = candles[i]["t"]
        t = xfmt(raw) if xfmt else (raw[11:16] if "T" in raw else raw[:5])
        out.append('<text class="axis" x="%.1f" y="%.1f">%s</text>'
                   % (x(i), H - 8, _esc(t)))

    for vl in vlines:
        i = vl.get("i")
        if i is None or not (0 <= i < n):
            continue
        out.append('<line class="vmark %s" x1="%.1f" y1="%d" x2="%.1f" y2="%.1f"/>'
                   % (_esc(vl.get("cls", "")), x(i), PAD_T, x(i), PAD_T + plot_h))
        if vl.get("label"):
            out.append('<text class="vmark-t %s" x="%.1f" y="%d">%s</text>'
                       % (_esc(vl.get("cls", "")), x(i), PAD_T + 9,
                          _esc(vl["label"])))

    for k, lab, cls in LEVELS:
        v = levels.get(k)
        if v is None or not (lo <= v <= hi):
            continue
        yy = y(v)
        out.append('<line class="lvl %s" x1="%d" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                   % (cls, PAD_L, yy, PAD_L + plot_w, yy))
        out.append('<text class="lvl-t %s" x="%.1f" y="%.1f">%s %.2f</text>'
                   % (cls, PAD_L + plot_w + 4, yy + 3.4, lab, v))

    for i, c in enumerate(candles):
        up = c["c"] >= c["o"]
        cls = "up" if up else "dn"
        cx = x(i)
        out.append('<line class="wk %s" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                   % (cls, cx, y(c["h"]), cx, y(c["l"])))
        top, bot = y(max(c["o"], c["c"])), y(min(c["o"], c["c"]))
        out.append('<rect class="bd %s" x="%.1f" y="%.1f" width="%.1f" height="%.1f"/>'
                   % (cls, cx - bw / 2, top, bw, max(1.0, bot - top)))

    for h in hlines:
        p = h.get("price")
        if p is None or not (lo <= p <= hi):
            continue
        out.append('<line class="hrail %s" x1="%d" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                   % (_esc(h.get("cls", "")), PAD_L, y(p), PAD_L + plot_w, y(p)))
        at = h.get("at")
        if at is not None and 0 <= at < n:
            # Label on the plot, above the line, so several candidate lines can
            # be told apart without stacking their labels in the gutter.
            out.append('<text class="hrail-t %s" x="%.1f" y="%.1f" '
                       'text-anchor="middle">%s %.2f</text>'
                       % (_esc(h.get("cls", "")), x(at), y(p) - 4,
                          _esc(h.get("label", "")), p))
        else:
            out.append('<text class="hrail-t %s" x="%.1f" y="%.1f">%s %.2f</text>'
                       % (_esc(h.get("cls", "")), PAD_L + plot_w + 4, y(p) + 3.4,
                          _esc(h.get("label", "")), p))

    for m in marks:
        cx, p = x(m["i"]), m.get("price")
        if p is not None:
            out.append('<line class="entry" x1="%d" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                       % (PAD_L, y(p), PAD_L + plot_w, y(p)))
            out.append('<text class="entry-t" x="%.1f" y="%.1f">%s %.2f</text>'
                       % (PAD_L + plot_w + 4, y(p) + 3.4, _esc(m.get("tag", "ENT")), p))
            up = (m.get("side") or "L") == "L"
            ay = y(p) + (14 if up else -14)
            tip = y(p) + (4 if up else -4)
            out.append('<path class="arrow" d="M %.1f %.1f L %.1f %.1f L %.1f %.1f Z"/>'
                       % (cx, tip, cx - 5, ay, cx + 5, ay))
        s = m.get("stop")
        if s is not None:
            out.append('<line class="stopl" x1="%d" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                       % (PAD_L, y(s), PAD_L + plot_w, y(s)))
            out.append('<text class="stop-t" x="%.1f" y="%.1f">STOP %.2f</text>'
                       % (PAD_L + plot_w + 4, y(s) + 3.4, s))

    for d in dots:
        i, p = d.get("i"), d.get("price")
        if i is None or p is None or not (0 <= i < n):
            continue
        cx, cy = x(i), y(p)
        out.append('<circle class="dot %s" cx="%.1f" cy="%.1f" r="4.5"/>'
                   % (_esc(d.get("cls", "")), cx, cy))
        if d.get("label"):
            # Above the dot, flipped below when the dot is near the top edge, so
            # the label never falls off the plot.
            up = cy - PAD_T > 18
            out.append('<text class="dot-t %s" x="%.1f" y="%.1f" '
                       'text-anchor="middle">%s</text>'
                       % (_esc(d.get("cls", "")), cx, cy - 9 if up else cy + 15,
                          _esc(d["label"])))

    if interactive:
        # Placeholders only. Every one of these is in the served markup; the page
        # sets x/y and drops the `hidden` attribute. Nothing is created by script.
        out.append(
            '<g class="usermark">'
            '<rect class="band" x="0" y="%d" width="0" height="%.1f" hidden></rect>'
            '<line class="uentry" x1="%d" y1="0" x2="%.1f" y2="0" hidden></line>'
            '<line class="ubar" x1="0" y1="%d" x2="0" y2="%.1f" hidden></line>'
            '<text class="uentry-t" x="%.1f" y="0" hidden></text>'
            '<line class="ustop" x1="%d" y1="0" x2="%.1f" y2="0" hidden></line>'
            '<text class="ustop-t" x="%.1f" y="0" hidden></text>'
            '</g>'
            % (PAD_T, plot_h,
               PAD_L, PAD_L + plot_w,
               PAD_T, PAD_T + plot_h,
               PAD_L + plot_w + 4,
               PAD_L, PAD_L + plot_w,
               PAD_L + plot_w + 4))

    if tappable:
        # Hit areas on top of the candles/rail, transparent so nothing visual
        # changes; pointer-events="all" because an unpainted fill ("transparent",
        # same as "none") does not receive pointer events under the default
        # visiblePainted behaviour. The rail is the plot's own right gutter --
        # same y-to-price mapping as the plot, just past PAD_L + plot_w.
        out.append(
            '<rect class="taphit" x="%.1f" y="%d" width="%.1f" height="%.1f" '
            'fill="transparent" pointer-events="all"></rect>'
            '<rect class="railhit" x="%.1f" y="%d" width="%d" height="%.1f" '
            'fill="transparent" pointer-events="all"></rect>'
            '<g class="tapmark">'
            '<line class="tap-entry" x1="0" y1="0" x2="0" y2="0" hidden></line>'
            '<text class="tap-entry-t" x="0" y="0" hidden></text>'
            '<line class="tap-stop" x1="0" y1="0" x2="0" y2="0" hidden></line>'
            '<text class="tap-stop-t" x="0" y="0" hidden></text>'
            '<line class="tap-pt0" x1="0" y1="0" x2="0" y2="0" hidden></line>'
            '<text class="tap-pt0-t" x="0" y="0" hidden></text>'
            '<line class="tap-pt1" x1="0" y1="0" x2="0" y2="0" hidden></line>'
            '<text class="tap-pt1-t" x="0" y="0" hidden></text>'
            '<line class="tap-pt2" x1="0" y1="0" x2="0" y2="0" hidden></line>'
            '<text class="tap-pt2-t" x="0" y="0" hidden></text>'
            '</g>'
            % (PAD_L, PAD_T, plot_w, plot_h,
               PAD_L + plot_w, PAD_T, PAD_R, plot_h))

    out.append("</svg>")
    return "".join(out)
