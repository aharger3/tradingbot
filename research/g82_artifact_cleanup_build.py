#!/usr/bin/env python3
"""Generator for research/omen-71-verdict.html.

No script produced this file when it was first committed (a0997963) -- it was
authored directly as HTML. Austin: "it has a lot of issues -- random repeats,
and some metrics that are not very clean." Investigation (research/g82_artifact_cleanup.md)
found the file had no generator at all, which is itself the violation of the
CLAUDE.md rule "if you publish a number, commit the script that made it." This
script is that fix: it re-derives the two cells in the "What moved" table that
had gone stale/wrong, from the canonical measurement outputs, and reprints the
rest of the page unchanged.

Two numbers were wrong in the committed HTML, both in the "What moved" table's
AFTER column, both because they were hand-transcribed instead of read from data:

  1. Win rate AFTER was typed as 49.7% (delta -3.4). research/t23_stack.json
     arms.stack.win_rate is 49.5 (research/t23_stack.md line 78 prints 49.50%
     to the same precision). Delta from the BEFORE figure (53.1%, T0's
     pre-ratification book, research/t0_ratified_rebaseline.md "before" column)
     is therefore -3.6, not -3.4.

  2. Index trades AFTER was typed as 137. That is T0's book (t23_stack.json
     arms.t0_base.index_trades = 137) -- i.e. the state BEFORE the T23 stack
     landed, not the shipped state the rest of the row's siblings (traded,
     mean R, total R, months green) all report. arms.stack.index_trades is
     164 (T23_stack.md's own before/after row: "index (ETF) trades | 137 |
     164"). The multiplier against the BEFORE figure (18, from
     t0_ratified_rebaseline.md) is therefore 164/18 = 9.1x, not 137/18 = 7.6x.

Every other cell on the page was checked against its cited source
(research/t23_stack.json, research/t23_stack.md, research/t0_ratified_rebaseline.md,
research/t0_heldout_recall.json) and reproduces exactly -- nothing else in this
page moved when this script was written. Re-running this script is idempotent:
it does not re-run any backtest, it only reprints the existing page with these
two cells re-derived from the JSON that already exists on disk.

Nothing about the underlying measurement is touched by this script. If the
route-bug caveat in note 1, or the T0-vs-T23 chaining in this table, is itself
wrong, that is a measurement question for Austin -- not something this script
silently "fixes".
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "research" / "omen-71-verdict.html"
STACK_JSON = REPO / "research" / "t23_stack.json"

# BEFORE figures for this row: T0's pre-ratification book, cited to
# research/t0_ratified_rebaseline.md ("## 1. The one table"). No structured
# JSON exists for that comparison (only research/t0_rebaseline_table.md, a
# markdown table) -- these two are held as constants rather than parsed out
# of prose, same as every other BEFORE cell already on this page.
WIN_RATE_BEFORE = 53.1
INDEX_TRADES_BEFORE = 18


def main() -> None:
    stack = json.loads(STACK_JSON.read_text(encoding="utf-8"))["arms"]["stack"]

    win_rate_after = stack["win_rate"]  # 49.5
    win_rate_move = win_rate_after - WIN_RATE_BEFORE

    index_after = stack["index_trades"]  # 164
    index_mult = index_after / INDEX_TRADES_BEFORE

    # The TEMPLATE literal below picks up one leading and one extra trailing
    # newline from how the string is embedded here; strip back to exactly the
    # single trailing newline the committed file has.
    html = TEMPLATE.strip("\n") + "\n"
    html = html.replace("__WR_AFTER__", f"{win_rate_after:.1f}%")
    html = html.replace("__WR_MOVE__", f"&minus;{abs(win_rate_move):.1f}")
    html = html.replace("__IDX_AFTER__", f"{index_after:,}")
    html = html.replace("__IDX_MOVE__", f"{index_mult:.1f}&times;")

    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({len(html)} bytes)")
    print(f"  win rate after:   {win_rate_after:.1f}%  (was 49.7%)")
    print(f"  win rate move:    -{abs(win_rate_move):.1f}  (was -3.4)")
    print(f"  index trades after: {index_after:,}  (was 137)")
    print(f"  index trades move:  {index_mult:.1f}x  (was 7.6x)")


TEMPLATE = '''
<title>OMEN 7.1 Verdict</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root{
  --bg:#EDEFF4; --surface:#FFFFFF; --surface2:#F5F7FA; --line:#D5DAE4;
  --ink:#111621; --muted:#5A6377; --faint:#8A93A6;
  --accent:#1F5FD1; --accent-soft:#DCE6FA;
  --met:#177A55; --met-soft:#DCF0E7;
  --miss:#BE3B2C; --miss-soft:#FBE2DE;
  --warn:#B4791A; --warn-soft:#FAEFD8;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0D1018; --surface:#151A25; --surface2:#1B2130; --line:#283041;
  --ink:#E7EBF3; --muted:#8C95A9; --faint:#697285;
  --accent:#6C9BFF; --accent-soft:#1B2740;
  --met:#3FBF8C; --met-soft:#14301F;
  --miss:#F0705E; --miss-soft:#331A18;
  --warn:#DDA83B; --warn-soft:#2E2413;
}}
:root[data-theme="dark"]{
  --bg:#0D1018; --surface:#151A25; --surface2:#1B2130; --line:#283041;
  --ink:#E7EBF3; --muted:#8C95A9; --faint:#697285;
  --accent:#6C9BFF; --accent-soft:#1B2740;
  --met:#3FBF8C; --met-soft:#14301F;
  --miss:#F0705E; --miss-soft:#331A18;
  --warn:#DDA83B; --warn-soft:#2E2413;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"IBM Plex Sans",system-ui,-apple-system,sans-serif;
  font-size:16px;line-height:1.6;-webkit-text-size-adjust:100%}
.mono{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}
h1,h2,h3{margin:0;text-wrap:balance}
a{color:var(--accent)}

.wrap{max-width:720px;margin:0 auto;padding:0 20px 90px}

/* ---- masthead ---- */
header{padding:40px 0 26px}
.eyebrow{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--muted);margin:0 0 12px}
h1{font-family:"Instrument Serif",Georgia,serif;font-size:clamp(34px,8vw,52px);
  font-weight:400;line-height:1.02;letter-spacing:-.01em}
.verdict{font-family:"Instrument Serif",Georgia,serif;font-size:clamp(21px,4.6vw,27px);
  line-height:1.34;margin:18px 0 0;max-width:30ch}
.verdict em{font-style:italic;color:var(--miss)}
.verdict b{font-style:normal;font-weight:400;color:var(--met)}

/* ---- gates ---- */
.gates{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:11px;
  margin:26px 0 0}
.gate{background:var(--surface);border:1px solid var(--line);border-radius:10px;
  padding:14px 15px;border-top:3px solid var(--line)}
.gate.met{border-top-color:var(--met)}
.gate.miss{border-top-color:var(--miss)}
.gate .g-name{font-size:11px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);margin-bottom:7px}
.gate .g-val{font-family:"IBM Plex Mono",monospace;font-size:25px;font-weight:600;
  line-height:1;font-variant-numeric:tabular-nums}
.gate.met .g-val{color:var(--met)}
.gate.miss .g-val{color:var(--miss)}
.gate .g-tgt{font-size:13px;color:var(--muted);margin-top:6px}
.pill{display:inline-block;font-family:"IBM Plex Mono",monospace;font-size:10px;
  letter-spacing:.09em;text-transform:uppercase;padding:2px 7px;border-radius:99px;
  vertical-align:2px;margin-left:7px}
.pill.met{background:var(--met-soft);color:var(--met)}
.pill.miss{background:var(--miss-soft);color:var(--miss)}
.pill.warn{background:var(--warn-soft);color:var(--warn)}

/* ---- sections ---- */
section{margin-top:44px}
h2{font-family:"Instrument Serif",Georgia,serif;font-size:27px;font-weight:400;
  padding-bottom:9px;border-bottom:1px solid var(--line);margin-bottom:6px}
.sub{color:var(--muted);font-size:14.5px;margin:10px 0 18px;max-width:62ch}

/* ---- table ---- */
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;
  border:1px solid var(--line);border-radius:10px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:14px;min-width:430px}
th,td{padding:9px 13px;text-align:left;border-bottom:1px solid var(--line)}
th{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);
  font-weight:600;background:var(--surface2);white-space:nowrap}
tr:last-child td{border-bottom:none}
td.n{font-family:"IBM Plex Mono",monospace;text-align:right;font-variant-numeric:tabular-nums;
  white-space:nowrap}
.up{color:var(--met)} .down{color:var(--miss)} .flat{color:var(--muted)}

/* ---- actions ---- */
ol.acts{list-style:none;counter-reset:a;margin:0;padding:0;
  display:flex;flex-direction:column;gap:13px}
ol.acts>li{counter-increment:a;background:var(--surface);border:1px solid var(--line);
  border-radius:10px;padding:16px 17px 16px 56px;position:relative}
ol.acts>li::before{content:counter(a);position:absolute;left:15px;top:15px;
  font-family:"IBM Plex Mono",monospace;font-size:13px;font-weight:600;
  color:var(--accent);background:var(--accent-soft);width:26px;height:26px;
  border-radius:7px;display:flex;align-items:center;justify-content:center}
ol.acts>li.top{border-color:var(--accent)}
.act-h{font-size:16.5px;font-weight:600;line-height:1.35;margin-bottom:7px}
.act-b{font-size:14.5px;color:var(--muted);margin:0}
.act-b b{color:var(--ink);font-weight:600}
.meta{display:flex;flex-wrap:wrap;gap:7px;margin-top:11px}
.tag{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.05em;
  text-transform:uppercase;color:var(--muted);background:var(--surface2);
  border:1px solid var(--line);border-radius:99px;padding:3px 9px}
.tag.time{color:var(--accent);border-color:var(--accent);background:var(--accent-soft)}

/* ---- notes ---- */
ul.notes{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:12px}
ul.notes li{font-size:14.5px;color:var(--muted);padding-left:16px;position:relative;
  max-width:64ch}
ul.notes li::before{content:"";position:absolute;left:0;top:9px;width:6px;height:6px;
  border-radius:50%;background:var(--faint)}
ul.notes li b{color:var(--ink)}

.callout{background:var(--surface);border:1px solid var(--line);
  border-left:3px solid var(--warn);border-radius:9px;padding:15px 17px;margin-top:18px}
.callout p{margin:0;font-size:14.5px;color:var(--muted);max-width:62ch}
.callout p+p{margin-top:9px}
.callout b{color:var(--ink)}

footer{margin-top:52px;padding-top:20px;border-top:1px solid var(--line);
  font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--faint);
  line-height:1.8;word-break:break-word}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
</style>

<div class="wrap">

<header>
  <p class="eyebrow">Overnight run &middot; 29 Aug 2026 &middot; 23 agents &middot; 10.3 hrs</p>
  <h1>OMEN 7.1</h1>
  <p class="verdict">The money gate is <em>not reached</em> and it got further away. Durability is <b>met for the first time</b>. Recall moved for the first time in the project&rsquo;s history &mdash; and the number that moved is measured on the wrong router.</p>
</header>

<div class="gates">
  <div class="gate miss">
    <div class="g-name">Money</div>
    <div class="g-val">+0.5495<span style="font-size:15px">R</span></div>
    <div class="g-tgt">target 2.0R &middot; was +0.8341R</div>
  </div>
  <div class="gate met">
    <div class="g-name">Durability</div>
    <div class="g-val">25 / 25</div>
    <div class="g-tgt">every month green &middot; was 23/25</div>
  </div>
  <div class="gate miss">
    <div class="g-name">Recall</div>
    <div class="g-val">67.6%</div>
    <div class="g-tgt">target 90% &middot; was 52.9% &mdash; see note 1</div>
  </div>
</div>

<section>
  <h2>What moved</h2>
  <p class="sub">Your 33 ratified answers landed first (T0), then three levers stacked on top. The <span class="mono">before</span> column is the book you saw yesterday, re-run and reproduced to four decimals.</p>
  <div class="scroll">
  <table>
    <thead><tr><th>Figure</th><th class="n">Before</th><th class="n">After</th><th class="n">Move</th></tr></thead>
    <tbody>
      <tr><td>Traded signals</td><td class="n">1,017</td><td class="n">2,437</td><td class="n up">+1,420</td></tr>
      <tr><td>Signals detected</td><td class="n">45,193</td><td class="n">76,019</td><td class="n up">+30,826</td></tr>
      <tr><td>Mean R</td><td class="n">+0.8341</td><td class="n">+0.5495</td><td class="n down">&minus;0.2846</td></tr>
      <tr><td>Win rate</td><td class="n">53.1%</td><td class="n">__WR_AFTER__</td><td class="n down">__WR_MOVE__</td></tr>
      <tr><td>Months green</td><td class="n">23 / 25</td><td class="n">25 / 25</td><td class="n up">gate met</td></tr>
      <tr><td>Total R</td><td class="n">+848</td><td class="n">+1,339</td><td class="n up">+491</td></tr>
      <tr><td>Worst single trade</td><td class="n">&minus;1.25R</td><td class="n">&minus;1.00R</td><td class="n up">capped</td></tr>
      <tr><td>Losses past 1R</td><td class="n">460</td><td class="n">0</td><td class="n up">fixed</td></tr>
      <tr><td>Index trades</td><td class="n">18</td><td class="n">__IDX_AFTER__</td><td class="n up">__IDX_MOVE__</td></tr>
      <tr><td>Held-out S recall</td><td class="n">18 / 34</td><td class="n">23 / 34</td><td class="n up">+5, &minus;0</td></tr>
    </tbody>
  </table>
  </div>
  <div class="callout">
    <p><b>Read the book honestly.</b> It is bigger, more durable and worse per trade. Twelve gates came off in one wave because you said so, and they were suppressing more than half the book &mdash; the trades they were hiding are real trades, and on average they are below the ones already there.</p>
    <p><b>Of the three levers stacked on top, none moved money outside its own error bar.</b> The X&nbsp;lift entered on recall alone; the stop floor and the loss halt entered because they are your ratified answers, not because they measured well. That is stated plainly rather than dressed up.</p>
  </div>
</section>

<section>
  <h2>What is still blocking</h2>
  <p class="sub">Three things, in the order they cost you.</p>
  <ul class="notes">
    <li><b>The recall number is measured on the wrong router.</b> <span class="mono">t4_engine_recall.CaptureRunner._route</span> is a hand-rolled copy of the real router that never calls <span class="mono">super()</span>. <span class="mono">backtest_week</span> had the identical bug and was fixed in 5.0; the recall harness never was. So 67.6% describes the harness. On the traded book it is <b>1 of 34</b>. The +5/&minus;0 gain is real (one harness, both arms) &mdash; the level is not.</li>
    <li><b>96.4% of what the recall lever promotes dies on one guard.</b> <span class="mono">_min_viable_stop</span> kills 10 of your 13 graded vetoes &mdash; not the X grade. The lever is operating on 3.6% of the population it was built for, which is why its money move is a null. Action 1 below unlocks it.</li>
    <li><b>Mean 2.0R is a selection problem and exits are closed.</b> 47 exit arms ran; zero beat the shipped exit outside its bar, and 29 cleared their bar moving <em>down</em>. A perfect non-causal selector on this exit reaches 2.0R on only <b>51.6%</b> of the book &mdash; so the gate cannot be reached without discarding at least half of it. No further exit work should be funded.</li>
  </ul>
</section>

<section>
  <h2>What you can do</h2>
  <p class="sub">Eleven actions, ranked by what each unlocks. Every one is a thing to do, not a question to answer. The first four are the whole morning if you only have one.</p>

  <ol class="acts">
    <li class="top">
      <div class="act-h">Settle where the stop goes</div>
      <p class="act-b">Two charts &mdash; <span class="mono">MARA 2026-03-10 09:49</span> and <span class="mono">PLTR 2026-05-27 10:03</span>. You graded both <b>S</b>; on both the engine&rsquo;s stop is the <em>same price</em> as the entry, so it refuses the trade. Three sentences: (a) does the level stop sit at the retested level, or one tolerance unit beyond it; (b) does &ldquo;no minimum stop, size to the stop&rdquo; extend past the one-candle rule to break-and-retest and the 84% re-entry; (c) is a stop narrower than one typical 1-minute candle ever a real order, or is that day a skip. <b>Your R4 and R15 collide on a four-cent stop.</b></p>
      <div class="meta"><span class="tag time">~10 min</span><span class="tag">unlocks 4 tracks</span><span class="tag">highest value</span></div>
    </li>

    <li class="top">
      <div class="act-h">Pick the disaster stop: &minus;1R or &minus;1.25R</div>
      <p class="act-b">At <b>&minus;1R</b> the resting order sits at the level stop&rsquo;s own price, so a wick takes you out and the close-only rule you have settled five times becomes unreachable &mdash; 1,462 of 1,468 losses exit exactly at the stop. At <b>&minus;1.25R</b> the close rule survives, the recoverable-trade kill halves (54 trades / 242R a year against 125 / 497R) and win rate goes 42.8% &rarr; 46.0%, but you lose one green month. Both numbers are yours; neither arm clears its error bar, so <b>no measurement can settle this.</b></p>
      <div class="meta"><span class="tag time">~2 min</span><span class="tag">one word</span></div>
    </li>

    <li class="top">
      <div class="act-h">Grade eight side-by-side chart pairs</div>
      <p class="act-b"><span class="mono">QQQ 2026-06-29 &middot; META 2025-12-22 &middot; META 2025-09-18 &middot; NVDA 2026-02-05 &middot; NVDA 2025-09-29 &middot; INTC 2025-06-05 &middot; SPCX 2026-06-30 &middot; IREN 2026-06-03</span>. On each you said the good entry was one candle earlier &mdash; and on each <b>the engine had already produced that exact candle and threw it away with an X.</b> Answer earlier / later / either. Decides an arm worth 218 traded rows.</p>
      <div class="meta"><span class="tag time">~10 min</span><span class="tag">8.4% of the book</span></div>
    </li>

    <li class="top">
      <div class="act-h">One question on twelve one-candle-rule charts</div>
      <p class="act-b">&ldquo;Is this candle a strong PA entry?&rdquo; Six the strict detector keeps, six it deletes that you would most plausibly have taken. That one clause does <b>96% of the filtering</b>, and the engine currently answers it with <span class="mono">1.5&times;</span> &mdash; a constant borrowed from the 84% rule&rsquo;s reclaim gate that nobody ever put to you. <b>147 of your own S-graded trades hang on it.</b></p>
      <div class="meta"><span class="tag time">~8 min</span><span class="tag">147 S trades</span></div>
    </li>

    <li>
      <div class="act-h">Strike out the levels you would never target</div>
      <p class="act-b">Your &ldquo;pick a level first, 2R only if none&rdquo; fires on <b>0.00%</b> of 2,437 trades &mdash; because the engine finds <b>9.43 levels</b> where you draw five or six. &ldquo;Level first&rdquo; currently means &ldquo;nearest of nine&rdquo;, and it measures as the worst exit arm tested. We list every level the engine can see on a handful of your graded cards; you circle the real ones.</p>
      <div class="meta"><span class="tag time">~10 min</span><span class="tag">fixes R9</span></div>
    </li>

    <li>
      <div class="act-h">Reply &ldquo;ship&rdquo; or &ldquo;don&rsquo;t&rdquo; on the arrival-order promote</div>
      <p class="act-b">Over two years <b>289</b> setups your own eight variables score as <b>S</b> were alerted and never traded, for one reason: they were not the first with-trend signal of the day. Your sentence was <em>&ldquo;don&rsquo;t let it cap you of S opportunities&rdquo;</em>, and arrival order is capping 289 of them. Measurably it changes nothing &mdash; mean R +0.0075 inside a &plusmn;0.0870 bar, 25/25 green either way.</p>
      <div class="meta"><span class="tag time">one word</span><span class="tag">289 S setups</span></div>
    </li>

    <li>
      <div class="act-h">Resolve the loss halt against &ldquo;trade every day&rdquo;</div>
      <p class="act-b">On the new book the two-consecutive-loss halt fires on <b>49% of trading days</b>, blocks <b>857 trades</b>, and those 857 would have booked <b>+320R</b> &mdash; 19% of the book&rsquo;s return, to buy a mean-R gain inside its own error bar. R31 says put it in both paths; R20 says you want to trade every day. Both are yours. Say whether halving your trading days is what you meant, or name a different trigger &mdash; three losses, an R drawdown, a time of day.</p>
      <div class="meta"><span class="tag time">~3 min</span><span class="tag">19% of return</span></div>
    </li>

    <li>
      <div class="act-h">Reply &ldquo;8R&rdquo; or &ldquo;5R&rdquo; for the card filter</div>
      <p class="act-b">The deck pre-filter that stops you being served trades that do not fit your system collapsed to one rule: reject a card whose furthest watched level ahead is more than 8R away. <b>8R</b> &rarr; you refuse 63.5% instead of 71.1%, costs 1 of 18 S-day cards. <b>5R</b> &rarr; you refuse 58.5%, costs 3. <b>8R ships until you say otherwise.</b> Also: <span class="mono">BABA 2025-07-23</span> is a clean A card the filter drops &mdash; if that should have reached you, the threshold loosens.</p>
      <div class="meta"><span class="tag time">one word</span><span class="tag">next deck</span></div>
    </li>

    <li>
      <div class="act-h">Resolve a contradiction inside your own corpus</div>
      <p class="act-b">Same mentor, two sources. <em>mastermind-1-0</em>: &ldquo;after first scale, can move stop to breakeven, then hold runner.&rdquo; The bread-and-butter bonus video says the opposite. Only one of the engine&rsquo;s three scaling rules is corpus-confirmed; the other two are contradicted by direct quotes. The corpus cannot settle this because the corpus disagrees with itself.</p>
      <div class="meta"><span class="tag time">~5 min</span><span class="tag">runner rules</span></div>
    </li>

    <li>
      <div class="act-h">Buy a small block of ES/NQ 1-minute bars</div>
      <p class="act-b">Weeks, not years &mdash; a real futures vendor such as Databento. The archive has <b>zero</b> futures bars (verified: 34 symbols, 16,817 symbol-days, 0 futures), Polygon sells no futures, and <span class="mono">futures_feed.py</span> only reads live. Nothing past a code-level check can start on futures or prop firms without it. The funded-account side is already priced and waiting: Apex $150K, $250&ndash;350 risk unit.</p>
      <div class="meta"><span class="tag">costs money</span><span class="tag">unblocks prop firms</span></div>
    </li>

    <li>
      <div class="act-h">Log into the Tastytrade sandbox once</div>
      <p class="act-b">Confirm a single live option quote returns through <span class="mono">broker/tastytrade.py</span>. Every options number in this wave is Black-Scholes on prior-session sigma, never a real bid/ask &mdash; Polygon&rsquo;s options snapshot 403s and the adapter has never completed a live round trip. One session turns &ldquo;modelled&rdquo; into &ldquo;quoted&rdquo;. Must be run from the Mac; the Windows box cannot reach the host.</p>
      <div class="meta"><span class="tag time">~5 min</span><span class="tag">Mac only</span></div>
    </li>
  </ol>
</section>

<section>
  <h2>What did not run</h2>
  <p class="sub">Stated so nothing here reads as more finished than it is.</p>
  <ul class="notes">
    <li><b>No options, contracts, spreads or futures in any number on this page.</b> Every R here is the underlying.</li>
    <li><b>The 84% rule&rsquo;s &ldquo;same stop unless a new stop makes more sense&rdquo; was never measured alone.</b> It now has its own switch and ships <b>OFF</b> &mdash; shipping an unmeasured default is the failure this repo keeps repeating.</li>
    <li><b>FVG and flag were not deleted.</b> The adjudicator recommended it; your own answer says <em>keep the code</em>, and a ratified answer outranks an adjudication. The corpus verdict &mdash; neither setup is taught anywhere &mdash; is recorded in the code instead.</li>
    <li><b>The exit, strike, break-even and faster-cut families were not re-measured on the new book.</b> Their nulls were computed on the old selection, so they are refutations of their families rather than numbers that automatically survive.</li>
    <li><b>The live path was wired but never executed.</b> The halt is account-wide in the scanner and asserted by a test, but no live session has run it &mdash; and the <span class="mono">A+</span> promotion gate above it is still untouched.</li>
    <li><b>One track of 22 failed outright</b> (symbol-balance, on a git worktree error) and one measured against the pre-ratification engine, so its index arm is unadjudicable and lands default OFF.</li>
  </ul>
</section>

<footer>
  2,437 traded signals &middot; 76,019 detected &middot; 500 sessions &middot; 28 symbols<br>
  1R = $1,000 &middot; entries 09:30&ndash;11:00 &middot; stops on the candle close &middot; on-disk 1-minute archive, reproduces offline<br>
  regression_gate.py PASS &middot; s_grade fires 5 &rarr; 13 &middot; nothing went silent<br>
  research/t23_stack.md &middot; research/t0_ratified_rebaseline.md &middot; Projects/omen-2y-backtest.md
</footer>

</div>

'''


if __name__ == "__main__":
    main()
