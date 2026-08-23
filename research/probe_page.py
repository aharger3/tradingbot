"""probe_page.py -- shared shell for the OMEN 6 elicitation probes.

One visual identity across the ballot, the autopsy and the head-to-head: IBM Plex
(Serif display / Sans UI / Mono for anything numeric), a grey ground biased toward
the teal accent, and the market's own semantics -- green/red candles, amber for
Austin's entry, red-brown for a stop -- kept separate from that accent.

The page is a LIVE DOC. Everything a tap changes is a real attribute on a real
element, so it saves and Claude can read the answers straight off the page.
"""
from __future__ import annotations

FONTS = ('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=IBM+Plex+Mono:wght@400;500;600&'
         'family=IBM+Plex+Sans:wght@400;500;600;700&'
         'family=IBM+Plex+Serif:wght@500;600&display=swap">')

CSS = """
<style>
:root{
  --bg:#f3f5f4; --surface:#ffffff; --surface-2:#eceff0;
  --ink:#131e1c; --ink-2:#4c5b58; --ink-3:#7b8b87;
  --rule:#dbe2e0; --rule-2:#c3cecb;
  --accent:#0d6961; --accent-ink:#ffffff; --accent-soft:#dcece9;
  --up:#1d7a4c; --dn:#a63229; --entry:#a86a06; --stop:#8d3b33;
  --lvl-pd:#5b6ea8; --lvl-pm:#8a5ea3; --lvl-or:#3f7f76;
  --shadow:0 1px 2px rgba(19,30,28,.06),0 8px 24px -14px rgba(19,30,28,.28);
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --bg:#0d1211; --surface:#151d1c; --surface-2:#1d2726;
    --ink:#e7edeb; --ink-2:#a3b3af; --ink-3:#7d8d89;
    --rule:#25322f; --rule-2:#33433f;
    --accent:#54cfbe; --accent-ink:#07201d; --accent-soft:#16332f;
    --up:#48b57c; --dn:#e07068; --entry:#e0a340; --stop:#d47a70;
    --lvl-pd:#8fa2dc; --lvl-pm:#bb92d1; --lvl-or:#6dbcb0;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 28px -16px rgba(0,0,0,.7);
  }
}
:root[data-theme="dark"]{
  --bg:#0d1211; --surface:#151d1c; --surface-2:#1d2726;
  --ink:#e7edeb; --ink-2:#a3b3af; --ink-3:#7d8d89;
  --rule:#25322f; --rule-2:#33433f;
  --accent:#54cfbe; --accent-ink:#07201d; --accent-soft:#16332f;
  --up:#48b57c; --dn:#e07068; --entry:#e0a340; --stop:#d47a70;
  --lvl-pd:#8fa2dc; --lvl-pm:#bb92d1; --lvl-or:#6dbcb0;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 28px -16px rgba(0,0,0,.7);
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:"IBM Plex Sans",system-ui,-apple-system,Segoe UI,sans-serif;
  font-size:16px; line-height:1.5; -webkit-text-size-adjust:100%;
}
.wrap{max-width:800px; margin:0 auto; padding:0 14px 96px}

/* masthead */
.mast{padding:28px 0 18px; border-bottom:1px solid var(--rule)}
.eyebrow{
  font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:11px; font-weight:500;
  letter-spacing:.14em; text-transform:uppercase; color:var(--accent); margin:0 0 8px;
}
h1{
  font-family:"IBM Plex Serif",Georgia,serif; font-weight:600;
  font-size:clamp(26px,6vw,36px); line-height:1.15; margin:0 0 10px; text-wrap:balance;
}
.lede{margin:0; color:var(--ink-2); font-size:15px; max-width:62ch}
.lede strong{color:var(--ink); font-weight:600}

/* sticky progress */
.bar{
  position:sticky; top:0; z-index:20; background:var(--bg);
  border-bottom:1px solid var(--rule); margin:0 -14px 20px; padding:9px 14px;
  display:flex; align-items:center; gap:12px;
}
.bar .count{
  font-family:"IBM Plex Mono",monospace; font-size:13px; font-weight:600;
  font-variant-numeric:tabular-nums; color:var(--ink); white-space:nowrap;
}
.track{flex:1; height:4px; background:var(--rule); border-radius:2px; overflow:hidden}
.fill{height:100%; width:0%; background:var(--accent); transition:width .25s ease}
.jump{
  font:600 12px/1 "IBM Plex Sans",sans-serif; letter-spacing:.03em;
  background:var(--accent); color:var(--accent-ink); border:0; border-radius:999px;
  padding:9px 14px; cursor:pointer; white-space:nowrap;
}
.jump:hover{filter:brightness(1.08)}

/* cards */
.card{
  background:var(--surface); border:1px solid var(--rule); border-radius:10px;
  box-shadow:var(--shadow); margin:0 0 18px; overflow:hidden; scroll-margin-top:64px;
}
.card[data-done="1"]{border-color:var(--accent)}
.card > header{
  display:flex; align-items:baseline; gap:10px; flex-wrap:wrap;
  padding:13px 16px; border-bottom:1px solid var(--rule); background:var(--surface-2);
}
.idx{
  font-family:"IBM Plex Mono",monospace; font-size:11px; font-weight:600;
  color:var(--ink-3); font-variant-numeric:tabular-nums;
}
.tick{
  font-family:"IBM Plex Mono",monospace; font-size:16px; font-weight:600;
  letter-spacing:.02em;
}
.when{font-family:"IBM Plex Mono",monospace; font-size:13px; color:var(--ink-2)}
.tags{margin-left:auto; display:flex; gap:6px; flex-wrap:wrap; align-items:center}
.tag{
  font-family:"IBM Plex Mono",monospace; font-size:10px; font-weight:600;
  letter-spacing:.08em; text-transform:uppercase; padding:3px 7px; border-radius:4px;
  background:var(--accent-soft); color:var(--accent); border:1px solid transparent;
}
.tag.warn{background:transparent; color:var(--stop); border-color:var(--stop)}
.done-dot{width:8px; height:8px; border-radius:50%; background:var(--rule-2); flex:none}
.card[data-done="1"] .done-dot{background:var(--accent)}

/* chart */
.chartwrap{padding:10px 6px 4px; background:var(--surface)}
.chart{width:100%; height:auto; display:block}
.chart .grid{stroke:var(--rule); stroke-width:.6}
.chart .axis{
  font-family:"IBM Plex Mono",monospace; font-size:9px; fill:var(--ink-3);
  text-anchor:middle;
}
.chart .wk{stroke-width:1}
.chart .bd{stroke-width:.5}
.chart .up{stroke:var(--up); fill:var(--up)}
.chart .dn{stroke:var(--dn); fill:var(--dn)}
.chart .lvl{stroke-width:1; stroke-dasharray:5 4; opacity:.85}
.chart .lvl-t{font-family:"IBM Plex Mono",monospace; font-size:9px; font-weight:500}
.chart .lvl-pd{stroke:var(--lvl-pd); fill:var(--lvl-pd)}
.chart .lvl-pm{stroke:var(--lvl-pm); fill:var(--lvl-pm)}
.chart .lvl-or{stroke:var(--lvl-or); fill:var(--lvl-or)}
.chart .entry{stroke:var(--entry); stroke-width:1.3}
.chart .entry-t{
  font-family:"IBM Plex Mono",monospace; font-size:9px; font-weight:600; fill:var(--entry);
}
.chart .arrow{fill:var(--entry)}
.chart .stopl{stroke:var(--stop); stroke-width:1; stroke-dasharray:2 3}
.chart .stop-t{
  font-family:"IBM Plex Mono",monospace; font-size:9px; font-weight:600; fill:var(--stop);
}
.legend{
  display:flex; gap:14px; flex-wrap:wrap; padding:2px 16px 12px;
  font-family:"IBM Plex Mono",monospace; font-size:10px; color:var(--ink-3);
}
.legend b{font-weight:600}

/* questions */
.q{padding:14px 16px; border-top:1px solid var(--rule)}
.q h3{margin:0 0 3px; font-size:14px; font-weight:600; line-height:1.35; color:var(--ink)}
.q .hint{margin:0 0 10px; font-size:12.5px; color:var(--ink-3)}
.chips{display:flex; flex-wrap:wrap; gap:7px}
.chip{
  font:500 13.5px/1.2 "IBM Plex Sans",sans-serif; color:var(--ink-2);
  background:var(--surface); border:1px solid var(--rule-2); border-radius:8px;
  padding:10px 12px; min-height:42px; cursor:pointer; text-align:left;
  transition:background .12s,border-color .12s,color .12s;
}
.chip:hover{border-color:var(--accent)}
.chip:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
.chip[aria-pressed="true"]{
  background:var(--accent); border-color:var(--accent); color:var(--accent-ink);
  font-weight:600;
}
.q[data-tone="veto"] .chip[aria-pressed="true"]{
  background:var(--stop); border-color:var(--stop); color:#fff;
}
textarea.note{
  width:100%; margin-top:8px; min-height:56px; resize:vertical;
  font:400 14px/1.5 "IBM Plex Sans",sans-serif; color:var(--ink);
  background:var(--surface-2); border:1px solid var(--rule-2); border-radius:8px;
  padding:9px 11px;
}
textarea.note:focus-visible{outline:2px solid var(--accent); outline-offset:1px}

/* footer */
.foot{
  margin-top:26px; padding:16px; border:1px dashed var(--rule-2); border-radius:10px;
  font-size:13.5px; color:var(--ink-2);
}
.foot h2{
  font-family:"IBM Plex Serif",Georgia,serif; font-size:16px; font-weight:600;
  margin:0 0 6px; color:var(--ink);
}
.foot code{
  font-family:"IBM Plex Mono",monospace; font-size:12.5px; background:var(--surface-2);
  padding:1px 5px; border-radius:4px;
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
@media (max-width:520px){
  .wrap{padding:0 10px 96px}
  .bar{margin:0 -10px 16px; padding:8px 10px}
  .chip{flex:1 1 calc(50% - 4px); min-width:0}
  .q{padding:13px 12px}
  .card > header{padding:11px 12px}
}
</style>
"""

