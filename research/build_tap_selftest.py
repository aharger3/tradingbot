"""build_tap_selftest.py -- self-verifying page for tap-on-chart marking (H2).

    python research/build_tap_selftest.py

Builds research/probes/tap_selftest.html: one card with a tappable chart
(research/probe_chart.py's `tappable=True`) and a driver script that, entirely
inside the browser and through the SAME pointerdown/input handlers the real
decks use:

  1. taps an entry candle, taps a second candle for the stop, taps the price
     rail three times for PT1/PT2/PT3, and moves the runner slider;
  2. exports (clicking the real #exportbtn) and reads the JSONL row back;
  3. reloads the page (sessionStorage carries a one-shot phase flag; the tap
     state itself is real localStorage, exactly like the deck) and asserts the
     restored marks equal what was tapped before the reload;
  4. prints PASS or FAIL into the page body and into document.title, so
     opening the file (or its claude.ai artifact) IS the test.

No question chips on this page -- only the tap surface and the runner --
because the point is to prove the tap contract, not to ask anything.
research/test_tap_marks.py drives the same page a second way (two jsdom
documents sharing one localStorage, matching research/test_omen_test1_page.py)
and checks the export format against a fixture.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from probe_chart import render          # noqa: E402
from probe_page import shell            # noqa: E402

OUT = os.path.join(HERE, "probes", "tap_selftest.html")


def make_candles(n=20):
    candles = []
    price = 100.0
    for i in range(n):
        o = round(price, 2)
        h = round(o + 0.6, 2)
        l = round(o - 0.6, 2)
        c = round(o + (0.22 if i % 2 == 0 else -0.17), 2)
        candles.append({
            "t": "2026-01-05T%02d:%02d:00" % (9 + (30 + i) // 60, (30 + i) % 60),
            "o": o, "h": h, "l": l, "c": c, "v": 1000,
        })
        price = c
    return candles


DRIVER = r"""
<script>
(function(){
  var PHASE_KEY = 'omen-tap-selftest:phase';
  var out = document.getElementById('result');
  var results = [];
  function check(name, cond, detail){
    results.push({name: name, ok: !!cond, detail: detail});
  }

  function svgOf(){ return document.querySelector('svg.chart[data-tappable="1"]'); }
  function geom(svg){
    return {
      n: +svg.getAttribute('data-n'), padl: +svg.getAttribute('data-padl'),
      padt: +svg.getAttribute('data-padt'), plotw: +svg.getAttribute('data-plotw'),
      ploth: +svg.getAttribute('data-ploth'), lo: +svg.getAttribute('data-lo'),
      hi: +svg.getAttribute('data-hi')
    };
  }
  function X(g, i){ return g.padl + (i + 0.5) * g.plotw / g.n; }
  function Y(g, p){
    var span = (g.hi - g.lo) || 1;
    return g.padt + (g.hi - p) * g.ploth / span;
  }
  /* exact inverse of probe_page.js's localXY(): given a desired viewBox point,
     produce the clientX/clientY that will map back to it -- whether the chart
     has real on-screen layout (a browser) or none at all (jsdom, no rect). */
  function toClient(svg, vx, vy){
    var rect = svg.getBoundingClientRect();
    var vbw = +svg.getAttribute('data-w'), vbh = +svg.getAttribute('data-h');
    if (!rect || !rect.width || !rect.height) return {x: vx, y: vy};
    return {x: rect.left + vx * (rect.width / vbw), y: rect.top + vy * (rect.height / vbh)};
  }
  function tap(el, cx, cy){
    var Evt = window.PointerEvent || window.MouseEvent;
    el.dispatchEvent(new Evt('pointerdown', {clientX: cx, clientY: cy,
                                              bubbles: true, cancelable: true}));
  }

  function readMarks(svg){
    function txt(sel){
      var el = svg.querySelector(sel);
      return el && !el.hasAttribute('hidden') ? el.textContent : null;
    }
    var card = svg.closest('.card');
    var slider = card.querySelector('input.runner');
    return {
      entry: txt('.tap-entry-t'), stop: txt('.tap-stop-t'),
      pt0: txt('.tap-pt0-t'), pt1: txt('.tap-pt1-t'), pt2: txt('.tap-pt2-t'),
      runner: slider ? slider.value : null
    };
  }

  function driveMarks(){
    var svg = svgOf(), ohlc = JSON.parse(svg.getAttribute('data-ohlc'));
    var g = geom(svg);
    var taphit = svg.querySelector('.taphit'), railhit = svg.querySelector('.railhit');

    // 1: entry on bar 5
    var p = toClient(svg, X(g, 5), g.padt + 5);
    tap(taphit, p.x, p.y);

    // 2: stop on bar 12, tapped near the bottom of the plot -> "long", so
    //    stop_p should land on bar 12's LOW (index 2 of [o,h,l,c]).
    p = toClient(svg, X(g, 12), g.padt + g.ploth - 2);
    tap(taphit, p.x, p.y);

    // 3-5: three rail taps for PT1/PT2/PT3, at three distinct prices
    var prices = [g.lo + (g.hi - g.lo) * 0.75,
                  g.lo + (g.hi - g.lo) * 0.85,
                  g.lo + (g.hi - g.lo) * 0.95];
    prices.forEach(function(pr){
      var q = toClient(svg, g.padl + g.plotw + 2, Y(g, pr));
      tap(railhit, q.x, q.y);
    });

    // runner slider -> 35%
    var card = svg.closest('.card');
    var slider = card.querySelector('input.runner');
    slider.value = '35';
    slider.dispatchEvent(new Event('input', {bubbles: true}));

    return {expect_stop: ohlc[12][2], expect_pts: prices};
  }

  function run(){
    var svg = svgOf();
    var exp = driveMarks();
    var before = readMarks(svg);

    check('entry mark drawn', before.entry === 'ENTRY i=5', before.entry);
    check('stop mark uses tapped candle low',
          before.stop && Math.abs(parseFloat(before.stop.split(' ')[1])
                                   - exp.expect_stop) < 0.005,
          before.stop);
    check('three PT marks drawn', before.pt0 && before.pt1 && before.pt2,
          [before.pt0, before.pt1, before.pt2].join(' | '));
    check('runner slider reads 35', before.runner === '35', before.runner);

    document.getElementById('exportbtn').click();
    var text = document.getElementById('out').value;
    var lines = text.split('\n').filter(function(l){ return l.trim(); });
    check('export is exactly one row', lines.length === 1, lines.length);
    var row = {};
    try { row = JSON.parse(lines[0]); } catch (e) {}
    check('row.entry_i is an int', Number.isInteger(row.entry_i), row.entry_i);
    check('row.entry_i == 5', row.entry_i === 5, row.entry_i);
    check('row.stop_p is a float near the tapped low',
          typeof row.stop_p === 'number' && Math.abs(row.stop_p - exp.expect_stop) < 0.005,
          row.stop_p);
    check('row.pt has 3 entries', Array.isArray(row.pt) && row.pt.length === 3,
          row.pt);
    check('row.runner_pct == 35', row.runner_pct === 35, row.runner_pct);

    sessionStorage.setItem(PHASE_KEY, JSON.stringify({before: before, row: row}));
    location.reload();
  }

  function verifyReload(){
    var prev;
    try { prev = JSON.parse(sessionStorage.getItem(PHASE_KEY) || 'null'); }
    catch (e) { prev = null; }
    if (!prev){ check('reload phase found a prior pass', false, 'no sessionStorage'); }
    else {
      var svg = svgOf();
      var after = readMarks(svg);
      check('reload restores entry mark', after.entry === prev.before.entry, after.entry);
      check('reload restores stop mark', after.stop === prev.before.stop, after.stop);
      check('reload restores all 3 PTs',
            after.pt0 === prev.before.pt0 && after.pt1 === prev.before.pt1
            && after.pt2 === prev.before.pt2,
            [after.pt0, after.pt1, after.pt2].join(' | '));
      check('reload restores runner slider', after.runner === prev.before.runner,
            after.runner);
      document.getElementById('exportbtn').click();
      var text2 = document.getElementById('out').value;
      check('export identical after reload',
            JSON.parse(text2.trim()).entry_i === prev.row.entry_i
            && JSON.parse(text2.trim()).stop_p === prev.row.stop_p
            && JSON.stringify(JSON.parse(text2.trim()).pt) === JSON.stringify(prev.row.pt)
            && JSON.parse(text2.trim()).runner_pct === prev.row.runner_pct,
            text2.trim());
    }
    sessionStorage.removeItem(PHASE_KEY);
    report();
  }

  function report(){
    var fails = results.filter(function(r){ return !r.ok; });
    var lines = results.map(function(r){
      return (r.ok ? 'PASS' : 'FAIL') + '  ' + r.name
             + (r.detail != null ? '  (' + JSON.stringify(r.detail) + ')' : '');
    });
    var verdict = fails.length ? 'FAIL' : 'PASS';
    out.textContent = verdict + '\n\n' + lines.join('\n');
    document.title = verdict + ' -- tap self-test';
  }

  if (sessionStorage.getItem(PHASE_KEY)){
    verifyReload();
  } else {
    run();
  }
})();
</script>
"""


def build():
    candles = make_candles()
    chart = render(candles, {}, label="tap self-test", tappable=True)
    card = (
        '<div class="card" data-cid="selftest-1" data-export=\'{"symbol":"TEST",'
        '"date":"2026-01-05"}\'>'
        '<header><span class="idx">1</span><span class="tick">TEST</span>'
        '<span class="when">2026-01-05</span></header>'
        '<div class="chartwrap">%s</div>'
        '<div class="tapout" data-role="tapout">tap a candle for entry</div>'
        '<div class="runnerrow"><label for="runner-1">runner</label>'
        '<input id="runner-1" type="range" class="runner" min="0" max="100" value="10">'
        '<span class="runnerval" data-role="runnerval">10%%</span></div>'
        '</div>'
    ) % chart
    footer = ('<h2>Self-test</h2><p>This page marks itself on load, reloads once, '
              'and reports PASS/FAIL below -- nothing to tap by hand.</p>'
              '<pre id="result" style="white-space:pre-wrap">running…</pre>')
    html = shell(
        title="tap self-test",
        eyebrow="H2 self-test",
        h1="Tap-on-chart self-test",
        lede="Drives entry / stop / 3 PTs / runner through the real handlers, "
             "exports, reloads, and checks it all comes back.",
        cards_html=card,
        footer_html=footer,
        deck_id="tap-selftest",
    )
    return html + DRIVER


def main():
    html = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("wrote %s (%d bytes)" % (OUT, len(html)))


if __name__ == "__main__":
    main()
