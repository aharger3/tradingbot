"""Build the interactive 2-year backtest report from backtest_2y.py's JSON.

Reads research/bt2y_trades.json (a row per signal) and writes a single
self-contained HTML page: facet filters over every dimension the replay
recorded, live metrics, an equity curve, and an edge scanner that ranks every
slice of the filtered set by mean-R against that set's own baseline.

The data is embedded columnar + dictionary-encoded so the 2-year corpus fits
inside one artifact-sized file.

Usage: python research/build_bt2y_report.py [--in ...] [--out ...]
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from universe import MIN_SAMPLE_N  # noqa: E402

# field -> label, in the order the filter rail renders them
FACETS = [
    ("book", "Book"), ("sgrade", "Austin grade S/A/C"),
    ("tripped", "Downgrades tripped"), ("confluence", "BR+OCR confluence"),
    ("cls", "Asset class"), ("pool", "Pool"), ("tier", "Watchlist tier"),
    ("sym", "Symbol"), ("setup", "Setup"), ("dir", "Direction"),
    ("grade", "Engine grade (legacy)"), ("status", "Fired / filtered"),
    ("out", "Outcome"), ("level", "Level broken"), ("stopb", "Stop width"),
    ("aligned", "vs HTF bias"), ("s", "S-score"), ("seq", "Nth signal of day"),
    ("slot", "Entry slot"), ("dow", "Weekday"), ("yr", "Year"),
    ("gapb", "Overnight gap"), ("rangeb", "Day range"),
    ("spy_trend", "SPY regime"), ("vol_regime", "Volatility regime"),
    ("scaled", "Ladder scaled"),
]
NUMS = ["r", "pnl", "bars", "stop_pct", "gap", "drange", "dret",
        "entry", "stop", "target", "exit"]
MULTI = ["tags", "downgrades"]      # a signal can carry several of each
STRS = ["day", "et", "ym"]          # kept raw, dictionary-encoded like the facets


def book_of(t):
    """Which book a signal lands in — the page defaults to the traded one."""
    if t["traded"]:
        return "traded"
    if t["alert"]:
        return "alert only (C)"
    if t["status"] == "skipped_tight_stop":
        return "tight-stop skip"
    return "filtered (X)"


def encode(trades):
    """Columnar + dictionary encoding. cols[f] = int codes, dicts[f] = values."""
    fields = [f for f, _ in FACETS] + STRS
    dicts, cols = {}, {}
    for f in fields:
        index, codes = {}, []
        for t in trades:
            v = t.get(f)
            v = "yes" if v is True else "no" if v is False else str(v)
            if v not in index:
                index[v] = len(index)
            codes.append(index[v])
        dicts[f] = list(index)
        cols[f] = codes
    for f in NUMS:
        cols[f] = [t.get(f, 0) for t in trades]
    for f in MULTI:
        vocab, codes = {}, []
        for t in trades:
            cs = []
            for v in t.get(f, []):
                if v not in vocab:
                    vocab[v] = len(vocab)
                cs.append(vocab[v])
            codes.append(cs)
        dicts[f] = list(vocab)
        cols[f] = codes
    return dicts, cols


TEMPLATE = """<title>OMEN Two-Year Tape</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root{
  --bg:#EDEFF4; --surface:#FFFFFF; --surface2:#F5F7FA; --line:#D5DAE4;
  --ink:#111621; --muted:#5A6377; --faint:#8A93A6;
  --accent:#1F5FD1; --accent-soft:#DCE6FA;
  --win:#177A55; --loss:#BE3B2C; --warn:#B4791A;
  --grid:#E3E7EF;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0D1018; --surface:#151A25; --surface2:#1B2130; --line:#283041;
  --ink:#E7EBF3; --muted:#8C95A9; --faint:#697285;
  --accent:#6C9BFF; --accent-soft:#1B2740;
  --win:#3FBF8C; --loss:#F0705E; --warn:#DDA83B;
  --grid:#1E2534;
}}
:root[data-theme="dark"]{
  --bg:#0D1018; --surface:#151A25; --surface2:#1B2130; --line:#283041;
  --ink:#E7EBF3; --muted:#8C95A9; --faint:#697285;
  --accent:#6C9BFF; --accent-soft:#1B2740;
  --win:#3FBF8C; --loss:#F0705E; --warn:#DDA83B;
  --grid:#1E2534;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"IBM Plex Sans",system-ui,sans-serif;font-size:14px;line-height:1.5}
h1,h2,h3{margin:0;text-wrap:balance}
.mono{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}
a{color:var(--accent)}

header.top{padding:34px 28px 22px;border-bottom:1px solid var(--line);
  background:var(--surface);display:flex;flex-wrap:wrap;gap:18px;align-items:flex-end;
  justify-content:space-between}
header.top h1{font-family:"Instrument Serif",Georgia,serif;font-size:44px;
  font-weight:400;letter-spacing:-.01em;line-height:1}
header.top h1 em{font-style:italic;color:var(--accent)}
.sub{color:var(--muted);max-width:62ch;margin-top:8px}
.stamp{font-size:12px;color:var(--faint);text-align:right}

.wrap{display:grid;grid-template-columns:264px minmax(0,1fr);gap:0;align-items:start}
@media (max-width:900px){.wrap{grid-template-columns:1fr}}

aside{position:sticky;top:0;max-height:100vh;overflow-y:auto;padding:18px 16px 60px;
  border-right:1px solid var(--line);background:var(--surface)}
@media (max-width:900px){aside{position:static;max-height:none;border-right:0;
  border-bottom:1px solid var(--line)}}
.railhead{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.railhead h2{font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}
button.ghost{background:none;border:1px solid var(--line);color:var(--muted);
  border-radius:5px;padding:4px 9px;font:inherit;font-size:12px;cursor:pointer}
button.ghost:hover{border-color:var(--accent);color:var(--accent)}
details.facet{border-top:1px solid var(--line);padding:9px 0}
details.facet>summary{cursor:pointer;list-style:none;display:flex;justify-content:space-between;
  align-items:center;font-size:12px;letter-spacing:.07em;text-transform:uppercase;color:var(--muted)}
details.facet>summary::-webkit-details-marker{display:none}
details.facet>summary::after{content:"+";color:var(--faint)}
details.facet[open]>summary::after{content:"\\2212"}
.chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:9px}
.chip{border:1px solid var(--line);background:var(--surface2);color:var(--ink);
  border-radius:99px;padding:3px 9px;font-size:12px;cursor:pointer;
  font-family:"IBM Plex Mono",monospace}
.chip .n{color:var(--faint);margin-left:5px;font-size:11px}
.chip[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
.chip[aria-pressed="true"] .n{color:#ffffffb0}
.chip:focus-visible,button:focus-visible,.tabbtn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}

main{padding:22px 28px 80px;min-width:0}
section{margin-bottom:34px}
section>h2{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
  margin-bottom:12px;display:flex;gap:10px;align-items:baseline}
section>h2 span.hint{text-transform:none;letter-spacing:0;color:var(--faint);font-size:12px}

.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));gap:10px}
.kpi{background:var(--surface);border:1px solid var(--line);border-radius:9px;padding:12px 13px;
  display:flex;flex-direction:column;gap:3px}
