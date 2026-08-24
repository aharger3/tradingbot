"""build_master_homework.py -- OMEN 6: the one-hour merged homework page.

    python research/build_master_homework.py
    -> research/probes/omen-master-homework.html

Four decks became one page because Austin sits down once. In order:

  1. GRADER CALIBRATION   the 12 disagreement cards from build_calibration.py,
                          unchanged in substance -- that module's select() and
                          card() are imported, not copied.
  2. AUTOPSY RESCUE       the five silent-day cards that came back flagged
                          NO_ANSWER_placeholder_text_only in
                          marks/probe_autopsy_2026-08-23.jsonl. A placeholder
                          leaked into the answer slot, so nothing he tapped
                          survived. Rebuilt through build_probes.autopsy_card().
  3. HEAD-TO-HEAD, PART 2 the 9 TSLA days in marks/probe_head2head_2026-08-24.jsonl.
                          He answered "no" to all nine and the veto question was
                          never asked. This asks the one missing question: which
                          single thing killed each. build_probes.VETO_OPTS verbatim.
  4. S-RECALL, FRESH      25 symbol-days he has never been judged on, drawn
                          behind build_deck.marked_card_ids() -- the no-repeat
                          guard that reads EVERY mark corpus, not just
                          research/marks/. One question: is there an S here.
                          The S denominator is 28 and the OMEN 6 gate is measured
                          on it; 28 is too few to gate on.

ANSWER SURVIVAL is the whole point of this build. Three previous artifacts lost
his answers. This page therefore:
  * carries probe_page.py's own localStorage save (per card, on every tap),
    restore-on-load, visible saved indicator and editable export textarea;
  * does NOT use the claude.ai `artifact` capability for persistence -- that is
    exactly what silently dropped everything before;
  * asserts at build time that no two cards share a data-cid, because a
    duplicate cid means two cards writing the same localStorage slot and one of
    them losing.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_calibration as cal
import build_deck as deck
import build_probes as probes
import probe_chart
import probe_page
from research.t60_baseline import load_day_cards
from v52_scaleout_run import corpus_b_trades

OUT_DIR = os.path.join(HERE, "probes")
MARKS = os.path.join(HERE, "marks")
AUTOPSY_MARKS = os.path.join(MARKS, "probe_autopsy_2026-08-23.jsonl")
H2H_MARKS = os.path.join(MARKS, "probe_head2head_2026-08-24.jsonl")
SILENT = os.path.join(HERE, "t60_silent_days.jsonl")

DECK_ID = "omen-master-homework"
OUT_NAME = "omen-master-homework.html"

# Section 4 draw. TSLA and QQQ only: they are the two symbols in his live corpus
# that the engine is allowed to trade (SPY is configured off), so a yes/no S call
# on them lands in the same denominator the gate is measured on. 2026 only, to
# keep the regime next to the corpus he already graded.
SREC_SYMBOLS = ("TSLA", "QQQ")
SREC_FROM = "2026-01-01"
SREC_N = 25
SREC_SEED = 24

NO_ANSWER_FLAG = "NO_ANSWER_placeholder_text_only"


# ---------------------------------------------------------------------------
# section chrome
# ---------------------------------------------------------------------------

EXTRA_CSS = """
<style>
.sec{display:block}
.sechead{
  margin:30px 0 16px; padding:15px 17px; border-radius:10px;
  background:var(--surface-2); border:1px solid var(--rule-2); scroll-margin-top:64px;
}
.sechead .kicker{
  font-family:"IBM Plex Mono",monospace; font-size:10.5px; font-weight:600;
  letter-spacing:.14em; text-transform:uppercase; color:var(--accent);
  display:block; margin:0 0 5px;
}
.sechead h2{
  font-family:"IBM Plex Serif",Georgia,serif; font-weight:600; font-size:21px;
  line-height:1.2; margin:0 0 6px; color:var(--ink);
}
.sechead p{margin:0; font-size:13.5px; color:var(--ink-2); max-width:66ch}
.sechead p + p{margin-top:6px}
.sechead code{
  font-family:"IBM Plex Mono",monospace; font-size:12.5px;
  background:var(--surface); padding:1px 5px; border-radius:4px;
}
.secprog{display:flex; align-items:center; gap:9px; margin:11px 0 0}
.secprog .seccount{
  font-family:"IBM Plex Mono",monospace; font-size:12px; font-weight:600;
  font-variant-numeric:tabular-nums; color:var(--ink-2); white-space:nowrap;
}
.secprog .sectrack{
  flex:1 1 60px; height:4px; background:var(--rule-2); border-radius:2px; overflow:hidden;
}
.secprog .secfill{height:100%; width:0%; background:var(--accent); transition:width .25s ease}
.sec[data-complete="1"] .sechead{border-color:var(--accent)}
.sec[data-complete="1"] .sechead .kicker::after{content:" — done"; color:var(--accent)}
.endbar{
  display:flex; gap:8px; flex-wrap:wrap; align-items:center;
  margin:18px 0 0; padding-top:14px; border-top:1px solid var(--rule);
}
.q[data-tone="srec"] .chip[aria-pressed="true"]{
  background:var(--up); border-color:var(--up); color:#fff;
}
@media (max-width:520px){.sechead{padding:13px 13px}.sechead h2{font-size:19px}}
</style>
"""

EXTRA_JS = r"""
<script>
/* Section progress + a second Export button at the foot of the page. This runs
   AFTER probe_page's own script (document order), so by the time a click reaches
   here every .card already carries its refreshed data-done. Nothing here touches
   storage -- probe_page.js owns saving, and only one thing should. */
