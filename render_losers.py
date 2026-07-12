"""Render backtest trades as SVG candlestick charts for eyeball review.

Goal: let Austin SEE the entries the detector took, so he can mark which
break-and-retests he'd never trade. His rejections = the entry-filter label.

Picks counted losers across setups + a few winners for contrast. Each panel:
candles, entry/stop/target lines, structure levels (PDH/PDL/PMH/PML/ORH/ORL),
entry bar highlighted. Writes losers_review.html (open in browser).

Run: python render_losers.py
"""
import json
from pathlib import Path

CHARTS = Path(__file__).with_name("backtest_charts.json")
OUT = Path(__file__).with_name("losers_review.html")
W, H, PAD = 460, 240, 34  # per-panel svg


def panel(t):
    cs = t["candles"]
    if not cs:
        return ""
    lo = min(c["l"] for c in cs)
    hi = max(c["h"] for c in cs)
    for v in t["levels"].values():
        lo, hi = min(lo, v), max(hi, v)
    lo, hi = min(lo, t["stop"], t["target"]), max(hi, t["stop"], t["target"])
    rng = hi - lo or 1
    n = len(cs)
    cw = (W - 2 * PAD) / n

    def y(p):
        return PAD + (hi - p) / rng * (H - 2 * PAD)

    def x(i):
        return PAD + i * cw + cw / 2

    parts = []
    # structure levels
    for name, v in t["levels"].items():
        yy = y(v)
        parts.append(f'<line x1="{PAD}" y1="{yy:.0f}" x2="{W-PAD}" y2="{yy:.0f}" '
                     f'stroke="#888" stroke-width="0.5" stroke-dasharray="3 3"/>')
        parts.append(f'<text x="{W-PAD+1:.0f}" y="{yy+3:.0f}" font-size="8" fill="#888">{name}</text>')
    # entry / stop / target
    for p, col, lab in [(t["entry"], "#3b82f6", "entry"),
                        (t["stop"], "#ef4444", "stop"),
                        (t["target"], "#22c55e", "2R tgt")]:
        yy = y(p)
        parts.append(f'<line x1="{PAD}" y1="{yy:.0f}" x2="{W-PAD}" y2="{yy:.0f}" '
                     f'stroke="{col}" stroke-width="1"/>')
        parts.append(f'<text x="{PAD}" y="{yy-2:.0f}" font-size="8" fill="{col}">{lab} {p:.2f}</text>')
    # candles
    for i, c in enumerate(cs):
        up = c["c"] >= c["o"]
        col = "#e5e7eb" if up else "#6b7280"
        xx = x(i)
        parts.append(f'<line x1="{xx:.1f}" y1="{y(c["h"]):.1f}" x2="{xx:.1f}" y2="{y(c["l"]):.1f}" stroke="{col}" stroke-width="0.7"/>')
        yo, yc = y(c["o"]), y(c["c"])
        top, bh = min(yo, yc), abs(yc - yo) or 0.6
        parts.append(f'<rect x="{xx-cw*0.32:.1f}" y="{top:.1f}" width="{cw*0.64:.1f}" height="{bh:.1f}" fill="{col}"/>')
    # entry bar marker
    ex = x(t["entry_i"])
    parts.append(f'<line x1="{ex:.1f}" y1="{PAD}" x2="{ex:.1f}" y2="{H-PAD}" stroke="#3b82f6" stroke-width="0.5" stroke-dasharray="2 2" opacity="0.6"/>')
    return f'<svg viewBox="0 0 {W+40} {H}" width="100%">{"".join(parts)}</svg>'


def card(t):
    dirw = "LONG" if t["direction"] == "call" else "SHORT"
    oc = t["outcome"].upper()
    ocol = "#22c55e" if t["outcome"] == "win" else "#ef4444"
    return f'''<div class="card">
      <div class="hd"><b>{t["day"]} {t["symbol"]}</b> · {t["setup"]} · {t["grade"]} · {dirw}
        <span style="color:{ocol}">{oc} ${t["pnl"]:.0f}</span></div>
      <div class="rs">{t["reason"]}</div>
      {panel(t)}
      <div class="q">Would you take this entry? <b>Y / N</b> — why?</div>
    </div>'''


def main():
    d = json.load(open(CHARTS))
    counted = [t for t in d if not t["alert_only"]]
    def pick(setup, outcome, k):
        xs = [t for t in counted if t["setup"] == setup and t["outcome"] == outcome]
        xs.sort(key=lambda t: t["pnl"])  # worst first for losses
        return xs[:k]
    sel = (pick("break_and_retest", "loss", 8)
           + pick("break_and_retest", "win", 4)
           + pick("one_candle_rule", "loss", 4))

    cards = "\n".join(card(t) for t in sel)
    html = f'''<!doctype html><meta charset=utf8>
<style>
 body{{background:#111;color:#ddd;font:13px system-ui;margin:0;padding:16px}}
 h1{{font-size:18px}} .sub{{color:#999;margin-bottom:16px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(500px,1fr));gap:14px}}
 .card{{background:#1a1a1a;border:1px solid #333;border-radius:8px;padding:10px}}
 .hd{{font-size:12px;margin-bottom:2px}} .rs{{color:#888;font-size:11px;margin-bottom:4px}}
 .q{{color:#f59e0b;font-size:11px;margin-top:4px}}
</style>
<h1>OMEN entry review — which of these would YOU actually take?</h1>
<div class="sub">Blue=entry, red=stop, green=blind 2R target, gray=structure levels.
 8 break&retest losers (worst first), 4 B&R winners (contrast), 4 one-candle losers.
 81% of all losers never reached +1R — the machine's picking bad entries. Mark the ones you'd skip.</div>
<div class="grid">{cards}</div>'''
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}  ({len(sel)} trades)")


if __name__ == "__main__":
    main()