.kpi .k{font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--muted)}
.kpi .v{font-family:"IBM Plex Mono",monospace;font-size:23px;font-weight:500;
  font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.kpi .foot{font-size:11px;color:var(--faint)}
.pos{color:var(--win)}.neg{color:var(--loss)}.neu{color:var(--ink)}
.gate{display:inline-flex;align-items:center;gap:5px;border-radius:99px;padding:2px 8px;
  font-size:11px;font-weight:600;letter-spacing:.03em}
.gate.pass{background:color-mix(in srgb,var(--win) 16%,transparent);color:var(--win)}
.gate.fail{background:color-mix(in srgb,var(--loss) 16%,transparent);color:var(--loss)}

.panel{background:var(--surface);border:1px solid var(--line);border-radius:9px;padding:14px}
.charts{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);gap:12px}
@media (max-width:820px){.charts{grid-template-columns:1fr}}
svg{display:block;width:100%;height:auto}
.axlab{font-size:9px;fill:var(--faint);font-family:"IBM Plex Mono",monospace}
.gridline{stroke:var(--grid);stroke-width:1}

.tabs{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:11px}
.tabbtn{border:1px solid var(--line);background:var(--surface);color:var(--muted);
  border-radius:6px;padding:4px 10px;font:inherit;font-size:12px;cursor:pointer}
.tabbtn[aria-pressed="true"]{background:var(--accent-soft);border-color:var(--accent);color:var(--accent)}

.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:6px 9px;text-align:right;white-space:nowrap;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
thead th{position:sticky;top:0;background:var(--surface);font-size:11px;
  letter-spacing:.06em;text-transform:uppercase;color:var(--muted);cursor:pointer;z-index:2}
tbody tr:hover{background:var(--surface2)}
td.num{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums}
.bar{position:relative;display:block;height:4px;border-radius:2px;background:var(--grid);margin-top:3px}
.bar>i{position:absolute;top:0;bottom:0;border-radius:2px}
.tag{display:inline-block;border:1px solid var(--line);border-radius:4px;padding:0 5px;
  font-size:11px;color:var(--muted);font-family:"IBM Plex Mono",monospace;margin-right:3px}
.empty{color:var(--faint);padding:22px 0}
.badge{display:inline-block;border-radius:99px;padding:0 6px;font-size:10px;
  letter-spacing:.03em;text-transform:uppercase;margin-left:6px;vertical-align:1px}
.badge.low{background:color-mix(in srgb,var(--warn) 18%,transparent);color:var(--warn)}
tr.lowsample{opacity:.55}
tr.lowsample:hover{opacity:.9}
.note{color:var(--muted);font-size:12px;max-width:70ch}
.note b{color:var(--ink)}
footer{padding:22px 28px 60px;border-top:1px solid var(--line);color:var(--faint);font-size:12px}
.pager{display:flex;gap:8px;align-items:center;margin-top:10px;color:var(--muted);font-size:12px}

/* --- overnight summary block, injected via --summary; absent when unused --- */
#summary{margin-bottom:34px}
#summary .lede{font-family:"Instrument Serif",Georgia,serif;font-size:26px;line-height:1.28;
  font-weight:400;letter-spacing:-.01em;max-width:34ch;margin:0 0 14px}