(function(){
  function tally(){
    Array.prototype.forEach.call(document.querySelectorAll('.sec'), function(sec){
      var cs = sec.querySelectorAll('.card'), done = 0;
      Array.prototype.forEach.call(cs, function(c){
        if (c.getAttribute('data-done') === '1') done++;
      });
      var n = cs.length;
      var cnt = sec.querySelector('.seccount');
      if (cnt) cnt.textContent = done + ' / ' + n;
      var fill = sec.querySelector('.secfill');
      if (fill) fill.style.width = (n ? done * 100 / n : 0) + '%';
      sec.setAttribute('data-complete', (n && done === n) ? '1' : '0');
    });
  }
  document.addEventListener('click', function(e){
    if (e.target.closest && e.target.closest('.exportjump')){
      var b = document.getElementById('exportbtn');
      if (b) b.click();
      return;
    }
    tally();
  });
  document.addEventListener('input', tally);
  tally();
})();
</script>
"""


def section(num, kicker, title, paras, cards, minutes):
    """A titled block of cards with its own live progress bar."""
    body = "".join("<p>%s</p>" % p for p in paras)
    return ('<section class="sec" data-complete="0" id="sec%d">'
            '<div class="sechead"><span class="kicker">%s &middot; %d card%s '
            '&middot; ~%d min</span><h2>%s</h2>%s'
            '<div class="secprog"><span class="seccount">0 / %d</span>'
            '<span class="sectrack"><span class="secfill"></span></span></div>'
            '</div>%s</section>'
            % (num, kicker, len(cards), "" if len(cards) == 1 else "s", minutes,
               title, body, len(cards), "".join(cards)))


def jsonl_rows(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


# ---------------------------------------------------------------------------
# 1 -- grader calibration, imported wholesale
# ---------------------------------------------------------------------------

def build_calibration_section():
    picked, harsh, soft = cal.select()
    total = len(picked)
    cards, days = [], []
    for i, (sym, date, sig, klass, g) in enumerate(picked, 1):
        html = cal.card(i, total, sym, date, sig, klass, g, cid_prefix="cal_")
        if html:
            cards.append(html)
            days.append((sym, date))
    return cards, days, len(harsh), len(soft)


# ---------------------------------------------------------------------------
# 2 -- the five autopsy cards whose answers were lost
# ---------------------------------------------------------------------------

def build_autopsy_section():
    """Rebuild exactly the cards flagged NO_ANSWER in the 08-23 export."""
    want = []
    for row in jsonl_rows(AUTOPSY_MARKS):
        if NO_ANSWER_FLAG in (row.get("flags") or []):
            sym, date = row["card_id"].split("_", 1)
            want.append((sym, date, row.get("grade") or "S"))
    expected = {("TSLA", "2026-05-21"), ("QQQ", "2026-07-09"), ("QQQ", "2026-07-20"),
                ("QQQ", "2026-07-24"), ("QQQ", "2026-08-03")}
    got = {(s, d) for s, d, _g in want}
    assert got == expected, "NO_ANSWER set drifted: %s" % sorted(got ^ expected)

    # grade on file comes from the silent-days corpus, same source build_autopsy uses
    silent = {(r["symbol"], r["date"]): r for r in jsonl_rows(SILENT)}
    _days, marks = load_day_cards()
    by_day = defaultdict(list)
    for m in marks:
        by_day[(m["symbol"], m["date"])].append(m)

    want.sort(key=lambda t: (t[1], t[0]))
    total = len(want)
    cards, days = [], []
    for i, (sym, date, grade) in enumerate(want, 1):
        row = silent.get((sym, date))
        grade = (row or {}).get("grade") or grade
        candles = probes.session(sym, date)
        assert len(candles) >= 60, "no session bars for %s %s" % (sym, date)
        cards.append(probes.autopsy_card(i, total, sym, date, grade, candles,
                                         by_day.get((sym, date), []),
                                         cid_prefix="au_"))
        days.append((sym, date))
    return cards, days


# ---------------------------------------------------------------------------
# 3 -- head-to-head follow-up: the question that was never asked
# ---------------------------------------------------------------------------

def build_head2head_section():
    answered = {}
    for row in jsonl_rows(H2H_MARKS):
        sym, date = row["card_id"].split("_", 1)
        answered[(sym, date)] = row

    days_cards, _marks = load_day_cards()
    fired = defaultdict(list)
    for t in corpus_b_trades():
        fired[(t["symbol"], t["date"])].append(t)
    none_days = {k for k, d in days_cards.items()
                 if (d.get("grade") or "").strip() == "none"}
    keys = sorted(k for k in none_days if k in fired)
    assert set(keys) == set(answered), (
        "head-to-head set drifted: %s" % sorted(set(keys) ^ set(answered)))

    total = len(keys)
    cards, days = [], []
    for i, (sym, day) in enumerate(keys, 1):
        candles = probes.session(sym, day)
        if not candles:
            continue
        lv = probes.levels_for(sym, day, candles)
        ts = sorted(fired[(sym, day)], key=lambda t: t["entry_i"])
        marks_svg = [{"i": t["entry_i"], "price": t["entry"], "stop": t["stop"],
                      "side": t.get("side", "L"), "tag": "OMEN"} for t in ts]
        entry_t = ", ".join(t.get("entry_t", "")[:5] for t in ts if t.get("entry_t"))
        reason = (days_cards[(sym, day)].get("reason_none") or "").strip()
        tags = [("you said: no", False),
                ("%d engine fire%s" % (len(ts), "" if len(ts) == 1 else "s"), True)]
        if reason:
            tags.insert(0, ("day card: %s" % reason, False))
        chart = probe_chart.render(candles, lv, marks_svg, "%s %s" % (sym, day))
        body = [
            '<article class="card" data-cid="h2_%s_%s" data-grade="none" data-done="0">'
            % (sym, day),
            probes.header(i, total, sym, day, tags),
            '<div class="chartwrap">%s</div>' % chart, probes.LEGEND,
            probe_page.question(
                "veto", "Which single thing killed it?",
                "OMEN entered at the amber line%s and you already told me you would "
                "not have taken it. One tag only &mdash; your own rule: an X gets one "
                "reason, not a list."
                % (" at %s" % entry_t if entry_t else ""),
                probes.VETO_OPTS, tone="veto",
                note_placeholder="Optional: your reason in your own words"),
            "</article>",
        ]
        cards.append("".join(body))
        days.append((sym, day))
    return cards, days


# ---------------------------------------------------------------------------
# 4 -- fresh S-recall deck
# ---------------------------------------------------------------------------

SREC_OPTS = [
    ("s", "Yes &mdash; there is an S here"),
    ("no", "No S on this chart"),
    ("unsure", "Can&rsquo;t tell from this chart"),
]


def build_srecall_section(exclude):
    """25 symbol-days never judged in ANY mark corpus.

    The guard is build_deck.marked_card_ids() and it is non-negotiable: it reads
    research/marks/*.jsonl plus the legacy corpora outside that directory. A day
    that repeats one he already answered burns the only scarce input in the
    project. ``exclude`` additionally drops anything used earlier on this page.
    """
    seen = deck.marked_card_ids()
    banned = set(seen) | {"%s_%s" % (s, d) for s, d in exclude}
    pool = [(s, d) for s, d in deck.universe()
            if s in SREC_SYMBOLS and d >= SREC_FROM
            and "%s_%s" % (s, d) not in banned]
    pool.sort()
    rng = random.Random(SREC_SEED)
    rng.shuffle(pool)

    chosen, prepared = [], []
    for sym, day in pool:
        if len(chosen) >= SREC_N:
            break
        candles = probes.session(sym, day)
        if len(candles) < 60:
            continue
        chosen.append((sym, day))
        prepared.append((sym, day, candles))
    assert len(chosen) == SREC_N, "only %d fresh days available" % len(chosen)

    # no positional tell by symbol
    rng.shuffle(prepared)
    total = len(prepared)
    cards = []
    for i, (sym, day, candles) in enumerate(prepared, 1):
        lv = probes.levels_for(sym, day, candles)
        chart = probe_chart.render(candles, lv, [], "%s %s" % (sym, day))
        body = [
            '<article class="card" data-cid="sr_%s_%s" data-grade="" data-done="0">'
            % (sym, day),
            probes.header(i, total, sym, day, [("never shown", False)]),
            '<div class="chartwrap">%s</div>' % chart, probes.LEGEND,
            probe_page.question(
                "s_call", "Is there an S trade on this chart?",
                "09:30&ndash;11:00 only, levels drawn. One tap. Nothing else to mark "
                "&mdash; not the entry, not the stop, not the setup.",
                SREC_OPTS, tone="srec",
                note_placeholder="(optional) one line, only if you want to"),
            "</article>",
        ]
        cards.append("".join(body))
    return cards, chosen, len(seen), len(pool)


# ---------------------------------------------------------------------------

def build():
    cal_cards, cal_days, n_harsh, n_soft = build_calibration_section()
    au_cards, au_days = build_autopsy_section()
    h2_cards, h2_days = build_head2head_section()
    used = set(cal_days) | set(au_days) | set(h2_days)
    sr_cards, sr_days, n_seen, n_pool = build_srecall_section(used)

    s1 = section(
        1, "Section 1", "The machine says these are wrong. Are they?",
        ["Twelve charts where the grader and you <b>disagree</b>. The first six are "
         "entries you took that it did not grade S; the last six are days you refused "
         "that it graded S anyway. It shows its reasons &mdash; you say which reasons "
         "are bad.",
         "The thresholds behind those flags are <b>numbers I invented</b>. You gave the "
         "eight variables; nobody set the constants. Every flag you reject is one whose "
         "number is too tight, and that is the entire point of this section."],
        cal_cards, 15)

    s2 = section(
        2, "Section 2", "Five answers that never made it back.",
        ["These five came back from the 08-23 autopsy with <b>nothing in the answer "
         "slot</b> &mdash; a placeholder leaked in where your taps should have been, so "
         "whatever you said on them was lost. Not your fault, and not asking you to "
         "repeat the other ten.",
         "Same questions as before: never <i>where</i> you entered &mdash; your entry is "
         "already the amber line &mdash; only <b>what made it a trade</b>."],
        au_cards, 10)

    s3 = section(
        3, "Section 3", "You said no nine times. Nine times, why?",
        ["Every day OMEN fired on and you graded <code>none</code>. You already "
         "answered the first half &mdash; <b>no</b> on all nine &mdash; but the follow-up "
         "was never asked, so all I have on file is a refusal with no reason.",
         "One tag each. These nine tags become the engine's <b>veto list</b>: the checks "
         "it runs <i>after</i> it finds a setup. Nine days is the entire false-fire set "
         "in the corpus, so each one is worth about eleven percent of that list."],
        h2_cards, 8)

    s4 = section(
        4, "Section 4", "Twenty-five you have never seen.",
        ["The OMEN 6 gate is measured on S-days and you have graded <b>28</b> of them. "
         "Twenty-eight is too few to gate on &mdash; one disagreement moves recall by "
         "three and a half points. This grows the denominator.",
         "Not one of these repeats a day in any mark corpus (%d already-judged "
         "symbol-days excluded, %d fresh days in the pool). No engine marks on the "
         "chart, so there is nothing to agree or disagree with. <b>One tap each</b>: is "
         "there an S on it. Nothing else &mdash; not the entry, not the stop."
         % (n_seen, n_pool)],
        sr_cards, 25)

    foot = ("<h2>Your answers cannot go anywhere</h2>"
            "<p>Every tap writes to this browser the moment you make it. Close the tab, "
            "lose the battery, come back next week &mdash; it is all still here. The "
            "indicator at the top says <code>saved</code> each time it lands, and if "
            "your browser ever refuses to store it, that indicator turns red and says "
            "so. It does not fail quietly.</p>"
            "<p>When you are done &mdash; or partway, it does not matter &mdash; hit "
            "<b>Export</b>, then <b>Copy all</b>, and paste it into the chat. The box is "
            "an ordinary editable text box, so ctrl/cmd+A then ctrl/cmd+C works even "
            "where the button is blocked. <b>Download .jsonl</b> works too where the "
            "browser allows it.</p>"
            "<p>Order does not matter and you do not have to finish. Partial answers are "
            "worth exactly as much per card as complete ones.</p>"
            '<div class="endbar">'
            '<button class="jump exportjump" type="button">Export &amp; copy</button>'
            '<span class="hint">or scroll back up &mdash; the bar follows you</span>'
            "</div>")

    html = probe_page.shell(
        "OMEN Master Homework",
        "OMEN 6 &middot; one sitting",
        "One hour. Four things I cannot get any other way.",
        "Fifty-one charts in four sections: <strong>tune the grader</strong>, "
        "<strong>five answers that got lost</strong>, <strong>nine refusals that need a "
        "reason</strong>, and <strong>twenty-five fresh days</strong> to make the S "
        "denominator big enough to gate on. Every question is a tap. Nothing needs "
        "typing. It saves as you go.",
        EXTRA_CSS + s1 + s2 + s3 + s4, foot, DECK_ID)
    html += EXTRA_JS

    counts = {"1 grader calibration": len(cal_cards),
              "2 autopsy rescue": len(au_cards),
              "3 head-to-head veto": len(h2_cards),
              "4 fresh S-recall": len(sr_cards)}
    return html, counts, {"harsh": n_harsh, "soft": n_soft,
                          "excluded_marked_days": n_seen, "fresh_pool": n_pool}


CID_RE = re.compile(r'<article class="card" data-cid="([^"]+)"')


def verify(html, counts):
    """Fail loudly. Every one of these has actually bitten this project."""
    cids = CID_RE.findall(html)
    dupes = sorted({c for c in cids if cids.count(c) > 1})
    assert not dupes, "duplicate data-cid -- two cards share a save slot: %s" % dupes
    assert len(cids) == sum(counts.values()), (
        "card count mismatch: %d cards in HTML, %d expected"
        % (len(cids), sum(counts.values())))

    export = re.search(r'<textarea id="out"[^>]*>', html)
    assert export, "no export textarea"
    assert "readonly" not in export.group(0), "export box is readonly -- he cannot copy"
    assert "readonly" not in html.lower(), "a readonly attribute leaked into the page"
    assert "localStorage.setItem" in html, "no localStorage save"
    assert 'id="exportbtn"' in html, "no #exportbtn"
    assert 'id="saved"' in html, "no saved indicator"
    assert "window.claude" not in html or "artifact" not in html.split("window.claude")[1][:400], \
        "page leans on the artifact capability for persistence"

    # every card must be countable by the sticky bar: at least one required question
    for block in html.split('<article class="card"')[1:]:
        card = block.split("</article>")[0]
        assert 'data-required="1"' in card, (
            "card with no required question would never count: %s"
            % card[:80])
    return cids


def main():
    html, counts, extra = build()
    cids = verify(html, counts)
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, OUT_NAME)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    print("wrote %s  (%d bytes)" % (path, len(html)))
    for name in sorted(counts):
        print("  %-24s %2d cards" % (name, counts[name]))
    print("  %-24s %2d cards, %d unique data-cid" % ("TOTAL", len(cids), len(set(cids))))
    print("  calibration split: %d harsh / %d soft" % (extra["harsh"], extra["soft"]))
    print("  S-recall guard: %d judged symbol-days excluded, %d fresh days in pool"
          % (extra["excluded_marked_days"], extra["fresh_pool"]))
    print("  checks: no readonly on export, localStorage.setItem present, "
          "#exportbtn present, zero duplicate cids")


if __name__ == "__main__":
    main()
