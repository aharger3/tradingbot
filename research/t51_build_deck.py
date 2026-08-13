"""omen-5.1 T6: Build two self-contained HTML day-decks + manifest.

Usage: python research/t51_build_deck.py

Generates:
  research/omen-5.1-tsla-day-deck.html    — 60 most recent TSLA trading days
  research/omen-5.1-index-day-deck.html   — 30 most recent QQQ + 30 most recent SPY
  research/t51_day_deck_manifest.jsonl     — 120 rows with engine fire counts

Both decks export grades as JSONL via download and clipboard, persist via
localStorage, and show NO engine-derived overlays.
"""

from __future__ import annotations
import csv
import glob
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from research.t4_engine_recall import run_day, rth_candles

ARCHIVE = os.path.join(ROOT, "data_archive")
TSLA_DECK = os.path.join(HERE, "omen-5.1-tsla-day-deck.html")
INDEX_DECK = os.path.join(HERE, "omen-5.1-index-day-deck.html")
MANIFEST = os.path.join(HERE, "t51_day_deck_manifest.jsonl")

# 09:30-11:00 ET session window
SESSION_START = "09:30"
SESSION_END = "11:00"


def _trading_days(symbol: str) -> list[str]:
    """All archived trading days for a symbol, sorted ascending."""
    pat = os.path.join(ARCHIVE, symbol, "*.csv")
    names = sorted(os.path.basename(f)[:-4] for f in glob.glob(pat))
    return names


def _to_min(ts: str) -> str:
    """Extract HH:MM from ISO timestamp."""
    return ts[11:16] if "T" in ts else ts[:5]


def _filter_session(candles) -> list:
    """Return candles in 09:30-11:00 ET window."""
    out = []
    for c in candles:
        t = _to_min(c.timestamp)
        if SESSION_START <= t < SESSION_END:
            out.append(c)
    return out


def _load_session_candles(symbol: str, day: str) -> list:
    """Load 09:30-11:00 1-min candles for (symbol, day)."""
    candles = rth_candles(symbol, day)
    if not candles:
        return []
    return _filter_session(candles)


def _candle_to_dict(c) -> dict:
    return {
        "t": c.timestamp,
        "o": round(c.open, 2),
        "h": round(c.high, 2),
        "l": round(c.low, 2),
        "c": round(c.close, 2),
        "v": int(c.volume),
    }


def _engine_fire_count(symbol: str, day: str) -> int:
    """Count how many signals the engine fires (accepts) on this (symbol, day).

    Uses run_day from t4_engine_recall which already replays bar-by-bar with
    deduplication. Returns 0 when the engine cannot run (no archived data).
    """
    entries, all_sigs, _raw = run_day(symbol, day)
    if entries is None:
        return 0
    return len(entries)


