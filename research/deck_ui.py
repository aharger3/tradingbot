"""OMEN Day Deck UI v5.2 — HTML/CSS/JS template for the marking decks.

Single source of truth for the deck front-end. Both t51_build_deck.py (fresh
builds) and retrofit_deck.py (patch an already-generated deck without re-running
the engine) import from here.

Changes vs 5.1
--------------
1. FIXED: save-handler closure bug. In 5.1 every radio/textarea listener was
   created inside a `var cid` loop, so all 60 cards wrote to the LAST card's
   localStorage key. Marks appeared to vanish on reload and exports came back
   blank. Handlers are now bound per-card in an IIFE.
2. FIXED: exportJSONL/copyJSONL joined rows with the two-character sequence
   backslash-n, so the "JSONL" was one single line. Real newlines now.
3. NEW: click-to-mark entry/exit/stop on the canvas, unlimited trades per day.
4. NEW: per-trade side (L/S), source (taken vs missed), setup label, auto R.
5. NEW: day-level day-type and reason-not-taken labels.
6. NEW: Import JSONL — paste marks back in to restore a session.
"""

# Austin's setup vocabulary. value -> dropdown label.
SETUPS = [
    ["BR",      "BR — break and retest"],
    ["OCR",     "OCR — one candle rule"],
    ["BR+OCR",  "BR + OCR — both"],
    ["84",      "84% rule — re-entry after stop-out"],
    ["other",   "other"],
]

REASONS = [
    "no level", "chop / no structure", "too extended", "gap too big",
    "low volume", "news risk", "range too tight", "missed it", "other",
]

DAYTYPES = ["trend", "range", "chop", "reversal", "gap-and-go"]


