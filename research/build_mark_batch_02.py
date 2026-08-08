"""Build research/mark_batch_02.html — the next marking batch for Austin to grade.

omen-3.7 T7. Austin's labelled corpus is 159 marks and every effect measured on
it is underpowered; growing it is the highest-value thing he can do, so this
script renders the next batch ready to grade with zero setup on his end.

The batch is 60 charts:

  * every S mark whose `miss_reason` is not `detected` (the engine is blind
    here; his grade on the same bar is the label that teaches it), up to 40,
    most recent first — read from research/miss_autopsy.jsonl.
  * filled to 60 with engine entries on marked days that Austin did NOT mark
    (the false positives; his X on them is worth as much as his S) — read from
    research/engine_entries.jsonl.

It reuses build_review_artifact.py's template and level-colouring verbatim and
changes only the data source. Bars come from data_archive/<SYMBOL>/<DAY>.csv,
windowed to ~40 bars before and 30 after `entry_i`, with the entry bar marked.
Levels are coloured by type — premarket (PMH/PML), prior-day (PDH/PDL),
opening-range (ORH/ORL) — reconstructed exactly as t4_engine_recall feeds the
engine (PMH/PML = 04:00-09:29 same day, PDH/PDL = prior archived day's RTH,
ORH/ORL = first 5 RTH candles).

Each card carries symbol, date, time-of-day from `entry_i`, and — for the S
misses — the `miss_reason`. Austin's existing tier is NOT printed (grades must
be blind or they are worthless as labels); the engine's own B/C grade is
withheld for the same reason.

Run: python research/build_mark_batch_02.py
"""
from __future__ import annotations
import csv, html as _html, json, os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ARCHIVE = ROOT / "data_archive"

import levels  # research/levels.py — load_rth_bars, _prior_day (same dir)


def _to_min(dtstr: str) -> str:
    return dtstr[11:16]


def raw_rows(symbol: str, day: str):
    p = ARCHIVE / symbol / f"{day}.csv"
    if not p.exists():
        return None
    return list(csv.DictReader(open(p)))


def premarket_extremes(symbol: str, day: str):
    """PMH/PML: high/low of 04:00-09:29 extended-hours bars (t4_engine_recall)."""
    rows = raw_rows(symbol, day)
    if not rows:
        return (None, None)
    pm = [r for r in rows if "04:00" <= _to_min(r["Datetime"]) < "09:30"]
    if not pm:
        return (None, None)
    return (max(float(r["High"]) for r in pm), min(float(r["Low"]) for r in pm))


def prior_day_levels(symbol: str, day: str):
    """PDH/PDL from the prior archived trading day's RTH bars."""
    prev = levels._prior_day(symbol, day)
    if not prev:
        return (None, None)
    bars = levels.load_rth_bars(symbol, prev)
    if not bars:
        return (None, None)
    return (max(b["h"] for b in bars), min(b["l"] for b in bars))


def build_levels(symbol: str, day: str, rth):
    pmh, pml = premarket_extremes(symbol, day)
    pdh, pdl = prior_day_levels(symbol, day)
    orh = max(b["h"] for b in rth[:5]) if len(rth) >= 1 else None
    orl = min(b["l"] for b in rth[:5]) if len(rth) >= 1 else None
    return {k: round(v, 4) for k, v in [("PMH", pmh), ("PML", pml),
                                        ("PDH", pdh), ("PDL", pdl),
                                        ("ORH", orh), ("ORL", orl)]
            if v is not None}


def window_candles(rth, entry_i, before=40, after=30):
    """~`before` bars before and `after` after the entry bar; entry bar included."""
    s = max(0, entry_i - before)
    e = min(len(rth), entry_i + after + 1)
    cs = [{"t": b["t"], "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"]}
          for b in rth[s:e]]
    return cs, entry_i - s


# ---- select the 60 cards -----------------------------------------------------

ma = [json.loads(l) for l in open(HERE / "miss_autopsy.jsonl")]
austin_marks = [json.loads(l) for l in open(HERE / "austin_marks_v2.jsonl")]
mark_keys = {(m["symbol"], m["day"], m["entry_i"]) for m in austin_marks}
day_keys = {(m["symbol"], m["day"]) for m in austin_marks}

# (1) S misses: miss_reason != 'detected', most recent first, up to 40.
s_misses = [r for r in ma
            if r["tier"] == "S" and r["miss_reason"] != "detected"]
s_misses.sort(key=lambda r: r["day"], reverse=True)
s_misses = s_misses[:40]