JS = """
<script>
(function(){
  function cards(){ return Array.prototype.slice.call(document.querySelectorAll('.card')); }
  function answered(card){
    var qs = card.querySelectorAll('.q[data-required="1"]');
    for (var i = 0; i < qs.length; i++){
      if (!qs[i].querySelector('.chip[aria-pressed="true"]')) return false;
    }
    return qs.length > 0;
  }
  function refresh(){
    var cs = cards(), done = 0;
    cs.forEach(function(c){
      var d = answered(c) ? '1' : '0';
      c.setAttribute('data-done', d);
      if (d === '1') done++;
    });
    var n = cs.length;
    var cnt = document.getElementById('count');
    if (cnt) cnt.textContent = done + ' / ' + n;
    var fill = document.getElementById('fill');
    if (fill) fill.style.width = (n ? (done * 100 / n) : 0) + '%';
  }
  document.addEventListener('click', function(e){
    if (!e.target.closest) return;
    var chip = e.target.closest('.chip');
    if (!chip){
      if (e.target.closest('.jump')){
        var next = cards().filter(function(c){
          return c.getAttribute('data-done') !== '1';
        })[0];
        if (next) next.scrollIntoView({behavior: 'smooth', block: 'start'});
      }
      return;
    }
    var q = chip.closest('.q');
    var on = chip.getAttribute('aria-pressed') === 'true';
    if (q.getAttribute('data-multi') !== '1'){
      q.querySelectorAll('.chip').forEach(function(o){
        o.setAttribute('aria-pressed', 'false');
      });
    }
    chip.setAttribute('aria-pressed', on ? 'false' : 'true');
    refresh();
  });
  refresh();
})();
</script>
"""


