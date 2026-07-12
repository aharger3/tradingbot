"""Build a self-contained Canvas artifact of backtest entries for eyeball review.

Austin's asks: (1) the ENTRY candle must be unmistakable (we enter at its
close), (2) levels colored by TYPE — premarket / prev-day / opening-range each
one color, (3) proper artifact. Emits review_artifact.html (body content only,
no <html>/<head>/<body> — the Artifact tool wraps it).

Run: python build_review_artifact.py
"""
import json
import re
from pathlib import Path

# 12mo snapshots (backtest_charts.json gets overwritten by longer runs)
d = json.load(open(Path(__file__).with_name("backtest_charts_12mo.json")))
counted = [t for t in d if not t["alert_only"]]

# Pull the REAL current numbers from the latest report so the header can't go
# stale (was hardcoded — showed old baseline after a re-run).
rpt = Path(__file__).with_name("backtest_report_12mo.md").read_text(encoding="utf-8")
def grab(pat, default="?"):
    m = re.search(pat, rpt)
    return m.group(1) if m else default
traded = grab(r"viable stop\): \*\*(\d+)\*\*")
winrate = grab(r"win rate ([\d.]+)% \(of decided\)")
pnl = grab(r"Simulated P&L.*?\$(-?[\d.]+)")
br = re.search(r"\| break_and_retest \| \d+ \|.*?\| ([\d.]+)% \| \$(-?[\d.]+) \|", rpt)
br_wr, br_pnl = (br.group(1), br.group(2)) if br else ("?", "?")
def money(s):
    try:
        v = float(s); return ("-$" if v < 0 else "+$") + f"{abs(v):,.0f}"
    except ValueError:
        return s
STAT = (f'12-month backtest (251 sessions): <b>{traded} trades · {winrate}% win at 2R · '
        f'<span class="{"neg" if pnl.startswith("-") else ""}">{money(pnl)}</span></b><br>'
        f'break-and-retest: <b style="color:var(--tgt)">{money(br_pnl)} · {br_wr}% win</b> · '
        f'your 07-10 rules encoded: clean-first-break, no adverse-wick entries, real displacement. '
        f'All 3 setups green. Selection score (clean+A+structural stop): 44% win, ~$1.5k/mo.')


def pick(setup, outcome, k):
    xs = [t for t in counted if t["setup"] == setup and t["outcome"] == outcome]
    xs.sort(key=lambda t: t["pnl"])           # losers: worst first
    if outcome == "win":
        xs.sort(key=lambda t: -t["pnl"])
    return xs[:k]


sel = (pick("break_and_retest", "loss", 5)
       + pick("break_and_retest", "win", 3)
       + pick("one_candle_rule", "loss", 2)
       + pick("one_candle_rule", "win", 2))

keep = ("day", "symbol", "setup", "grade", "direction", "outcome", "pnl",
        "entry", "stop", "target", "entry_i", "reason", "levels", "candles")
trimmed = [{k: t[k] for k in keep} for t in sel]
DATA = json.dumps(trimmed)