# (2) Engine false positives: on a marked day, at a bar Austin did NOT mark.
eng = [json.loads(l) for l in open(HERE / "engine_entries.jsonl")]
seen, engine_fps = set(), []
for e in eng:
    k = (e["symbol"], e["day"], e["bar"])
    if k in seen:
        continue
    seen.add(k)
    if k in mark_keys:          # Austin marked this exact bar -> not a false positive
        continue
    if (e["symbol"], e["day"]) not in day_keys:  # not a marked day
        continue
    engine_fps.append(e)

need = 60 - len(s_misses)
engine_fps = engine_fps[:need]

cards = []
for r in s_misses:
    rth = levels.load_rth_bars(r["symbol"], r["day"])
    cs, eIdx = window_candles(rth, r["entry_i"])
    entry = round(rth[r["entry_i"]]["c"], 4)   # "we enter at its close"
    cards.append({
        "kind": "s_miss",
        "symbol": r["symbol"], "day": r["day"],
        "tod": rth[r["entry_i"]]["t"],
        "entry_i": eIdx,
        "miss_reason": r["miss_reason"],
        "detail": r["detail"],
        "entry": entry, "stop": None, "target": None,
        "levels": build_levels(r["symbol"], r["day"], rth),
        "candles": cs,
    })

for e in engine_fps:
    rth = levels.load_rth_bars(e["symbol"], e["day"])
    cs, eIdx = window_candles(rth, e["bar"])
    risk = abs(e["entry"] - e["stop"])
    target = e["entry"] + 2 * risk if e["direction"] == "call" else e["entry"] - 2 * risk
    cards.append({
        "kind": "engine_fp",
        "symbol": e["symbol"], "day": e["day"],
        "tod": rth[e["bar"]]["t"],
        "entry_i": eIdx,
        "miss_reason": None,
        "direction": e["direction"],
        "signal_type": e["signal_type"],
        "stop_level": e["stop_level"],
        "detail": f"engine {e['signal_type']} · {e['direction']} · stop ref {e['stop_level']}",
        "entry": round(e["entry"], 4),
        "stop": round(e["stop"], 4),
        "target": round(target, 4),
        "levels": build_levels(e["symbol"], e["day"], rth),
        "candles": cs,
    })

DATA = json.dumps(cards).replace("</", "<\\/")  # safe inside <script>: no "</script>"
S_MISS_N = len(s_misses)
FP_N = len(engine_fps)
assert S_MISS_N + FP_N == 60, f"expected 60 cards, got {S_MISS_N}+{FP_N}"


def _esc(s):
    return _html.escape(str(s), quote=True)


def card_html(t):
    """One STATIC card div (its <canvas> is drawn onto client-side, by index).

    The cards are emitted into the HTML source — not built by JS — so the file
    embeds exactly 60 chart cards no matter how it is inspected. No tier is
    printed: S-miss cards show only the miss_reason (why the engine was blind),
    engine-fp cards show only the engine's own signal — never Austin's prior
    S/A/X. Text is HTML-escaped because some autopsy details contain '<'
    (e.g. 'risk < $0.671'), and they are now static markup, not JS-injected."""
    if t["kind"] == "s_miss":
        subtitle = "miss · " + t["miss_reason"]
        why_cls, why = "why", "miss_reason: " + t["miss_reason"]
    else:
        subtitle = "engine entry · " + t["direction"]
        why_cls = "why fp"
        why = (f"engine {t['signal_type']} · {t['direction']} · "
               f"stop {t['stop_level']}")
    return (
        '<div class="card">'
        '<div class="ch"><div class="ttl">' + _esc(t["day"]) + ' ' + _esc(t["symbol"]) +
        ' <span class="sub">· ' + _esc(t["tod"]) + ' · ' + _esc(subtitle) +
        '</span></div></div>'
        '<canvas></canvas>'
        '<div class="' + why_cls + '">' + _esc(why) + '</div>'
        '<div class="rz">' + _esc(t["detail"]) + '</div>'
        '<div class="ask">Grade this bar: S / A / X</div>'
        '</div>'
    )


CARDS_HTML = "\n".join(card_html(t) for t in cards)

