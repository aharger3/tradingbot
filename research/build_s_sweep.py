"""build_s_sweep.py -- T22: the 250-card S sweep, Austin's wave-1 priority.

    python research/build_s_sweep.py                     # 250-card sweep, default seed
    python research/build_s_sweep.py --n 250 --seed 22
    python research/build_s_sweep.py --selfcheck          # zero-repeat + pool-shrinkage report

Austin, 2026-08-28: "im concerned about getting me homework to help S accuracy because
my eye is still better, the quicker you have a large sample size the better." And:
"you cant refute my s marks they are important and hard work and stats have been
backing them up." research/x11_homework_roi.md found the outstanding 60 cards (the
h2-3lane deck's lanes 2/3) worth nothing -- zero new held-out S days. This is the
replacement: a wide, fast, ONE-TAP draw across the archive, never repeating a
symbol-day he has already judged.

Design, and why it looks nothing like the 60-card deck standard:

  * ONE required tap. The card asks the single question the recall gate needs --
    S / A / C / none, his own ladder (never the engine's legacy A+/A/B/C/X). No
    entry, no stop, no setup type -- those are a different instrument's job
    (`build_omen_test1.py`) and asking for them here would trade card count for
    card cost, which is exactly the trade this track exists to avoid.
  * ONE optional tap ("why not S"), the eight `omen-rulebook.md` downgrade
    variables as a multi-select. Never required, never pre-pressed -- see
    research/t22_s_sweep.md for why that matters (the entry_p trap).
  * A per-card millisecond stamp, captured on the FIRST grade tap of each card and
    persisted across a reload, so a future version can measure real per-card cost
    instead of guessing it. See EXTRA_JS below for exactly what it can and cannot
    record.
  * probe_page.py / probe_chart.py are imported, not copied. No CSS class in this
    file exists outside the ones probe_page.CSS already defines.
  * No positional tell, no fire/silent mixing -- unlike build_deck.py's 60-card
    standard, this instrument is not testing detection, only building graded
    sample size, so the draw is a uniform random sample of the whole archive.

Output: research/probes/omen-s-sweep.html
        research/probes/omen-s-sweep-manifest.jsonl   (answer key -- OUTSIDE the html)
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import probe_chart
import probe_page
from research.build_deck import (candle_dict, marked_card_ids, mark_sources,
                                 session_candles, universe)
from research.t4_engine_recall import premarket_extremes, prior_day_levels

OUT_DIR = os.path.join(HERE, "probes")
DECK_ID = "s-sweep"
N_CARDS = 250
SEED = 22
MIN_BARS = 60
MAX_PROBE_DEFAULT = 4000

# Austin's ladder, CLAUDE.md / omen-rulebook.md -- never the engine's legacy
# A+/A/B/C/X. "none" is a judgement (an explicit refusal), not a blank.
GRADE_OPTS = [
    ("S", "S — clean, nothing tripped"),
    ("A", "A — one downgrade"),
    ("C", "C — two (the floor)"),
    ("none", "none — would not trade this"),
]

# The eight countable downgrade variables, omen-rulebook.md "settled 2026-08-23".
# Tap 2. Optional refinement only -- never required, never pre-pressed. A blank
# answer here is not a blank judgement; the grade above is the whole judgement.
DOWNGRADE_OPTS = [
    ("no_displacement", "No displacement candle"),
    ("stale_retest", "Stale retest (too many bars after the break)"),
    ("level_not_respected", "Level not respected (closing/chopping on it)"),
    ("exhausted", "Stock already exhausted"),
    ("counter_trend", "Counter-trend candles not respected"),
    ("break_then_reject", "Broke, then immediately rejected"),
    ("no_retest", "No retest — ran without coming back"),
    ("ocr_not_honoured", "One-candle rule not honoured"),
]

LEGEND = ('<div class="legend">'
          '<span><b style="color:var(--lvl-pd)">- - PDH/PDL</b> prior day</span>'
          '<span><b style="color:var(--lvl-pm)">- - PMH/PML</b> premarket 04:00-09:29</span>'
          '<span><b style="color:var(--lvl-or)">- - ORH/ORL</b> first 5 RTH bars</span>'
          '</div>')


# ---------------------------------------------------------------------------
# per-card millisecond stamp -- see the module docstring for the contract.
# Stamped once, on the FIRST grade tap of each card; persisted in its own
# localStorage key so a reload does not lose stamps already taken. The clock
# itself (`lastAt`) is NOT persisted across a reload -- see t22_s_sweep.md
# "what this instrument cannot record" for why that is a documented limit and
# not the thing being measured.
# ---------------------------------------------------------------------------
EXTRA_JS = r"""
<script>
(function(){
  var bar = document.querySelector('.bar');
  var DECK = (bar && bar.getAttribute('data-deck')) || 'DECK_ID_PLACEHOLDER';
  var MSKEY = 'omen-probe:' + DECK + ':_ms';

  var msMap = {};
  try { msMap = JSON.parse(localStorage.getItem(MSKEY) || '{}'); } catch (e) {}

  var lastAt = Date.now();

  function persist(){
    try { localStorage.setItem(MSKEY, JSON.stringify(msMap)); } catch (e) {}
  }

  document.addEventListener('click', function(e){
    if (!e.target.closest) return;
    var chip = e.target.closest('.q[data-q="grade"] .chip');
    if (!chip) return;
    var card = chip.closest('.card');
    var cid = card && card.getAttribute('data-cid');
    if (!cid || msMap[cid] != null) return;   /* stamp once: first grade tap only */
    var now = Date.now();
    msMap[cid] = now - lastAt;
    lastAt = now;
    persist();
  });

  function pressedVal(card, q){
    var el = card.querySelector('.q[data-q="' + q + '"] .chip[aria-pressed="true"]');
    return el ? el.getAttribute('data-v') : null;
  }
  function pressedVals(card, q){
    var out = [];
    card.querySelectorAll('.q[data-q="' + q + '"] .chip[aria-pressed="true"]')
        .forEach(function(c){ out.push(c.getAttribute('data-v')); });
    return out;
  }

  /* promote taps to top-level fields, same convention as OMEN Test 1's
     window.probeRow, so a row joins back to bars with no `answers` parsing */
  window.probeRow = function(card, row){
    var g = pressedVal(card, 'grade');
    if (g) { row.grade = g; row.grade_std = g; }
    var dg = pressedVals(card, 'downgrades');
    if (dg.length) row.downgrades = dg;
    var cid = card.getAttribute('data-cid');
    if (msMap[cid] != null) row.ms = msMap[cid];
  };
})();
</script>
"""


def header(idx, total, symbol, day):
    return ('<header><span class="idx">%03d/%03d</span>'
            '<span class="tick">%s</span><span class="when">%s</span>'
            '<span class="tags"><span class="done-dot"></span></span></header>'
            % (idx, total, symbol, day))


def s_sweep_card(idx, total, symbol, day, candles, lv):
    chart = probe_chart.render(candles, lv, None, "%s %s" % (symbol, day))
    export = json.dumps({"symbol": symbol, "date": day},
                        separators=(",", ":"), sort_keys=True)
    body = [
        '<article class="card" data-cid="%s_%s" data-grade="" data-done="0" '
        "data-export='%s'>" % (symbol, day, export),
        header(idx, total, symbol, day),
        '<div class="chartwrap">%s</div>' % chart, LEGEND,
        probe_page.question(
            "grade", "Grade this chart.",
            "The single question this page exists to ask. S/A/C/none, your ladder. "
            "One tap and the card is done.",
            GRADE_OPTS),
        probe_page.question(
            "downgrades", "If not S — what tripped it? (optional)",
            "Only if it helps. Tap as many as apply, or skip it entirely.",
            DOWNGRADE_OPTS, multi=True, required=False),
        "</article>",
    ]
    return "".join(body)


def pick(n: int, seed: int, max_probe: int):
    """A uniform random, never-before-judged sample of n symbol-days.

    Unlike build_deck.pick(), this does not stratify on engine fires -- this
    instrument is not testing detection, it is building graded sample size, so
    every archived day is an equally good draw. Returns (cards, probed,
    n_seen, per_source) where cards is a list of
    {symbol, day, candles, pdh, pdl, pmh, pml, orh, orl}.
    """
    per_source: dict[str, int] = {}
    seen = marked_card_ids(per_source)
    full = universe()
    pool = [(s, d) for s, d in full if "%s_%s" % (s, d) not in seen]
    print("no-repeat guard: %d judged symbol-days across %d sources; "
          "pool %d -> %d archived days"
          % (len(seen), len(per_source), len(full), len(pool)))
    for path, cnt in sorted(per_source.items(), key=lambda kv: -kv[1]):
        if cnt:
            print("    %5d  %s" % (cnt, os.path.relpath(path, ROOT)))

    rng = random.Random(seed)
    rng.shuffle(pool)

    cards = []
    probed = 0
    for sym, day in pool:
        if len(cards) >= n or probed >= max_probe:
            break
        candles = session_candles(sym, day)
        probed += 1
        if len(candles) < MIN_BARS:
            continue
        pdh, pdl, _o, _c = prior_day_levels(sym, day)
        pmh, pml = premarket_extremes(sym, day)
        orh = max(c.high for c in candles[:5]) if len(candles) >= 5 else None
        orl = min(c.low for c in candles[:5]) if len(candles) >= 5 else None
        candles = [candle_dict(c) for c in candles]
        cards.append({"symbol": sym, "day": day, "candles": candles,
                     "pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
                     "orh": orh, "orl": orl})
        if probed % 100 == 0:
            print("  probed %d  drawn %d" % (probed, len(cards)))

    return cards, probed, len(seen), per_source


def write_page(cards, name: str) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    total = len(cards)
    card_html = []
    manifest = []
    for i, c in enumerate(cards, 1):
        lv = {"pdh": c["pdh"], "pdl": c["pdl"], "pmh": c["pmh"], "pml": c["pml"],
              "orh": c["orh"], "orl": c["orl"]}
        card_html.append(s_sweep_card(i, total, c["symbol"], c["day"], c["candles"], lv))
        manifest.append({"card_id": "%s_%s" % (c["symbol"], c["day"]),
                         "symbol": c["symbol"], "date": c["day"], "deck": name})

    foot = ("<h2>What happens to these answers</h2>"
            "<p>Every tap saves in this page as you make it -- close the tab, come "
            "back, it is still here. When you are done, or partway through (it does "
            "not matter), hit <b>Export</b> at the top, then <b>Copy all</b> and "
            "paste it into the chat, or <b>Download .jsonl</b> and send the file. "
            "Stop anywhere -- there is no part boundary to finish.</p>"
            "<p>%d cards, drawn at random from the archive, none of them a day you "
            "have graded before in any corpus. One tap each. A rough guide: stop "
            "roughly every 50 and export -- five sittings clears the page.</p>"
            % total)

    html = probe_page.shell(
        "OMEN S Sweep",
        "OMEN 7.0 &middot; T22",
        "Is this an S day?",
        "%d never-before-graded charts. One tap: S / A / C / none. A second, "
        "optional tap if you want to say why it wasn't S. That's the whole card."
        % total,
        "".join(card_html), foot, DECK_ID)
    html += EXTRA_JS.replace("DECK_ID_PLACEHOLDER", DECK_ID)

    path = os.path.join(OUT_DIR, name + ".html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    man = os.path.join(OUT_DIR, name + "-manifest.jsonl")
    with open(man, "w", encoding="utf-8") as f:
        for row in manifest:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    return path


def selfcheck(n: int, seed: int, max_probe: int) -> int:
    cards, probed, nseen, per_source = pick(n, seed, max_probe)
    ids = ["%s_%s" % (c["symbol"], c["day"]) for c in cards]
    fails = []

    def check(name, cond, detail=""):
        print("%-40s %s%s" % (name, "PASS" if cond else "FAIL",
                              ("  " + str(detail)) if detail else ""))
        if not cond:
            fails.append(name)

    check("drew the requested count", len(cards) == n or probed >= max_probe,
          "%d/%d drawn, %d probed" % (len(cards), n, probed))
    check("no duplicate card_id inside the draw", len(set(ids)) == len(ids))
    repeats = set(ids) & marked_card_ids()
    check("zero repeats against marked_card_ids()", not repeats,
          sorted(repeats)[:10])
    check("pool shrinkage reported", nseen > 0, "%d judged symbol-days" % nseen)

    print()
    if fails:
        print("SELFCHECK FAILED: %s" % ", ".join(fails))
        return 1
    print("selfcheck ok: %d cards, %d probed, %d already-judged symbol-days excluded"
          % (len(cards), probed, nseen))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="omen-s-sweep")
    ap.add_argument("--n", type=int, default=N_CARDS)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--max-probe", type=int, default=MAX_PROBE_DEFAULT)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()

    if a.selfcheck:
        sys.exit(selfcheck(a.n, a.seed, a.max_probe))

    cards, probed, nseen, per_source = pick(a.n, a.seed, a.max_probe)
    path = write_page(cards, a.name)

    ids = ["%s_%s" % (c["symbol"], c["day"]) for c in cards]
    assert len(set(ids)) == len(ids), "duplicate card_id inside the draw"
    repeats = set(ids) & marked_card_ids()
    assert not repeats, "sweep repeats already-judged days: %s" % sorted(repeats)

    print("Wrote %s" % path)
    print("  cards=%d  probed=%d  excluded=%d already-judged symbol-days"
          % (len(cards), probed, nseen))


if __name__ == "__main__":
    main()