TEMPLATE = r"""
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
  .neg{color:var(--stop)}
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
  .oc{font-family:var(--mono);font-size:12px;font-weight:700;font-variant-numeric:tabular-nums}
  .win{color:var(--tgt)} .loss{color:var(--stop)}
  canvas{width:100%;height:auto;display:block;border-radius:6px;background:#0b1017}
  .why{font-family:var(--mono);font-size:11px;color:var(--pm)}
  .rz{font-size:11px;color:var(--dim);line-height:1.4}
  .ask{font-family:var(--mono);font-size:11px;color:var(--or);
       border-top:1px dashed var(--edge);padding-top:7px;margin-top:1px}
</style>
<div class="wrap">
  <div class="head">
    <h1>OMEN entry review — which of these would you actually take?</h1>
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
  <div class="grid" id="grid"></div>
</div>
<script>
const DATA = __DATA__;
const LVLCOL = {PMH:'#fbbf24',PML:'#fbbf24',PDH:'#a78bfa',PDL:'#a78bfa',ORH:'#38bdf8',ORL:'#38bdf8'};
const CW=560, CH=340, PL=8, PR=58, PT=16, PB=22;

function draw(cv, t){
  const dpr = window.devicePixelRatio||1;
  cv.width = CW*dpr; cv.height = CH*dpr; cv.style.aspectRatio = CW+'/'+CH;
  const g = cv.getContext('2d'); g.scale(dpr,dpr);
  // zoom to ~40 bars centered on the entry so candles are big enough to read
  const raw = t.candles;
  const s = Math.max(0, t.entry_i-16), e = Math.min(raw.length, t.entry_i+24);
  const cs = raw.slice(s, e);
  const eIdx = t.entry_i - s;
  let lo=Infinity, hi=-Infinity;
  for(const c of cs){ lo=Math.min(lo,c.l); hi=Math.max(hi,c.h); }
  for(const k in t.levels){ lo=Math.min(lo,t.levels[k]); hi=Math.max(hi,t.levels[k]); }
  lo=Math.min(lo,t.stop,t.target); hi=Math.max(hi,t.stop,t.target);
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
  // entry / stop / target (solid, label at right)
  g.setLineDash([]);
  [['entry',t.entry,'#f4f7fb'],['stop',t.stop,'#f87171'],['2R',t.target,'#4ade80']].forEach(([lab,p,col])=>{
    const yy=y(p); g.strokeStyle=col; g.lineWidth=1; g.beginPath(); g.moveTo(PL,yy); g.lineTo(CW-PR,yy); g.stroke();
    g.fillStyle=col; g.textAlign='left'; g.fillText(lab+' '+p.toFixed(2), CW-PR+3, yy);
  });
  // entry-bar vertical guide
  const ex=x(eIdx);
  g.strokeStyle='rgba(244,247,251,.28)'; g.setLineDash([2,3]); g.lineWidth=1;
  g.beginPath(); g.moveTo(ex,PT); g.lineTo(ex,CH-PB); g.stroke(); g.setLineDash([]);
  // OB reference candle (Austin 08-20: "draw the one candle that you're
  // referencing") — reason carries "block $lo-$hi (at HH:MM:SS)"
  let obIdx=-1;
  const m=t.reason.match(/\(at (\d\d:\d\d)/);
  if(m){ obIdx=cs.findIndex(c=>c.t===m[1]); }
  // candles
  for(let i=0;i<n;i++){ const c=cs[i], up=c.c>=c.o, col=up?'#26a69a':'#ef5350', xx=x(i);
    g.strokeStyle=col; g.lineWidth=1; g.beginPath(); g.moveTo(xx,y(c.h)); g.lineTo(xx,y(c.l)); g.stroke();
    const yo=y(c.o), yc=y(c.c), top=Math.min(yo,yc), h=Math.max(Math.abs(yc-yo),1);
    g.fillStyle=col; g.fillRect(xx-cw*0.34, top, Math.max(cw*0.68,1), h);
    if(i===eIdx){ g.strokeStyle='#f4f7fb'; g.lineWidth=1.4;
      g.strokeRect(xx-cw*0.34-1.5, top-1.5, Math.max(cw*0.68,1)+3, h+3); }
    if(i===obIdx){ g.strokeStyle='#fbbf24'; g.lineWidth=1.4; g.setLineDash([2,2]);
      g.strokeRect(xx-cw*0.34-2.5, y(c.h)-3, Math.max(cw*0.68,1)+5, y(c.l)-y(c.h)+6);
      g.setLineDash([]); g.fillStyle='#fbbf24'; g.font='9px ui-monospace,monospace';
      g.textAlign='center'; g.fillText('OB', xx, y(c.h)-6); }
  }
  // entry arrow under the entry bar
  g.fillStyle='#f4f7fb'; g.beginPath();
  g.moveTo(ex,CH-PB+2); g.lineTo(ex-4,CH-PB+9); g.lineTo(ex+4,CH-PB+9); g.closePath(); g.fill();
  // minute labels every 5 bars (Austin: label each candle's minute)
  g.fillStyle='#5b6675'; g.font='8px ui-monospace,monospace'; g.textBaseline='alphabetic';
  g.textAlign='center';
  for(let i=0;i<n;i+=5){ g.fillText(cs[i].t.slice(3), x(i), CH-6); }
  g.textAlign='right'; g.fillText(cs[n-1].t, CW-PR+42, CH-6);
}

const grid=document.getElementById('grid');
for(const t of DATA){
  const card=document.createElement('div'); card.className='card';
  const dir = t.direction==='call'?'LONG':'SHORT';
  const ocCls = t.outcome==='win'?'win':'loss';
  const pnl = (t.pnl>=0?'+$':'-$')+Math.abs(t.pnl).toFixed(0);
  card.innerHTML =
    '<div class="ch"><div class="ttl">'+t.day+' '+t.symbol+
      ' <span class="sub">'+t.setup.replace(/_/g,' ')+' · '+t.grade+' · '+dir+'</span></div>'+
      '<div class="oc '+ocCls+'">'+t.outcome.toUpperCase()+' '+pnl+'</div></div>'+
    '<canvas></canvas>'+
    '<div class="rz">'+t.reason+'</div>'+
    '<div class="ask">Take this entry? &nbsp;Y / N &nbsp;— what does your eye see?</div>';
  grid.appendChild(card);
  draw(card.querySelector('canvas'), t);
}
</script>
"""

out = Path(__file__).with_name("review_artifact.html")
out.write_text(TEMPLATE.replace("__DATA__", DATA).replace("__STAT__", STAT), encoding="utf-8")
print("wrote", out, "with", len(trimmed), "trades")