def shell(title, eyebrow, h1, lede, cards_html, footer_html):
    return "".join([
        "<title>%s</title>" % title, FONTS, CSS,
        '<div class="wrap">',
        '<div class="mast"><p class="eyebrow">%s</p><h1>%s</h1><p class="lede">%s</p></div>'
        % (eyebrow, h1, lede),
        '<div class="bar"><span class="count" id="count">0 / 0</span>'
        '<span class="track"><span class="fill" id="fill"></span></span>'
        '<button class="jump" type="button">Next unanswered</button></div>',
        cards_html,
        '<div class="foot">%s</div>' % footer_html,
        "</div>", JS,
    ])


def question(key, heading, hint, options, multi=False, required=True, tone="",
             note_placeholder=None):
    chips = "".join(
        '<button class="chip" type="button" data-v="%s" aria-pressed="false">%s</button>'
        % (v.replace('"', "&quot;"), lab) for v, lab in options)
    note = ""
    if note_placeholder:
        note = ('<textarea class="note" data-note="%s" placeholder="%s"></textarea>'
                % (key, note_placeholder.replace('"', "&quot;")))
    return ('<section class="q" data-q="%s" data-multi="%s" data-required="%s"%s>'
            '<h3>%s</h3><p class="hint">%s</p><div class="chips">%s</div>%s</section>'
            % (key, "1" if multi else "0", "1" if required else "0",
               ' data-tone="%s"' % tone if tone else "", heading, hint, chips, note))
