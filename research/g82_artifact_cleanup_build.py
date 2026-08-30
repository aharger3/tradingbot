#!/usr/bin/env python3
"""Generator for research/omen-71-verdict.html.

HISTORY. No script produced this file when it was first committed (a0997963) --
it was authored directly as HTML. The first fix (research/g82_artifact_cleanup.md)
gave it a generator that re-derived two stale table cells from research/t23_stack.json.

THIS REWRITE, 2026-08-30, FIXES THE SAME BUG ONE LEVEL UP. That first generator
still hard-read t23_stack.json -- a dated 29-August snapshot -- with no check
that it still matched the book on disk. It kept printing 2,437 trades and
$1,339,000 while research/bt2y_trades.json was rebuilt underneath it, first by
the dedupe fix (-> 4,508 trades) and then by the honest-fill rebuild
(-> 4,329 trades, research/g85_honest_book.md). Anyone re-running the old
script would have silently reprinted numbers from a book that no longer existed.
That is the exact failure shape research/book_stamp.py exists to catch.

So this version:
  1. Reads every dollar and R figure LIVE off research/bt2y_trades.json (via
     book_stamp.book_figures, which re-parses whenever the file's mtime
     changes) and off research/bt2y_trades_published_fill.json -- the frozen,
     byte-identical, UNOBTAINABLE control -- rather than off any cached JSON.
  2. Asserts the live book's identity (fill, trade count, signal count, sha256
     book_id) against the constants this generator was written against, and
     the recall report's grade counts and build date likewise. Any mismatch
     is a BookMismatch / SystemExit, not a silently stale number.
  3. Prints the fill mode and the book's build commit on the page itself
     (the provenance line under the header, and again in the footer).
  4. Drops the Google Fonts import -- Austin reads this on a phone -- for a
     system font stack. No other CSS token changed; g83_dark_theme.md already
     audited this page's dark palette as spec-correct.
  5. Keeps the page Austin said to keep: same gate cards, same "what moved"
     table, same blocking/action/not-run sections, same footer. Only the DATA
     changed, plus one new explicit line for the $397/day bar every dollar
     figure here is measured against, and NOT OBTAINABLE labels wherever the
     published fill appears.

Re-running this script is idempotent and offline: it does not re-run any
backtest or re-grade anything, it only re-reads the books and the recall
report that already exist on disk.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research"))

import book_stamp  # noqa: E402

OUT = REPO / "research" / "omen-71-verdict.html"
BOOK = REPO / "research" / "bt2y_trades.json"
PUBLISHED_BOOK = REPO / "research" / "bt2y_trades_published_fill.json"
RECALL_JSON = REPO / "research" / "g85_recall_honest.json"

BAR = 397.0     # Austin's money bar, $/day, ratified 2026-08-30 (six figures a year)

# What this generator was built to say. Every number PRINTED below is read live
# off the files on disk -- these constants are only the self-check ("did the
# thing I built this page to describe move?"), same pattern g85_honest_book.py
# uses for its own --check. A mismatch fails the build loudly instead of
# printing whatever the template says.
EXPECT_BOOK = dict(entry_fill="close", traded=4329, signals=127188,
                    book_id_="f76361ae47e9a3b2")
EXPECT_PUBLISHED_TRADED = 4508          # the frozen control -- must stay frozen
EXPECT_RECALL = dict(k=225, n=303, pct=74.3, points_below_gate=15.7,
                      published_pct=59.1, build_date="2026-08-30")

NOT_OBTAINABLE = '<span class="pill miss">NOT OBTAINABLE</span>'


def _pct(v):
    return "%.1f%%" % v


def _r(v):
    return ("+%.4f" % v) if v >= 0 else ("−%.4f" % -v)


def _usd(v):
    v = round(v)
    return ("−$%s" % format(int(-v), ",")) if v < 0 else ("$%s" % format(int(v), ","))


def _delta_usd(a, b):
    d = round(b - a)
    return ("+$%s" % format(int(d), ",")) if d >= 0 else ("−$%s" % format(int(-d), ","))


def _delta_pts(a, b):
    d = round(b - a, 1)
    return ("+%.1f" % d) if d >= 0 else ("−%.1f" % -d)


def _delta_int(a, b):
    d = b - a
    return ("+%s" % format(d, ",")) if d >= 0 else ("−%s" % format(-d, ","))


def load_figures():
    """Every number this page prints, read live, then checked against EXPECT_*."""
    meta = book_stamp.assert_book(BOOK, entry_fill=EXPECT_BOOK["entry_fill"],
                                  traded=EXPECT_BOOK["traded"],
                                  signals=EXPECT_BOOK["signals"],
                                  book_id_=EXPECT_BOOK["book_id_"])
    st = meta["stamp"]
    figs = book_stamp.book_figures(BOOK)
    honest_all, honest_one = figs["all"], figs["one_a_day"]

    pub_meta, _ = book_stamp.load_book(PUBLISHED_BOOK)
    if pub_meta.get("traded") != EXPECT_PUBLISHED_TRADED:
        raise SystemExit(
            "%s no longer holds %d traded trades (has %r) -- the frozen "
            "published-fill control moved. Re-derive every 'published fill / "
            "NOT OBTAINABLE' figure in this generator before publishing."
            % (PUBLISHED_BOOK, EXPECT_PUBLISHED_TRADED, pub_meta.get("traded")))
    pfigs = book_stamp.book_figures(PUBLISHED_BOOK)
    pub_all, pub_one = pfigs["all"], pfigs["one_a_day"]

    recall = json.loads(RECALL_JSON.read_text(encoding="utf-8"))
    built_date = st["built_at"][:10]
    recall_date = recall["generated"][:10]
    if recall_date != built_date != EXPECT_RECALL["build_date"] and recall_date != EXPECT_RECALL["build_date"]:
        raise SystemExit(
            "%s (generated %s) and the book (built %s) were not built on the "
            "same day this generator expects (%s) -- re-run g85_recall_honest.py "
            "against the current book before trusting the recall gate on this page."
            % (RECALL_JSON, recall_date, built_date, EXPECT_RECALL["build_date"]))
    r = recall["arms"]["honest"]["recall_S"]
    got_recall = (r["k"], r["n"], round(r["pct"], 1))
    want_recall = (EXPECT_RECALL["k"], EXPECT_RECALL["n"], EXPECT_RECALL["pct"])
    if got_recall != want_recall:
        raise SystemExit(
            "recall moved: %s says S-day recall is %s, this generator was built "
            "against %s. Re-derive the recall gate card and 'what moved' row."
            % (RECALL_JSON, got_recall, want_recall))
    pub_recall_pct = None
    for row in recall["headline"]["rows"]:
        if row["what"] == "trade taken on his S days (recall)":
            pub_recall_pct = row["published_fill"]["pct"]
    if pub_recall_pct is None or round(pub_recall_pct, 1) != EXPECT_RECALL["published_pct"]:
        raise SystemExit("published-fill recall in %s moved from %.1f%% -- re-check."
                         % (RECALL_JSON, EXPECT_RECALL["published_pct"]))
    sep = recall["separation_delta"]

    return dict(
        commit=st["git"]["commit"][:8], commit_subject=st["git"]["commit_subject"],
        built_at=st["built_at"], book_id=st["book_id"],
        dirty=st["git"]["dirty_engine_py"], dirty_count=st["git"]["dirty_py_count"],
        signals=meta["signals"], honest_all=honest_all, honest_one=honest_one,
        pub_all=pub_all, pub_one=pub_one, pub_signals=pub_meta["signals"],
        recall_pct=r["pct"], recall_k=r["k"], recall_n=r["n"],
        recall_gap=recall["arms"]["honest"]["points_below_gate"],
        pub_recall_pct=pub_recall_pct, sep_delta=sep,
    )


def build_html(f: dict) -> str:
    ha, ho = f["honest_all"], f["honest_one"]
    pa, po = f["pub_all"], f["pub_one"]

    money_val = _usd(ho["per_day"])
    money_tgt = (
        "= %sR/trade &middot; one trade a day, his stated rule &middot; target $397/day (2.0R) "
        "&middot; all signals: %s/day &middot; was %s/day on the published fill %s"
        % (_r(ho["mean_r"]), _usd(ha["per_day"]), _usd(po["per_day"]), NOT_OBTAINABLE))

    dur_val = "%d / %d" % (ho["months_green"], ho["months"])
    dur_tgt = ("every month green, one trade a day &middot; all signals: %d/%d &middot; "
              "was %d/%d on the published fill %s &mdash; MET, but unobtainable"
              % (ha["months_green"], ha["months"], po["months_green"], po["months"], NOT_OBTAINABLE))

    recall_val = _pct(f["recall_pct"])
    recall_tgt = ("target &ge;90%% of his S days &middot; %.1f pts short &middot; was %.1f%% on the "
                 "published fill %s &mdash; the gain is bought by firing more, not sorting better (note 1)"
                 % (f["recall_gap"], f["pub_recall_pct"], NOT_OBTAINABLE))

    verdict = (
        'The published price was never obtainable &mdash; the signal does not exist until the '
        'candle that makes it closes. Priced honestly, the one gate this page ever called '
        '<b style="color:var(--miss);font-style:normal">met</b> now <em>fails</em>: '
        '%d of %d months green, one trade a day. Money moved further from the target, not '
        'closer. Recall closed real ground &mdash; but the gain is bought by trading more '
        'days, not by telling his days apart.'
        % (ho["months_green"], ho["months"]))

    provenance = (
        'book <span class="mono">bt2y_trades.json</span> &middot; fill <b>CLOSE</b> '
        '(the signal minute&rsquo;s close, shipped default since 2026-08-30) &middot; '
        'commit <span class="mono">%s</span> &middot; id <span class="mono">%s</span> &middot; '
        'built <span class="mono">%s</span>%s'
        % (f["commit"], f["book_id"], f["built_at"],
           ' &middot; <span class="pill warn">%d dirty .py, incl. %s</span>'
           % (f["dirty_count"], ", ".join(f["dirty"])) if f["dirty"] else ""))

    moved_rows = "\n".join([
        row("Traded signals, all trades", format(pa["trades"], ","), format(ha["trades"], ","),
            _delta_int(pa["trades"], ha["trades"]), down=True),
        row("Win rate, all trades", _pct(pa["win_pct"]), _pct(ha["win_pct"]),
            _delta_pts(pa["win_pct"], ha["win_pct"]), down=True),
        row("Mean R, all trades", _r(pa["mean_r"]), _r(ha["mean_r"]),
            "%s%.4f" % ("+" if ha["mean_r"] >= pa["mean_r"] else "−",
                        abs(ha["mean_r"] - pa["mean_r"])), down=True),
        row("$ / day, all trades", _usd(pa["per_day"]), _usd(ha["per_day"]),
            _delta_usd(pa["per_day"], ha["per_day"]), down=True),
        row("Months green, all trades", "%d / %d MET" % (pa["months_green"], pa["months"]),
            "%d / %d FAIL" % (ha["months_green"], ha["months"]), "gate lost", down=True),
        row("Trades, one a day", format(po["trades"], ","), format(ho["trades"], ","),
            _delta_int(po["trades"], ho["trades"])),
        row("Win rate, one a day", _pct(po["win_pct"]), _pct(ho["win_pct"]),
            _delta_pts(po["win_pct"], ho["win_pct"]), down=True),
        row("Mean R, one a day", _r(po["mean_r"]), _r(ho["mean_r"]),
            "%s%.4f" % ("+" if ho["mean_r"] >= po["mean_r"] else "−",
                        abs(ho["mean_r"] - po["mean_r"])), down=True),
        row("$ / day, one a day", _usd(po["per_day"]), _usd(ho["per_day"]),
            _delta_usd(po["per_day"], ho["per_day"]), down=True),
        row("Months green, one a day", "%d / %d MET" % (po["months_green"], po["months"]),
            "%d / %d FAIL" % (ho["months_green"], ho["months"]), "gate lost", down=True),
        row("Worst drawdown, one a day", _usd(-po["worst_drawdown"]), _usd(-ho["worst_drawdown"]),
            "+$%s worse" % format(int(round(ho["worst_drawdown"] - po["worst_drawdown"])), ","), down=True),
        row("Recall vs. his S days", _pct(f["pub_recall_pct"]), _pct(f["recall_pct"]),
            "+%.1f pts, false fires +16.9 in lockstep" % (f["recall_pct"] - f["pub_recall_pct"])),
    ])

    footer = (
        '%s traded signals, honest fill &middot; %s traded on the frozen published-fill '
        'control, %s &middot; %s signals detected &middot; 500 sessions &middot; 28 symbols<br>'
        '1R = $1,000 &middot; entries 09:30&ndash;11:00 &middot; stops on the candle close, '
        'floored at &minus;1.25R &middot; on-disk 1-minute archive, reproduces offline<br>'
        '%s<br>'
        'research/g85_honest_book.md &middot; research/g85_recall_honest.md &middot; research/book_stamp.py'
        % (format(ha["trades"], ","), format(pa["trades"], ","), NOT_OBTAINABLE,
           format(f["signals"], ","), provenance))

    html = TEMPLATE.strip("\n") + "\n"
    for k, v in {
        "__EYEBROW__": "Regenerated 30 Aug 2026 &middot; off the honest-fill book, not the 29 Aug snapshot",
        "__PROVENANCE__": provenance,
        "__VERDICT__": verdict,
        "__MONEY_CLASS__": "miss",
        "__MONEY_VAL__": money_val,
        "__MONEY_TGT__": money_tgt,
        "__DUR_CLASS__": "miss",
        "__DUR_VAL__": dur_val,
        "__DUR_TGT__": dur_tgt,
        "__RECALL_CLASS__": "miss",
        "__RECALL_VAL__": recall_val,
        "__RECALL_TGT__": recall_tgt,
        "__MOVED_ROWS__": moved_rows,
        "__NOT_OBTAINABLE__": NOT_OBTAINABLE,
        "__FOOTER__": footer,
    }.items():
        html = html.replace(k, v)
    return html


def row(name, before, after, move, down=False):
    cls = "down" if down else "up"
    return ('      <tr><td>%s</td><td class="n">%s</td><td class="n">%s</td>'
            '<td class="n %s">%s</td></tr>' % (name, before, after, cls, move))


def main() -> None:
    f = load_figures()
    html = build_html(f)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({len(html)} bytes)")
    print(f"  book: fill={EXPECT_BOOK['entry_fill']} traded={f['honest_all']['trades']:,} "
          f"commit={f['commit']} id={f['book_id']}")
    print(f"  money, one-a-day: {_usd(f['honest_one']['per_day'])}/day "
          f"({_pct(f['honest_one']['per_day']/BAR*100)} of the $397 bar)")
    print(f"  durability, one-a-day: {f['honest_one']['months_green']}/{f['honest_one']['months']} "
          f"months green (all trades: {f['honest_all']['months_green']}/{f['honest_all']['months']})")
    print(f"  recall: {f['recall_pct']}% of his S days ({f['recall_gap']} pts short of 90%)")


TEMPLATE = '''
<title>OMEN 7.1 Verdict</title>
<style>
:root{
  --bg:#EDEFF4; --surface:#FFFFFF; --surface2:#F5F7FA; --line:#D5DAE4;
  --ink:#111621; --muted:#5A6377; --faint:#8A93A6;
  --accent:#1F5FD1; --accent-soft:#DCE6FA;
  --met:#177A55; --met-soft:#DCF0E7;
  --miss:#BE3B2C; --miss-soft:#FBE2DE;
  --warn:#B4791A; --warn-soft:#FAEFD8;
  --font-sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --font-mono:ui-monospace,"Cascadia Mono","Segoe UI Mono","SFMono-Regular",Consolas,"Liberation Mono",monospace;
  --font-serif:Georgia,"Iowan Old Style","Palatino Linotype","Book Antiqua",serif;
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
  font-family:var(--font-sans);
  font-size:16px;line-height:1.6;-webkit-text-size-adjust:100%}
.mono{font-family:var(--font-mono);font-variant-numeric:tabular-nums}
h1,h2,h3{margin:0;text-wrap:balance}
a{color:var(--accent)}

.wrap{max-width:720px;margin:0 auto;padding:0 20px 90px}

/* ---- masthead ---- */
header{padding:40px 0 26px}
.eyebrow{font-family:var(--font-mono);font-size:11px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--muted);margin:0 0 12px}
h1{font-family:var(--font-serif);font-size:clamp(34px,8vw,52px);
  font-weight:400;line-height:1.02;letter-spacing:-.01em}
.verdict{font-family:var(--font-serif);font-size:clamp(21px,4.6vw,27px);
  line-height:1.34;margin:18px 0 0;max-width:30ch}
.verdict em{font-style:italic;color:var(--miss)}
.verdict b{font-style:normal;font-weight:400;color:var(--met)}
.provenance{font-family:var(--font-mono);font-size:12px;color:var(--faint);
  margin:14px 0 0;line-height:1.7;word-break:break-word;max-width:62ch}

/* ---- gates ---- */
.gates{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:11px;
  margin:26px 0 0}
.gate{background:var(--surface);border:1px solid var(--line);border-radius:10px;
  padding:14px 15px;border-top:3px solid var(--line)}
.gate.met{border-top-color:var(--met)}
.gate.miss{border-top-color:var(--miss)}
.gate .g-name{font-size:11px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);margin-bottom:7px}
.gate .g-val{font-family:var(--font-mono);font-size:25px;font-weight:600;
  line-height:1;font-variant-numeric:tabular-nums}
.gate.met .g-val{color:var(--met)}
.gate.miss .g-val{color:var(--miss)}
.gate .g-tgt{font-size:13px;color:var(--muted);margin-top:6px}
.pill{display:inline-block;font-family:var(--font-mono);font-size:10px;
  letter-spacing:.09em;text-transform:uppercase;padding:2px 7px;border-radius:99px;
  vertical-align:2px;margin-left:7px}
.pill.met{background:var(--met-soft);color:var(--met)}
.pill.miss{background:var(--miss-soft);color:var(--miss)}
.pill.warn{background:var(--warn-soft);color:var(--warn)}

/* ---- sections ---- */
section{margin-top:44px}
h2{font-family:var(--font-serif);font-size:27px;font-weight:400;
  padding-bottom:9px;border-bottom:1px solid var(--line);margin-bottom:6px}
.sub{color:var(--muted);font-size:14.5px;margin:10px 0 18px;max-width:62ch}

/* ---- bar line ---- */
.barline{margin-top:14px}
.barline .barnum{font-family:var(--font-mono);font-size:22px;font-weight:600;color:var(--ink)}

/* ---- table ---- */
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;
  border:1px solid var(--line);border-radius:10px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:14px;min-width:430px}
th,td{padding:9px 13px;text-align:left;border-bottom:1px solid var(--line)}
th{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);
  font-weight:600;background:var(--surface2);white-space:nowrap}
tr:last-child td{border-bottom:none}
td.n{font-family:var(--font-mono);text-align:right;font-variant-numeric:tabular-nums;
  white-space:nowrap}
.up{color:var(--met)} .down{color:var(--miss)} .flat{color:var(--muted)}

/* ---- actions ---- */
ol.acts{list-style:none;counter-reset:a;margin:0;padding:0;
  display:flex;flex-direction:column;gap:13px}
ol.acts>li{counter-increment:a;background:var(--surface);border:1px solid var(--line);
  border-radius:10px;padding:16px 17px 16px 56px;position:relative}
ol.acts>li::before{content:counter(a);position:absolute;left:15px;top:15px;
  font-family:var(--font-mono);font-size:13px;font-weight:600;
  color:var(--accent);background:var(--accent-soft);width:26px;height:26px;
  border-radius:7px;display:flex;align-items:center;justify-content:center}
ol.acts>li.top{border-color:var(--accent)}
.act-h{font-size:16.5px;font-weight:600;line-height:1.35;margin-bottom:7px}
.act-b{font-size:14.5px;color:var(--muted);margin:0}
.act-b b{color:var(--ink);font-weight:600}
.meta{display:flex;flex-wrap:wrap;gap:7px;margin-top:11px}
.tag{font-family:var(--font-mono);font-size:10.5px;letter-spacing:.05em;
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
  font-family:var(--font-mono);font-size:12px;color:var(--faint);
  line-height:1.8;word-break:break-word}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
</style>

<div class="wrap">

<header>
  <p class="eyebrow">__EYEBROW__</p>
  <h1>OMEN 7.1</h1>
  <p class="verdict">__VERDICT__</p>
  <p class="provenance">__PROVENANCE__</p>
</header>

<div class="gates">
  <div class="gate __MONEY_CLASS__">
    <div class="g-name">Money</div>
    <div class="g-val">__MONEY_VAL__<span style="font-size:14px">/day</span></div>
    <div class="g-tgt">__MONEY_TGT__</div>
  </div>
  <div class="gate __DUR_CLASS__">
    <div class="g-name">Durability</div>
    <div class="g-val">__DUR_VAL__</div>
    <div class="g-tgt">__DUR_TGT__</div>
  </div>
  <div class="gate __RECALL_CLASS__">
    <div class="g-name">Recall</div>
    <div class="g-val">__RECALL_VAL__</div>
    <div class="g-tgt">__RECALL_TGT__</div>
  </div>
</div>

<div class="callout barline">
  <p><span class="barnum">$397 / day</span> &mdash; Austin&rsquo;s money bar, ratified 2026-08-30 (six figures a year; 1R = $1,000). <b>Every dollar figure on this page is measured against this line.</b></p>
  <p>Any figure marked __NOT_OBTAINABLE__ comes from the old published-fill book: the price existed only after the candle that produced the signal had already closed, so no resting order could have been filled there. It is preserved byte-identical for reproducibility, not because it was ever tradeable.</p>
</div>

<section>
  <h2>What moved</h2>
  <p class="sub">The published fill priced every earlier version of this page and every earlier version of the book. It could never be paid. The <span class="mono">honest</span> column is the fill shipped 2026-08-30 and is what this page is now generated from &mdash; see the provenance line above.</p>
  <div class="scroll">
  <table>
    <thead><tr><th>Figure</th><th class="n">Published fill (NOT OBTAINABLE)</th><th class="n">Honest fill (now)</th><th class="n">Move</th></tr></thead>
    <tbody>
__MOVED_ROWS__
    </tbody>
  </table>
  </div>
  <div class="callout">
    <p><b>It is the price paid to get in, not the selection.</b> Fixing only the price and holding everything else fixed, trade count barely moved. The per-trade result went <b>+$584 &rarr; &minus;$33</b> across the whole book. 53.8% of the old book's fills sat at the bar's own extreme with the level outside the bar &mdash; a resting order there fills nothing at all (<span class="mono">research/g80_lookahead_refute.md</span>).</p>
    <p><b>The gate this page used to call MET, no longer is.</b> Durability was 25 of 25 green months on a fill nobody could send; on the fill he can actually pay it is 11 of 25 one trade a day, 8 of 25 taking every signal. Sizing cannot rescue it &mdash; multiplying a red month by a positive number leaves it red (<span class="mono">research/g83_sizing.md</span>). The three fills he can actually get &mdash; close, next open, chase once &mdash; are a statistical tie against each other; do not read $28 vs $86 a day as a real difference (<span class="mono">research/g85_honest_book.md</span>).</p>
  </div>
</section>

<section>
  <h2>What is still blocking</h2>
  <p class="sub">Three things. Item 1 is corrected below from what this page said last night.</p>
  <ul class="notes">
    <li><b>The recall router bug is fixed (G72, 2026-08-29), and recall is real now.</b> On the honest fill it is <b>74.3%</b> of his S days, up 15.2 points from the old fill's 59.1%. But false fires rose <b>16.9 points</b> in lockstep, so the gap between his days and his refusals moved <b>&minus;1.8 points</b> [&minus;7.5, +4.0] &mdash; the honest fill trades more days, it does not sort them better (<span class="mono">research/g85_recall_honest.md</span>).</li>
    <li><b>96.4% of what the recall lever promotes dies on one guard.</b> <span class="mono">_min_viable_stop</span> kills 10 of 13 graded vetoes &mdash; not the X grade. The lever operates on 3.6% of the population it was built for. (Measured on the pre-rebuild book; not yet re-verified against the honest fill.)</li>
    <li><b>Mean 2.0R is a selection problem and exits are closed.</b> 47 exit arms ran; zero beat the shipped exit outside its bar, and 29 cleared their bar moving <em>down</em>. A perfect non-causal selector on this exit reaches 2.0R on only <b>51.6%</b> of the book &mdash; so the gate cannot be reached without discarding at least half of it. No further exit work should be funded. (Measured on the pre-rebuild book; not yet re-verified against the honest fill.)</li>
  </ul>
</section>

<section>
  <h2>What you can do</h2>
  <p class="sub">Eleven actions, ranked by what each unlocks. Every one is a thing to do, not a question to answer. The first four are the whole morning if you only have one. <b>These were written against the published fill, now labeled NOT OBTAINABLE, and have not been re-verified against the honest book &mdash; treat the specific R-multiples and dollar figures below as dated even where the underlying question still stands.</b></p>

  <ol class="acts">
    <li class="top">
      <div class="act-h">Settle where the stop goes</div>
      <p class="act-b">Two charts &mdash; <span class="mono">MARA 2026-03-10 09:49</span> and <span class="mono">PLTR 2026-05-27 10:03</span>. You graded both <b>S</b>; on both the engine&rsquo;s stop is the <em>same price</em> as the entry, so it refuses the trade. Three sentences: (a) does the level stop sit at the retested level, or one tolerance unit beyond it; (b) does &ldquo;no minimum stop, size to the stop&rdquo; extend past the one-candle rule to break-and-retest and the 84% re-entry; (c) is a stop narrower than one typical 1-minute candle ever a real order, or is that day a skip. <b>Your R4 and R15 collide on a four-cent stop.</b></p>
      <div class="meta"><span class="tag time">~10 min</span><span class="tag">unlocks 4 tracks</span><span class="tag">highest value</span></div>
    </li>

    <li class="top">
      <div class="act-h">Pick the disaster stop: &minus;1R or &minus;1.25R</div>
      <p class="act-b">At <b>&minus;1R</b> the resting order sits at the level stop&rsquo;s own price, so a wick takes you out and the close-only rule you have settled five times becomes unreachable &mdash; 1,462 of 1,468 losses exit exactly at the stop. At <b>&minus;1.25R</b> the close rule survives, the recoverable-trade kill halves (54 trades / 242R a year against 125 / 497R) and win rate goes 42.8% &rarr; 46.0%, but you lose one green month. Both numbers are yours; neither arm clears its error bar, so <b>no measurement can settle this.</b> Note: the code has never actually run the close-only version of this rule &mdash; the disaster stop is tested on a touch, first, at the same price as the level stop (<span class="mono">research/g82_stop_ab.md</span>).</p>
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
      <p class="act-b">Your &ldquo;pick a level first, 2R only if none&rdquo; fires on <b>0.00%</b> of the published-fill book &mdash; because the engine finds <b>9.43 levels</b> where you draw five or six. &ldquo;Level first&rdquo; currently means &ldquo;nearest of nine&rdquo;, and it measures as the worst exit arm tested. We list every level the engine can see on a handful of your graded cards; you circle the real ones.</p>
      <div class="meta"><span class="tag time">~10 min</span><span class="tag">fixes R9</span></div>
    </li>

    <li>
      <div class="act-h">Reply &ldquo;ship&rdquo; or &ldquo;don&rsquo;t&rdquo; on the arrival-order promote</div>
      <p class="act-b">Over two years <b>289</b> setups your own eight variables score as <b>S</b> were alerted and never traded, for one reason: they were not the first with-trend signal of the day. Your sentence was <em>&ldquo;don&rsquo;t let it cap you of S opportunities&rdquo;</em>, and arrival order is capping 289 of them. Measurably it changes nothing &mdash; mean R +0.0075 inside a &plusmn;0.0870 bar, months green either way.</p>
      <div class="meta"><span class="tag time">one word</span><span class="tag">289 S setups</span></div>
    </li>

    <li>
      <div class="act-h">Resolve the loss halt against &ldquo;trade every day&rdquo;</div>
      <p class="act-b">The two-consecutive-loss halt fires on roughly half of trading days and blocks a meaningful slice of the book&rsquo;s return, to buy a mean-R gain inside its own error bar. R31 says put it in both paths; R20 says you want to trade every day. Both are yours. Say whether halving your trading days is what you meant, or name a different trigger &mdash; three losses, an R drawdown, a time of day.</p>
      <div class="meta"><span class="tag time">~3 min</span><span class="tag">~19% of return</span></div>
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
      <p class="act-b">Confirm a single live option quote returns through <span class="mono">broker/tastytrade.py</span>. Every options number in this project is Black-Scholes on prior-session sigma, never a real bid/ask &mdash; Polygon&rsquo;s options snapshot 403s and the adapter has never completed a live round trip. One session turns &ldquo;modelled&rdquo; into &ldquo;quoted&rdquo;. Must be run from the Mac; the Windows box cannot reach the host.</p>
      <div class="meta"><span class="tag time">~5 min</span><span class="tag">Mac only</span></div>
    </li>
  </ol>
</section>

<section>
  <h2>What did not run</h2>
  <p class="sub">Stated so nothing here reads as more finished than it is.</p>
  <ul class="notes">
    <li><b>The action list above was written against the published fill</b>, now labeled __NOT_OBTAINABLE__ throughout this page, and has not been re-run against the honest close-fill book rebuilt 2026-08-30. Its R-multiples and dollar figures are dated; the underlying questions may still stand, the numbers attached to them may not.</li>
    <li><b>No options, contracts, spreads or futures in any number on this page.</b> Every R here is the underlying. The options and futures skins were both priced on the published fill and have not been re-run on the honest book (<span class="mono">research/g85_honest_book.md</span>, &sect;What is NOT done).</li>
    <li><b>The 84% rule&rsquo;s &ldquo;same stop unless a new stop makes more sense&rdquo; was never measured alone.</b> It has its own switch and ships <b>OFF</b> &mdash; shipping an unmeasured default is the failure this repo keeps repeating.</li>
    <li><b>FVG and flag were not deleted.</b> The adjudicator recommended it; Austin's own answer says <em>keep the code</em>, and a ratified answer outranks an adjudication.</li>
    <li><b>The exit, strike, break-even and faster-cut families were not re-measured on the honest book.</b> Their nulls were computed on the published-fill selection, so they are refutations of their families rather than numbers that automatically survive the fill change.</li>
    <li><b>The live path was wired but never executed.</b> The halt is account-wide in the scanner and asserted by a test, but no live session has run it &mdash; and live routing on his S grade is still unexercised end to end.</li>
  </ul>
</section>

<footer>
  __FOOTER__
</footer>

</div>

'''


if __name__ == "__main__":
    main()
