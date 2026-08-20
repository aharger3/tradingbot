"""T6 -- build the next homework decks.

Produces:
  research/omen-5.2-entry-deck.html  -- 200 unmarked trading days, entry+stop only
  research/omen-5.2-blind-deck.html   -- 100 engine fires, bars cut at the fire bar,
                                         grade + direction held out entirely
  research/omen-5.2-blind-key.json    -- the answers for the blind deck

Self-contained HTML: all CSS/JS inline, bar data embedded as JSON in a
<script> tag, candles drawn with inline canvas, zero network refs. Marks
persist via localStorage, one key per card_id (the 5.1 closure bug that wrote
every card to one id is fixed by using `let` in the wiring loops).
"""
import json, os, csv
from research.levels import load_rth_bars

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(REPO, "research")
DATA = os.path.join(REPO, "data_archive")
BARS_PER_CARD = 120  # first ~2h of RTH; entries are early per the trend gate

# ── already-marked days (excluded from the entry deck) ────────────────────
MARKED = set()
for fn in ("deck_marks_index_2026-08-19.jsonl", "deck_marks_tsla_2026-08-20.jsonl"):
    p = os.path.join(RES, "marks", fn)
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if line:
            MARKED.add(json.loads(line)["card_id"])

ENTRY_SYMS = ("TSLA", "QQQ", "SPY")
ENTRY_COUNTS = {"TSLA": 100, "QQQ": 50, "SPY": 50}  # 200 total, 2:1:1 like 5.2


def pick_entry_days():
    days = []
    for sym in ENTRY_SYMS:
        files = sorted(
            (os.path.basename(f)[:-4] for f in os.listdir(os.path.join(DATA, sym))),
            reverse=True,
        )
        unmarked = [d for d in files if sym + "_" + d not in MARKED]
        days.extend((sym, d) for d in unmarked[: ENTRY_COUNTS[sym]])
    # stable, deterministic order: newest first, TSLA/QQQ/SPY blocks
    return days