#summary .lede em{font-style:italic;color:var(--accent)}
#summary .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(232px,1fr));gap:12px}
#summary .card{background:var(--surface);border:1px solid var(--line);border-radius:9px;
  padding:13px 14px;display:flex;flex-direction:column;gap:6px;
  border-left:3px solid var(--line)}
#summary .card.win{border-left-color:var(--win)}
#summary .card.loss{border-left-color:var(--loss)}
#summary .card.warn{border-left-color:var(--warn)}
#summary .card.open{border-left-color:var(--accent)}
#summary .card .w{font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}
#summary .card .h{font-size:15px;font-weight:600;line-height:1.32;text-wrap:balance}
#summary .card p{margin:0;color:var(--muted);font-size:13px;line-height:1.5}
#summary .card p b{color:var(--ink)}
#summary .card .src{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--faint);
  margin-top:auto;padding-top:4px;word-break:break-all}
#summary .ask{background:var(--accent-soft);border:1px solid var(--accent);border-radius:9px;
  padding:14px 15px;margin-top:12px}
#summary .ask .w{font-size:11px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--accent);margin-bottom:6px}
#summary .ask p{margin:0 0 8px;max-width:72ch}
#summary .ask p:last-child{margin-bottom:0}
#summary table{margin-top:10px}
</style>

<header class="top">
  <div>
    <h1>OMEN <em>Two-Year Tape</em></h1>
    <p class="sub">Every signal the engine produced over __SESSIONS__ sessions
    (__FIRST__ &rarr; __LAST__), replayed bar-by-bar from the 1-minute archive.
    Every signal carries <b>both</b> grades: Austin&rsquo;s S/A/C ladder
    (<span class="mono">research/downgrade.py</span>, scored here, still not wired into
    detection) and the engine&rsquo;s legacy A+/A/B/C/X. Filter anything; the numbers,
    the curve and the edge scanner all recompute against what is left.</p>
  </div>
  <div class="stamp mono">built __GEN__<br>__NSIG__ signals &middot; __NTRADED__ traded<br>1R = $__RISK__</div>
</header>

<div class="wrap">
<aside>
  <div class="railhead">
    <h2>Filters</h2>
    <span style="display:flex;gap:5px">
      <button class="ghost" id="reset" type="button">Traded only</button>
      <button class="ghost" id="clear" type="button">Clear</button>
    </span>
  </div>
  <div id="rail"></div>
</aside>

<main>
__SUMMARY__
  <section id="kpisec">
    <h2>Scoreboard <span class="hint" id="scope"></span></h2>
    <div class="kpis" id="kpis"></div>
  </section>

  <section>
    <h2>Curve &amp; distribution <span class="hint">equity in R, chronological &middot; per-trade R</span></h2>
    <div class="charts">
      <div class="panel"><svg id="equity" viewBox="0 0 720 260" role="img" aria-label="Equity curve in R"></svg></div>
      <div class="panel"><svg id="hist" viewBox="0 0 420 260" role="img" aria-label="R distribution"></svg></div>
    </div>
  </section>

  <section>
    <h2>Monthly durability <span class="hint">the gate is every month green</span></h2>
    <div class="panel"><svg id="months" viewBox="0 0 720 200" role="img" aria-label="R by month"></svg></div>
  </section>

  <section>
    <h2>Edge scanner <span class="hint">every slice of the current selection, ranked by mean R against its own baseline</span></h2>
    <div class="tabs" id="scantabs"></div>
    <div class="panel scroll"><table id="scan"></table></div>
    <p class="note" style="margin-top:9px"><b>&Delta;R</b> is that slice&rsquo;s mean R
    minus the mean R of everything currently selected &mdash; positive is where the edge
    lives, negative is where it leaks. Rows under <b id="minn">__MIN_SAMPLE_N__</b> trades are marked
    <span class="badge low">low n</span> and always sort below every row that clears the
    floor, no matter how big their &Delta;R looks &mdash; a two-trade slice can show a
    huge number purely by luck.</p>
  </section>

  <section>
    <h2>Breakdown <span class="hint">pick a dimension</span></h2>
    <div class="tabs" id="dimtabs"></div>
    <div class="panel scroll"><table id="dim"></table></div>
    <p class="note" style="margin-top:9px">Rows marked <span class="badge low">low n</span>
    haven&rsquo;t happened enough times yet for the number next to them to mean anything
    &mdash; it could easily flip with the next few trades. They&rsquo;re still shown in full,
    just pushed to the bottom regardless of which column you sort by.</p>
  </section>

  <section>
    <h2>Trades <span class="hint" id="tradecount"></span></h2>
    <div class="panel scroll"><table id="trades"></table></div>
    <div class="pager"><button class="ghost" id="prev" type="button">Prev</button>
      <span id="pageinfo" class="mono"></span>
      <button class="ghost" id="next" type="button">Next</button></div>
  </section>
</main>
</div>

<footer>
  Replay engine: <span class="mono">backtest_week.simulate_day</span> via
  <span class="mono">backtest_2y.py</span>, ladder mode B, stops on the candle close,
  pessimistic same-bar fills, $__RISK__ risk per trade, 09:30&ndash;11:00 entries.
  Grades are the <em>engine&rsquo;s</em> (A+/A/B alert-and-trade, C alert-only, X filtered),
  not Austin&rsquo;s S/A/C marks. No futures contracts are in the archive, so the asset-class
  filter offers stocks and index ETFs only.
  A row tagged <span class="badge low">low n</span> below still shows its real number,
  it&rsquo;s just too early to trust it &mdash; not enough of that slice has happened yet.