HTML_HEAD = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OMEN Day Deck</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #1a1a2e; color: #e0e0e0; padding: 16px; }
h1 { text-align: center; margin: 0 0 6px 0; font-size: 18px; color: #ccc; }
h1 span { font-size: 12px; color: #888; }
.howto { text-align: center; font-size: 11px; color: #7f8ca6; margin-bottom: 12px;
         line-height: 1.6; }
.howto kbd { background: #23233f; border: 1px solid #3a3a5c; border-radius: 3px;
             padding: 1px 5px; font-family: monospace; color: #b9c4dd; }
.controls { text-align: center; margin: 8px 0 16px 0; }
.controls button { background: #2d2d5e; color: #e0e0e0; border: 1px solid #444;
                   padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 13px;
                   margin: 0 2px; }
.controls button:hover { background: #3d3d7e; }
.controls .stats { display: inline-block; margin-left: 16px; font-size: 12px; color: #888; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(460px, 1fr));
             gap: 12px; }
.card { background: #16213e; border-radius: 8px; padding: 10px; border: 1px solid #2a2a5e; }
.card.has-trades { border-color: #3f6ea8; }
.card-header { display: flex; justify-content: space-between; align-items: center;
               margin-bottom: 4px; font-size: 12px; }
.card-id { color: #6a9ef0; font-weight: 600; font-family: monospace; font-size: 11px; }
.card-symbol { color: #aaa; font-size: 11px; }
canvas { display: block; width: 100%; height: 180px; border-radius: 4px;
         background: #0d1b2a; cursor: crosshair; }
.mark-bar { display: flex; align-items: center; gap: 6px; margin-top: 5px;
            font-size: 11px; flex-wrap: wrap; }
.mark-hint { color: #7f8ca6; font-family: monospace; }
.mark-hint b { color: #ffcf6a; }
.mini { background: #22224a; color: #cfd6e6; border: 1px solid #3a3a5c; border-radius: 3px;
        font-size: 10px; padding: 2px 6px; cursor: pointer; }
.mini:hover { background: #32325f; }
.mini.on { background: #3f6ea8; border-color: #6a9ef0; color: #fff; }
.trade-list { margin-top: 5px; display: flex; flex-direction: column; gap: 3px; }
.trade-row { display: flex; align-items: center; gap: 5px; font-size: 10px;
             background: #101a33; border: 1px solid #26365c; border-radius: 4px;
             padding: 3px 5px; font-family: monospace; flex-wrap: wrap; }
.trade-row .tno { color: #6a9ef0; font-weight: 700; }
.trade-row .times { color: #aab4cc; }
.trade-row .r-pos { color: #4caf50; font-weight: 700; }
.trade-row .r-neg { color: #f44336; font-weight: 700; }
.trade-row .r-na { color: #666; }
.trade-row .open { color: #ffcf6a; }
.trade-row select { background: #0d1b2a; color: #cfd6e6; border: 1px solid #333;
                    border-radius: 3px; font-size: 10px; padding: 1px 3px; }
.trade-row .del { color: #f44336; cursor: pointer; margin-left: auto; padding: 0 4px; }
.side-L { color: #4caf50; } .side-S { color: #ef5350; }
.src-missed { color: #ffcf6a; }
.card-footer { display: flex; gap: 10px; margin-top: 6px; align-items: flex-start;
               flex-wrap: wrap; }
.grade-group { display: flex; gap: 4px; align-items: center; flex-wrap: wrap; }
.grade-group label { font-size: 11px; color: #aaa; cursor: pointer; padding: 2px 6px;
                     border-radius: 3px; border: 1px solid transparent; }
.grade-group label:hover { border-color: #555; }
.grade-group input { display: none; }
.grade-group input:checked + label { font-weight: 700; }
.grade-group input:checked + label[data-g="S"] { background: #1a4a2a; color: #4caf50; border-color: #4caf50; }
.grade-group input:checked + label[data-g="A"] { background: #2a3a1a; color: #8bc34a; border-color: #8bc34a; }
.grade-group input:checked + label[data-g="C"] { background: #3a2a1a; color: #ff9800; border-color: #ff9800; }
.grade-group input:checked + label[data-g="none"] { background: #2a1a1a; color: #f44336; border-color: #f44336; }
.day-selects { display: flex; gap: 5px; align-items: center; }
.day-selects select { background: #0d1b2a; color: #cfd6e6; border: 1px solid #333;
                      border-radius: 3px; font-size: 10px; padding: 2px 4px; }
.notes-box { flex: 1 1 100%; }
.notes-box textarea { width: 100%; min-height: 34px; background: #0d1b2a; color: #ccc;
                      border: 1px solid #333; border-radius: 3px; padding: 3px 6px;
                      font-size: 11px; resize: vertical; font-family: inherit; }
.notes-box textarea::placeholder { color: #555; }
.status-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%;
              margin-right: 4px; }
.status-dot.graded { background: #4caf50; }
.status-dot.empty { background: #555; }
#importPane { display: none; max-width: 900px; margin: 0 auto 16px auto; }
#importPane textarea { width: 100%; height: 130px; background: #0d1b2a; color: #ccc;
                       border: 1px solid #333; border-radius: 4px; padding: 6px;
                       font-family: monospace; font-size: 11px; }
@media (max-width: 600px) {
  .card-grid { grid-template-columns: 1fr; }
  .card-footer { flex-direction: column; }
}
</style>
</head>
<body>
<h1>OMEN Day Deck <span id="deckLabel">__LABEL__</span></h1>
<p class="howto">
  Click the chart to drop marks: 1st click = <b style="color:#4da6ff">ENTRY</b>,
  2nd click = <b style="color:#bd93f9">EXIT</b> &rarr; that closes trade #1 and the next
  click starts trade #2. Mark as many trades per day as happened.<br>
  <kbd>Shift</kbd>+click = <b style="color:#ff5555">STOP</b> for the current trade (needed for R).
  <kbd>Alt</kbd>+click = undo last mark on that card. Set L/S, taken vs missed, and setup on each trade row.<br>
  Levels drawn on every card:
  <span style="color:#4477aa">— PDH/PDL</span>
  <span style="color:#9b7ede">— PMH/PML</span>
  <span style="color:#e0a458">&middot;&middot; ORH/ORL (5-min)</span>
  &nbsp;Setups: <b>BR</b> break-and-retest &middot; <b>OCR</b> one-candle-rule &middot;
  <b>BR+OCR</b> &middot; <b>84</b> re-entry after stop-out.
</p>
<div class="controls">
  <button onclick="exportJSONL()">📥 Download JSONL</button>
  <button onclick="copyJSONL()">📋 Copy to Clipboard</button>
  <button onclick="toggleImport()">📤 Import / Restore</button>
  <button id="levelsBtn" onclick="toggleLevels()">📏 Levels: on</button>
  <button onclick="resetAll()">🗑️ Reset All</button>
  <span class="stats" id="stats">0 / __TOTAL__ graded &middot; 0 trades</span>
</div>
<div id="importPane">
  <textarea id="importBox" placeholder="Paste a previously exported JSONL here, then press Restore. Existing marks for those card_ids are overwritten."></textarea>
  <div style="text-align:center;margin-top:6px">
    <button class="mini" onclick="doImport()">Restore marks</button>
  </div>
</div>
<div class="card-grid" id="cardGrid">
"""

HTML_PER_CARD = r"""<div class="card" id="card-__CID__" data-id="__CID__">
  <div class="card-header">
    <span class="card-id"><span class="status-dot empty" id="dot-__CID__"></span>__CID__</span>
    <span class="card-symbol">__SYMBOL__</span>
  </div>
  <canvas id="chart-__CID__" height="180"></canvas>
  <div class="mark-bar">
    <span class="mark-hint" id="hint-__CID__">next click: <b>ENTRY #1</b></span>
    <button class="mini" onclick="undoMark('__CID__')">undo</button>
    <button class="mini" onclick="clearTrades('__CID__')">clear trades</button>
  </div>
  <div class="trade-list" id="trades-__CID__"></div>
  <div class="card-footer">
    <div class="grade-group">
      <input type="radio" name="g-__CID__" value="S" id="s-__CID__">
      <label data-g="S" for="s-__CID__">S</label>
      <input type="radio" name="g-__CID__" value="A" id="a-__CID__">
      <label data-g="A" for="a-__CID__">A</label>
      <input type="radio" name="g-__CID__" value="C" id="c-__CID__">
      <label data-g="C" for="c-__CID__">C</label>
      <input type="radio" name="g-__CID__" value="none" id="n-__CID__">
      <label data-g="none" for="n-__CID__">none</label>
    </div>
    <div class="day-selects">
      <select id="daytype-__CID__" title="What kind of day was it?">__DAYTYPE_OPTS__</select>
      <select id="reason-__CID__" title="If no trade: why not?">__REASON_OPTS__</select>
    </div>
    <div class="notes-box">
      <textarea placeholder="What made this a trade (or not)?" id="notes-__CID__" rows="1"></textarea>
    </div>
  </div>
</div>
"""

HTML_SCRIPT_PREAMBLE = r"""</div>
<script>
var DAY_DATA = __DAY_DATA__;
var PRIOR_LEVELS = __PRIOR_LEVELS__;
var CARD_IDS = __CARD_IDS__;
var SETUPS = __SETUPS__;
var STORE_PREFIX = 'omen-deck2-';
var LEGACY_PREFIX = 'omen-deck-';

// MARKS[cid] = { trades: [ {side, src, setup, e:{i,p,t}, x:{i,p,t}|null, stop:{i,p,t}|null} ] }
var MARKS = {};
// MAP[cid] = coordinate mapping produced by the last render of that canvas
var MAP = {};

// The levels Austin watches. [key, colour, on-chart label]
// Dotted = intraday-formed (opening range); dashed = carried in from before the open.
var LEVEL_KEYS = [
  ['pdh', 'rgba(68,119,170,0.55)',  'PDH'],
  ['pdl', 'rgba(68,119,170,0.55)',  'PDL'],
  ['pmh', 'rgba(155,126,222,0.60)', 'PMH'],
  ['pml', 'rgba(155,126,222,0.60)', 'PML'],
  ['orh', 'rgba(224,164,88,0.70)',  'ORH'],
  ['orl', 'rgba(224,164,88,0.70)',  'ORL']
];
var SHOW_LEVELS = (localStorage.getItem('omen-deck2-levels') !== '0');

// ── Canvas rendering ──────────────────────────────────────────────────────

function renderCandle(canvas, candles, levels, cid) {
  var ctx = canvas.getContext('2d');
  var W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  if (!candles || candles.length < 2) {
    ctx.fillStyle = '#555'; ctx.font = '12px monospace';
    ctx.textAlign = 'center'; ctx.fillText('no data', W/2, H/2);
    return;
  }

  var pad = { t: 8, b: 12, l: 45, r: 12 };
  var cw = (W - pad.l - pad.r) / candles.length;

  // price range
  var hi = -Infinity, lo = Infinity;
  for (var i = 0; i < candles.length; i++) {
    var c = candles[i];
    hi = Math.max(hi, c.h); lo = Math.min(lo, c.l);
  }
  // A level far outside the session would squash the candles flat, so only
  // stretch the axis for levels within 35% of the session range. Anything
  // further is pinned to the chart edge with an arrow instead.
  var lv = levels || {};
  var sessHi = hi, sessLo = lo;
  var allow = (sessHi - sessLo || 1) * 0.35;
  if (SHOW_LEVELS) {
    for (var lk = 0; lk < LEVEL_KEYS.length; lk++) {
      var lvv = lv[LEVEL_KEYS[lk][0]];
      if (lvv == null) continue;
      if (lvv <= sessHi + allow && lvv >= sessLo - allow) {
        hi = Math.max(hi, lvv); lo = Math.min(lo, lvv);
      }
    }
  }
  var range = hi - lo || 1;
  var yPrice = function(p) { return pad.t + (hi - p) / range * (H - pad.t - pad.b); };
  var priceAtY = function(y) { return hi - (y - pad.t) / (H - pad.t - pad.b) * range; };
  var xIdx = function(i) { return pad.l + i * cw + cw / 2; };
  var idxAtX = function(x) {
    var i = Math.round((x - pad.l - cw / 2) / cw);
    if (!isFinite(i)) return 0;
    return Math.max(0, Math.min(candles.length - 1, i));
  };
  if (cid) MAP[cid] = { yPrice: yPrice, priceAtY: priceAtY, xIdx: xIdx,
                        idxAtX: idxAtX, pad: pad, H: H, W: W };

  // background grid
  ctx.strokeStyle = '#1a2a3a'; ctx.lineWidth = 0.5;
  for (var g = 0; g <= 4; g++) {
    var yy = pad.t + g * (H - pad.t - pad.b) / 4;
    ctx.beginPath(); ctx.moveTo(pad.l, yy); ctx.lineTo(W - pad.r, yy); ctx.stroke();
    ctx.fillStyle = '#555'; ctx.font = '9px monospace'; ctx.textAlign = 'right';
    var pv = hi - g * range / 4;
    ctx.fillText(pv.toFixed(1), pad.l - 3, yy + 3);
  }

  // watched levels — PDH/PDL, PMH/PML, 5-min ORH/ORL
  if (SHOW_LEVELS) {
    for (var lk = 0; lk < LEVEL_KEYS.length; lk++) {
      var key = LEVEL_KEYS[lk][0], color = LEVEL_KEYS[lk][1], name = LEVEL_KEYS[lk][2];
      var price = lv[key];
      if (price == null) continue;
      var off = (price > hi) ? 1 : (price < lo) ? -1 : 0;
      var ly = off ? (off > 0 ? pad.t + 1 : H - pad.b - 1) : yPrice(price);
      ctx.strokeStyle = color; ctx.lineWidth = 1;
      ctx.setLineDash(off ? [1, 4] : (key.charAt(0) === 'o' ? [1, 2] : [3, 3]));
      ctx.beginPath(); ctx.moveTo(pad.l, ly); ctx.lineTo(W - pad.r, ly); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = color; ctx.font = '8px monospace'; ctx.textAlign = 'right';
      // Off-chart levels get an arrow and their price, so they still inform.
      var text = off ? (name + (off > 0 ? ' \u2191 ' : ' \u2193 ') + price.toFixed(2)) : name;
      ctx.fillText(text, W - pad.r - 1, off > 0 ? ly + 8 : ly - 2);
    }
  }

  // candlesticks
  for (var i = 0; i < candles.length; i++) {
    var c = candles[i];
    var x = xIdx(i);
    var yO = yPrice(c.o), yH = yPrice(c.h), yL = yPrice(c.l), yC = yPrice(c.c);
    var bullish = c.c >= c.o;
    ctx.strokeStyle = bullish ? '#26a69a' : '#ef5350';
    ctx.fillStyle = bullish ? '#26a69a' : '#ef5350';

    var halfW = Math.max(1, cw * 0.35);
    ctx.beginPath(); ctx.moveTo(x, yH); ctx.lineTo(x, yL); ctx.stroke();
    var top = Math.min(yO, yC), bot = Math.max(yO, yC);
    ctx.fillRect(x - halfW, top, halfW * 2, Math.max(1, bot - top));
  }

  // time labels every ~15 min
  ctx.fillStyle = '#555'; ctx.font = '8px monospace'; ctx.textAlign = 'center';
  var step = Math.max(1, Math.floor(candles.length / 6));
  for (var i = 0; i < candles.length; i += step) {
    var t = candles[i].t;
    var label = t.substring(t.length - 8, t.length - 3);
    ctx.fillText(label, xIdx(i), H - 1);
  }

  if (cid) drawMarks(cid, ctx);
}

// ── Mark overlay ──────────────────────────────────────────────────────────

function drawMarks(cid, ctx) {
  var m = MARKS[cid];
  var map = MAP[cid];
  if (!m || !map || !m.trades.length) return;
  var dpr = window.devicePixelRatio || 1;

  for (var ti = 0; ti < m.trades.length; ti++) {
    var t = m.trades[ti];
    var no = String(ti + 1);

    if (t.stop) {
      var ys = map.yPrice(t.stop.p);
      ctx.strokeStyle = 'rgba(255,85,85,0.8)'; ctx.lineWidth = 1 * dpr;
      ctx.setLineDash([4 * dpr, 3 * dpr]);
      ctx.beginPath(); ctx.moveTo(map.pad.l, ys); ctx.lineTo(map.W - map.pad.r, ys); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = '#ff5555'; ctx.font = (8 * dpr) + 'px monospace'; ctx.textAlign = 'left';
      ctx.fillText('S' + no, map.pad.l + 2, ys - 2 * dpr);
    }

    if (t.e && t.x) {
      var x1 = map.xIdx(t.e.i), y1 = map.yPrice(t.e.p);
      var x2 = map.xIdx(t.x.i), y2 = map.yPrice(t.x.p);
      var win = (t.side === 'S') ? (t.x.p < t.e.p) : (t.x.p > t.e.p);
      ctx.strokeStyle = win ? 'rgba(76,175,80,0.75)' : 'rgba(244,67,54,0.75)';
      ctx.lineWidth = 1.5 * dpr;
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    }

    if (t.e) markDot(ctx, map, t.e, '#4da6ff', 'E' + no, dpr);
    if (t.x) markDot(ctx, map, t.x, '#bd93f9', 'X' + no, dpr);
  }
}

function markDot(ctx, map, pt, color, label, dpr) {
  var x = map.xIdx(pt.i), y = map.yPrice(pt.p);
  var r = 3.5 * dpr;
  ctx.fillStyle = color;
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = '#0d1b2a'; ctx.lineWidth = 1 * dpr; ctx.stroke();
  ctx.fillStyle = color; ctx.font = 'bold ' + (9 * dpr) + 'px monospace';
  ctx.textAlign = 'center';
  ctx.fillText(label, x, y - 6 * dpr);
}

function repaint(cid) {
  var canvas = document.getElementById('chart-' + cid);
  if (!canvas || !DAY_DATA[cid]) return;
  renderCandle(canvas, DAY_DATA[cid], PRIOR_LEVELS[cid] || {}, cid);
}

function toggleLevels() {
  SHOW_LEVELS = !SHOW_LEVELS;
  localStorage.setItem('omen-deck2-levels', SHOW_LEVELS ? '1' : '0');
  var b = document.getElementById('levelsBtn');
  if (b) b.textContent = SHOW_LEVELS ? '📏 Levels: on' : '📏 Levels: off';
  for (var ci = 0; ci < CARD_IDS.length; ci++) repaint(CARD_IDS[ci]);
}

// ── Click-to-mark ─────────────────────────────────────────────────────────

function ensureMarks(cid) {
  if (!MARKS[cid]) MARKS[cid] = { trades: [] };
  return MARKS[cid];
}

function openTrade(cid) {
  var m = ensureMarks(cid);
  if (!m.trades.length) return null;
  var last = m.trades[m.trades.length - 1];
  return last.x ? null : last;
}

function onCanvasClick(cid, ev) {
  var canvas = document.getElementById('chart-' + cid);
  var map = MAP[cid];
  var candles = DAY_DATA[cid];
  if (!canvas || !map || !candles || !candles.length) return;

  var rect = canvas.getBoundingClientRect();
  var dpr = window.devicePixelRatio || 1;
  var x = (ev.clientX - rect.left) * (canvas.width / rect.width);
  var y = (ev.clientY - rect.top) * (canvas.height / rect.height);

  if (ev.altKey) { undoMark(cid); return; }

  var i = map.idxAtX(x);
  var price = Math.round(map.priceAtY(y) * 10000) / 10000;
  if (!isFinite(price)) price = candles[i].c;
  var pt = { i: i, p: price, t: candles[i].t };
  var m = ensureMarks(cid);
  var open = openTrade(cid);

  if (ev.shiftKey) {
    // stop for the current (or most recent) trade
    var target = open || m.trades[m.trades.length - 1];
    if (!target) return;             // nothing to attach a stop to yet
    target.stop = pt;
  } else if (!open) {
    m.trades.push({ side: '', src: 'taken', setup: '', e: pt, x: null, stop: null });
  } else {
    open.x = pt;
    if (!open.side) open.side = inferSide(open);
  }
  saveCard(cid);
  renderTrades(cid);
  repaint(cid);
  updateHint(cid);
}

function inferSide(t) {
  if (t.stop) return (t.stop.p < t.e.p) ? 'L' : 'S';
  if (t.x) return (t.x.p >= t.e.p) ? 'L' : 'S';
  return 'L';
}

function undoMark(cid) {
  var m = ensureMarks(cid);
  if (!m.trades.length) return;
  var last = m.trades[m.trades.length - 1];
  if (last.stop) last.stop = null;
  else if (last.x) last.x = null;
  else m.trades.pop();
  saveCard(cid); renderTrades(cid); repaint(cid); updateHint(cid);
}

function clearTrades(cid) {
  MARKS[cid] = { trades: [] };
  saveCard(cid); renderTrades(cid); repaint(cid); updateHint(cid);
}

function delTrade(cid, ti) {
  var m = ensureMarks(cid);
  m.trades.splice(ti, 1);
  saveCard(cid); renderTrades(cid); repaint(cid); updateHint(cid);
}

function setTradeField(cid, ti, field, val) {
  var m = ensureMarks(cid);
  if (!m.trades[ti]) return;
  m.trades[ti][field] = val;
  saveCard(cid); renderTrades(cid); repaint(cid);
}

function cycleSide(cid, ti) {
  var t = MARKS[cid].trades[ti];
  setTradeField(cid, ti, 'side', t.side === 'L' ? 'S' : 'L');
}

function cycleSrc(cid, ti) {
  var t = MARKS[cid].trades[ti];
  setTradeField(cid, ti, 'src', t.src === 'taken' ? 'missed' : 'taken');
}

function updateHint(cid) {
  var el = document.getElementById('hint-' + cid);
  if (!el) return;
  var m = ensureMarks(cid);
  var open = openTrade(cid);
  var n = m.trades.length;
  if (open) el.innerHTML = 'next click: <b>EXIT #' + n + '</b>' +
      (open.stop ? '' : ' &middot; shift+click = stop');
  else el.innerHTML = 'next click: <b>ENTRY #' + (n + 1) + '</b>';
  var card = document.getElementById('card-' + cid);
  if (card) card.className = n ? 'card has-trades' : 'card';
}

function rMultiple(t) {
  if (!t.e || !t.x || !t.stop) return null;
  var risk = (t.side === 'S') ? (t.stop.p - t.e.p) : (t.e.p - t.stop.p);
  if (!risk || risk <= 0) return null;
  var pnl = (t.side === 'S') ? (t.e.p - t.x.p) : (t.x.p - t.e.p);
  return Math.round(pnl / risk * 100) / 100;
}

function hhmm(ts) { return ts ? ts.substring(ts.length - 8, ts.length - 3) : '--:--'; }

function renderTrades(cid) {
  var box = document.getElementById('trades-' + cid);
  if (!box) return;
  var m = ensureMarks(cid);
  var html = '';
  for (var ti = 0; ti < m.trades.length; ti++) {
    var t = m.trades[ti];
    var side = t.side || inferSide(t);
    var r = rMultiple(t);
    var rHtml = (r === null)
      ? '<span class="r-na">' + (t.x ? 'no stop' : 'open') + '</span>'
      : '<span class="' + (r >= 0 ? 'r-pos' : 'r-neg') + '">' +
        (r >= 0 ? '+' : '') + r.toFixed(2) + 'R</span>';
    var opts = '<option value="">setup?</option>';
    for (var si = 0; si < SETUPS.length; si++) {
      var sv = SETUPS[si][0], sl = SETUPS[si][1];
      opts += '<option value="' + sv + '"' +
              (t.setup === sv ? ' selected' : '') + '>' + sl + '</option>';
    }
    html += '<div class="trade-row">' +
      '<span class="tno">#' + (ti + 1) + '</span>' +
      '<span class="mini side-' + side + '" onclick="cycleSide(\'' + cid + '\',' + ti + ')">' + side + '</span>' +
      '<span class="mini ' + (t.src === 'missed' ? 'src-missed' : '') + '" onclick="cycleSrc(\'' + cid + '\',' + ti + ')">' + t.src + '</span>' +
      '<span class="times">' + hhmm(t.e && t.e.t) + '&rarr;' + (t.x ? hhmm(t.x.t) : '<span class="open">open</span>') + '</span>' +
      rHtml +
      '<select onchange="setTradeField(\'' + cid + '\',' + ti + ',\'setup\',this.value)">' + opts + '</select>' +
      '<span class="del" onclick="delTrade(\'' + cid + '\',' + ti + ')">&#10005;</span>' +
      '</div>';
  }
  box.innerHTML = html;
}

// ── localStorage persistence ──────────────────────────────────────────────

function cardState(cid) {
  var grade = '';
  var radios = document.querySelectorAll('input[name="g-' + cid + '"]');
  for (var i = 0; i < radios.length; i++) {
    if (radios[i].checked) { grade = radios[i].value; break; }
  }
  var notes = document.getElementById('notes-' + cid);
  var dt = document.getElementById('daytype-' + cid);
  var rs = document.getElementById('reason-' + cid);
  return {
    grade: grade,
    notes: notes ? notes.value : '',
    day_type: dt ? dt.value : '',
    reason_none: rs ? rs.value : '',
    trades: (MARKS[cid] || {trades: []}).trades
  };
}

function applyState(cid, data) {
  if (!data) return;
  var radios = document.querySelectorAll('input[name="g-' + cid + '"]');
  for (var i = 0; i < radios.length; i++) {
    radios[i].checked = (radios[i].value === data.grade);
  }
  var notes = document.getElementById('notes-' + cid);
  if (notes) notes.value = data.notes || '';
  var dt = document.getElementById('daytype-' + cid);
  if (dt) dt.value = data.day_type || '';
  var rs = document.getElementById('reason-' + cid);
  if (rs) rs.value = data.reason_none || '';
  MARKS[cid] = { trades: (data.trades || []) };
}

function loadCard(cid) {
  var saved = localStorage.getItem(STORE_PREFIX + cid);
  if (!saved) {
    // migrate a v5.1 record if one is sitting there
    var legacy = localStorage.getItem(LEGACY_PREFIX + cid);
    if (legacy) { try { applyState(cid, JSON.parse(legacy)); } catch(e) {} }
  } else {
    try { applyState(cid, JSON.parse(saved)); } catch(e) {}
  }
  renderTrades(cid);
  updateDot(cid);
  updateHint(cid);
}

function saveCard(cid) {
  try {
    localStorage.setItem(STORE_PREFIX + cid, JSON.stringify(cardState(cid)));
  } catch (e) {
    alert('Browser storage is full or blocked — marks are NOT being saved. ' +
          'Export to JSONL now before you lose them.');
  }
  updateDot(cid);
  updateStats();
}

function updateDot(cid) {
  var dot = document.getElementById('dot-' + cid);
  if (!dot) return;
  var st = cardState(cid);
  dot.className = (st.grade || st.trades.length) ? 'status-dot graded' : 'status-dot empty';
}

function updateStats() {
  var graded = 0, trades = 0;
  for (var ci = 0; ci < CARD_IDS.length; ci++) {
    var saved = localStorage.getItem(STORE_PREFIX + CARD_IDS[ci]);
    if (!saved) continue;
    try {
      var d = JSON.parse(saved);
      if (d.grade) graded++;
      trades += (d.trades || []).length;
    } catch(e) {}
  }
  document.getElementById('stats').textContent =
    graded + ' / ' + CARD_IDS.length + ' graded · ' + trades + ' trades marked';
}

function resetAll() {
  if (!confirm('Reset all grades, notes and trade marks for this deck?')) return;
  for (var ci = 0; ci < CARD_IDS.length; ci++) {
    var cid = CARD_IDS[ci];
    localStorage.removeItem(STORE_PREFIX + cid);
    localStorage.removeItem(LEGACY_PREFIX + cid);
    MARKS[cid] = { trades: [] };
    applyState(cid, { grade: '', notes: '', day_type: '', reason_none: '', trades: [] });
    renderTrades(cid); repaint(cid); updateDot(cid); updateHint(cid);
  }
  updateStats();
}

// ── Export / import ───────────────────────────────────────────────────────

function getRows() {
  var rows = [];
  for (var ci = 0; ci < CARD_IDS.length; ci++) {
    var cid = CARD_IDS[ci];
    var us = cid.lastIndexOf('_');
    var symbol = cid.substring(0, us), date = cid.substring(us + 1);
    var st = cardState(cid);
    if (!st.grade && !st.notes && !st.day_type && !st.reason_none && !st.trades.length) continue;

    rows.push({
      type: 'day', card_id: cid, symbol: symbol, date: date,
      grade: st.grade, day_type: st.day_type,
      reason_none: st.grade === 'none' ? st.reason_none : '',
      n_trades: st.trades.length, notes: st.notes
    });

    for (var ti = 0; ti < st.trades.length; ti++) {
      var t = st.trades[ti];
      rows.push({
        type: 'trade', card_id: cid, symbol: symbol, date: date,
        trade_no: ti + 1,
        side: t.side || inferSide(t),
        source: t.src || 'taken',
        setup: t.setup || '',
        entry_i: t.e ? t.e.i : null, entry_t: t.e ? t.e.t : null, entry_p: t.e ? t.e.p : null,
        exit_i: t.x ? t.x.i : null, exit_t: t.x ? t.x.t : null, exit_p: t.x ? t.x.p : null,
        stop_i: t.stop ? t.stop.i : null, stop_t: t.stop ? t.stop.t : null,
        stop_p: t.stop ? t.stop.p : null,
        r_multiple: rMultiple(t)
      });
    }
  }
  return rows;
}

function jsonlText() {
  return getRows().map(function(r) { return JSON.stringify(r); }).join('\n');
}

function exportJSONL() {
  var blob = new Blob([jsonlText() + '\n'], {type: 'application/x-ndjson'});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url; a.download = 'deck_marks.jsonl';
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
}

function copyJSONL() {
  var txt = jsonlText();
  if (!txt) { alert('Nothing marked yet.'); return; }
  navigator.clipboard.writeText(txt).then(function() {
    alert(getRows().length + ' rows copied as JSONL.');
  }).catch(function() {
    var ta = document.getElementById('importBox');
    document.getElementById('importPane').style.display = 'block';
    ta.value = txt; ta.select();
    alert('Clipboard blocked. The JSONL is in the box below — copy it manually.');
  });
}

function toggleImport() {
  var p = document.getElementById('importPane');
  p.style.display = (p.style.display === 'block') ? 'none' : 'block';
}

function doImport() {
  var txt = document.getElementById('importBox').value.trim();
  if (!txt) return;
  var lines = txt.split(/\r?\n/);
  var byCard = {};
  var bad = 0;
  for (var i = 0; i < lines.length; i++) {
    if (!lines[i].trim()) continue;
    var r;
    try { r = JSON.parse(lines[i]); } catch(e) { bad++; continue; }
    if (!r.card_id) { bad++; continue; }
    if (!byCard[r.card_id]) {
      byCard[r.card_id] = { grade: '', notes: '', day_type: '', reason_none: '', trades: [] };
    }
    var b = byCard[r.card_id];
    if (r.type === 'day') {
      b.grade = r.grade || ''; b.notes = r.notes || '';
      b.day_type = r.day_type || ''; b.reason_none = r.reason_none || '';
    } else if (r.type === 'trade') {
      b.trades.push({
        side: r.side || '', src: r.source || 'taken', setup: r.setup || '',
        e: r.entry_i == null ? null : { i: r.entry_i, p: r.entry_p, t: r.entry_t },
        x: r.exit_i == null ? null : { i: r.exit_i, p: r.exit_p, t: r.exit_t },
        stop: r.stop_i == null ? null : { i: r.stop_i, p: r.stop_p, t: r.stop_t }
      });
    }
  }
  var n = 0;
  for (var cid in byCard) {
    if (DAY_DATA[cid] === undefined) continue;   // not a card in this deck
    applyState(cid, byCard[cid]);
    saveCard(cid); renderTrades(cid); repaint(cid); updateHint(cid);
    n++;
  }
  updateStats();
  alert('Restored ' + n + ' cards.' + (bad ? ' (' + bad + ' unparseable lines skipped)' : ''));
}

// ── Init ──────────────────────────────────────────────────────────────────

function resizeCanvases() {
  var canvases = document.querySelectorAll('canvas');
  var dpr = window.devicePixelRatio || 1;
  for (var i = 0; i < canvases.length; i++) {
    var rect = canvases[i].getBoundingClientRect();
    if (rect.width > 0) {
      canvases[i].width = rect.width * dpr;
      canvases[i].height = 180 * dpr;
      canvases[i].style.height = '180px';
    }
  }
}

function wireCard(cid) {
  // NOTE: bound per-card. In 5.1 these handlers closed over a loop `var`, so
  // every card saved into the LAST card's key and marks appeared to vanish.
  var radios = document.querySelectorAll('input[name="g-' + cid + '"]');
  for (var ri = 0; ri < radios.length; ri++) {
    radios[ri].addEventListener('change', function() { saveCard(cid); });
  }
  var notes = document.getElementById('notes-' + cid);
  if (notes) notes.addEventListener('input', function() { saveCard(cid); });
  var dt = document.getElementById('daytype-' + cid);
  if (dt) dt.addEventListener('change', function() { saveCard(cid); });
  var rs = document.getElementById('reason-' + cid);
  if (rs) rs.addEventListener('change', function() { saveCard(cid); });
  var canvas = document.getElementById('chart-' + cid);
  if (canvas) canvas.addEventListener('click', function(ev) { onCanvasClick(cid, ev); });
}

window.addEventListener('load', function() {
  resizeCanvases();
  for (var ci = 0; ci < CARD_IDS.length; ci++) {
    (function(cid) {
      loadCard(cid);
      repaint(cid);
      wireCard(cid);
    })(CARD_IDS[ci]);
  }
  updateStats();
});

window.addEventListener('resize', function() {
  resizeCanvases();
  for (var ci = 0; ci < CARD_IDS.length; ci++) repaint(CARD_IDS[ci]);
});

// Last-ditch guard: warn if leaving with unexported marks.
window.addEventListener('beforeunload', function(e) {
  if (getRows().length) { e.preventDefault(); e.returnValue = ''; }
});
</script>
</body>
</html>
"""


def _opts(values, placeholder):
    out = ['<option value="">%s</option>' % placeholder]
    out += ['<option value="%s">%s</option>' % (v, v) for v in values]
    return "".join(out)


def render_card(cid: str, symbol: str) -> str:
    html = HTML_PER_CARD
    html = html.replace("__DAYTYPE_OPTS__", _opts(DAYTYPES, "day type?"))
    html = html.replace("__REASON_OPTS__", _opts(REASONS, "why no trade?"))
    html = html.replace("__CID__", cid)
    html = html.replace("__SYMBOL__", symbol)
    return html