# ── HTML template parts ──────────────────────────────────────────────────────

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
h1 { text-align: center; margin: 0 0 16px 0; font-size: 18px; color: #ccc; }
h1 span { font-size: 12px; color: #888; }
.controls { text-align: center; margin: 8px 0 16px 0; }
.controls button { background: #2d2d5e; color: #e0e0e0; border: 1px solid #444;
                   padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.controls button:hover { background: #3d3d7e; }
.controls .stats { display: inline-block; margin-left: 16px; font-size: 12px; color: #888; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
             gap: 12px; }
.card { background: #16213e; border-radius: 8px; padding: 10px; border: 1px solid #2a2a5e; }
.card-header { display: flex; justify-content: space-between; align-items: center;
               margin-bottom: 4px; font-size: 12px; }
.card-id { color: #6a9ef0; font-weight: 600; font-family: monospace; font-size: 11px; }
.card-symbol { color: #aaa; font-size: 11px; }
canvas { display: block; width: 100%; height: 180px; border-radius: 4px;
         background: #0d1b2a; cursor: crosshair; }
.card-footer { display: flex; gap: 12px; margin-top: 6px; align-items: flex-start; }
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
.notes-box { flex: 1; }
.notes-box textarea { width: 100%; min-height: 36px; background: #0d1b2a; color: #ccc;
                      border: 1px solid #333; border-radius: 3px; padding: 3px 6px;
                      font-size: 11px; resize: vertical; font-family: inherit; }
.notes-box textarea::placeholder { color: #555; }
.status-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%;
              margin-right: 4px; }
.status-dot.graded { background: #4caf50; }
.status-dot.empty { background: #555; }
.pdh-line { position: relative; pointer-events: none; }
.prior-line-label { font-size: 9px; color: #4477aa; opacity: 0.7; }
@media (max-width: 600px) {
  .card-grid { grid-template-columns: 1fr; }
  .card-footer { flex-direction: column; }
}
</style>
</head>
<body>
<h1>OMEN Day Deck <span id="deckLabel">__LABEL__</span></h1>
<div class="controls">
  <button onclick="exportJSONL()">📥 Download JSONL</button>
  <button onclick="copyJSONL()">📋 Copy to Clipboard</button>
  <button onclick="resetAll()">🗑️ Reset All</button>
  <span class="stats" id="stats">0 / __TOTAL__ graded</span>
</div>
<div class="card-grid" id="cardGrid">
"""

HTML_PER_CARD = r"""<div class="card" data-id="__CID__">
  <div class="card-header">
    <span class="card-id"><span class="status-dot empty" id="dot-__CID__"></span>__CID__</span>
    <span class="card-symbol">__SYMBOL__</span>
  </div>
  <canvas id="chart-__CID__" height="180"></canvas>
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

// ── Canvas rendering ──────────────────────────────────────────────────────

function renderCandle(canvas, candles, priorHi, priorLo) {
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
  if (priorHi != null) hi = Math.max(hi, priorHi);
  if (priorLo != null) lo = Math.min(lo, priorLo);
  var range = hi - lo || 1;
  var yPrice = function(p) { return pad.t + (hi - p) / range * (H - pad.t - pad.b); };
  var xIdx = function(i) { return pad.l + i * cw + cw / 2; };

  // background grid
  ctx.strokeStyle = '#1a2a3a'; ctx.lineWidth = 0.5;
  for (var g = 0; g <= 4; g++) {
    var yy = pad.t + g * (H - pad.t - pad.b) / 4;
    ctx.beginPath(); ctx.moveTo(pad.l, yy); ctx.lineTo(W - pad.r, yy); ctx.stroke();
    ctx.fillStyle = '#555'; ctx.font = '9px monospace'; ctx.textAlign = 'right';
    var pv = hi - g * range / 4;
    ctx.fillText(pv.toFixed(1), pad.l - 3, yy + 3);
  }

  // prior-day high/low lines
  var priorDrawn = {};
  if (priorHi != null) {
    var yh = yPrice(priorHi);
    ctx.strokeStyle = 'rgba(68, 119, 170, 0.35)'; ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
    ctx.beginPath(); ctx.moveTo(pad.l, yh); ctx.lineTo(W - pad.r, yh); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = 'rgba(68, 119, 170, 0.5)'; ctx.font = '8px monospace'; ctx.textAlign = 'left';
    ctx.fillText('PDH', W - pad.r - 20, yh - 2);
    priorDrawn['PDH'] = true;
  }
  if (priorLo != null && !priorDrawn['PDL']) {
    var yl = yPrice(priorLo);
    ctx.strokeStyle = 'rgba(68, 119, 170, 0.35)'; ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
    ctx.beginPath(); ctx.moveTo(pad.l, yl); ctx.lineTo(W - pad.r, yl); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = 'rgba(68, 119, 170, 0.5)'; ctx.font = '8px monospace'; ctx.textAlign = 'left';
    ctx.fillText('PDL', W - pad.r - 20, yl - 2);
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
    // wick
    ctx.beginPath(); ctx.moveTo(x, yH); ctx.lineTo(x, yL); ctx.stroke();
    // body
    var top = Math.min(yO, yC), bot = Math.max(yO, yC);
    ctx.fillRect(x - halfW, top, halfW * 2, Math.max(1, bot - top));
  }

  // time labels every ~15 min
  ctx.fillStyle = '#555'; ctx.font = '8px monospace'; ctx.textAlign = 'center';
  var step = Math.max(1, Math.floor(candles.length / 6));
  for (var i = 0; i < candles.length; i += step) {
    var t = candles[i].t;
    var label = t.substring(t.length - 8, t.length - 3);
    var xx = xIdx(i);
    ctx.fillText(label, xx, H - 1);
  }
}

// ── localStorage persistence ──────────────────────────────────────────────

function loadCard(cid) {
  var key = 'omen-deck-' + cid;
  var saved = localStorage.getItem(key);
  if (saved) {
    try {
      var data = JSON.parse(saved);
      var radios = document.querySelectorAll('input[name="g-' + cid + '"]');
      for (var i = 0; i < radios.length; i++) {
        if (radios[i].value === data.grade) {
          radios[i].checked = true;
          break;
        }
      }
      var notes = document.getElementById('notes-' + cid);
      if (notes && data.notes) notes.value = data.notes;
      updateDot(cid);
    } catch(e) {}
  }
}

function saveCard(cid) {
  var key = 'omen-deck-' + cid;
  var grade = '';
  var radios = document.querySelectorAll('input[name="g-' + cid + '"]');
  for (var i = 0; i < radios.length; i++) {
    if (radios[i].checked) { grade = radios[i].value; break; }
  }
  var notes = document.getElementById('notes-' + cid);
  var data = { grade: grade, notes: notes ? notes.value : '' };
  localStorage.setItem(key, JSON.stringify(data));
  updateDot(cid);
  updateStats();
}

function updateDot(cid) {
  var dot = document.getElementById('dot-' + cid);
  if (!dot) return;
  var radios = document.querySelectorAll('input[name="g-' + cid + '"]');
  for (var i = 0; i < radios.length; i++) {
    if (radios[i].checked && radios[i].value !== '') {
      dot.className = 'status-dot graded';
      return;
    }
  }
  dot.className = 'status-dot empty';
}

function updateStats() {
  var graded = 0;
  for (var ci = 0; ci < CARD_IDS.length; ci++) {
    var key = 'omen-deck-' + CARD_IDS[ci];
    var saved = localStorage.getItem(key);
    if (saved) {
      try {
        var d = JSON.parse(saved);
        if (d.grade && d.grade !== '') graded++;
      } catch(e) {}
    }
  }
  document.getElementById('stats').textContent = graded + ' / ' + CARD_IDS.length + ' graded';
}

function resetAll() {
  if (!confirm('Reset all grades and notes for this deck?')) return;
  for (var ci = 0; ci < CARD_IDS.length; ci++) {
    localStorage.removeItem('omen-deck-' + CARD_IDS[ci]);
    var cid = CARD_IDS[ci];
    var radios = document.querySelectorAll('input[name="g-' + cid + '"]');
    for (var j = 0; j < radios.length; j++) radios[j].checked = false;
    var notes = document.getElementById('notes-' + cid);
    if (notes) notes.value = '';
    updateDot(cid);
  }
  updateStats();
}

// ── Export ────────────────────────────────────────────────────────────────

function getRows() {
  var rows = [];
  for (var ci = 0; ci < CARD_IDS.length; ci++) {
    var cid = CARD_IDS[ci];
    var parts = cid.split('_');
    var symbol = parts[0], date = parts[1];
    var key = 'omen-deck-' + cid;
    var saved = localStorage.getItem(key);
    var grade = '', notes = '';
    if (saved) {
      try { var d = JSON.parse(saved); grade = d.grade || ''; notes = d.notes || ''; } catch(e) {}
    }
    var entry_i = '';
    if (grade === 'none') { grade = 'none'; entry_i = ''; }
    rows.push({ card_id: cid, symbol: symbol, date: date, grade: grade, entry_i: entry_i, notes: notes });
  }
  return rows;
}

function exportJSONL() {
  var rows = getRows();
  var jsonl = rows.map(function(r) { return JSON.stringify(r); }).join('\\n');
  var blob = new Blob([jsonl], {type: 'application/jsonl'});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url; a.download = 'deck_grades.jsonl'; a.click();
  URL.revokeObjectURL(url);
}

function copyJSONL() {
  var rows = getRows();
  var jsonl = rows.map(function(r) { return JSON.stringify(r); }).join('\\n');
  navigator.clipboard.writeText(jsonl).catch(function(e) {
    alert('Clipboard copy failed, use download instead.');
  });
}

// ── Init ──────────────────────────────────────────────────────────────────

// Resize canvas to match CSS display size
function resizeCanvases() {
  var canvases = document.querySelectorAll('canvas');
  for (var i = 0; i < canvases.length; i++) {
    var rect = canvases[i].getBoundingClientRect();
    if (rect.width > 0) {
      canvases[i].width = rect.width * (window.devicePixelRatio || 1);
      canvases[i].height = 180 * (window.devicePixelRatio || 1);
      canvases[i].style.height = '180px';
    }
  }
}

window.addEventListener('load', function() {
  resizeCanvases();
  // Render each card's chart
  for (var ci = 0; ci < CARD_IDS.length; ci++) {
    var cid = CARD_IDS[ci];
    var canvas = document.getElementById('chart-' + cid);
    if (canvas && DAY_DATA[cid]) {
      var pl = PRIOR_LEVELS[cid] || {};
      renderCandle(canvas, DAY_DATA[cid], pl.pdh, pl.pdl);
    }
    loadCard(cid);
    // wire up save events
    var radios = document.querySelectorAll('input[name="g-' + cid + '"]');
    for (var ri = 0; ri < radios.length; ri++) {
      radios[ri].addEventListener('change', function() { saveCard(cid); });
    }
    var notes = document.getElementById('notes-' + cid);
    if (notes) {
      notes.addEventListener('input', function() { saveCard(cid); });
    }
  }
  updateStats();
});

window.addEventListener('resize', function() {
  resizeCanvases();
  for (var ci = 0; ci < CARD_IDS.length; ci++) {
    var cid = CARD_IDS[ci];
    var canvas = document.getElementById('chart-' + cid);
    if (canvas && DAY_DATA[cid]) {
      var pl = PRIOR_LEVELS[cid] || {};
      renderCandle(canvas, DAY_DATA[cid], pl.pdh, pl.pdl);
    }
  }
});
</script>
</body>
</html>
"""


def build_deck(days: list[tuple[str, str, list, float, float]],
               label: str, out_path: str) -> None:
    """Build a self-contained HTML deck.

    days: list of (symbol, date, session_candles, prior_hi, prior_lo)
    Each card shows the pure 09:30-11:00 candlestick chart with NO engine marks.
    """
    day_data = {}
    prior_levels = {}
    card_ids = []
    card_htmls = []

    for symbol, date, candles, pdh, pdl in days:
        cid = f"{symbol}_{date}"
        card_ids.append(cid)
        day_data[cid] = [_candle_to_dict(c) for c in candles]
        prior_levels[cid] = {"pdh": round(pdh, 2) if pdh else None,
                             "pdl": round(pdl, 2) if pdl else None}

        html = HTML_PER_CARD
        html = html.replace("__CID__", cid)
        html = html.replace("__SYMBOL__", symbol)
        card_htmls.append(html)

    full = HTML_HEAD.replace("__LABEL__", label)
    full += "\n".join(card_htmls)

    script = HTML_SCRIPT_PREAMBLE
    script = script.replace("__DAY_DATA__", json.dumps(day_data))
    script = script.replace("__PRIOR_LEVELS__", json.dumps(prior_levels))
    script = script.replace("__CARD_IDS__", json.dumps(card_ids))
    script = script.replace("__TOTAL__", str(len(card_ids)))

    full += script

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full)
    print(f"Wrote {out_path} ({len(card_ids)} cards)")


def main():
    # ── 1. Gather trading days ────────────────────────────────────────────
    tsla_days = _trading_days("TSLA")
    qqq_days = _trading_days("QQQ")
    spy_days = _trading_days("SPY")

    n_tsla = len(tsla_days)
    n_qqq = len(qqq_days)
    n_spy = len(spy_days)
    print(f"TSLA: {n_tsla} days, QQQ: {n_qqq} days, SPY: {n_spy} days")

    # Take the 60 most recent TSLA days, 30 most recent QQQ, 30 most recent SPY
    tsla_take = min(60, n_tsla)
    qqq_take = min(30, n_qqq)
    spy_take = min(30, n_spy)

    tsla_selected = tsla_days[-tsla_take:]
    qqq_selected = qqq_days[-qqq_take:]
    spy_selected = spy_days[-spy_take:]

    print(f"TSLA selected: {tsla_selected[0]} .. {tsla_selected[-1]} ({len(tsla_selected)} days)")
    print(f"QQQ selected:  {qqq_selected[0]} .. {qqq_selected[-1]} ({len(qqq_selected)} days)")
    print(f"SPY selected:  {spy_selected[0]} .. {spy_selected[-1]} ({len(spy_selected)} days)")

    # ── 2. Load session candles + compute engine fire counts ──────────────
    # TSLA deck
    tsla_cards = []
    for day in tsla_selected:
        candles = _load_session_candles("TSLA", day)
        if not candles:
            print(f"  WARNING: TSLA {day} has no session candles, skipping")
            continue
        # Prior-day levels (from t4_engine_recall)
        from research.t4_engine_recall import prior_day_levels
        pdh, pdl, _pdo, _pdc = prior_day_levels("TSLA", day)
        tsla_cards.append(("TSLA", day, candles, pdh, pdl))

    print(f"TSLA deck: {len(tsla_cards)} usable days (wanted {tsla_take})")

    # QQQ + SPY deck (30 each, contiguous blocks)
    index_cards = []
    for day in qqq_selected:
        candles = _load_session_candles("QQQ", day)
        if not candles:
            print(f"  WARNING: QQQ {day} has no session candles, skipping")
            continue
        pdh, pdl, _pdo, _pdc = prior_day_levels("QQQ", day)
        index_cards.append(("QQQ", day, candles, pdh, pdl))

    for day in spy_selected:
        candles = _load_session_candles("SPY", day)
        if not candles:
            print(f"  WARNING: SPY {day} has no session candles, skipping")
            continue
        pdh, pdl, _pdo, _pdc = prior_day_levels("SPY", day)
        index_cards.append(("SPY", day, candles, pdh, pdl))

    print(f"Index deck: {len(index_cards)} usable days (wanted 60)")

    # ── 3. Engine fire counts ─────────────────────────────────────────────
    # Run the engine on each (symbol, day) and record fire counts.
    # This modifies signal_runner module-level flags, so we need to save/restore.
    manifest_rows = []

    all_cards = tsla_cards + index_cards
    print(f"\nComputing engine fire counts for {len(all_cards)} days...")
    for idx, (symbol, day, _candles, _pdh, _pdl) in enumerate(all_cards):
        count = _engine_fire_count(symbol, day)
        deck = "tsla" if symbol == "TSLA" else "index"
        manifest_rows.append({
            "card_id": f"{symbol}_{day}",
            "symbol": symbol,
            "date": day,
            "deck": deck,
            "engine_fires_that_day": count,
        })
        if (idx + 1) % 20 == 0:
            print(f"  {idx + 1}/{len(all_cards)} done (last: {symbol}_{day} fires={count})")

    # ── 4. Write manifest ─────────────────────────────────────────────────
    with open(MANIFEST, "w", encoding="utf-8") as f:
        for row in manifest_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    print(f"\nWrote {MANIFEST} ({len(manifest_rows)} rows)")

    # ── 5. Build HTML decks ───────────────────────────────────────────────
    build_deck(tsla_cards, "TSLA — 60 days", TSLA_DECK)
    build_deck(index_cards, "QQQ/SPY — 60 days", INDEX_DECK)

    # ── 6. Summary ────────────────────────────────────────────────────────
    tsla_fires = sum(r["engine_fires_that_day"] for r in manifest_rows
                     if r["symbol"] == "TSLA")
    qqq_fires = sum(r["engine_fires_that_day"] for r in manifest_rows
                    if r["symbol"] == "QQQ")
    spy_fires = sum(r["engine_fires_that_day"] for r in manifest_rows
                    if r["symbol"] == "SPY")
    print(f"\n=== Summary ===")
    print(f"TSLA: {len(tsla_cards)} cards, {tsla_fires} engine fires across all days")
    print(f"QQQ:  {len(qqq_selected)} days selected, {qqq_fires} engine fires")
    print(f"SPY:  {len(spy_selected)} days selected, {spy_fires} engine fires")


if __name__ == "__main__":
    main()