# ---- template (reused from build_review_artifact.py; data source changed) ----

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OMEN mark batch 02 — grade blind</title>
<style>
  :root{
    --bg:#0d1117; --panel:#141b24; --edge:#243040; --ink:#e6edf3; --dim:#8b98a8;
    --up:#26a69a; --down:#ef5350;
    --pm:#fbbf24;   /* premarket high/low  */
    --pd:#a78bfa;   /* previous day high/low */
    --or:#38bdf8;   /* opening-range high/low */
    --entry:#f4f7fb; --stop:#f87171; --tgt:#4ade80;
    --mono:ui-monospace,"SFMono-Regular","JetBrains Mono",Menlo,Consolas,monospace;
    --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  }
  *{box-sizing:border-box}
  .wrap{background:var(--bg);color:var(--ink);font-family:var(--sans);
        padding:28px 22px 60px;min-height:100vh}
  .head{max-width:1200px;margin:0 auto 22px}
  h1{font-size:22px;font-weight:650;letter-spacing:-.01em;margin:0 0 6px;text-wrap:balance}
  .stat{font-family:var(--mono);font-size:13px;color:var(--dim);line-height:1.7}
  .stat b{color:var(--ink);font-variant-numeric:tabular-nums}
  .legend{display:flex;flex-wrap:wrap;gap:14px 20px;margin:16px 0 0;
          font-family:var(--mono);font-size:11px;color:var(--dim)}
  .legend span{display:inline-flex;align-items:center;gap:6px}
  .sw{width:16px;height:0;border-top-width:2px;border-top-style:solid;display:inline-block}
  .dot{width:9px;height:9px;border-radius:2px;display:inline-block}
  .grid{max-width:1240px;margin:0 auto;display:grid;
        grid-template-columns:repeat(auto-fill,minmax(560px,1fr));gap:18px}
  .card{background:var(--panel);border:1px solid var(--edge);border-radius:10px;
        padding:12px 12px 10px;display:flex;flex-direction:column;gap:8px}
  .ch{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
  .ttl{font-family:var(--mono);font-size:12px;font-weight:600}
  .ttl .sub{color:var(--dim);font-weight:400}
  canvas{width:100%;height:auto;display:block;border-radius:6px;background:#0b1017}
  .why{font-family:var(--mono);font-size:11px;color:var(--pm)}
  .why.fp{color:var(--or)}
  .rz{font-size:11px;color:var(--dim);line-height:1.4}
  .ask{font-family:var(--mono);font-size:11px;color:var(--tgt);
       border-top:1px dashed var(--edge);padding-top:7px;margin-top:1px}
</style>
</head>
<body>
<div class="wrap">
  <div class="head">
    <h1>OMEN mark batch 02 — grade these 60 bars blind</h1>
    <div class="stat">__STAT__</div>
    <div class="legend">
      <span><i class="sw" style="border-top-color:var(--entry)"></i>entry (candle close)</span>
      <span><i class="sw" style="border-top-color:var(--stop)"></i>stop</span>
      <span><i class="sw" style="border-top-color:var(--tgt)"></i>2R target</span>
      <span><i class="sw" style="border-top-color:var(--pm);border-top-style:dashed"></i>premarket H/L</span>
      <span><i class="sw" style="border-top-color:var(--pd);border-top-style:dashed"></i>prev-day H/L</span>
      <span><i class="sw" style="border-top-color:var(--or);border-top-style:dashed"></i>opening-range H/L</span>
      <span><i class="dot" style="background:var(--up)"></i>up <i class="dot" style="background:var(--down)"></i>down · <b style="color:var(--entry)">▲</b> entry bar</span>
    </div>
  </div>
  <div class="grid" id="grid">__CARDS__</div>
</div>
<script>
const DATA = __DATA__;
const LVLCOL = {PMH:'#fbbf24',PML:'#fbbf24',PDH:'#a78bfa',PDL:'#a78bfa',ORH:'#38bdf8',ORL:'#38bdf8'};
const CW=560, CH=340, PL=8, PR=58, PT=16, PB=22;

function draw(cv, t){
  const dpr = window.devicePixelRatio||1;
  cv.width = CW*dpr; cv.height = CH*dpr; cv.style.aspectRatio = CW+'/'+CH;
  const g = cv.getContext('2d'); g.scale(dpr,dpr);
  const cs = t.candles;           // already windowed ~40 before / 30 after
  const eIdx = t.entry_i;
  let lo=Infinity, hi=-Infinity;
  for(const c of cs){ lo=Math.min(lo,c.l); hi=Math.max(hi,c.h); }
  for(const k in t.levels){ lo=Math.min(lo,t.levels[k]); hi=Math.max(hi,t.levels[k]); }
  if(t.entry!=null){ lo=Math.min(lo,t.entry); hi=Math.max(hi,t.entry); }
  if(t.stop!=null){ lo=Math.min(lo,t.stop); hi=Math.max(hi,t.stop); }
  if(t.target!=null){ lo=Math.min(lo,t.target); hi=Math.max(hi,t.target); }
  const pad=(hi-lo)*0.06||1; lo-=pad; hi+=pad;
  const y=p=>PT+(hi-p)/(hi-lo)*(CH-PT-PB);
  const n=cs.length, cw=(CW-PL-PR)/n, x=i=>PL+i*cw+cw/2;

  // structure levels (dashed, colored by type, label at right)
  g.font='9px ui-monospace,monospace'; g.textBaseline='middle';
  g.setLineDash([3,3]); g.lineWidth=1;
  for(const k in t.levels){ const yy=y(t.levels[k]);
    g.strokeStyle=LVLCOL[k]||'#889'; g.beginPath(); g.moveTo(PL,yy); g.lineTo(CW-PR,yy); g.stroke();
    g.fillStyle=LVLCOL[k]||'#889'; g.textAlign='left'; g.fillText(k, CW-PR+3, yy);
  }
  // entry / stop / target (solid, label at right) — only when present
  g.setLineDash([]);
  [['entry',t.entry,'#f4f7fb'],['stop',t.stop,'#f87171'],['2R',t.target,'#4ade80']]
    .filter(([_,p])=>p!=null).forEach(([lab,p,col])=>{
      const yy=y(p); g.strokeStyle=col; g.lineWidth=1; g.beginPath(); g.moveTo(PL,yy); g.lineTo(CW-PR,yy); g.stroke();
      g.fillStyle=col; g.textAlign='left'; g.fillText(lab+' '+p.toFixed(2), CW-PR+3, yy);
    });
  // entry-bar vertical guide
  const ex=x(eIdx);
  g.strokeStyle='rgba(244,247,251,.28)'; g.setLineDash([2,3]); g.lineWidth=1;
  g.beginPath(); g.moveTo(ex,PT); g.lineTo(ex,CH-PB); g.stroke(); g.setLineDash([]);
  // candles
  for(let i=0;i<n;i++){ const c=cs[i], up=c.c>=c.o, col=up?'#26a69a':'#ef5350', xx=x(i);
    g.strokeStyle=col; g.lineWidth=1; g.beginPath(); g.moveTo(xx,y(c.h)); g.lineTo(xx,y(c.l)); g.stroke();
    const yo=y(c.o), yc=y(c.c), top=Math.min(yo,yc), h=Math.max(Math.abs(yc-yo),1);
    g.fillStyle=col; g.fillRect(xx-cw*0.34, top, Math.max(cw*0.68,1), h);
    if(i===eIdx){ g.strokeStyle='#f4f7fb'; g.lineWidth=1.4;
      g.strokeRect(xx-cw*0.34-1.5, top-1.5, Math.max(cw*0.68,1)+3, h+3); }
  }
  // entry arrow under the entry bar
  g.fillStyle='#f4f7fb'; g.beginPath();
  g.moveTo(ex,CH-PB+2); g.lineTo(ex-4,CH-PB+9); g.lineTo(ex+4,CH-PB+9); g.closePath(); g.fill();
  // minute labels every 5 bars
  g.fillStyle='#5b6675'; g.font='8px ui-monospace,monospace'; g.textBaseline='alphabetic';
  g.textAlign='center';
  for(let i=0;i<n;i+=5){ g.fillText(cs[i].t.slice(3), x(i), CH-6); }
  g.textAlign='right'; g.fillText(cs[n-1].t, CW-PR+42, CH-6);
}

// Cards are emitted statically (one card div + canvas per entry, 60 total) so
// the document embeds exactly 60 chart cards. JS only paints each pre-existing
// canvas, by index, from the embedded DATA.
const canvases = document.querySelectorAll('.grid canvas');
canvases.forEach((cv, i) => { if (DATA[i]) draw(cv, DATA[i]); });
</script>
</body>
</html>
"""

STAT = (f"<b>60 cards</b> — {S_MISS_N} S-miss bars (engine was blind; miss_reason != "
        f"'detected', most recent first) + {FP_N} unmarked engine entries (false "
        f"positives: engine fired on a marked day at a bar Austin did not mark). "
        f"Graded blind — no existing tier or engine grade shown. "
        f"Return one grade per card: S / A / X.")

out = HERE / "mark_batch_02.html"
out.write_text(
    TEMPLATE.replace("__DATA__", DATA)
            .replace("__STAT__", STAT)
            .replace("__CARDS__", CARDS_HTML),
    encoding="utf-8")
print(f"wrote {out} with {len(cards)} cards "
      f"({S_MISS_N} S-miss + {FP_N} engine-fp)")