def build_entry_deck():
    days = pick_entry_days()
    assert len(days) == 200, len(days)
    day_data = {}
    card_ids = []
    for sym, date in days:
        bars = load_rth_bars(sym, date)
        if not bars:
            raise RuntimeError("no bars for %s %s" % (sym, date))
        bars = bars[:BARS_PER_CARD]
        cid = sym + "_" + date
        day_data[cid] = bars
        card_ids.append(cid)

    cards_html = []
    for cid in card_ids:
        sym = cid.split("_")[0]
        date = cid.split("_")[1]
        cards_html.append(f"""
<div class="card" data-card-id="{cid}">
  <div class="card-header">
    <span class="card-id"><span class="status-dot empty" id="dot-{cid}"></span>{cid}</span>
    <span class="card-symbol">{sym}</span>
  </div>
  <canvas id="chart-{cid}" height="150"></canvas>
  <div class="card-footer">
    <div class="field side-group">
      <span class="lbl">side</span>
      <input type="radio" name="sid-{cid}" value="L" id="sl-{cid}"><label for="sl-{cid}">L</label>
      <input type="radio" name="sid-{cid}" value="S" id="ss-{cid}"><label for="ss-{cid}">S</label>
      <input type="checkbox" id="skip-{cid}"><label for="skip-{cid}" class="skip">no&nbsp;trade</label>
    </div>
    <div class="field">
      <span class="lbl">entry bar</span>
      <input type="number" class="num" id="entry-{cid}" min="0" max="{BARS_PER_CARD-1}" placeholder="click chart">
    </div>
    <div class="field">
      <span class="lbl">stop $</span>
      <input type="number" class="num" id="stop-{cid}" step="0.01" placeholder="stop price">
    </div>
  </div>
</div>""")

    html = ENTRY_TEMPLATE.format(
        deck_label="200 days · entry + stop",
        total=200,
        cards="\n".join(cards_html),
        day_data=json.dumps(day_data, separators=(",", ":")),
        card_ids=json.dumps(card_ids),
    )
    with open(os.path.join(RES, "omen-5.2-entry-deck.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("entry deck:", len(card_ids), "cards")


def build_blind_deck():
    trades = json.load(open(os.path.join(REPO, "backtest_charts.json"), encoding="utf-8"))
    ok = [t for t in trades if t.get("candles") and isinstance(t.get("entry_i"), int)]
    # deterministic stratified sample so every grade tier is represented
    by_grade = {"A+": [], "A": [], "B": [], "C": []}
    for i, t in enumerate(ok):
        g = t.get("grade")
        if g not in by_grade:
            continue
        by_grade[g].append((i, t))
    for g in by_grade:
        by_grade[g].sort(key=lambda it: (it[1]["symbol"], it[1]["day"]))
    sample = []
    sample += by_grade["A+"][:]   # 3
    sample += by_grade["A"][:]    # 7
    sample += by_grade["B"][:70]  # 70
    sample += by_grade["C"][:20]  # 20
    assert len(sample) == 100, len(sample)

    day_data = {}
    card_ids = []
    key = []
    for n, (i, t) in enumerate(sample):
        cid = "BT%03d" % n
        candles = t["candles"]
        ei = t["entry_i"]
        # cut at and including the engine's fire bar, no further
        cut = candles[: ei + 1]
        day_data[cid] = cut
        card_ids.append(cid)
        key.append({
            "card_id": cid,
            "symbol": t["symbol"],
            "day": t["day"],
            "entry_i": ei,
            "direction": t["direction"],
            "grade": t["grade"],
        })

    cards_html = []
    for cid, k in zip(card_ids, key):
        cards_html.append(f"""
<div class="card" data-card-id="{cid}">
  <div class="card-header">
    <span class="card-id"><span class="status-dot empty" id="dot-{cid}"></span>{cid}</span>
    <span class="card-symbol">{k['symbol']} · {k['day']}</span>
  </div>
  <canvas id="chart-{cid}" height="150"></canvas>
  <div class="card-footer">
    <div class="field side-group">
      <span class="lbl">verdict</span>
      <input type="radio" name="ver-{cid}" value="take" id="vt-{cid}"><label for="vt-{cid}">take</label>
      <input type="radio" name="ver-{cid}" value="skip" id="vk-{cid}"><label for="vk-{cid}">skip</label>
    </div>
    <div class="field side-group">
      <span class="lbl">side</span>
      <input type="radio" name="sid-{cid}" value="L" id="bl-{cid}"><label for="bl-{cid}">L</label>
      <input type="radio" name="sid-{cid}" value="S" id="bs-{cid}"><label for="bs-{cid}">S</label>
    </div>
  </div>
</div>""")

    html = BLIND_TEMPLATE.format(
        deck_label="100 engine fires · take or skip",
        total=100,
        cards="\n".join(cards_html),
        day_data=json.dumps(day_data, separators=(",", ":")),
        card_ids=json.dumps(card_ids),
    )
    with open(os.path.join(RES, "omen-5.2-blind-deck.html"), "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join(RES, "omen-5.2-blind-key.json"), "w", encoding="utf-8") as f:
        json.dump(key, f, indent=2)
    print("blind deck:", len(card_ids), "cards  key:", len(key), "rows")


# ── templates ──────────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #1a1a2e; color: #e0e0e0; padding: 12px; }
h1 { text-align: center; margin: 0 0 12px 0; font-size: 18px; color: #ccc; }
h1 span { font-size: 12px; color: #888; }
.controls { text-align: center; margin: 8px 0 14px 0; }
.controls button { background: #2d2d5e; color: #e0e0e0; border: 1px solid #444;
                   padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 13px;
                   margin: 0 2px; }
.controls button:hover { background: #3d3d7e; }
.controls .stats { display: inline-block; margin-left: 12px; font-size: 12px; color: #888; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 10px; }
.card { background: #16213e; border-radius: 8px; padding: 8px; border: 1px solid #2a2a5e; }
.card-header { display: flex; justify-content: space-between; align-items: center;
               margin-bottom: 4px; font-size: 12px; }
.card-id { color: #6a9ef0; font-weight: 600; font-family: monospace; font-size: 11px; }
.card-symbol { color: #aaa; font-size: 11px; }
canvas { display: block; width: 100%; height: 150px; border-radius: 4px;
         background: #0d1b2a; cursor: crosshair; }
.card-footer { display: flex; gap: 10px; margin-top: 6px; align-items: center; flex-wrap: wrap; }
.field { display: flex; align-items: center; gap: 4px; }
.field .lbl { font-size: 10px; color: #888; text-transform: uppercase; letter-spacing: .5px; }
.field label { font-size: 11px; color: #bbb; cursor: pointer; padding: 1px 5px;
               border-radius: 3px; border: 1px solid transparent; }
.field label:hover { border-color: #555; }
.field input[type=radio], .field input[type=checkbox] { display: none; }
.field input[type=radio]:checked + label,
.field input[type=checkbox]:checked + label { font-weight: 700; background: #2a3a5e; border-color: #6a9ef0; }
.num { width: 70px; background: #0d1b2a; color: #ccc; border: 1px solid #333;
       border-radius: 3px; padding: 2px 4px; font-size: 11px; font-family: monospace; }
.num::placeholder { color: #444; }
.status-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 4px; }
.status-dot.graded { background: #4caf50; }
.status-dot.empty { background: #555; }
@media (max-width: 600px) {
  .card-grid { grid-template-columns: 1fr; }
  .card-footer { flex-direction: column; align-items: flex-start; }
}
"""

ENTRY_TEMPLATE_RAW = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OMEN 5.2 Entry Deck</title>
<style>__CSS__</style>
</head>
<body>
<h1>OMEN Entry Deck <span id="deckLabel">{deck_label}</span></h1>
<div class="controls">
  <button onclick="exportJSONL()">Download JSONL</button>
  <button onclick="copyJSONL()">Copy</button>
  <button onclick="resetAll()">Reset All</button>
  <span class="stats" id="stats">0 / {total} done</span>
</div>
<div class="card-grid" id="cardGrid">
{cards}
</div>
<script>
var DAY_DATA = {day_data};
var CARD_IDS = {card_ids};

// canvas candle rendering (copied from the 5.2 deck machinery)
function renderCandle(canvas, candles, entryI) {{
  var ctx = canvas.getContext('2d');
  var W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  if (!candles || candles.length < 2) {{
    ctx.fillStyle = '#555'; ctx.font = '12px monospace'; ctx.textAlign = 'center';
    ctx.fillText('no data', W/2, H/2); return;
  }}
  var pad = {{ t: 8, b: 12, l: 42, r: 10 }};
  var cw = (W - pad.l - pad.r) / candles.length;
  var hi = -Infinity, lo = Infinity;
  for (var i = 0; i < candles.length; i++) {{
    hi = Math.max(hi, candles[i].h); lo = Math.min(lo, candles[i].l);
  }}
  var range = (hi - lo) || 1;
  var yPrice = function(p) {{ return pad.t + (hi - p) / range * (H - pad.t - pad.b); }};
  var xIdx = function(i) {{ return pad.l + i * cw + cw / 2; }};
  ctx.strokeStyle = '#1a2a3a'; ctx.lineWidth = 0.5;
  for (var g = 0; g <= 4; g++) {{
    var yy = pad.t + g * (H - pad.t - pad.b) / 4;
    ctx.beginPath(); ctx.moveTo(pad.l, yy); ctx.lineTo(W - pad.r, yy); ctx.stroke();
    ctx.fillStyle = '#555'; ctx.font = '9px monospace'; ctx.textAlign = 'right';
    ctx.fillText((hi - g * range / 4).toFixed(2), pad.l - 3, yy + 3);
  }}
  for (var i = 0; i < candles.length; i++) {{
    var c = candles[i]; var x = xIdx(i);
    var yO = yPrice(c.o), yH = yPrice(c.h), yL = yPrice(c.l), yC = yPrice(c.c);
    var bull = c.c >= c.o;
    ctx.strokeStyle = bull ? '#26a69a' : '#ef5350';
    ctx.fillStyle = bull ? '#26a69a' : '#ef5350';
    var hw = Math.max(1, cw * 0.35);
    ctx.beginPath(); ctx.moveTo(x, yH); ctx.lineTo(x, yL); ctx.stroke();
    var top = Math.min(yO, yC), bot = Math.max(yO, yC);
    ctx.fillRect(x - hw, top, hw * 2, Math.max(1, bot - top));
  }}
  if (entryI != null && entryI >= 0 && entryI < candles.length) {{
    var xe = xIdx(entryI);
    ctx.strokeStyle = 'rgba(255,210,80,0.9)'; ctx.lineWidth = 1.2;
    ctx.setLineDash([4, 3]);
    ctx.beginPath(); ctx.moveTo(xe, pad.t); ctx.lineTo(xe, H - pad.b); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = '#ffd250'; ctx.font = '8px monospace'; ctx.textAlign = 'left';
    ctx.fillText('entry', xe + 2, pad.t + 8);
  }}
  ctx.fillStyle = '#555'; ctx.font = '8px monospace'; ctx.textAlign = 'center';
  var step = Math.max(1, Math.floor(candles.length / 6));
  for (var i = 0; i < candles.length; i += step) {{
    var t = candles[i].t || '';
    ctx.fillText(t.substring(0, 5), xIdx(i), H - 1);
  }}
}}

// localStorage persistence — one key per card_id (5.1 closure bug fixed via let)
function loadCard(cid) {{
  var saved = localStorage.getItem('omen-entry-deck-' + cid);
  if (!saved) {{ updateDot(cid); return; }}
  try {{
    var d = JSON.parse(saved);
    var rs = document.querySelectorAll('input[name="sid-' + cid + '"]');
    for (var i = 0; i < rs.length; i++) if (rs[i].value === d.side) rs[i].checked = true;
    if (d.skip) document.getElementById('skip-' + cid).checked = true;
    if (d.entry_i != null) document.getElementById('entry-' + cid).value = d.entry_i;
    if (d.stop_p != null) document.getElementById('stop-' + cid).value = d.stop_p;
  }} catch(e) {{}}
  updateDot(cid);
}}
function saveCard(cid) {{
  var side = '', skip = false, entry_i = '', stop_p = '';
  var rs = document.querySelectorAll('input[name="sid-' + cid + '"]');
  for (var i = 0; i < rs.length; i++) if (rs[i].checked) side = rs[i].value;
  var sk = document.getElementById('skip-' + cid); if (sk) skip = sk.checked;
  var ei = document.getElementById('entry-' + cid); if (ei) entry_i = ei.value;
  var sp = document.getElementById('stop-' + cid); if (sp) stop_p = sp.value;
  localStorage.setItem('omen-entry-deck-' + cid, JSON.stringify(
    {{ side: side, skip: skip, entry_i: entry_i, stop_p: stop_p }}));
  updateDot(cid); updateStats();
  var cv = document.getElementById('chart-' + cid);
  if (cv && DAY_DATA[cid]) renderCandle(cv, DAY_DATA[cid], entry_i === '' ? null : +entry_i);
}}
function updateDot(cid) {{
  var dot = document.getElementById('dot-' + cid); if (!dot) return;
  var filled = false;
  var sk = document.getElementById('skip-' + cid); if (sk && sk.checked) filled = true;
  var rs = document.querySelectorAll('input[name="sid-' + cid + '"]');
  for (var i = 0; i < rs.length; i++) if (rs[i].checked) filled = true;
  dot.className = filled ? 'status-dot graded' : 'status-dot empty';
}}
function updateStats() {{
  var n = 0;
  for (var ci = 0; ci < CARD_IDS.length; ci++) {{
    var s = localStorage.getItem('omen-entry-deck-' + CARD_IDS[ci]);
    if (s) {{ try {{ var d = JSON.parse(s); if (d.skip || d.side) n++; }} catch(e) {{}} }}
  }}
  document.getElementById('stats').textContent = n + ' / ' + CARD_IDS.length + ' done';
}}
function resetAll() {{
  if (!confirm('Reset all entries for this deck?')) return;
  for (var ci = 0; ci < CARD_IDS.length; ci++) {{
    var cid = CARD_IDS[ci];
    localStorage.removeItem('omen-entry-deck-' + cid);
    var rs = document.querySelectorAll('input[name="sid-' + cid + '"]');
    for (var j = 0; j < rs.length; j++) rs[j].checked = false;
    var sk = document.getElementById('skip-' + cid); if (sk) sk.checked = false;
    var ei = document.getElementById('entry-' + cid); if (ei) ei.value = '';
    var sp = document.getElementById('stop-' + cid); if (sp) sp.value = '';
    updateDot(cid);
  }}
  updateStats();
  for (var ci = 0; ci < CARD_IDS.length; ci++) {{
    var cid = CARD_IDS[ci]; var cv = document.getElementById('chart-' + cid);
    if (cv && DAY_DATA[cid]) renderCandle(cv, DAY_DATA[cid], null);
  }}
}}
function getRows() {{
  var rows = [];
  for (var ci = 0; ci < CARD_IDS.length; ci++) {{
    var cid = CARD_IDS[ci]; var parts = cid.split('_');
    var symbol = parts[0], date = parts[1];
    var side = '', skip = false, entry_i = '', stop_p = '';
    var s = localStorage.getItem('omen-entry-deck-' + cid);
    if (s) {{ try {{ var d = JSON.parse(s);
      side = d.side || ''; skip = !!d.skip; entry_i = d.entry_i || ''; stop_p = d.stop_p || '';
    }} catch(e) {{}} }}
    rows.push({{ card_id: cid, symbol: symbol, date: date,
                side: side, entry_i: entry_i, stop_p: stop_p, skip: skip }});
  }}
  return rows;
}}
function exportJSONL() {{
  var rows = getRows();
  var blob = new Blob([rows.map(function(r){{return JSON.stringify(r);}}).join('\\n')],
                      {{type: 'application/jsonl'}});
  var url = URL.createObjectURL(blob); var a = document.createElement('a');
  a.href = url; a.download = 'entry_marks.jsonl'; a.click(); URL.revokeObjectURL(url);
}}
function copyJSONL() {{
  navigator.clipboard.writeText(
    getRows().map(function(r){{return JSON.stringify(r);}}).join('\\n')
  ).catch(function(){{ alert('Clipboard failed, use download.'); }});
}}
function resizeCanvases() {{
  var cs = document.querySelectorAll('canvas');
  for (var i = 0; i < cs.length; i++) {{
    var r = cs[i].getBoundingClientRect();
    if (r.width > 0) {{ cs[i].width = r.width * (window.devicePixelRatio || 1);
      cs[i].height = 150 * (window.devicePixelRatio || 1); cs[i].style.height = '150px'; }}
  }}
}}
window.addEventListener('load', function() {{
  resizeCanvases();
  for (let ci = 0; ci < CARD_IDS.length; ci++) {{
    let cid = CARD_IDS[ci];
    let cv = document.getElementById('chart-' + cid);
    if (cv && DAY_DATA[cid]) renderCandle(cv, DAY_DATA[cid], null);
    loadCard(cid);
    var rs = document.querySelectorAll('input[name="sid-' + cid + '"]');
    for (let ri = 0; ri < rs.length; ri++)
      rs[ri].addEventListener('change', function(){{ saveCard(cid); }});
    var sk = document.getElementById('skip-' + cid);
    if (sk) sk.addEventListener('change', function(){{ saveCard(cid); }});
    var ei = document.getElementById('entry-' + cid);
    if (ei) ei.addEventListener('input', function(){{ saveCard(cid); }});
    var sp = document.getElementById('stop-' + cid);
    if (sp) sp.addEventListener('input', function(){{ saveCard(cid); }});
    if (cv) cv.addEventListener('click', function(ev){{
      var rect = cv.getBoundingClientRect();
      var x = (ev.clientX - rect.left) * (window.devicePixelRatio || 1);
      var padl = 42 * (window.devicePixelRatio || 1), padr = 10 * (window.devicePixelRatio || 1);
      var n = DAY_DATA[cid] ? DAY_DATA[cid].length : 0;
      var cw = (cv.width - padl - padr) / n;
      var idx = Math.round((x - padl) / cw - 0.5);
      if (idx < 0) idx = 0; if (idx >= n) idx = n - 1;
      document.getElementById('entry-' + cid).value = idx;
      saveCard(cid);
    }});
  }}
  updateStats();
}});
window.addEventListener('resize', function() {{
  resizeCanvases();
  for (let ci = 0; ci < CARD_IDS.length; ci++) {{
    let cid = CARD_IDS[ci]; let cv = document.getElementById('chart-' + cid);
    var ei = document.getElementById('entry-' + cid);
    var v = ei && ei.value !== '' ? +ei.value : null;
    if (cv && DAY_DATA[cid]) renderCandle(cv, DAY_DATA[cid], v);
  }}
}});
</script>
</body>
</html>
"""

# CSS braces clash with str.format; double them so format restores them.
_CSS_ESC = CSS.strip().replace("{", "{{").replace("}", "}}")
ENTRY_TEMPLATE = ENTRY_TEMPLATE_RAW.replace("__CSS__", _CSS_ESC)
BLIND_TEMPLATE_RAW = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OMEN 5.2 Blind Deck</title>
<style>__CSS__</style>
</head>
<body>
<h1>OMEN Blind Deck <span id="deckLabel">{deck_label}</span></h1>
<div class="controls">
  <button onclick="exportJSONL()">Download JSONL</button>
  <button onclick="copyJSONL()">Copy</button>
  <button onclick="resetAll()">Reset All</button>
  <span class="stats" id="stats">0 / {total} done</span>
</div>
<div class="card-grid" id="cardGrid">
{cards}
</div>
<script>
var DAY_DATA = {day_data};
var CARD_IDS = {card_ids};

function renderCandle(canvas, candles) {{
  var ctx = canvas.getContext('2d');
  var W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  if (!candles || candles.length < 2) {{
    ctx.fillStyle = '#555'; ctx.font = '12px monospace'; ctx.textAlign = 'center';
    ctx.fillText('no data', W/2, H/2); return;
  }}
  var pad = {{ t: 8, b: 12, l: 42, r: 10 }};
  var cw = (W - pad.l - pad.r) / candles.length;
  var hi = -Infinity, lo = Infinity;
  for (var i = 0; i < candles.length; i++) {{
    hi = Math.max(hi, candles[i].h); lo = Math.min(lo, candles[i].l);
  }}
  var range = (hi - lo) || 1;
  var yPrice = function(p) {{ return pad.t + (hi - p) / range * (H - pad.t - pad.b); }};
  var xIdx = function(i) {{ return pad.l + i * cw + cw / 2; }};
  ctx.strokeStyle = '#1a2a3a'; ctx.lineWidth = 0.5;
  for (var g = 0; g <= 4; g++) {{
    var yy = pad.t + g * (H - pad.t - pad.b) / 4;
    ctx.beginPath(); ctx.moveTo(pad.l, yy); ctx.lineTo(W - pad.r, yy); ctx.stroke();
    ctx.fillStyle = '#555'; ctx.font = '9px monospace'; ctx.textAlign = 'right';
    ctx.fillText((hi - g * range / 4).toFixed(2), pad.l - 3, yy + 3);
  }}
  for (var i = 0; i < candles.length; i++) {{
    var c = candles[i]; var x = xIdx(i);
    var yO = yPrice(c.o), yH = yPrice(c.h), yL = yPrice(c.l), yC = yPrice(c.c);
    var bull = c.c >= c.o;
    ctx.strokeStyle = bull ? '#26a69a' : '#ef5350';
    ctx.fillStyle = bull ? '#26a69a' : '#ef5350';
    var hw = Math.max(1, cw * 0.35);
    ctx.beginPath(); ctx.moveTo(x, yH); ctx.lineTo(x, yL); ctx.stroke();
    var top = Math.min(yO, yC), bot = Math.max(yO, yC);
    ctx.fillRect(x - hw, top, hw * 2, Math.max(1, bot - top));
  }}
  // mark the engine's fire bar (the last bar shown — engine fired here)
  var li = candles.length - 1; var xf = xIdx(li);
  ctx.strokeStyle = 'rgba(255,210,80,0.8)'; ctx.lineWidth = 1.2; ctx.setLineDash([4, 3]);
  ctx.beginPath(); ctx.moveTo(xf, pad.t); ctx.lineTo(xf, H - pad.b); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = '#ffd250'; ctx.font = '8px monospace'; ctx.textAlign = 'left';
  ctx.fillText('fire', xf + 2, pad.t + 8);
  ctx.fillStyle = '#555'; ctx.font = '8px monospace'; ctx.textAlign = 'center';
  var step = Math.max(1, Math.floor(candles.length / 5));
  for (var i = 0; i < candles.length; i += step) {{
    var t = candles[i].t || '';
    ctx.fillText(t.substring(0, 5), xIdx(i), H - 1);
  }}
}}

function loadCard(cid) {{
  var saved = localStorage.getItem('omen-blind-deck-' + cid);
  if (!saved) {{ updateDot(cid); return; }}
  try {{
    var d = JSON.parse(saved);
    var vs = document.querySelectorAll('input[name="ver-' + cid + '"]');
    for (var i = 0; i < vs.length; i++) if (vs[i].value === d.verdict) vs[i].checked = true;
    var ss = document.querySelectorAll('input[name="sid-' + cid + '"]');
    for (var i = 0; i < ss.length; i++) if (ss[i].value === d.side) ss[i].checked = true;
  }} catch(e) {{}}
  updateDot(cid);
}}
function saveCard(cid) {{
  var verdict = '', side = '';
  var vs = document.querySelectorAll('input[name="ver-' + cid + '"]');
  for (var i = 0; i < vs.length; i++) if (vs[i].checked) verdict = vs[i].value;
  var ss = document.querySelectorAll('input[name="sid-' + cid + '"]');
  for (var i = 0; i < ss.length; i++) if (ss[i].checked) side = ss[i].value;
  localStorage.setItem('omen-blind-deck-' + cid, JSON.stringify({{ verdict: verdict, side: side }}));
  updateDot(cid); updateStats();
}}
function updateDot(cid) {{
  var dot = document.getElementById('dot-' + cid); if (!dot) return;
  var filled = false;
  var vs = document.querySelectorAll('input[name="ver-' + cid + '"]');
  for (var i = 0; i < vs.length; i++) if (vs[i].checked) filled = true;
  dot.className = filled ? 'status-dot graded' : 'status-dot empty';
}}
function updateStats() {{
  var n = 0;
  for (var ci = 0; ci < CARD_IDS.length; ci++) {{
    var s = localStorage.getItem('omen-blind-deck-' + CARD_IDS[ci]);
    if (s) {{ try {{ var d = JSON.parse(s); if (d.verdict) n++; }} catch(e) {{}} }}
  }}
  document.getElementById('stats').textContent = n + ' / ' + CARD_IDS.length + ' done';
}}
function resetAll() {{
  if (!confirm('Reset all marks for this deck?')) return;
  for (var ci = 0; ci < CARD_IDS.length; ci++) {{
    var cid = CARD_IDS[ci];
    localStorage.removeItem('omen-blind-deck-' + cid);
    var vs = document.querySelectorAll('input[name="ver-' + cid + '"]');
    for (var j = 0; j < vs.length; j++) vs[j].checked = false;
    var ss = document.querySelectorAll('input[name="sid-' + cid + '"]');
    for (var j = 0; j < ss.length; j++) ss[j].checked = false;
    updateDot(cid);
  }}
  updateStats();
}}
function getRows() {{
  var rows = [];
  for (var ci = 0; ci < CARD_IDS.length; ci++) {{
    var cid = CARD_IDS[ci];
    var verdict = '', side = '';
    var s = localStorage.getItem('omen-blind-deck-' + cid);
    if (s) {{ try {{ var d = JSON.parse(s);
      verdict = d.verdict || ''; side = d.side || '';
    }} catch(e) {{}} }}
    rows.push({{ card_id: cid, verdict: verdict, side: side }});
  }}
  return rows;
}}
function exportJSONL() {{
  var rows = getRows();
  var blob = new Blob([rows.map(function(r){{return JSON.stringify(r);}}).join('\\n')],
                      {{type: 'application/jsonl'}});
  var url = URL.createObjectURL(blob); var a = document.createElement('a');
  a.href = url; a.download = 'blind_marks.jsonl'; a.click(); URL.revokeObjectURL(url);
}}
function copyJSONL() {{
  navigator.clipboard.writeText(
    getRows().map(function(r){{return JSON.stringify(r);}}).join('\\n')
  ).catch(function(){{ alert('Clipboard failed, use download.'); }});
}}
function resizeCanvases() {{
  var cs = document.querySelectorAll('canvas');
  for (var i = 0; i < cs.length; i++) {{
    var r = cs[i].getBoundingClientRect();
    if (r.width > 0) {{ cs[i].width = r.width * (window.devicePixelRatio || 1);
      cs[i].height = 150 * (window.devicePixelRatio || 1); cs[i].style.height = '150px'; }}
  }}
}}
window.addEventListener('load', function() {{
  resizeCanvases();
  for (let ci = 0; ci < CARD_IDS.length; ci++) {{
    let cid = CARD_IDS[ci];
    let cv = document.getElementById('chart-' + cid);
    if (cv && DAY_DATA[cid]) renderCandle(cv, DAY_DATA[cid]);
    loadCard(cid);
    var vs = document.querySelectorAll('input[name="ver-' + cid + '"]');
    for (let ri = 0; ri < vs.length; ri++)
      vs[ri].addEventListener('change', function(){{ saveCard(cid); }});
    var ss = document.querySelectorAll('input[name="sid-' + cid + '"]');
    for (let ri = 0; ri < ss.length; ri++)
      ss[ri].addEventListener('change', function(){{ saveCard(cid); }});
  }}
  updateStats();
}});
window.addEventListener('resize', function() {{
  resizeCanvases();
  for (let ci = 0; ci < CARD_IDS.length; ci++) {{
    let cid = CARD_IDS[ci]; let cv = document.getElementById('chart-' + cid);
    if (cv && DAY_DATA[cid]) renderCandle(cv, DAY_DATA[cid]);
  }}
}});
</script>
</body>
</html>
"""

BLIND_TEMPLATE = BLIND_TEMPLATE_RAW.replace("__CSS__", _CSS_ESC)


if __name__ == "__main__":
    build_entry_deck()
    build_blind_deck()
