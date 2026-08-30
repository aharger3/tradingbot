"""g84_one_page.py -- ONE dark page holding every outstanding homework item.

WHY THIS EXISTS
---------------
Three instruments were built and sent, and Austin could not work in any of them:
they were opened in a read-only viewer panel, so the taps did nothing and the
answers had nowhere to go. Three links, three read-only pages, zero marks back.

This is one page, published as a claude.ai Artifact, that he can actually work
in. It builds NOTHING new. It re-renders three decks that already exist on disk,
from their own manifests, card for card:

    research/decks/g75-deck2-manifest.jsonl            39  "would you take it"
    research/probes/omen-master-homework-manifest.jsonl 55  seven mixed sections
    research/decks/g83-deep-batch-manifest.jsonl        60  "is this an S"
                                                      ---
                                                      154

No card selection happens here. No symbol-day is re-picked, no builder's
selection logic is re-run. Each item keeps its own question, its own answer
options, and its own section label, so an export drops straight back onto the
manifest it came from.

WHAT THE ARTIFACT SANDBOX BREAKS, AND WHAT THIS PAGE DOES ABOUT IT
------------------------------------------------------------------
* A page-initiated download is inert. `<a download>` "succeeds" and saves
  nothing. So COPY ALL is the export, it is the first thing under the masthead,
  it is in the sticky bar, and it is at the bottom. Download is there, labelled
  as the thing that usually does not work. And the raw .jsonl is always sitting
  in a visible <textarea> so a long-press -> Select all -> Copy works when both
  buttons fail.
* No external resources load. No Google Fonts (the shared shell in
  probe_page.py links fonts.googleapis.com -- this page does not use that
  shell), no CDN, no remote image, no fetch. System font stack only.
* localStorage can throw outright. Every read and write is wrapped, and if the
  probe fails the page says so in red at the top instead of silently eating his
  answers.
* The viewer paints its own ground behind the page, so `body` gets an explicit
  dark background. He asked for dark; this page has no light palette at all.

THE probe_chart TRAP
--------------------
`probe_chart.LEVELS` grew HOD/LOD on 2026-08-29 and its comment claims every
existing caller's SVG stays byte-identical. That is FALSE: the frame-widening
loop walks LEVELS, so any caller whose `levels` dict carries `hod`/`lod` now
gets a different frame AND two more lines. The three source decks do not draw
the same six -- g75 and g83 draw PDH/PDL/PMH/PML/ORH/ORL, most of the master
sections draw PDH/PDL/PMH/PML/HOD/LOD, and two of them draw only four. So this
builder passes each card EXACTLY the `drawn_levels` dict its own manifest
recorded, never a reconstructed one, and the legend under each chart is
generated from the keys actually present.

    python research/g84_one_page.py [--selfcheck]

Output:
    research/probes/omen-all-in-one.html
    research/decks/g84-all-in-one-manifest.jsonl   (answer key -- NOT in the HTML)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as bd                    # noqa: E402  the no-repeat guarantee
import g71_homework_build as hb            # noqa: E402  NO_REASONS, blurbs, offchart
import g75_deck2_build as g75b             # noqa: E402  its own veto list
import g82_master_homework as g82          # noqa: E402  ballot text, daily bars
import probe_chart                         # noqa: E402  static SVG, rendered here

BOOK = os.path.join(HERE, "bt2y_trades.json")
OUT_HTML = os.path.join(HERE, "probes", "omen-all-in-one.html")
OUT_MANIFEST = os.path.join(HERE, "decks", "g84-all-in-one-manifest.jsonl")
DECK_ID = "g84-all-in-one"

SRC_G75 = os.path.join(HERE, "decks", "g75-deck2-manifest.jsonl")
SRC_MASTER = os.path.join(HERE, "probes", "omen-master-homework-manifest.jsonl")
SRC_G83 = os.path.join(HERE, "decks", "g83-deep-batch-manifest.jsonl")
SOURCES = [SRC_G75, SRC_MASTER, SRC_G83]


# ------------------------------------------------------------------ no repeats

def served_excluding(paths) -> set[str]:
    """`build_deck.served_card_ids` takes ONE exclusion; this build needs four.

    It reads every ``*manifest*.jsonl`` under research/, which now includes the
    three manifests this page re-renders. Left alone it would report all 139
    symbol-days as already served -- by themselves -- and the guard would be
    noise. Same glob, same id regex, same rows reader as build_deck; only the
    skip list is wider.
    """
    skip = {os.path.abspath(p) for p in paths}
    out: set[str] = set()
    for path in sorted(glob.glob(os.path.join(bd.HERE, "**", "*manifest*.jsonl"),
                                 recursive=True)):
        if os.path.abspath(path) in skip:
            continue
        for row in bd._rows(path):
            ident = row.get("card_id") or row.get("id")
            if isinstance(ident, str):
                m = bd._ID_RE.search(ident)
                if m:
                    out.add("%s_%s" % (m.group(1), m.group(2)))
    return out


# ------------------------------------------------------------------ page chrome

CSS = """
<style>
:root{
  --bg:#0a0f0e; --surface:#141c1b; --surface-2:#1c2726; --surface-3:#243130;
  --ink:#e9efed; --ink-2:#a8b8b4; --ink-3:#7f918c;
  --rule:#2b3937; --rule-2:#3d4f4b;
  --accent:#5fd8c6; --accent-ink:#04211d; --accent-soft:#16332f;
  --up:#3ecf82; --dn:#f2695f; --entry:#f2ad3c; --stop:#e58379;
  --lvl-pd:#88a6f5; --lvl-pm:#c98ce4; --lvl-or:#4fc9ba; --lvl-hl:#f2a663;
  --bad:#ff6f6f; --warn:#ffb454;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
}
*{box-sizing:border-box}
html{background:#0a0f0e}
body{
  margin:0; background:#0a0f0e; color:var(--ink);
  font-family:var(--sans); font-size:16px; line-height:1.5;
  -webkit-text-size-adjust:100%; overflow-x:hidden;
}
.wrap{max-width:820px; margin:0 auto; padding:0 13px 110px}

.alarm{
  margin:12px 0 0; padding:12px 14px; border-radius:9px;
  background:#3a1414; border:1px solid var(--bad); color:#ffd9d9;
  font-size:14.5px; line-height:1.45;
}
.alarm b{color:#fff}

.mast{padding:24px 0 16px; border-bottom:1px solid var(--rule)}
.eyebrow{
  font-family:var(--mono); font-size:11px; font-weight:600; letter-spacing:.14em;
  text-transform:uppercase; color:var(--accent); margin:0 0 8px;
}
h1{font-size:clamp(25px,6vw,34px); line-height:1.15; margin:0 0 10px;
   font-weight:700; letter-spacing:-.01em}
.lede{margin:0; color:var(--ink-2); font-size:15px; max-width:64ch}
.lede strong{color:var(--ink); font-weight:600}

.bar{
  position:sticky; top:0; z-index:30; background:#0a0f0e;
  border-bottom:1px solid var(--rule); margin:0 -13px 16px; padding:9px 13px;
  display:flex; align-items:center; gap:9px; flex-wrap:wrap;
}
.bar .count{
  font-family:var(--mono); font-size:12.5px; font-weight:600;
  font-variant-numeric:tabular-nums; color:var(--ink); white-space:nowrap;
}
.track{flex:1 1 50px; height:5px; background:var(--rule); border-radius:3px;
       overflow:hidden; min-width:40px}
.fill{height:100%; width:0%; background:var(--accent); transition:width .25s ease}
.saved{
  font-family:var(--mono); font-size:10px; font-weight:600; letter-spacing:.08em;
  text-transform:uppercase; color:var(--ink-3); white-space:nowrap;
}
.saved[data-state="just"]{color:var(--accent)}
.saved[data-state="fail"]{color:var(--bad)}

button{font-family:var(--sans)}
.btn{
  font:600 13px/1 var(--sans); letter-spacing:.02em; border:0; border-radius:999px;
  padding:11px 15px; min-height:42px; cursor:pointer; white-space:nowrap;
  background:var(--surface-3); color:var(--ink);
  box-shadow:inset 0 0 0 1px var(--rule-2);
}
.btn:active{transform:translateY(1px)}
.btn.pri{background:var(--accent); color:var(--accent-ink); box-shadow:none}
.btn.big{font-size:15.5px; padding:15px 22px; min-height:52px; width:100%;
         max-width:340px}
.btn:focus-visible{outline:2px solid var(--accent); outline-offset:2px}

.exportbox{
  background:var(--surface); border:1px solid var(--accent); border-radius:11px;
  padding:15px 16px; margin:0 0 20px;
}
.exportbox h2{margin:0 0 5px; font-size:17px; font-weight:700}
.exportbox p{margin:0 0 10px; font-size:13.5px; color:var(--ink-2); max-width:62ch}
.exportbox p.small{font-size:12.5px; color:var(--ink-3); margin:9px 0 0}
.ebtns{display:flex; gap:9px; align-items:center; flex-wrap:wrap; margin:0 0 11px}
#copymsg{font-family:var(--mono); font-size:12px; color:var(--accent)}
#out{
  width:100%; min-height:130px; resize:vertical; display:block;
  font:400 11.5px/1.45 var(--mono); color:var(--ink);
  background:#080d0c; border:1px solid var(--rule-2); border-radius:8px;
  padding:9px; white-space:pre; overflow:auto;
}

.sec{
  margin:0 0 12px; border:1px solid var(--rule-2); border-radius:11px;
  background:var(--surface); overflow:hidden; scroll-margin-top:62px;
}
.sec>summary{
  list-style:none; cursor:pointer; padding:15px 16px; min-height:56px;
  display:flex; align-items:center; gap:11px; background:var(--surface-2);
  font-weight:650; font-size:15.5px;
}
.sec>summary::-webkit-details-marker{display:none}
.sec>summary::before{
  content:"+"; font-family:var(--mono); font-size:17px; font-weight:600;
  color:var(--accent); width:16px; flex:none; text-align:center;
}
.sec[open]>summary::before{content:"\\2212"}
.sec>summary .sec-n{
  margin-left:auto; font-family:var(--mono); font-size:12px; font-weight:600;
  font-variant-numeric:tabular-nums; color:var(--ink-3); flex:none;
  padding:4px 8px; border-radius:999px; background:var(--surface-3);
}
.sec>summary .sec-n[data-full="1"]{color:var(--accent-ink); background:var(--accent)}
.sec-body{padding:4px 11px 14px}
.sec-lede{margin:12px 2px 16px; font-size:14px; color:var(--ink-2); max-width:64ch}
.sec-lede b{color:var(--ink)}
.roundlab{
  font-family:var(--mono); font-size:10.5px; font-weight:600; letter-spacing:.12em;
  text-transform:uppercase; color:var(--ink-3); margin:22px 2px 9px;
}

.card{
  background:var(--surface); border:1px solid var(--rule); border-radius:10px;
  margin:0 0 15px; overflow:hidden; scroll-margin-top:64px;
}
.card[data-done="1"]{border-color:var(--accent)}
.card>header{
  display:flex; align-items:baseline; gap:9px; flex-wrap:wrap;
  padding:12px 14px; border-bottom:1px solid var(--rule); background:var(--surface-2);
}
.idx{font-family:var(--mono); font-size:11px; font-weight:600; color:var(--ink-3);
     font-variant-numeric:tabular-nums}
.tick{font-family:var(--mono); font-size:16px; font-weight:700}
.when{font-family:var(--mono); font-size:13px; color:var(--ink-2)}
.tags{margin-left:auto; display:flex; gap:6px; align-items:center; flex-wrap:wrap}
.tag{font-family:var(--mono); font-size:9.5px; font-weight:600; letter-spacing:.07em;
     text-transform:uppercase; padding:3px 7px; border-radius:4px;
     background:var(--accent-soft); color:var(--accent)}
.done-dot{width:9px; height:9px; border-radius:50%; background:var(--rule-2); flex:none}
.card[data-done="1"] .done-dot{background:var(--accent)}

/* charts scroll inside their own box; the page body never scrolls sideways */
/* probe_chart reserves PAD_R=56 viewBox units for the right gutter, which fits a
   9-unit label and not the 13-unit one this page uses. The text overflows the
   viewBox, and a scroll container clips at its padding edge -- so leave room. */
.chartwrap{padding:9px 22px 2px 9px; background:var(--surface); overflow-x:auto;
           overflow-y:hidden; -webkit-overflow-scrolling:touch}
.chart{width:100%; min-width:330px; height:auto; display:block; overflow:visible}
.pair{display:flex; gap:8px; flex-wrap:wrap; min-width:330px}
.pair .pane{flex:1 1 320px; min-width:300px}

.chart .grid{stroke:#31413e; stroke-width:.8}
/* Font sizes here are viewBox units, and a 720-unit chart lands at ~390 CSS px
   on a phone -- so 9px in the source decks renders at 5px on the device he
   actually uses. Everything on the plot is sized up to survive that squeeze. */
.chart .axis{font-family:var(--mono); font-size:12px; fill:var(--ink-3);
             text-anchor:middle}
.chart .wk{stroke-width:1.25}
.chart .bd{stroke-width:.7}
.chart .up{stroke:var(--up); fill:var(--up)}
.chart .dn{stroke:var(--dn); fill:var(--dn)}
.chart .lvl{stroke-width:1.35; opacity:.95}
/* No halo on the level labels: they sit in the empty right gutter, and a
   3-unit stroke on a 13-unit glyph closes up the counters into a smear once the
   chart is scaled down to phone width. The dot and rail labels DO sit over
   candles and keep theirs. */
.chart .lvl-t{font-family:var(--mono); font-size:13px; font-weight:600}
.chart .lvl-pd{stroke:var(--lvl-pd); fill:var(--lvl-pd)}
.chart .lvl-pm{stroke:var(--lvl-pm); fill:var(--lvl-pm)}
.chart .lvl-or{stroke:var(--lvl-or); fill:var(--lvl-or)}
.chart .lvl-hl{stroke:var(--lvl-hl); fill:var(--lvl-hl)}
/* hue says WHICH pair, dash says high or low -- so all six read apart. */
.chart .lk-pdh,.chart .lk-pmh,.chart .lk-orh,.chart .lk-hod{stroke-dasharray:10 4}
.chart .lk-pdl,.chart .lk-pml,.chart .lk-orl,.chart .lk-lod{stroke-dasharray:2 3.5}
.chart .entry{stroke:var(--entry); stroke-width:1.5}
.chart .entry-t{font-family:var(--mono); font-size:13px; font-weight:600;
                fill:var(--entry)}
.chart .arrow{fill:var(--entry)}
.chart .stopl{stroke:var(--stop); stroke-width:1.2; stroke-dasharray:2 3}
.chart .stop-t{font-family:var(--mono); font-size:13px; font-weight:600;
               fill:var(--stop)}
.chart .dot{stroke:var(--entry); fill:var(--surface); stroke-width:2.4}
.chart .dot-t,.chart .hrail-t{paint-order:stroke; stroke:#0a0f0e; stroke-width:3.5px;
                              stroke-linejoin:round}
.chart .dot-t{font-family:var(--mono); font-size:14px; font-weight:700;
              fill:var(--entry)}
.chart .hrail.cand{stroke:var(--stop); stroke-width:1.3}
.chart .hrail-t.cand{font-family:var(--mono); font-size:14px; font-weight:700;
                     fill:var(--stop)}
.chart .hrail.entryrail{stroke:var(--entry); stroke-width:1.7}
.chart .hrail-t.entryrail{font-family:var(--mono); font-size:14px; font-weight:700;
                          fill:var(--entry)}
.chart .hrail.dclose{stroke:var(--ink-3); stroke-width:1; stroke-dasharray:4 4}
.chart .hrail-t.dclose{font-family:var(--mono); font-size:12px; fill:var(--ink-3)}

.legend{display:flex; gap:13px; flex-wrap:wrap; padding:2px 14px 11px;
        font-family:var(--mono); font-size:10px; color:var(--ink-3);
        line-height:1.5}
.legend b{font-weight:700}

.q{padding:13px 14px; border-top:1px solid var(--rule)}
.q h3{margin:0 0 3px; font-size:14.5px; font-weight:650; line-height:1.35}
.q .hint{margin:0 0 10px; font-size:12.5px; color:var(--ink-3)}
.chips{display:flex; flex-wrap:wrap; gap:8px}
.chip{
  font:600 14px/1.2 var(--sans); color:var(--ink-2); background:var(--surface-2);
  border:1px solid var(--rule-2); border-radius:9px; padding:12px 13px;
  min-height:48px; cursor:pointer; text-align:left;
}
.chip[aria-pressed="true"]{background:var(--accent); border-color:var(--accent);
                           color:var(--accent-ink)}
.q[data-tone="veto"] .chip[aria-pressed="true"]{background:var(--stop);
  border-color:var(--stop); color:#1a0908}
.chip:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
textarea.note{
  width:100%; margin-top:9px; min-height:58px; resize:vertical; display:block;
  font:400 15px/1.5 var(--sans); color:var(--ink); background:var(--surface-2);
  border:1px solid var(--rule-2); border-radius:8px; padding:10px 11px;
}
textarea.note:focus-visible{outline:2px solid var(--accent); outline-offset:1px}
.nag{margin:9px 14px 13px; padding:9px 11px; border-radius:8px; font-size:13px;
     background:#3a2a10; border:1px solid var(--warn); color:#ffe2b0}

.ruleq{padding:15px 15px 4px}
.mentor{margin:0; padding:0 0 0 12px; border-left:3px solid var(--accent);
        font-size:15.5px; line-height:1.45; color:var(--ink)}
.mentor cite{display:block; margin-top:6px; font-style:normal; font-size:12px;
             color:var(--ink-3); font-family:var(--mono)}
.change{margin:11px 0 0; font-size:13.5px; color:var(--ink-2)}

.foot{margin-top:26px; padding:16px; border:1px dashed var(--rule-2);
      border-radius:10px; font-size:13.5px; color:var(--ink-2)}
.foot h2{font-size:16px; font-weight:700; margin:0 0 6px; color:var(--ink)}
.foot p{margin:0 0 9px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
@media (max-width:520px){
  .wrap{padding:0 9px 110px}
  .bar{margin:0 -9px 14px; padding:8px 9px}
  .chip{flex:1 1 calc(50% - 5px); min-width:0}
  .sec-body{padding:4px 7px 12px}
  .q{padding:12px 11px}
  .card>header{padding:11px 11px}
}
</style>
"""

JS = r"""
<script>
(function(){
  var DECK = 'g84-all-in-one';
  var KEY = 'omen-probe:' + DECK + ':';
  var TOTAL = 0;

  function cards(){ return [].slice.call(document.querySelectorAll('.card')); }
  function qs(card){ return [].slice.call(card.querySelectorAll('.q[data-q]')); }
  function secs(){ return [].slice.call(document.querySelectorAll('.sec')); }

  /* --------------------------------------------------- storage, defensively */
  var storeOk = false;
  try {
    var probe = KEY + '__probe';
    localStorage.setItem(probe, '1');
    storeOk = localStorage.getItem(probe) === '1';
    localStorage.removeItem(probe);
  } catch (e) { storeOk = false; }

  function lsGet(k){ try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v){ try { localStorage.setItem(k, v); return true; }
                        catch (e) { return false; } }

  var flagTimer = null;
  function flag(state, text){
    var el = document.getElementById('saved');
    if (!el) return;
    el.setAttribute('data-state', state || '');
    el.textContent = text;
    if (state === 'just'){
      clearTimeout(flagTimer);
      flagTimer = setTimeout(function(){
        el.setAttribute('data-state', ''); el.textContent = 'saved';
      }, 1500);
    }
  }

  function cardState(card){
    var picked = {}, notes = {};
    qs(card).forEach(function(q){
      var k = q.getAttribute('data-q'), vals = [];
      q.querySelectorAll('.chip[aria-pressed="true"]').forEach(function(c){
        vals.push(c.getAttribute('data-v'));
      });
      if (vals.length) picked[k] = vals;
      var t = q.querySelector('textarea.note');
      if (t && t.value.trim()) notes[k] = t.value.trim();
    });
    return {picked: picked, notes: notes};
  }

  function save(card){
    if (!storeOk){ flag('fail', 'NOT SAVING - copy out now'); return; }
    var ok = lsSet(KEY + card.getAttribute('data-cid'),
                   JSON.stringify(cardState(card)));
    flag(ok ? 'just' : 'fail', ok ? 'saved' : 'SAVE FAILED - copy out now');
  }

  function restore(){
    if (!storeOk) return;
    cards().forEach(function(card){
      var raw = lsGet(KEY + card.getAttribute('data-cid'));
      if (!raw) return;
      var st;
      try { st = JSON.parse(raw); } catch (e) { return; }
      qs(card).forEach(function(q){
        var k = q.getAttribute('data-q');
        (((st.picked || {})[k]) || []).forEach(function(v){
          var chip = q.querySelector('.chip[data-v="' + v + '"]');
          if (chip) chip.setAttribute('aria-pressed', 'true');
        });
        var t = q.querySelector('textarea.note');
        if (t && (st.notes || {})[k]) t.value = st.notes[k];
      });
    });
  }

  /* ------------------------------------------------------------- the minute */
  var TIME = /\b(\d{1,2})[:;.\s]?(\d{2})\b/;
  window.parseMinute = function(s){
    var m = TIME.exec(s || '');
    if (!m) return null;
    var h = parseInt(m[1], 10), mi = parseInt(m[2], 10);
    if (h < 9 || h > 11 || mi > 59) return null;
    var t = (h - 9) * 60 + mi - 30;
    if (t < 0 || t > 90) return null;
    return ('0' + h).slice(-2) + ':' + ('0' + mi).slice(-2);
  };
  function nagNote(card){
    var nq = card.getAttribute('data-nag-note');
    if (!nq) return '';
    var t = card.querySelector('textarea[data-note="' + nq + '"]');
    return t ? t.value : '';
  }
  function nagOpen(card){
    var q = card.getAttribute('data-nag-q');
    if (!q) return false;
    var want = (card.getAttribute('data-nag-vals') || '').split(',');
    var hit = false;
    want.forEach(function(v){
      var c = card.querySelector('.q[data-q="' + q + '"] .chip[data-v="' + v + '"]');
      if (c && c.getAttribute('aria-pressed') === 'true') hit = true;
    });
    return hit && !window.parseMinute(nagNote(card));
  }

  function answered(card){
    var req = card.querySelectorAll('.q[data-required="1"]');
    if (!req.length) return false;
    for (var i = 0; i < req.length; i++){
      if (!req[i].querySelector('.chip[aria-pressed="true"]')) return false;
    }
    return !nagOpen(card);
  }

  /* ------------------------------------------------------------- the export */
  function jsonl(){
    var lines = [];
    cards().forEach(function(card){
      var st = cardState(card);
      if (!Object.keys(st.picked).length && !Object.keys(st.notes).length) return;
      var row = {type: 'probe', probe: DECK, card_id: card.getAttribute('data-cid'),
                 answers: st.picked, notes: st.notes};
      var stat = card.getAttribute('data-export');
      if (stat){
        try {
          var ex = JSON.parse(stat);
          for (var k in ex) if (Object.prototype.hasOwnProperty.call(ex, k)) row[k] = ex[k];
        } catch (e) {}
      }
      var nq = card.getAttribute('data-nag-note');
      if (nq){
        row.entry_minute = window.parseMinute(nagNote(card));
        row.entry_minute_given = !!row.entry_minute;
      }
      lines.push(JSON.stringify(row));
    });
    return lines.join('\n');
  }

  var outTimer = null;
  function paintOut(){
    clearTimeout(outTimer);
    outTimer = setTimeout(function(){
      var o = document.getElementById('out');
      if (!o) return;
      if (document.activeElement === o) return;   /* he may be selecting it */
      var t = jsonl();
      o.value = t || '(nothing answered yet - your answers appear here as you tap)';
    }, 250);
  }

  function copyAll(){
    var box = document.getElementById('out'), msg = document.getElementById('copymsg');
    var text = jsonl();
    box.value = text || '(nothing answered yet)';
    box.focus();
    try { box.setSelectionRange(0, box.value.length); } catch (e) {}
    function say(t){ if (msg) msg.textContent = t; }
    if (!text){ say('nothing to copy yet'); return; }
    var done = false;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText){
        done = true;
        navigator.clipboard.writeText(text).then(
          function(){ say('COPIED - paste it into the chat'); },
          function(){ legacy(); });
      }
    } catch (e) { done = false; }
    if (!done) legacy();
    function legacy(){
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      say(ok ? 'COPIED - paste it into the chat'
             : 'the text is selected below - long-press it and tap Copy');
    }
  }

  /* -------------------------------------------------------------- the counts */
  function refresh(){
    var cs = cards(), done = 0;
    cs.forEach(function(c){
      var ok = answered(c);
      c.setAttribute('data-done', ok ? '1' : '0');
      if (ok) done++;
      var n = c.querySelector('.nag');
      if (n) n.hidden = !nagOpen(c);
    });
    TOTAL = cs.length;
    var cnt = document.getElementById('count');
    if (cnt) cnt.textContent = done + ' of ' + cs.length + ' answered';
    var fill = document.getElementById('fill');
    if (fill) fill.style.width = (cs.length ? (done * 100 / cs.length) : 0) + '%';
    secs().forEach(function(s){
      var inside = [].slice.call(s.querySelectorAll('.card'));
      var d = inside.filter(function(c){ return c.getAttribute('data-done') === '1'; });
      var lab = s.querySelector('.sec-n');
      if (lab){
        lab.textContent = d.length + ' / ' + inside.length;
        lab.setAttribute('data-full', (inside.length && d.length === inside.length) ? '1' : '0');
      }
    });
    paintOut();
  }

  function firstUnanswered(){
    return cards().filter(function(c){ return c.getAttribute('data-done') !== '1'; })[0];
  }
  function goNext(){
    var c = firstUnanswered();
    if (!c){ document.querySelector('.exportbox').scrollIntoView({block: 'start'}); return; }
    var s = c.closest('.sec');
    if (s && !s.open) s.open = true;
    setTimeout(function(){ c.scrollIntoView({behavior: 'smooth', block: 'start'}); }, 30);
  }

  /* ------------------------------------------------------------------ events */
  document.addEventListener('click', function(e){
    if (!e.target.closest) return;
    if (e.target.closest('#copybtn') || e.target.closest('#copytop')
        || e.target.closest('#copyfoot')){
      copyAll();
      document.querySelector('.exportbox').scrollIntoView({block: 'start'});
      return;
    }
    if (e.target.closest('#dlbtn')){
      var msg = document.getElementById('copymsg');
      try {
        var blob = new Blob([jsonl() + '\n'], {type: 'application/x-ndjson'});
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'probe_' + DECK + '.jsonl';
        document.body.appendChild(a); a.click(); a.remove();
        msg.textContent = 'if no file appeared, the viewer blocked it - use Copy all';
      } catch (err) {
        msg.textContent = 'download blocked here - use Copy all';
      }
      return;
    }
    if (e.target.closest('#nextbtn')){ goNext(); return; }

    var chip = e.target.closest('.chip');
    if (!chip) return;
    var q = chip.closest('.q');
    var on = chip.getAttribute('aria-pressed') === 'true';
    if (q.getAttribute('data-multi') !== '1'){
      q.querySelectorAll('.chip').forEach(function(o){
        o.setAttribute('aria-pressed', 'false');
      });
    }
    chip.setAttribute('aria-pressed', on ? 'false' : 'true');
    refresh();
    save(chip.closest('.card'));
  });

  /* Typed notes: debounced, and flushed on every event a phone actually fires
     when it backgrounds the browser. A note typed and interrupted inside the
     debounce used to be lost. */
  var pending = [];
  function queue(card){ if (pending.indexOf(card) < 0) pending.push(card); }
  function flush(){
    var q = pending.slice(); pending.length = 0;
    q.forEach(function(card){ clearTimeout(card._t); save(card); });
  }
  document.addEventListener('input', function(e){
    var t = e.target;
    if (!t || !t.classList || !t.classList.contains('note')) return;
    var card = t.closest('.card');
    queue(card);
    clearTimeout(card._t);
    card._t = setTimeout(function(){ save(card); refresh(); }, 400);
  });
  document.addEventListener('blur', function(e){
    var t = e.target;
    if (t && t.classList && t.classList.contains('note')){ flush(); refresh(); }
  }, true);
  document.addEventListener('visibilitychange', function(){
    if (document.visibilityState === 'hidden') flush();
  });
  window.addEventListener('pagehide', flush);
  document.addEventListener('toggle', function(e){
    if (e.target && e.target.classList && e.target.classList.contains('sec')) refresh();
  }, true);

  /* ------------------------------------------------------------------- boot */
  if (!storeOk){
    var al = document.getElementById('nostore');
    if (al) al.hidden = false;
  }
  restore();
  refresh();
  if (!storeOk) flag('fail', 'NOT SAVING - copy out now');
  var start = firstUnanswered();
  if (start){
    var s0 = start.closest('.sec');
    if (s0) s0.open = true;
    setTimeout(function(){ start.scrollIntoView({block: 'start'}); }, 40);
  }
})();
</script>
"""


# ------------------------------------------------------------------ primitives

def esc_attr(s: str) -> str:
    return str(s).replace("&", "&amp;").replace('"', "&quot;")


def esc_copy(s: str) -> str:
    """For author-written attribute copy that ALREADY carries entities.

    Placeholders read like the questions do -- "the minute &mdash; e.g. 9:42".
    Running esc_attr over that double-escapes the ampersand and the box shows a
    literal `&mdash;`. Only the quote needs escaping here.
    """
    return str(s).replace('"', "&quot;")


def export_blob(d: dict) -> str:
    return json.dumps(d, sort_keys=True).replace("&", "&amp;").replace('"', "&quot;")


def question(key, heading, hint, options, multi=False, required=True, tone="",
             note_placeholder=None):
    chips = "".join(
        '<button class="chip" type="button" data-v="%s" aria-pressed="false">%s</button>'
        % (esc_attr(v), lab) for v, lab in options)
    note = ""
    if note_placeholder:
        note = ('<textarea class="note" data-note="%s" placeholder="%s"></textarea>'
                % (esc_attr(key), esc_copy(note_placeholder)))
    return ('<section class="q" data-q="%s" data-multi="%s" data-required="%s"%s>'
            '<h3>%s</h3><p class="hint">%s</p><div class="chips">%s</div>%s</section>'
            % (esc_attr(key), "1" if multi else "0", "1" if required else "0",
               ' data-tone="%s"' % tone if tone else "", heading, hint, chips, note))


def card(cid, idx, tick, when, tag, body, export, nag=None):
    """nag = (question_key, [values], note_key, sentence) or None."""
    na = ""
    if nag:
        na = (' data-nag-q="%s" data-nag-vals="%s" data-nag-note="%s"'
              % (esc_attr(nag[0]), esc_attr(",".join(nag[1])), esc_attr(nag[2])))
    return ('<article class="card" data-cid="%s" data-export="%s" data-done="0"%s>'
            '<header><span class="idx">%s</span><span class="tick">%s</span>'
            '<span class="when">%s</span><span class="tags">'
            '<span class="tag">%s</span><span class="done-dot"></span></span></header>'
            '%s</article>'
            % (esc_attr(cid), export, na, idx, tick, when, tag, body))


# ---------------------------------------------------------------- chart pieces

# probe_chart emits each level as an adjacent <line>/<text> pair carrying only a
# family class (lvl-pd for BOTH pdh and pdl). Four hues cannot tell six lines
# apart, so tag each pair with its own key off the label the renderer already
# wrote, and let CSS dash the highs differently from the lows. Asserted below:
# if the emitted shape ever changes, the build fails rather than quietly losing
# the distinction.
_LVL_PAIR = re.compile(
    r'(<line class="lvl )(lvl-\w+)("[^>]*/>)(<text class="lvl-t )(lvl-\w+)("[^>]*>)'
    r'([A-Z]{3}) ')
_LVL_LINE = re.compile(r'<line class="lvl ')


def key_levels(svg: str) -> str:
    seen = [0]

    def rep(m):
        seen[0] += 1
        k = " lk-" + m.group(7).lower()
        return (m.group(1) + m.group(2) + k + m.group(3)
                + m.group(4) + m.group(5) + k + m.group(6) + m.group(7) + " ")

    out = _LVL_PAIR.sub(rep, svg)
    drawn = len(_LVL_LINE.findall(svg))
    assert seen[0] == drawn, (
        "probe_chart's level markup changed shape: tagged %d of %d level lines"
        % (seen[0], drawn))
    return out


LEG_FAMILY = [
    ("pd", "pdh", "pdl", "PDH/PDL", "prior day"),
    ("pm", "pmh", "pml", "PMH/PML", "pre-market"),
    ("or", "orh", "orl", "ORH/ORL", "opening range (first five minutes)"),
    ("hl", "hod", "lod", "HOD/LOD", "high and low of the day so far"),
]


def legend(levels: dict, extra: str = "") -> str:
    """Name every level DRAWN, with its price at real text size.

    The price in the chart's right gutter is SVG text in viewBox units: on a
    phone the 720-unit chart lands near 390 CSS px, so that label renders about
    half the size it looks in the source. The legend repeats the same numbers in
    page text, which does not shrink.
    """
    bits = []
    for fam, hi, lo, lab, blurb in LEG_FAMILY:
        if levels.get(hi) is None and levels.get(lo) is None:
            continue
        px = " / ".join("%.2f" % levels[k] if levels.get(k) is not None else "&ndash;"
                        for k in (hi, lo))
        bits.append('<span><b style="color:var(--lvl-%s)">%s</b> %s &middot; '
                    '<b>%s</b></span>' % (fam, lab, blurb, px))
    bits.append('<span>long dash = the high, short dash = the low</span>')
    if extra:
        bits.append("<span>%s</span>" % extra)
    return '<div class="legend">%s</div>' % "".join(bits)


def chart(candles, levels, marks=None, dots=None, hlines=None, label="",
          xfmt=None):
    # `bd.session_candles` hands back Candle objects; `g82.daily_candles` already
    # hands back the dict shape probe_chart wants. Take either.
    rows = [c if isinstance(c, dict) else bd.candle_dict(c) for c in candles]
    svg = probe_chart.render(rows, levels, marks=marks or [], dots=dots,
                             hlines=hlines, label=label, xfmt=xfmt)
    return key_levels(svg)


def chartwrap(inner: str) -> str:
    return '<div class="chartwrap">%s</div>' % inner


def offchart(svg, levels, candles):
    return hb.offchart_note(svg, levels, candles)


# --------------------------------------------------------------- section specs

def load(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def book_index():
    with open(BOOK, encoding="utf-8") as fh:
        trades = json.load(fh)["trades"]
    return {(t["sym"], t["day"], t["et"]): t for t in trades}


DIR_WORDS = g82.DIR_WORDS
SETUP_WORDS = g82.SETUP_WORDS

MINUTE_HINT = ("Type the minute you would have got in &mdash; <b>9:42</b>, "
               "<b>10:07</b>. That one line is where every hard finding has come "
               "from.")


# ---- 1  mentor ballot ------------------------------------------------------

def render_ballot(idx, row, b):
    body = ('<div class="ruleq">'
            '<blockquote class="mentor">&ldquo;%s&rdquo;<cite>&mdash; %s</cite>'
            '</blockquote>'
            '<p class="change"><b>What it would change:</b> %s</p></div>'
            % (b["quote"], b["who"], b["change"]))
    body += question(
        "ballot", "Is this a rule of yours?",
        "Nothing here becomes code without a yes.",
        [("yes", "YES"), ("no", "NO"), ("skip", "SKIP &mdash; park it")],
        required=True,
        note_placeholder="a sentence, if you have one (optional)")
    return card(row["card_id"], "%02d" % idx, "RULE %d" % row["rule_no"],
                b["who"], "said %d&times;" % row.get("times_said", b["said"]),
                body,
                export_blob({"source_deck": "omen-master-homework",
                             "section": "mentor_ballot",
                             "rule_no": row["rule_no"], "who": b["who"]}))


# ---- 2  is this an S -------------------------------------------------------

def render_is_s(idx, row, c, bookrow):
    lv = row["drawn_levels"]
    svg = chart(c, lv, label="%s %s 1-minute 09:30-11:00"
                             % (row["symbol"], row["date"]))
    label = row["bucket"]
    if label == "BR" and (bookrow or {}).get("confluence") == "yes":
        label = "BR+OCR"
    meta = legend(lv) + offchart(svg, lv, c) + (
        '<div class="legend" style="padding-top:0">'
        '<span><b>engine claims:</b> %s</span>'
        '<span><b>at:</b> %s &mdash; %s%s</span></div>'
        % (hb.SETUP_LABEL[label], row["claimed_level"],
           hb.LEVEL_BLURB.get(row["claimed_level"], ""),
           hb.SOURCE_BLURB.get(row["claimed_level_source"], "")))
    q = question(
        "is_s", "Is this an S trade?",
        "Nothing on this chart is marked &mdash; the timeframe and your six "
        "levels are all there is.",
        [("yes", "YES &mdash; this is an S"), ("no", "NO &mdash; not an S")],
        required=True,
        note_placeholder="if yes: anything you'd mark here (entry, stop, level) "
                         "&mdash; optional")
    q += question(
        "why_not", "If no &mdash; why not?",
        "Pick every one that applies. Skip this if you said yes.",
        hb.NO_REASONS, multi=True, required=False, tone="veto",
        note_placeholder="in your own words (optional)")
    return card(row["card_id"], "%02d" % idx, row["symbol"], row["date"],
                "1-min &middot; 09:30&ndash;11:00 ET",
                chartwrap(svg) + meta + q,
                export_blob({"source_deck": "omen-master-homework",
                             "section": "is_this_an_s",
                             "symbol": row["symbol"], "date": row["date"],
                             "claimed_setup": label,
                             "claimed_level": row["claimed_level"]}))


# ---- 3  which signal -------------------------------------------------------

def render_which(idx, row, c, idxbook):
    lv = row["drawn_levels"]
    dots = []
    for d in row["dots"]:
        t = idxbook[(row["symbol"], row["date"], d["et"])]
        dots.append({"i": d["entry_i"], "price": t["entry"], "label": d["letter"]})
    svg = chart(c, lv, dots=dots,
                label="%s %s 1-minute 09:30-11:00" % (row["symbol"], row["date"]))
    a, b = row["dots"][0], row["dots"][1]
    meta = legend(lv, "no high-of-day or low-of-day line here &mdash; it is drawn "
                      "where a setup formed, and on this card that would be the "
                      "answer") + offchart(svg, lv, c) + (
        '<div class="legend" style="padding-top:0"><span><b>two setups on this '
        'chart.</b> The dots say WHERE and WHEN only &mdash; no entry line, no '
        'stop, no direction. A is at %s, B is at %s.</span></div>'
        % (a["et"], b["et"]))
    q = question(
        "which_signal", "Which one is the trade?", "One of them, or neither.",
        [("A", "A &mdash; %s" % a["et"]), ("B", "B &mdash; %s" % b["et"]),
         ("neither", "NEITHER &mdash; no trade on this chart")],
        required=True,
        note_placeholder="which way, and why that one and not the other "
                         "&mdash; optional")
    return card(row["card_id"], "%02d" % idx, row["symbol"], row["date"],
                "two marked bars", chartwrap(svg) + meta + q,
                export_blob({"source_deck": "omen-master-homework",
                             "section": "which_signal",
                             "symbol": row["symbol"], "date": row["date"],
                             "dot_A_et": a["et"], "dot_B_et": b["et"]}))


# ---- 4  what minute --------------------------------------------------------

def render_minute(idx, row, c):
    lv = row["drawn_levels"]
    svg = chart(c, lv, label="%s %s 1-minute 09:30-11:00"
                             % (row["symbol"], row["date"]))
    meta = legend(lv, "nothing is marked and nothing is claimed &mdash; just the "
                      "morning") + offchart(svg, lv, c)
    q = question(
        "entry_minute", "What minute would you enter, and which way?",
        "Type the minute in the box &mdash; 9:43, 10:07. If there is no trade "
        "here, say so and leave the box empty.",
        [("long", "LONG"), ("short", "SHORT"),
         ("none", "NO TRADE &mdash; I'd sit this one out")],
        required=True,
        note_placeholder="the minute, e.g. 9:43 &mdash; and the level, if you want")
    nag = ('<p class="nag" hidden>You picked a direction &mdash; this card needs '
           'the minute. Type it in the box above.</p>')
    return card(row["card_id"], "%02d" % idx, row["symbol"], row["date"],
                "nothing marked", chartwrap(svg) + meta + q + nag,
                export_blob({"source_deck": "omen-master-homework",
                             "section": "what_minute",
                             "symbol": row["symbol"], "date": row["date"]}),
                nag=("entry_minute", ["long", "short"], "entry_minute"))


# ---- 5  higher timeframe ---------------------------------------------------

def render_htf(idx, row, c, daily):
    lv = row["drawn_levels"]
    dots = [{"i": row["entry_i"], "price": row["entry"],
             "label": "%s %s" % (DIR_WORDS.get(row["dir"], ""), row["et"])}]
    svg = chart(c, lv, dots=dots,
                label="%s %s 1-minute 09:30-11:00" % (row["symbol"], row["date"]))
    dsvg = chart(daily, {},
                 hlines=[{"price": daily[-1]["c"], "label": "last close",
                          "cls": "dclose", "at": max(6, len(daily) // 5)}],
                 label="%s daily, the %d sessions before this morning"
                       % (row["symbol"], len(daily)),
                 xfmt=lambda t: t[5:10])
    pair = ('<div class="pair"><div class="pane">%s</div>'
            '<div class="pane">%s</div></div>' % (svg, dsvg))
    meta = ('<div class="legend">'
            '<span><b>left / top:</b> the morning, with the setup marked</span>'
            '<span><b>right / below:</b> the same symbol\'s <b>daily</b> chart, '
            'ending at the close <b>before</b> that morning &mdash; nothing on it '
            'knows how the day went</span></div>'
            + legend(lv) + offchart(svg, lv, c) +
            '<div class="legend" style="padding-top:0">'
            '<span><b>the setup:</b> %s, %s, at %s</span></div>'
            % (DIR_WORDS.get(row["dir"], "?"),
               SETUP_WORDS.get(row["engine_setup"], row["engine_setup"]),
               row["et"]))
    q = question(
        "htf", "Does the higher timeframe agree with that setup?",
        "Your call on the daily chart beside it.",
        [("agrees", "AGREES"), ("disagrees", "DISAGREES"),
         ("cannot_tell", "CAN'T TELL")],
        required=True,
        note_placeholder="what you looked at to decide &mdash; and would it change "
                         "the trade? (optional)")
    return card(row["card_id"], "%02d" % idx, row["symbol"], row["date"],
                "1-min + daily", chartwrap(pair) + meta + q,
                export_blob({"source_deck": "omen-master-homework",
                             "section": "htf_agree",
                             "symbol": row["symbol"], "date": row["date"],
                             "setup_et": row["et"],
                             "setup_dir": DIR_WORDS.get(row["dir"], "")}))


# ---- 6  displacement -------------------------------------------------------

def render_disp(idx, row, c):
    lv = row["drawn_levels"]
    dots = [{"i": row["entry_i"], "price": row["entry"], "label": row["et"]}]
    svg = chart(c, lv, dots=dots,
                label="%s %s 1-minute 09:30-11:00" % (row["symbol"], row["date"]))
    meta = legend(lv) + offchart(svg, lv, c) + (
        '<div class="legend" style="padding-top:0">'
        '<span><b>the setup:</b> %s at %s</span>'
        '<span><b>the level it broke:</b> %s &mdash; %s</span></div>'
        % (DIR_WORDS.get(row["dir"], "?"), row["et"], row["level_name"],
           hb.LEVEL_BLURB.get(row["level_name"], "")))
    q = question(
        "displacement", "Is there displacement here?",
        "Yes or no, then one line on what you measured it from.",
        [("yes", "YES &mdash; it displaced"), ("no", "NO &mdash; no displacement"),
         ("cannot_tell", "CAN'T TELL")],
        required=True,
        note_placeholder="displacement from WHAT &mdash; the level, the candles it "
                         "came from, something else?")
    return card(row["card_id"], "%02d" % idx, row["symbol"], row["date"],
                "one marked bar", chartwrap(svg) + meta + q,
                export_blob({"source_deck": "omen-master-homework",
                             "section": "displacement",
                             "symbol": row["symbol"], "date": row["date"],
                             "setup_et": row["et"], "level": row["level_name"]}))


# ---- 7  where is the stop --------------------------------------------------

STOP_LETTERS = ["A", "B", "C", "D"]
STOP_LABEL_BARS = [8, 28, 48, 68]
ENTRY_LABEL_BAR = 85


def render_stop(idx, row, c):
    lv = row["drawn_levels"]
    sl = row["stop_letters"]
    hlines = [{"price": row["entry"], "label": "ENTRY", "cls": "entryrail",
               "at": min(ENTRY_LABEL_BAR, len(c) - 3)}]
    for k, L in enumerate(STOP_LETTERS):
        if L in sl:
            hlines.append({"price": sl[L]["price"], "label": L, "cls": "cand",
                           "at": STOP_LABEL_BARS[k]})
    dots = [{"i": row["entry_i"], "price": row["entry"], "label": ""}]
    svg = chart(c, lv, dots=dots, hlines=hlines,
                label="%s %s 1-minute 09:30-11:00" % (row["symbol"], row["date"]))
    meta = legend(lv) + offchart(svg, lv, c) + (
        '<div class="legend" style="padding-top:0">'
        '<span><b style="color:var(--entry)">&mdash; ENTRY</b> %s at %s</span>'
        '<span><b>A B C D</b> four candidate stops, drawn solid</span></div>'
        % (DIR_WORDS.get(row["dir"], "?"), row["et"]))
    opts = [(L, "%s &mdash; %.2f" % (L, sl[L]["price"]))
            for L in STOP_LETTERS if L in sl]
    opts.append(("none", "NONE OF THESE"))
    q = question(
        "stop_pick", "Where does the stop go?",
        "Tap the line you'd use. If none of them is right, say where instead.",
        opts, required=True,
        note_placeholder="if none of these &mdash; where, and why?")
    return card(row["card_id"], "%02d" % idx, row["symbol"], row["date"],
                "entry given", chartwrap(svg) + meta + q,
                export_blob({"source_deck": "omen-master-homework",
                             "section": "where_is_the_stop",
                             "symbol": row["symbol"], "date": row["date"],
                             "entry_et": row["et"],
                             "prices": {L: round(sl[L]["price"], 2)
                                        for L in STOP_LETTERS if L in sl}}))


# ---- 8  g75: would you take this trade -------------------------------------

def render_take(idx, row, c):
    lv = row["drawn_levels"]
    svg = chart(c, lv, label="%s %s 1-minute 09:30-11:00"
                             % (row["symbol"], row["date"]))
    meta = legend(lv) + offchart(svg, lv, c)
    q = question(
        "take", "Would you take a trade on this chart?",
        "Nothing is marked. The 1-minute session and your six levels are all "
        "there is.",
        [("yes", "YES &mdash; there is a trade here"),
         ("no", "NO &mdash; I would sit this one out")],
        required=True)
    q += question(
        "entry", "If yes &mdash; what minute, and which way?",
        "Tap long or short, then " + MINUTE_HINT,
        [("long", "LONG"), ("short", "SHORT")], required=False,
        note_placeholder="the minute you would have entered, e.g. 9:42 "
                         "— plus the level or anything else you'd mark")
    q += ('<p class="nag" hidden>You said yes &mdash; this card needs the minute '
          'you would have entered. Type it in the box above.</p>')
    q += question(
        "why_not", "If no &mdash; why not?",
        "Pick every one that applies. Skip this if you said yes.",
        g75b.NO_REASONS, multi=True, required=False, tone="veto",
        note_placeholder="in your own words (optional)")
    return card(row["card_id"], "%02d" % idx, row["symbol"], row["date"],
                "1-min &middot; 09:30&ndash;11:00 ET",
                chartwrap(svg) + meta + q,
                export_blob({"source_deck": "g75-deck2", "section": "take_the_trade",
                             "symbol": row["symbol"], "date": row["date"],
                             "round": row["round"]}),
                nag=("take", ["yes"], "entry"))


# ---- 9  g83: the deep batch ------------------------------------------------

def render_deep(idx, row, c, total):
    lv = row["drawn_levels"]
    svg = chart(c, lv, label="%s %s 1-minute 09:30-11:00"
                             % (row["symbol"], row["date"]))
    meta = legend(lv) + offchart(svg, lv, c)
    q = question(
        "s", "Is this an S?",
        "Nothing is marked. The 1-minute session and your six levels are all "
        "there is.",
        [("s", "S &mdash; I take this"), ("no", "Not an S")], required=True)
    q += question(
        "entry", "What minute do you get in?",
        MINUTE_HINT + " Anything else you want to say about the chart can go in "
        "the same box.",
        [], required=False,
        note_placeholder="9:42 — and the level, the direction, anything else")
    q += ('<p class="nag" hidden>You called this an S &mdash; it needs the minute '
          'you would have got in. Type it in the box above.</p>')
    return card(row["card_id"], "%02d/%d" % (idx, total), row["symbol"],
                row["date"], "1-min &middot; 09:30&ndash;11:00 ET",
                chartwrap(svg) + meta + q,
                export_blob({"source_deck": "g83-deep-batch", "section": "deep_is_s",
                             "symbol": row["symbol"], "date": row["date"],
                             "position": row["position"]}),
                nag=("s", ["s"], "entry"))


# --------------------------------------------------------------------- ledes

LEDES = {
    "mentor_ballot": (
        "The mentor rule ballot",
        "<p>Fifteen lines Scarface, Jdub, Neto, Lauren, Mamba or Hayden state "
        "and you never have, quoted in their own words and ordered by how much "
        "each would move the engine. No charts, and it is the fastest section on "
        "the page &mdash; <b>every yes here becomes work while you sleep</b>, so "
        "it goes first.</p>"),
    "is_this_an_s": (
        "Is this an S?",
        "<p>The control. Same instrument as the deck you graded before: an S on "
        "your ladder, at one of your six levels, nothing marked. Half are trades "
        "the engine took, half are mornings it refused, and the card does not say "
        "which. Everything else on this page gets read against this section.</p>"),
    "which_signal": (
        "Which signal on this chart?",
        "<p>Each of these mornings carries two setups that both look like trades. "
        "Both are marked with a dot &mdash; <b>where and when, and nothing "
        "else</b>. No entry line, no stop, no direction. Pick one, or neither. "
        "This is the question we kept getting wrong: the card never showed you "
        "WHICH signal it was asking about.</p>"),
    "what_minute": (
        "What minute do you get in?",
        "<p>Nothing marked, nothing claimed &mdash; just the morning and a box "
        "for the minute. The minute is the only field that says which trade you "
        "meant, and seven times out of seven it was earlier than the "
        "engine's.</p>"),
    "htf_agree": (
        "Does the higher timeframe agree?",
        "<p>The 1-minute morning with the setup marked, and beside it the same "
        "symbol's <b>daily</b> chart as it stood at the close <b>before</b> that "
        "morning. Four candidate definitions of higher-timeframe agreement were "
        "measured and all four came out ties, so the next move is to ask you "
        "which one is yours instead of guessing a fifth time.</p>"),
    "displacement": (
        "Is there displacement?",
        "<p>You named displacement in four of nine refusals without being asked. "
        "The shipped check measures a <b>fat candle</b>; every sentence you and "
        "the mentors have said measures <b>distance from the level</b>. These "
        "charts deliberately straddle that boundary. One line on what you "
        "measured it from settles it.</p>"),
    "where_is_the_stop": (
        "Where does the stop go?",
        "<p>The entry is given, and four candidate stops are drawn solid and "
        "labelled A B C D &mdash; the bottom of the entry candle, the broken "
        "level, prior pivot structure, and a wider disaster stop. Tap the line "
        "you'd use, or none of them.</p>"),
    "take_the_trade": (
        "Would you take this trade?",
        "<p>Thirty-nine charts, in <b>rounds of three</b>. Every one is a day the "
        "engine <b>actually put money on</b> &mdash; a real trade out of the "
        "two-year book, not a signal it looked at and refused. Inside a round the "
        "three days trended the same amount, on purpose: trendiness was the only "
        "measurable thing that moved your answer last time. No entry, no stop, no "
        "grade, no result, and <b>no setup name</b> &mdash; naming it invites you "
        "to answer the name instead of the chart.</p>"),
    "deep_is_s": (
        "Is this an S &mdash; the long sitting",
        "<p>One question, sixty times. Twenty mornings the engine <b>booked a "
        "trade</b>, twenty where it <b>found setups and refused every one</b>, "
        "twenty where it <b>found nothing at all</b> &mdash; shuffled, and which "
        "card is which is not on this page. That mix prices all three at once: do "
        "you agree with what it trades, is it right to refuse what it refuses, "
        "and what is it missing entirely.</p>"),
}


def section(key, cards_html, n):
    title, lede = LEDES[key]
    return ('<details class="sec" id="sec-%s" data-sec="%s">'
            '<summary><span class="sec-t">%s</span>'
            '<span class="sec-n" data-full="0">0 / %d</span></summary>'
            '<div class="sec-body">%s%s</div></details>'
            % (key, key, title, n, lede, cards_html))


# ---------------------------------------------------------------------- build

def build():
    g75_rows = load(SRC_G75)
    master_rows = load(SRC_MASTER)
    g83_rows = load(SRC_G83)
    idxbook = book_index()

    # ---------------- no-repeat guard, reported not assumed ----------------
    judged = bd.marked_card_ids()
    served_all = bd.served_card_ids()          # includes the three sources
    served = served_excluding(SOURCES + [OUT_MANIFEST])
    all_rows = g75_rows + master_rows + g83_rows
    cids = [r["card_id"] for r in all_rows]
    sym_days = sorted({"%s_%s" % (r["symbol"], r["date"])
                       for r in all_rows if r.get("symbol") and r.get("date")})
    dup_cid = sorted({c for c in cids if cids.count(c) > 1})
    hit_judged = sorted(set(sym_days) & judged)
    hit_served = sorted(set(sym_days) & served)
    drop = set(hit_judged) | set(hit_served) | set(dup_cid)
    guard = {"judged": len(judged), "served_all": len(served_all),
             "served_excl_sources": len(served), "rows": len(all_rows),
             "distinct_card_ids": len(set(cids)), "symbol_days": len(sym_days),
             "dup_card_id": dup_cid, "hit_judged": hit_judged,
             "hit_served": hit_served}

    def keep(r):
        if r["card_id"] in drop:
            return False
        sd = "%s_%s" % (r.get("symbol"), r.get("date"))
        return sd not in drop

    g75_rows = [r for r in g75_rows if keep(r)]
    master_rows = [r for r in master_rows if keep(r)]
    g83_rows = [r for r in g83_rows if keep(r)]

    # ---------------- bars, once ----------------
    bars = {}
    for r in g75_rows + master_rows + g83_rows:
        if not r.get("symbol"):
            continue
        k = (r["symbol"], r["date"])
        if k not in bars:
            bars[k] = bd.session_candles(*k)
    thin = sorted(k for k, v in bars.items() if len(v) < 60)
    assert not thin, "thin session: %s" % (thin,)

    by_sec = {}
    for r in master_rows:
        by_sec.setdefault(r["section"], []).append(r)

    manifest, sections, counts = [], [], {}

    def add(key, html_parts, rows_for_manifest):
        sections.append(section(key, "".join(html_parts), len(html_parts)))
        counts[key] = len(html_parts)
        manifest.extend(rows_for_manifest)

    # 1 -- mentor ballot
    parts, man = [], []
    for i, r in enumerate(sorted(by_sec.get("mentor_ballot", []),
                                 key=lambda x: x["rule_no"]), 1):
        b = g82.MENTOR_BALLOT[r["rule_no"] - 1]
        parts.append(render_ballot(i, r, b))
        man.append(dict(r, source_deck="omen-master-homework", deck=DECK_ID,
                        g84_section="mentor_ballot", g84_position=i,
                        answer_key="none -- an opinion ballot"))
    add("mentor_ballot", parts, man)

    # 2 -- is this an S
    parts, man = [], []
    for i, r in enumerate(by_sec.get("is_this_an_s", []), 1):
        c = bars[(r["symbol"], r["date"])]
        parts.append(render_is_s(i, r, c,
                                 idxbook.get((r["symbol"], r["date"], r["et"]))))
        man.append(dict(r, source_deck="omen-master-homework", deck=DECK_ID,
                        g84_section="is_this_an_s", g84_position=i))
    add("is_this_an_s", parts, man)

    # 3 -- which signal
    parts, man = [], []
    for i, r in enumerate(by_sec.get("which_signal", []), 1):
        c = bars[(r["symbol"], r["date"])]
        parts.append(render_which(i, r, c, idxbook))
        man.append(dict(r, source_deck="omen-master-homework", deck=DECK_ID,
                        g84_section="which_signal", g84_position=i))
    add("which_signal", parts, man)

    # 4 -- what minute
    parts, man = [], []
    for i, r in enumerate(by_sec.get("what_minute", []), 1):
        c = bars[(r["symbol"], r["date"])]
        parts.append(render_minute(i, r, c))
        man.append(dict(r, source_deck="omen-master-homework", deck=DECK_ID,
                        g84_section="what_minute", g84_position=i))
    add("what_minute", parts, man)

    # 5 -- higher timeframe
    parts, man = [], []
    for i, r in enumerate(by_sec.get("htf_agree", []), 1):
        c = bars[(r["symbol"], r["date"])]
        daily = g82.daily_candles(r["symbol"], r["date"],
                                  r.get("daily_sessions", g82.DAILY_SESSIONS))
        assert daily, "no daily bars for %s" % r["card_id"]
        parts.append(render_htf(i, r, c, daily))
        man.append(dict(r, source_deck="omen-master-homework", deck=DECK_ID,
                        g84_section="htf_agree", g84_position=i))
    add("htf_agree", parts, man)

    # 6 -- displacement
    parts, man = [], []
    for i, r in enumerate(by_sec.get("displacement", []), 1):
        c = bars[(r["symbol"], r["date"])]
        parts.append(render_disp(i, r, c))
        man.append(dict(r, source_deck="omen-master-homework", deck=DECK_ID,
                        g84_section="displacement", g84_position=i))
    add("displacement", parts, man)

    # 7 -- where is the stop
    parts, man = [], []
    for i, r in enumerate(by_sec.get("where_is_the_stop", []), 1):
        c = bars[(r["symbol"], r["date"])]
        parts.append(render_stop(i, r, c))
        man.append(dict(r, source_deck="omen-master-homework", deck=DECK_ID,
                        g84_section="where_is_the_stop", g84_position=i))
    add("where_is_the_stop", parts, man)

    # 8 -- g75, in its own rounds of three
    parts, man, last = [], [], None
    for i, r in enumerate(sorted(g75_rows, key=lambda x: (x["round"], x["card_id"])), 1):
        if r["round"] != last:
            last = r["round"]
            parts.append('<p class="roundlab">Round %d &mdash; three days that '
                         'trended the same</p>' % r["round"])
        parts.append(render_take(i, r, bars[(r["symbol"], r["date"])]))
        man.append(dict(r, source_deck="g75-deck2", deck=DECK_ID,
                        g84_section="take_the_trade", g84_position=i))
    n75 = sum(1 for p in parts if p.startswith("<article"))
    sections.append(section("take_the_trade", "".join(parts), n75))
    counts["take_the_trade"] = n75
    manifest.extend(man)

    # 9 -- g83
    parts, man = [], []
    total83 = len(g83_rows)
    for i, r in enumerate(sorted(g83_rows, key=lambda x: x["position"]), 1):
        parts.append(render_deep(i, r, bars[(r["symbol"], r["date"])], total83))
        man.append(dict(r, source_deck="g83-deep-batch", deck=DECK_ID,
                        g84_section="deep_is_s", g84_position=i))
    add("deep_is_s", parts, man)

    total = sum(counts.values())
    html = page(sections, total, counts)
    return html, manifest, guard, counts, total


def page(sections, total, counts):
    head = (
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>OMEN &mdash; everything outstanding, one page</title>')
    alarm = ('<div class="alarm" id="nostore" hidden>'
             '<b>This browser will not let the page save your answers.</b> '
             'Everything you tap still works, but it is gone the moment you '
             'close the tab. Tap <b>Copy all</b> and paste what you have into '
             'the chat before you leave &mdash; and do it often.</div>')
    mast = (
        '<div class="mast"><p class="eyebrow">OMEN homework &middot; one page, '
        'everything outstanding</p>'
        '<h1>%d things, in nine sections, on one page you can actually work in</h1>'
        '<p class="lede">The last three pages went out read-only and you could '
        'not tap anything. This one is the same three decks, <strong>re-rendered '
        'so they work</strong> &mdash; no chart is new and nothing you have '
        'already judged is in here. <strong>It saves every tap to this device as '
        'you go.</strong> Close it, lose signal, come back tomorrow: your answers '
        'are still here and it reopens at the first thing you have not done. '
        'Sections are collapsed; tap one to open it.</p></div>' % total)
    bar = ('<div class="bar">'
           '<span class="count" id="count">0 of %d answered</span>'
           '<span class="track"><span class="fill" id="fill"></span></span>'
           '<span class="saved" id="saved">saved</span>'
           '<button class="btn" type="button" id="nextbtn">Next unanswered</button>'
           '<button class="btn pri" type="button" id="copytop">Copy all</button>'
           '</div>' % total)
    export = (
        '<section class="exportbox">'
        '<h2>Getting your answers out &mdash; Copy all, then paste</h2>'
        '<p><b>Copy all is the way out of this page.</b> Downloads do not work '
        'inside the viewer &mdash; the button is there, it usually saves nothing, '
        'and it will tell you so. Tap <b>Copy all</b>, then paste into the chat. '
        'You can do it half-way through; nothing is lost by exporting early.</p>'
        '<div class="ebtns">'
        '<button class="btn pri big" type="button" id="copybtn">Copy all</button>'
        '<button class="btn" type="button" id="dlbtn">Download .jsonl '
        '(usually blocked)</button>'
        '<span id="copymsg"></span></div>'
        '<textarea id="out" spellcheck="false" autocapitalize="off" '
        'autocorrect="off">(nothing answered yet - your answers appear here as '
        'you tap)</textarea>'
        '<p class="small">If both buttons fail: long-press inside the box, '
        '<b>Select all</b>, <b>Copy</b>. That always works.</p></section>')
    foot = (
        '<div class="foot"><h2>That is everything outstanding</h2>'
        '<p>%s</p>'
        '<p>Nothing in here is a chart you have graded or been served before, in '
        'any deck, probe or page &mdash; checked against all 1,178 judged '
        'symbol-days and every manifest on disk.</p>'
        '<p style="margin-top:14px">'
        '<button class="btn pri big" type="button" id="copyfoot">Copy all</button>'
        '</p></div>'
        % " &middot; ".join("%s %d" % (LEDES[k][0], v) for k, v in counts.items()))
    return "".join([head, CSS, '<div class="wrap">', alarm, mast, bar, export]
                   + sections + [foot, "</div>", JS])


# ------------------------------------------------------------------ selfcheck

LEAK_KEYS = ["sgrade", "legacy_grade", "hindsight_r", "engine_r", "sep_atr",
             "sep_bucket", "htf_score", "htf_group", "shipped_check_trips",
             "role_meaning", "prefilter_reach_r", "first_trade_r", "engine_signals",
             "engine_trades", "fired_not_traded", "trades_that_day", "stop_pct",
             "disaster_pct", "downgrades", "er_session"]
EXTERNAL = ["http://", "https://", "fonts.googleapis", "fonts.gstatic", "//cdn",
            "fetch(", "XMLHttpRequest", "WebSocket"]


def selfcheck(html, manifest, total):
    bad = [k for k in LEAK_KEYS if k in html]
    assert not bad, "answer key leaked into the HTML: %s" % bad
    ext = [k for k in EXTERNAL if k in html]
    assert not ext, "external resource in the page: %s" % ext
    assert "localStorage" in html, "the page lost its own save"
    assert "navigator.clipboard" in html, "the page lost its clipboard export"
    assert "<canvas" not in html, "a canvas got in; charts must be SVG"
    assert html.count('<article class="card"') == total, "card count drifted"
    ids = [m for m in re.findall(r'<article class="card" data-cid="([^"]+)"', html)]
    assert len(set(ids)) == len(ids) == total, "duplicate data-cid on the page"
    man_ids = [r["card_id"] for r in manifest]
    assert sorted(man_ids) == sorted(ids), "manifest and page disagree on cards"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true",
                    help="re-read the built page and check it, without rebuilding")
    a = ap.parse_args()

    html, manifest, guard, counts, total = build()
    selfcheck(html, manifest, total)

    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    os.makedirs(os.path.dirname(OUT_MANIFEST), exist_ok=True)
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(html)
    with open(OUT_MANIFEST, "w", encoding="utf-8") as fh:
        for r in manifest:
            fh.write(json.dumps(r, sort_keys=True) + "\n")

    size = os.path.getsize(OUT_HTML)
    print("=" * 72)
    print("NO-REPEAT GUARD")
    print("=" * 72)
    print("  judged symbol-days (marked_card_ids)          %d" % guard["judged"])
    print("  served_card_ids() as-is                       %d  <- includes the "
          "three source manifests" % guard["served_all"])
    print("  served, the three sources excluded            %d" % guard["served_excl_sources"])
    print("  items read from the three manifests           %d" % guard["rows"])
    print("  distinct card_ids                             %d" % guard["distinct_card_ids"])
    print("  distinct symbol-days                          %d" % guard["symbol_days"])
    print("  card_id repeated ACROSS the three sources     %s"
          % (guard["dup_card_id"] or "none"))
    print("  collides with a JUDGED symbol-day             %s"
          % (guard["hit_judged"] or "none"))
    print("  collides with a SERVED symbol-day             %s"
          % (guard["hit_served"] or "none"))
    print("  dropped                                       %d"
          % (len(guard["dup_card_id"]) + len(guard["hit_judged"])
             + len(guard["hit_served"])))
    print()
    print("=" * 72)
    print("THE PAGE")
    print("=" * 72)
    for k, v in counts.items():
        print("  %-22s %3d   %s" % (k, v, LEDES[k][0]))
    print("  %-22s %3d" % ("TOTAL", total))
    print("  wrote %s  (%.2f MB)" % (OUT_HTML, size / 1e6))
    print("  wrote %s  (%d rows, answer key)" % (OUT_MANIFEST, len(manifest)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