</footer>

<script id="data" type="application/json">__DATA__</script>
<script>
(function(){
"use strict";
var D = JSON.parse(document.getElementById("data").textContent);
var dicts = D.dicts, cols = D.cols, N = cols.day.length;
var FACETS = D.facets, RISK = D.meta.risk_dollars;
var MULTI = {tags:1, downgrades:1};       // fields holding a list per signal
var EXTRA = [["downgrades","Which downgrade fired"],["tags","Reason tags"]];

// ---- decode helpers -------------------------------------------------------
function val(f,i){ return dicts[f][cols[f][i]]; }
var order = [];              // chronological index order
(function(){
  var idx = []; for(var i=0;i<N;i++) idx.push(i);
  idx.sort(function(a,b){
    var da=cols.day[a],db=cols.day[b];
    if(da!==db) return dicts.day[da]<dicts.day[db]?-1:1;
    var ta=dicts.et[cols.et[a]],tb=dicts.et[cols.et[b]];
    return ta<tb?-1:ta>tb?1:0;
  });
  order = idx;
})();

// ---- filter state ---------------------------------------------------------
var sel = {};                 // field -> Set of selected dict codes
function clearSel(){
  FACETS.forEach(function(f){ sel[f[0]] = new Set(); });
  EXTRA.forEach(function(f){ sel[f[0]] = new Set(); });
}
function defaultSel(){          // the page opens on the traded book, not the raw firehose
  clearSel();
  var c = dicts.book.indexOf("traded");
  if(c >= 0) sel.book.add(c);
}
defaultSel();

function passes(i){
  for(var k in sel){
    var s = sel[k]; if(!s.size) continue;
    if(MULTI[k]){
      var has=false, cs=cols[k][i];
      for(var j=0;j<cs.length;j++) if(s.has(cs[j])){has=true;break;}
      if(!has) return false;
    } else if(!s.has(cols[k][i])) return false;
  }
  return true;
}

var live = [];               // filtered, chronological
function refilter(){
  live = [];
  for(var k=0;k<order.length;k++){ var i=order[k]; if(passes(i)) live.push(i); }
}

// ---- stats ----------------------------------------------------------------
function stats(idxs){
  var n=idxs.length, w=0,l=0,sc=0, sumR=0, gp=0, gl=0, bars=0, dec=0;
  var eq=0, peak=0, dd=0, streak=0, worstStreak=0;
  var byMonth = {}, days = {};
  for(var k=0;k<n;k++){
    var i=idxs[k], r=cols.r[i], o=val("out",i);
    sumR+=r; bars+=cols.bars[i];
    if(o==="win"){w++;dec++;} else if(o==="loss"){l++;dec++;} else sc++;
    if(r>0) gp+=r; else gl+=-r;
    eq+=r; if(eq>peak) peak=eq; if(peak-eq>dd) dd=peak-eq;
    if(r<0){ streak++; if(streak>worstStreak) worstStreak=streak; } else streak=0;
    var m=val("ym",i); byMonth[m]=(byMonth[m]||0)+r;
    days[val("day",i)]=1;
  }
  var months=Object.keys(byMonth).sort();
  var green=0; months.forEach(function(m){ if(byMonth[m]>0) green++; });
  return {n:n, w:w, l:l, sc:sc, dec:dec,
    wr: dec? w/dec*100 : 0,
    meanR: n? sumR/n : 0, sumR: sumR,
    pf: gl? gp/gl : (gp?Infinity:0),
    dd: dd, worstStreak: worstStreak,
    bars: n? bars/n : 0,
    months: months, byMonth: byMonth,
    greenPct: months.length? green/months.length*100 : 0,
    days: Object.keys(days).length};
}

function fmt(x,d){ if(!isFinite(x)) return "\\u221e"; return (x).toFixed(d===undefined?2:d); }
function money(x){
  var s = x<0?"-":"", v=Math.abs(x);
  if(v>=1000) return s+"$"+(v/1000).toFixed(1)+"k";
  return s+"$"+v.toFixed(0);
}
function cls(x){ return x>0?"pos":x<0?"neg":"neu"; }

// ---- filter rail ----------------------------------------------------------
function buildRail(){
  var rail = document.getElementById("rail"), html = "";
  var all = FACETS.concat(EXTRA);
  all.forEach(function(f,fi){
    var field=f[0], label=f[1];
    var open = ["book","sgrade","setup","cls"].indexOf(field)>=0 ? " open" : "";
    html += '<details class="facet'+open+'"><summary>'+label+'</summary>'+
            '<div class="chips" data-field="'+field+'"></div></details>';
  });
  rail.innerHTML = html;
  renderChips();
  rail.addEventListener("click", function(e){
    var c = e.target.closest(".chip"); if(!c) return;
    var field = c.parentNode.getAttribute("data-field"), code = +c.getAttribute("data-code");
    var s = sel[field];
    if(s.has(code)) s.delete(code); else s.add(code);
    render();
  });
}

function facetCounts(field){
  // count with every OTHER filter applied, so counts stay meaningful
  var saved = sel[field]; sel[field] = new Set();
  var counts = {};
  for(var i=0;i<N;i++){
    if(!passes(i)) continue;
    if(MULTI[field]){ cols[field][i].forEach(function(c){counts[c]=(counts[c]||0)+1;}); }
    else { var c=cols[field][i]; counts[c]=(counts[c]||0)+1; }
  }
  sel[field] = saved;
  return counts;
}

function renderChips(){
  var all = FACETS.concat(EXTRA);
  all.forEach(function(f){
    var field=f[0];
    var box = document.querySelector('.chips[data-field="'+field+'"]');
    if(!box) return;
    var counts = facetCounts(field), d = dicts[field];
    var codes = d.map(function(_,i){return i;}).filter(function(c){return counts[c];});
    codes.sort(function(a,b){
      if(field==="s"||field==="seq") return (+d[a])-(+d[b]);
      if(field==="ym"||field==="yr"||field==="slot")
        return d[a]<d[b]?-1:1;
      return counts[b]-counts[a];
    });
    box.innerHTML = codes.map(function(c){
      return '<button class="chip" type="button" data-code="'+c+'" aria-pressed="'+
        (sel[field].has(c)?"true":"false")+'">'+d[c]+
        '<span class="n">'+counts[c]+'</span></button>';
    }).join("");
  });
}

// ---- KPIs -----------------------------------------------------------------
function renderKPIs(){
  var s = stats(live);
  var gate = s.meanR >= 2 ? "pass" : "fail";
  var durable = s.greenPct >= 100 ? "pass" : "fail";
  var k = [
    ["Signals", s.n.toLocaleString(), s.days+" sessions touched", "neu"],
    ["Win rate", fmt(s.wr,1)+"%", s.w+"W / "+s.l+"L / "+s.sc+" scratch", "neu"],
    ["Mean R", fmt(s.meanR,3),
      '<span class="gate '+gate+'">money gate 2.0R</span>', cls(s.meanR)],
    ["Total R", fmt(s.sumR,1), money(s.sumR*RISK)+" at $"+RISK+"/R", cls(s.sumR)],
    ["Profit factor", fmt(s.pf,2), "gross win R / gross loss R", cls(s.pf-1)],
    ["Max drawdown", "-"+fmt(s.dd,1)+"R", "worst peak-to-trough", "neg"],
    ["Worst losing run", s.worstStreak, "consecutive negative trades", "neu"],
    ["Months green", fmt(s.greenPct,0)+"%",
      '<span class="gate '+durable+'">'+s.months.length+" months</span>", cls(s.greenPct-50)],
    ["Avg hold", fmt(s.bars,0)+" min", "entry bar to exit bar", "neu"]
  ];
  document.getElementById("kpis").innerHTML = k.map(function(x){
    return '<div class="kpi"><span class="k">'+x[0]+'</span>'+
      '<span class="v '+x[3]+'">'+x[1]+'</span><span class="foot">'+x[2]+'</span></div>';
  }).join("");
  var chosen = [];
  for(var f in sel) if(sel[f].size)
    chosen.push(f+": "+Array.from(sel[f]).map(function(c){return dicts[f][c];}).join("/"));
  document.getElementById("scope").textContent =
    chosen.length ? chosen.join("  \\u00b7  ") : "no filters \\u2014 everything the engine saw";
}

// ---- charts ---------------------------------------------------------------
function svgEl(tag,attrs,text){
  var e=document.createElementNS("http://www.w3.org/2000/svg",tag);
  for(var k in attrs) e.setAttribute(k,attrs[k]);
  if(text!==undefined) e.textContent=text;
  return e;
}
function clear(el){ while(el.firstChild) el.removeChild(el.firstChild); }

function drawEquity(){
  var svg=document.getElementById("equity"); clear(svg);
  var W=720,H=260,P=34;
  if(!live.length){ svg.appendChild(svgEl("text",{x:W/2,y:H/2,"class":"axlab","text-anchor":"middle"},"no trades in selection")); return; }
  var eq=[],run=0;
  for(var i=0;i<live.length;i++){ run+=cols.r[live[i]]; eq.push(run); }
  var mn=Math.min(0,Math.min.apply(null,eq)), mx=Math.max(0,Math.max.apply(null,eq));
  if(mx===mn) mx=mn+1;
  var x=function(i){return P+i*(W-P-8)/Math.max(1,eq.length-1);};
  var y=function(v){return H-P-(v-mn)*(H-P-14)/(mx-mn);};
  [0,.25,.5,.75,1].forEach(function(t){
    var v=mn+(mx-mn)*t;
    svg.appendChild(svgEl("line",{x1:P,x2:W-8,y1:y(v),y2:y(v),"class":"gridline"}));
    svg.appendChild(svgEl("text",{x:4,y:y(v)+3,"class":"axlab"},v.toFixed(0)+"R"));
  });
  var d="M"+x(0)+","+y(eq[0]);
  for(var j=1;j<eq.length;j++) d+="L"+x(j)+","+y(eq[j]);
  var area=d+"L"+x(eq.length-1)+","+y(Math.max(mn,0))+"L"+x(0)+","+y(Math.max(mn,0))+"Z";
  var up = eq[eq.length-1]>=0;
  svg.appendChild(svgEl("path",{d:area,fill:up?"var(--win)":"var(--loss)","fill-opacity":".10"}));
  svg.appendChild(svgEl("path",{d:d,fill:"none",stroke:up?"var(--win)":"var(--loss)","stroke-width":"1.6"}));
  svg.appendChild(svgEl("circle",{cx:x(eq.length-1),cy:y(eq[eq.length-1]),r:3.2,
    fill:up?"var(--win)":"var(--loss)"}));
  svg.appendChild(svgEl("text",{x:P,y:H-8,"class":"axlab"},val("day",live[0])));
  svg.appendChild(svgEl("text",{x:W-8,y:H-8,"class":"axlab","text-anchor":"end"},val("day",live[live.length-1])));
}

function drawHist(){
  var svg=document.getElementById("hist"); clear(svg);
  var W=420,H=260,P=30;
  if(!live.length) return;
  var edges=[-1.25,-1,-.75,-.5,-.25,0,.25,.5,.75,1,1.5,2,3];
  var b=new Array(edges.length+1).fill(0);
  live.forEach(function(i){
    var r=cols.r[i], k=edges.length;
    for(var e=0;e<edges.length;e++) if(r<=edges[e]){k=e;break;}
    b[k]++;
  });
  var mx=Math.max.apply(null,b)||1;
  var bw=(W-P-10)/b.length;
  b.forEach(function(v,k){
    var h=(H-P-24)*v/mx;
    var neg = k<=5;
    svg.appendChild(svgEl("rect",{x:P+k*bw+1,y:H-P-h,width:bw-2,height:h,rx:1.5,
      fill:neg?"var(--loss)":"var(--win)","fill-opacity":".78"}));
  });
  svg.appendChild(svgEl("line",{x1:P+6*bw,x2:P+6*bw,y1:12,y2:H-P,stroke:"var(--faint)","stroke-dasharray":"3 3"}));
  svg.appendChild(svgEl("text",{x:P+6*bw+4,y:18,"class":"axlab"},"0R"));
  svg.appendChild(svgEl("text",{x:P,y:H-10,"class":"axlab"},"-1.25R"));
  svg.appendChild(svgEl("text",{x:W-10,y:H-10,"class":"axlab","text-anchor":"end"},"+3R"));
  svg.appendChild(svgEl("text",{x:P,y:12,"class":"axlab"},"trades per R bucket"));
}

function drawMonths(){
  var svg=document.getElementById("months"); clear(svg);
  var W=720,H=200,P=30;
  var s=stats(live), ms=s.months;
  if(!ms.length) return;
  var vals=ms.map(function(m){return s.byMonth[m];});
  var mx=Math.max.apply(null,vals.map(Math.abs))||1;
  var bw=(W-P-8)/ms.length, zero=(H-24)/2+8;
  ms.forEach(function(m,k){
    var v=s.byMonth[m], h=Math.abs(v)/mx*((H-40)/2);
    svg.appendChild(svgEl("rect",{x:P+k*bw+1,y:v>=0?zero-h:zero,width:Math.max(1,bw-2),
      height:Math.max(1,h),rx:1.5,fill:v>=0?"var(--win)":"var(--loss)"}));
    if(ms.length<=30 || k%3===0)
      svg.appendChild(svgEl("text",{x:P+k*bw+bw/2,y:H-6,"class":"axlab","text-anchor":"middle"},m.slice(2)));
  });
  svg.appendChild(svgEl("line",{x1:P,x2:W-8,y1:zero,y2:zero,stroke:"var(--line)"}));
  svg.appendChild(svgEl("text",{x:4,y:zero-4,"class":"axlab"},"+"+mx.toFixed(0)+"R"));
}

// ---- tables ---------------------------------------------------------------
// Sample floor for any per-slice row (edge scanner AND the breakdown table).
// Not a JS-only number: it is universe.MIN_SAMPLE_N, threaded through by the
// Python builder below (see __MIN_SAMPLE_N__) so this page can never drift
// from every other per-symbol/per-pool report in the repo. Below it a single
// trade can swing a slice's mean R by half a point or more, so the figure is
// noise, not evidence. A slice under the floor still renders -- it's just
// marked low-confidence and always sorts last (see markLow/lowSort below)
// rather than being dropped, so a thin slice is still findable, just not
// mistakable for a finding.
var SCAN_MIN = __MIN_SAMPLE_N__;
// Outcome-derived fields are excluded from the scanner: "scaled" and "out" are
// results, not conditions you could have known at entry, so ranking by them is
// circular (every scaled trade is a win by construction).
var POST_HOC = {out:1, scaled:1};
function markLow(st){ return st.n < SCAN_MIN; }
// Comparator: low-confidence rows always sink below every trustworthy row,
// regardless of the column being sorted on -- a 2-trade slice can never top
// a leaderboard just because its lucky mean R is large. `cmp` breaks ties
// among rows on the same side of the floor.
function lowSort(a, b, cmp){
  if(a.low !== b.low) return a.low ? 1 : -1;
  return cmp(a, b);
}
function groupStats(field){
  var by={};
  live.forEach(function(i){
    if(MULTI[field]){
      cols[field][i].forEach(function(c){ (by[dicts[field][c]]=by[dicts[field][c]]||[]).push(i); });
    } else {
      var v=val(field,i); (by[v]=by[v]||[]).push(i);
    }
  });
  return by;
}

var scanField = "__ALL__";
function buildTabs(id, fields, current, onpick){
  var el=document.getElementById(id);
  el.innerHTML = fields.map(function(f){
    return '<button class="tabbtn" type="button" data-f="'+f[0]+'" aria-pressed="'+
      (f[0]===current?"true":"false")+'">'+f[1]+"</button>";
  }).join("");
  el.onclick=function(e){ var b=e.target.closest(".tabbtn"); if(b) onpick(b.getAttribute("data-f")); };
}

function renderScan(){
  var base = stats(live), rows=[];
  var pool = FACETS.concat(EXTRA).filter(function(f){return !POST_HOC[f[0]];});
  var fields = scanField==="__ALL__" ? pool
    : pool.filter(function(f){return f[0]===scanField;});
  fields.forEach(function(f){
    var by=groupStats(f[0]);
    for(var v in by){
      var st=stats(by[v]);
      rows.push({dim:f[1], val:v, st:st, d:st.meanR-base.meanR, low:markLow(st)});
    }
  });
  rows.sort(function(a,b){ return lowSort(a,b,function(a,b){ return b.d-a.d; }); });
  var trusted = rows.filter(function(r){ return !r.low; });
  var mxd = trusted.length? Math.max.apply(null,trusted.map(function(r){return Math.abs(r.d);})) : 1;
  var head='<thead><tr><th>Dimension</th><th>Slice</th><th>N</th><th>Win%</th>'+
    '<th>Mean R</th><th>&Delta;R vs selection</th><th>Total R</th></tr></thead>';
  var body = rows.map(function(r){
    var w=Math.abs(r.d)/mxd*100;
    var badge=r.low?' <span class="badge low" title="fewer than '+SCAN_MIN+
      ' trades -- too few for this number to mean anything">low n</span>':'';
    return '<tr'+(r.low?' class="lowsample"':'')+'><td>'+r.dim+'</td><td class="num">'+
      r.val+badge+'</td>'+
      '<td class="num">'+r.st.n+'</td><td class="num">'+fmt(r.st.wr,1)+'</td>'+
      '<td class="num '+cls(r.st.meanR)+'">'+fmt(r.st.meanR,3)+'</td>'+
      '<td class="num '+cls(r.d)+'">'+(r.d>=0?"+":"")+fmt(r.d,3)+
        '<span class="bar"><i style="'+(r.d>=0?"left:50%":"right:50%")+';width:'+(w/2)+
        '%;background:'+(r.d>=0?"var(--win)":"var(--loss)")+'"></i></span></td>'+
      '<td class="num '+cls(r.st.sumR)+'">'+fmt(r.st.sumR,1)+'</td></tr>';
  }).join("");
  document.getElementById("scan").innerHTML = head+"<tbody>"+
    (body||'<tr><td colspan="7" class="empty">no trades in selection</td></tr>')+"</tbody>";
}

var dimField="sgrade", dimSort="sumR", dimDesc=true;
function renderDim(){
  var by=groupStats(dimField), rows=[];
  for(var v in by){ var st=stats(by[v]); rows.push({val:v, st:st, low:markLow(st)}); }
  rows.sort(function(a,b){
    return lowSort(a,b,function(a,b){
      var x=dimSort==="val"?a.val:a.st[dimSort], y=dimSort==="val"?b.val:b.st[dimSort];
      if(x<y) return dimDesc?1:-1; if(x>y) return dimDesc?-1:1; return 0;
    });
  });
  var cols_=[["val","Slice"],["n","N"],["wr","Win%"],["meanR","Mean R"],
             ["sumR","Total R"],["pf","PF"],["dd","MaxDD"],["greenPct","Months green%"],["bars","Avg min"]];
  var head='<thead><tr>'+cols_.map(function(c){
    return '<th data-s="'+c[0]+'">'+c[1]+(dimSort===c[0]?(dimDesc?" \\u25be":" \\u25b4"):"")+"</th>";}).join("")+"</tr></thead>";
  var body=rows.map(function(r){
    var badge=r.low?' <span class="badge low" title="fewer than '+SCAN_MIN+
      ' trades -- too few for this number to mean anything">low n</span>':'';
    return '<tr'+(r.low?' class="lowsample"':'')+'><td class="num">'+r.val+badge+'</td>'+
      '<td class="num">'+r.st.n+'</td>'+
      '<td class="num">'+fmt(r.st.wr,1)+'</td>'+
      '<td class="num '+cls(r.st.meanR)+'">'+fmt(r.st.meanR,3)+'</td>'+
      '<td class="num '+cls(r.st.sumR)+'">'+fmt(r.st.sumR,1)+'</td>'+
      '<td class="num">'+fmt(r.st.pf,2)+'</td>'+
      '<td class="num neg">-'+fmt(r.st.dd,1)+'</td>'+
      '<td class="num">'+fmt(r.st.greenPct,0)+'</td>'+
      '<td class="num">'+fmt(r.st.bars,0)+'</td></tr>';
  }).join("");
  var t=document.getElementById("dim");
  t.innerHTML=head+"<tbody>"+(body||'<tr><td colspan="9" class="empty">nothing selected</td></tr>')+"</tbody>";
  t.querySelector("thead").onclick=function(e){
    var th=e.target.closest("th"); if(!th) return;
    var s=th.getAttribute("data-s");
    if(s===dimSort) dimDesc=!dimDesc; else { dimSort=s; dimDesc=true; }
    renderDim();
  };
}

var page=0, PAGE=60;
function renderTrades(){
  var total=live.length, pages=Math.max(1,Math.ceil(total/PAGE));
  if(page>=pages) page=pages-1;
  var slice=live.slice(page*PAGE,(page+1)*PAGE);
  var head='<thead><tr><th>Date</th><th>Time</th><th>Sym</th><th>Setup</th><th>Dir</th>'+
    '<th>S/A/C</th><th>Eng</th><th>Entry</th><th>Stop</th><th>Stop%</th><th>Exit</th><th>Out</th>'+
    '<th>R</th><th>$</th><th>Level</th><th>S#</th><th>Bias</th><th>Tags</th></tr></thead>';
  var body=slice.map(function(i){
    var r=cols.r[i];
    return '<tr><td class="num">'+val("day",i)+'</td><td class="num">'+val("et",i)+'</td>'+
      '<td class="num">'+val("sym",i)+'</td><td>'+val("setup",i)+'</td>'+
      '<td>'+val("dir",i)+'</td><td class="num">'+val("sgrade",i)+'</td>'+
      '<td class="num">'+val("grade",i)+'</td>'+
      '<td class="num">'+cols.entry[i].toFixed(2)+'</td><td class="num">'+cols.stop[i].toFixed(2)+'</td>'+
      '<td class="num">'+cols.stop_pct[i].toFixed(2)+'</td>'+
      '<td class="num">'+cols.exit[i].toFixed(2)+'</td><td>'+val("out",i)+'</td>'+
      '<td class="num '+cls(r)+'">'+fmt(r,2)+'</td>'+
      '<td class="num '+cls(r)+'">'+money(cols.pnl[i])+'</td>'+
      '<td class="num">'+val("level",i)+'</td><td class="num">'+val("s",i)+'</td>'+
      '<td class="num">'+val("aligned",i)+'</td>'+
      '<td>'+cols.tags[i].map(function(c){return '<span class="tag">'+dicts.tags[c]+"</span>";}).join("")+'</td></tr>';
  }).join("");
  document.getElementById("trades").innerHTML=head+"<tbody>"+
    (body||'<tr><td colspan="18" class="empty">nothing selected</td></tr>')+"</tbody>";
  document.getElementById("pageinfo").textContent=(page+1)+" / "+pages;
  document.getElementById("tradecount").textContent=total.toLocaleString()+" in selection";
}

// ---- orchestration --------------------------------------------------------
function render(){
  refilter();
  renderChips();
  renderKPIs();
  drawEquity(); drawHist(); drawMonths();
  renderScan(); renderDim(); renderTrades();
}

var DIMS = FACETS.concat(EXTRA);
var SCANDIMS = [["__ALL__","Every dimension"]].concat(
  DIMS.filter(function(f){return !POST_HOC[f[0]];}));
function pickScan(f){ scanField=f; buildTabs("scantabs",SCANDIMS,scanField,pickScan); renderScan(); }
function pickDim(f){ dimField=f; buildTabs("dimtabs",DIMS,dimField,pickDim); renderDim(); }

buildRail();
buildTabs("scantabs",SCANDIMS,scanField,pickScan);
buildTabs("dimtabs",DIMS,dimField,pickDim);
document.getElementById("reset").onclick=function(){ defaultSel(); page=0; render(); };
document.getElementById("clear").onclick=function(){ clearSel(); page=0; render(); };
document.getElementById("prev").onclick=function(){ if(page>0){page--;renderTrades();} };
document.getElementById("next").onclick=function(){ page++; renderTrades(); };
document.getElementById("minn").textContent=SCAN_MIN;
render();
})();
</script>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inp", default="research/bt2y_trades.json")
    ap.add_argument("--out", default="research/omen-2y-backtest.html")
    ap.add_argument("--summary", default=None,
                    help="HTML fragment injected above the scoreboard. Omit and the "
                         "page renders exactly as it did before this option existed.")
    args = ap.parse_args()

    summary = ""
    if args.summary:
        summary = Path(args.summary).read_text(encoding="utf-8")
    raw = json.loads((ROOT / args.inp).read_text(encoding="utf-8"))
    trades, meta = raw["trades"], raw["meta"]
    for t in trades:
        t["book"] = book_of(t)
    dicts, cols = encode(trades)
    payload = {"meta": meta, "facets": FACETS, "dicts": dicts, "cols": cols}
    data = json.dumps(payload, separators=(",", ":"))

    html = (TEMPLATE
            .replace("__DATA__", data)
            .replace("__SESSIONS__", str(meta["sessions"]))
            .replace("__FIRST__", meta["first"]).replace("__LAST__", meta["last"])
            .replace("__GEN__", meta["generated"].replace("T", " "))
            .replace("__NSIG__", "{:,}".format(meta["signals"]))
            .replace("__NTRADED__", "{:,}".format(meta["traded"]))
            .replace("__RISK__", str(int(meta["risk_dollars"])))
            .replace("__MIN_SAMPLE_N__", str(MIN_SAMPLE_N))
            .replace("__SUMMARY__", summary))
    out = ROOT / args.out
    out.write_text(html, encoding="utf-8")
    print("wrote %s (%.1f MB)" % (out, out.stat().st_size / 1e6))


if __name__ == "__main__":
    main()
