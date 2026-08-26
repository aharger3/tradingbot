"""probe_chart.py -- static SVG candle charts for the OMEN 6 elicitation probes.

Why static and not the deck's canvas renderer: these instruments ship as claude.ai
Artifacts with the `artifact` capability, which is a LIVE DOC -- only markup that is
IN the served HTML is the document, and only DOM changes made by a viewer gesture are
saved. A chart painted by JS on load is not part of the document. So the chart is
rendered to SVG here, in Python, and the page ships it as markup.

Also: no chart-click interaction. Austin's homework contract (OMEN 6 map, 2026-08-22)
requires these work on a phone, and entry-marking by pointer does not.
"""
from __future__ import annotations

W, H = 720, 330
PAD_L, PAD_R, PAD_T, PAD_B = 4, 56, 10, 24

LEVELS = [
    ("pdh", "PDH", "lvl-pd"), ("pdl", "PDL", "lvl-pd"),
    ("pmh", "PMH", "lvl-pm"), ("pml", "PML", "lvl-pm"),
    ("orh", "ORH", "lvl-or"), ("orl", "ORL", "lvl-or"),
]


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def render(candles, levels, marks=None, label="", interactive=False):
    """candles: [{t,o,h,l,c,v}]  levels: {pdh:..}  marks: [{i,price,stop,side,tag}]

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
    """
    marks = marks or []
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
    if interactive:
        scale = (' data-n="%d" data-padl="%d" data-padt="%d" data-plotw="%.2f"'
                 ' data-ploth="%.2f" data-lo="%.4f" data-hi="%.4f" data-w="%d"'
                 % (n, PAD_L, PAD_T, plot_w, plot_h, lo, hi, W))
    out = ['<svg class="chart" viewBox="0 0 %d %d" role="img" aria-label="%s" '
           'preserveAspectRatio="xMidYMid meet"%s>'
           % (W, H, _esc(label or "session chart"), scale)]

    # session grid: a faint line every 15 bars, i.e. every 15 minutes
    for i in range(0, n, 15):
        out.append('<line class="grid" x1="%.1f" y1="%d" x2="%.1f" y2="%.1f"/>'
                   % (x(i), PAD_T, x(i), PAD_T + plot_h))
        t = candles[i]["t"][11:16] if "T" in candles[i]["t"] else candles[i]["t"][:5]
        out.append('<text class="axis" x="%.1f" y="%.1f">%s</text>'
                   % (x(i), H - 8, _esc(t)))

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
    out.append("</svg>")
    return "".join(out)
