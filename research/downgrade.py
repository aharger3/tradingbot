"""downgrade.py -- Austin's grade, as arithmetic instead of a candle-pattern verdict.

Settled 2026-08-23:

    S = clean.  A = one variable downgrade.  C = two.

and 2026-08-24:

    with OCR and level confluence, that counts as +1 instead of a downgrade

so the whole grade is:

    tripped = number of downgrade variables that fired
    score   = tripped - (1 if confluence else 0)
    grade   = S if score <= 0, A if score == 1, C if score >= 2      # floors at C

**C is the floor.** Austin, asked directly what happens at three or more: floor at C.
Nothing below it, and nothing is auto-skipped by candle shape ever again -- that was
`TradeGrade.D`, which he asked to be removed entirely (2026-08-24). Its three branches
survive here as REPORTED observations (`observations`), because they are real entry
criteria and worth measuring; they simply no longer hold a veto.

WHY THIS EXISTS
---------------
`research/t62_veto_autopsy.md`: of 144 engine signals that land within +/-3 bars of one
of Austin's 64 marked entries, **134 are graded X and dropped** by
`PriceActionAnalyzer._grade_pa`. Detection reaches 58% of his entries; grading cuts it to
12%. `_grade_pa` asks "is this candle a hammer at a level" -- a question about candle
SHAPE. Austin's eight variables are about STRUCTURE, and not one of them is a candle
pattern. It is not a buggy grader; it answers a different question.

DELIBERATELY NOT WIRED INTO THE ENGINE YET
------------------------------------------
Pure functions over bars, so it can be measured against the 120 graded day-cards before
anything downstream changes. Measure, then wire. The reverse order is how 5.2 published a
scale-out table nobody could reproduce.

THE THRESHOLDS ARE GUESSES AND ARE MARKED AS SUCH
-------------------------------------------------
Austin gave the variables, not the numbers. Every constant below carries a comment saying
so. They are the first thing to tune once the measurement exists, and no result computed
from them should be quoted as though the numbers came from him -- except `STALE_BARS`,
ratified in rule ballot batch 02 (`research/rule_ballot_batch02.jsonl`, 2026-08-27, b11).
That one now carries a citation instead of a guess; the rest are still first guesses.
"""
from __future__ import annotations

# --- thresholds. AUSTIN HAS NOT SET ANY OF THESE. -------------------------
# Each is a starting point chosen to be defensible, not fitted. Tune against the
# 120 graded day-cards; do not present a number computed from these as his rule.
STALE_BARS = 10          # bars between break and retest before the retest is stale.
                         # Ratified: ballot batch 02, b11 ("1m always needs fast
                         # happenstance, if you want a number ill say 10 right now").
CHOP_TOUCHES = 2         # closes sitting ON the level before it counts as disrespected
EXHAUSTED_ATR = 10.0     # move from the session open, in ATR, that counts as spent.
                         # 3.0 was the first guess and the selftest killed it: on
                         # 1-minute bars an ordinary trend day is 4-6 ATR off the
                         # open, so 3.0 flagged every clean setup as exhausted.
DISP_BODY_MULT = 1.5     # break candle body vs the average body before it
REJECT_BARS = 2          # bars after a break within which a close back through = rejection
UNRESPECTED_COUNTER = 2  # counter-trend candles left un-bought-back before it trips
ATR_WINDOW = 14

VARIABLES = (
    "no_displacement",
    "stale_retest",
    "level_not_respected",
    "exhausted",
    "counter_trend_not_respected",
    "break_then_rejection",
    "no_retest",
    "ocr_not_respected",
)

# --- P18/W4: a ninth downgrade variable, OFF by default --------------------
# Ballot batch 02, b6: "large 75 percent red body candles, espcially ones
# within range of other candles are less atractive trades." Measured in
# research/p18_p19_new_variables.md; not ratified, not wired into `score()`
# unless ENABLE_LARGE_COUNTER_BODY (or the equivalent `score()` kwarg) is set.
LARGE_BODY_FRAC = 0.75     # Austin's own number (ballot b6: "75 percent")
LARGE_BODY_WINDOW = 12     # guess: how far back to look; mirrors CHOP_WINDOW
LARGE_BODY_CONTAIN = 3     # guess: bars each side that make up "the bars around it"
ENABLE_LARGE_COUNTER_BODY = False

# --- P19/W5: a second, independent +1, OFF by default -----------------------
# Ballot batch 02, b5: "lets count bull/bear PA and below/above at least 5/6
# levels i watch a +1." The six levels and why those six (not HOD/LOD/T10
# pivots) are named in research/p18_p19_new_variables.md.
CONFLUENCE_LEVELS = ("PDH", "PDL", "PMH", "PML", "ORH", "ORL")
CONFLUENCE_MIN_LEVELS = 5   # Austin's own number (ballot b5: "at least 5/6")
ENABLE_MULTI_LEVEL_CONFLUENCE = False

# --- P20/W6: the sequence gate, OFF by default ------------------------------
# Ballot batch 02, b2: "doesent impact other symbols, but yes anytime there
# was an s a or c entry, a subsequent entry thats not 84 percent rule cannot
# be ranked the same quality." The 2nd+ graded entry on a SYMBOL on a DAY
# takes this downgrade; the 84%-rule re-entry is exempt -- it IS the
# sanctioned second bite at the same idea. No cross-symbol effect, per
# Austin's own words.
#
# This needs state none of the other nine variables need: how many entries on
# THIS symbol, THIS day, were already graded before this one. `score()` only
# ever sees one signal's own bars, so it cannot compute that itself -- the
# caller supplies `entry_seq` (1-based ordinal of this entry among every
# entry downgrade.score() has graded on the same symbol-day, as of this bar)
# and `is_84_reentry`. Both default to "unknown", and unknown means "do not
# judge" -- the same convention `ocr_not_respected` / `multi_level_confluence`
# use when they lack the input to decide, never guessed. Still causal:
# `entry_seq` only ever counts entries with an EARLIER bar index on the same
# symbol-day, which the caller already knows without reading past bar `i` of
# the entry being graded.
ENABLE_SEQUENCE_GATE = False


# ---------------------------------------------------------------------------
# small bar helpers -- every one is causal: nothing reads past `i`
# ---------------------------------------------------------------------------

def _body(b):
    return abs(b["c"] - b["o"])


def _rng(b):
    return b["h"] - b["l"]


def _atr(bars, i, n=ATR_WINDOW):
    lo = max(1, i - n + 1)
    rows = bars[lo:i + 1]
    return (sum(_rng(b) for b in rows) / len(rows)) if rows else 0.0


def _eps(bars, i):
    """How close to a level counts as 'at' it. A quarter of the average range --
    BAR_EXTREME_FRAC, the one tolerance unit Austin settled on 2026-08-23."""
    return 0.25 * (_atr(bars, i) or 0.0)


def _is_up(b):
    return b["c"] >= b["o"]


# ---------------------------------------------------------------------------
# the eight variables
# ---------------------------------------------------------------------------

def no_displacement(bars, i, level, is_long):
    """Ballot q18. The break has no force behind it.

    Measured on the candle that actually crossed the level, not on the entry bar --
    a retest entry is usually small by nature and judging IT for displacement would
    fail almost every clean setup.
    """
    br = _break_bar(bars, i, level, is_long)
    if br is None:
        return True                      # never broke with conviction -> no displacement
    prior = bars[max(0, br - 10):br]
    avg = (sum(_body(b) for b in prior) / len(prior)) if prior else 0.0
    if avg <= 0:
        return False                     # cannot judge; do not invent a downgrade
    return _body(bars[br]) < DISP_BODY_MULT * avg


def _break_bar(bars, i, level, is_long):
    """Index of the most recent bar that CLOSED through the level, else None."""
    for j in range(i, max(0, i - 30) - 1, -1):
        if j == 0:
            break
        prev, cur = bars[j - 1], bars[j]
        crossed = ((prev["c"] <= level < cur["c"]) if is_long
                   else (prev["c"] >= level > cur["c"]))
        if crossed:
            return j
    return None


def _retest_bar(bars, i, level, is_long, after):
    """First bar at/after `after` that comes back and TOUCHES the level."""
    e = _eps(bars, i)
    for j in range(after + 1, i + 1):
        back = (bars[j]["l"] <= level + e) if is_long else (bars[j]["h"] >= level - e)
        if back:
            return j
    return None


def stale_retest(bars, i, level, is_long):
    """Ballot q19, defined 2026-08-23: too many bars after the break.

    Price broke, ran, and only came back much later -- the break has stopped being
    news, so the reaction off it no longer means anything.
    """
    br = _break_bar(bars, i, level, is_long)
    if br is None:
        return False
    rt = _retest_bar(bars, i, level, is_long, br)
    if rt is None:
        return False                     # that is `no_retest`, not staleness
    return (rt - br) > STALE_BARS


def level_not_respected(bars, i, level, is_long):
    """Austin's own words: candles CLOSING AT the level, or chopping on it,
    instead of reacting off it."""
    e = _eps(bars, i)
    window = bars[max(0, i - 12):i + 1]
    return sum(1 for b in window if abs(b["c"] - level) <= e) >= CHOP_TOUCHES


def exhausted(bars, i, level, is_long):
    """Austin's reading of what I had called 'gap left untested': the stock has
    already made a large move, so the setup is real but the move is spent."""
    if not bars:
        return False
    a = _atr(bars, i)
    if a <= 0:
        return False
    return abs(bars[i]["c"] - bars[0]["o"]) >= EXHAUSTED_ATR * a


def counter_trend_not_respected(bars, i, level, is_long):
    """Austin, unprompted: red candles inside an uptrend that don't get bought back.

    "Bought back" = a later bar within two closes above that candle's high (mirrored
    for shorts). Structure quietly failing while the trend line still looks intact.
    """
    window = range(max(1, i - 12), i)
    bad = 0
    for j in window:
        b = bars[j]
        counter = (not _is_up(b)) if is_long else _is_up(b)
        if not counter:
            continue
        recovered = any(
            (bars[k]["c"] > b["h"]) if is_long else (bars[k]["c"] < b["l"])
            for k in range(j + 1, min(j + 3, i + 1))
        )
        if not recovered:
            bad += 1
    return bad >= UNRESPECTED_COUNTER


def break_then_rejection(bars, i, level, is_long):
    """Austin, unprompted: it broke, then immediately gave it back."""
    br = _break_bar(bars, i, level, is_long)
    if br is None:
        return False
    for j in range(br + 1, min(br + 1 + REJECT_BARS, i + 1)):
        back = (bars[j]["c"] < level) if is_long else (bars[j]["c"] > level)
        if back:
            return True
    return False


def no_retest(bars, i, level, is_long):
    """Austin, unprompted, and confirmed in the wild on TSLA 2026-06-10:
    "breaks and doesn't retest the level, instead goes to an OCR farther away"."""
    br = _break_bar(bars, i, level, is_long)
    if br is None:
        return False
    return _retest_bar(bars, i, level, is_long, br) is None


def find_ocr(bars, i, is_long, lookback=20):
    """The One Candle Rule candle, per Austin 2026-08-23 and `omen_bot.py:10`:

        one candle that's the opposite colour of the way it's trending

    In an uptrend that is the down-close candle (it should hold as support); in a
    downtrend the up-close candle (resistance). Returns the bar index of the most
    recent one, or None.

    He also said the OCR may sit far from the entry -- one of his cards has it NINE
    candles back -- so the lookback is generous on purpose.
    """
    for j in range(i - 1, max(1, i - lookback) - 1, -1):
        if j + 1 > i:
            continue
        b = bars[j]
        counter = (not _is_up(b)) if is_long else _is_up(b)
        if not counter:
            continue
        # ISOLATED. It is called the ONE candle rule -- the neighbours have to be
        # trend-coloured or it is a cluster, not a single candle. Austin only
        # marks an OCR when it is "isolated, hard to dispute, and can clearly be
        # used to mark a stop", and he called a two-candle version an A, not an S.
        #
        # Without this, T66 found confluence firing on 84% of all signals: a
        # 20-bar lookback almost always contains SOME counter-coloured candle, so
        # every setup got a free +1 and the grade distribution went to mush.
        left_ok = (_is_up(bars[j - 1])) if is_long else (not _is_up(bars[j - 1]))
        right_ok = (_is_up(bars[j + 1])) if is_long else (not _is_up(bars[j + 1]))
        if left_ok and right_ok:
            return j
    return None


def ocr_not_respected(bars, i, level, is_long):
    """The second half of the rule, the half that was never in the code:

        we want price to respect it and break and retest it

    So the OCR candle manufactures a level. Not respected = a later bar CLOSED
    through the wrong side of it. No OCR in range is not a downgrade -- absence of
    the setup is not a failure of it.
    """
    j = find_ocr(bars, i, is_long)
    if j is None:
        return False
    edge = bars[j]["l"] if is_long else bars[j]["h"]
    for k in range(j + 1, i + 1):
        through = (bars[k]["c"] < edge) if is_long else (bars[k]["c"] > edge)
        if through:
            return True
    return False


def large_counter_body(bars, i, level, is_long):
    """Ballot b6: 'large 75 percent red body candles, especially ones within
    range of other candles are less attractive trades.'

    Two conditions, both required. A counter-coloured candle with a big body
    is common on any real reversal attempt; Austin's second clause ('within
    range of other candles') is what tells a big candle sitting in chop apart
    from one that just made a new extreme (a breakout candle almost always
    pokes outside the recent range). Dropping containment would flag ordinary
    strong counter-moves as a downgrade. P18 in
    research/p18_p19_new_variables.md measures both halves separately.

    OFF by default (`ENABLE_LARGE_COUNTER_BODY`) -- `score()` only calls this
    when asked.
    """
    window = bars[max(0, i - LARGE_BODY_WINDOW):i + 1]
    base = max(0, i - LARGE_BODY_WINDOW)
    for j, b in enumerate(window, start=base):
        rng = _rng(b)
        if rng <= 0:
            continue
        counter = (not _is_up(b)) if is_long else _is_up(b)
        if not counter:
            continue
        if _body(b) / rng < LARGE_BODY_FRAC:
            continue
        lo = max(0, j - LARGE_BODY_CONTAIN)
        hi = min(i, j + LARGE_BODY_CONTAIN)
        neighbours = [bars[k] for k in range(lo, hi + 1) if k != j]
        if not neighbours:
            continue
        nb_hi = max(nb["h"] for nb in neighbours)
        nb_lo = min(nb["l"] for nb in neighbours)
        if b["h"] <= nb_hi and b["l"] >= nb_lo:
            return True
    return False


def multi_level_confluence(bars, i, level, is_long, levels):
    """Ballot b5: 'lets count bull/bear PA and below/above at least 5/6
    levels i watch a +1.'

    `levels` is the six-level roster (`CONFLUENCE_LEVELS`) as of the entry
    bar -- built by `research/p21_target_availability.py::levels_for_entry`,
    the same causal level-assembly code T11(c) and P21 already use, keyed by
    name with missing entries omitted. All six must resolve or this cannot
    judge "5 of 6" and returns False -- absence of data is not evidence of
    the setup, same convention as `ocr_not_respected`.

    `level` (the trade's stop / broken level) is unused; kept in the
    signature to match the other downgrade/confluence functions' shape.

    OFF by default (`ENABLE_MULTI_LEVEL_CONFLUENCE`) -- `score()` only calls
    this when asked, and it is a SEPARATE +1 from `has_confluence` (BR+OCR);
    the two are capped together in `score()`, not combined here.
    """
    if levels is None or not all(levels.get(k) is not None for k in CONFLUENCE_LEVELS):
        return False
    close = bars[i]["c"]
    on_side = sum(1 for k in CONFLUENCE_LEVELS
                  if ((levels[k] <= close) if is_long else (levels[k] >= close)))
    pa_agrees = _is_up(bars[i]) if is_long else (not _is_up(bars[i]))
    return pa_agrees and on_side >= CONFLUENCE_MIN_LEVELS


def sequence_gate(entry_seq, is_84_reentry):
    """Ballot b2: 'anytime there was an s a or c entry, a subsequent entry
    thats not 84 percent rule cannot be ranked the same quality' -- per
    symbol, no cross-symbol effect.

    `entry_seq` is the 1-based ordinal of THIS entry among every entry
    graded on the SAME symbol, SAME day, so far (the caller's job to track --
    see the module comment above `ENABLE_SEQUENCE_GATE`). None or 1 means
    this is the first entry (or the caller has no ordering information,
    which is not evidence of a repeat either way) -- does not trip.
    `is_84_reentry` exempts the one sanctioned second bite at the idea.
    """
    if not entry_seq or entry_seq <= 1:
        return False
    return not is_84_reentry


CHECKS = {
    "no_displacement": no_displacement,
    "stale_retest": stale_retest,
    "level_not_respected": level_not_respected,
    "exhausted": exhausted,
    "counter_trend_not_respected": counter_trend_not_respected,
    "break_then_rejection": break_then_rejection,
    "no_retest": no_retest,
    "ocr_not_respected": ocr_not_respected,
}


# ---------------------------------------------------------------------------
# confluence: an UPGRADE, not a neutral
# ---------------------------------------------------------------------------

def has_confluence(bars, i, level, is_long):
    """BR + OCR together. Austin, 2026-08-24: "that counts as +1 instead of a
    downgrade", so one downgrade plus clean confluence is still S.

    He counts an OCR only when it is isolated, hard to dispute, and **usable as a
    stop** -- so that is the test here: the OCR's far edge must sit on the correct
    side of the level, where it could actually hold a stop. Card 11 settled the
    borderline case ("count it -- the wick was the stop"), so candle SIZE is not a
    disqualifier; only the geometry is.
    """
    br = _break_bar(bars, i, level, is_long)
    if br is None:
        return False
    j = find_ocr(bars, i, is_long)
    if j is None:
        return False
    edge = bars[j]["l"] if is_long else bars[j]["h"]
    usable = (edge <= bars[i]["c"]) if is_long else (edge >= bars[i]["c"])
    return usable and not ocr_not_respected(bars, i, level, is_long)


# ---------------------------------------------------------------------------
# the grade
# ---------------------------------------------------------------------------

def score(bars, i, level, is_long, htf_bias=None, levels=None,
          enable_large_counter_body=None, enable_multi_level_confluence=None,
          enable_sequence_gate=None, entry_seq=None, is_84_reentry=False):
    """Return the full grading record for the signal on bar ``i``.

    ``observations`` carries what the removed TradeGrade.D used to veto on. Austin
    never listed any of the three as downgrades, so they do not count -- but they
    are real entry criteria and worth measuring, which is why they are reported
    rather than deleted.

    P18/P19/P20 additions, all OFF by default and all opt-in per call (the
    `enable_*` kwargs override the module flags so a caller can measure
    without mutating global state):

    ``levels`` -- the six-level roster (`CONFLUENCE_LEVELS`) for
    `multi_level_confluence`, ignored unless that check is enabled.
    ``enable_large_counter_body`` -- adds the ninth downgrade (ballot b6)
    when True; defaults to `ENABLE_LARGE_COUNTER_BODY` (False).
    ``enable_multi_level_confluence`` -- adds the second +1 (ballot b5) when
    True; defaults to `ENABLE_MULTI_LEVEL_CONFLUENCE` (False). It is a
    SEPARATE upgrade from `has_confluence` (BR+OCR) -- either or both firing
    still costs only one point off `net`, since Austin has not been asked
    whether two independent +1s should stack.
    ``enable_sequence_gate`` -- adds the tenth downgrade (ballot b2) when
    True; defaults to `ENABLE_SEQUENCE_GATE` (False). ``entry_seq`` and
    ``is_84_reentry`` are its inputs -- see `sequence_gate` and the module
    comment above `ENABLE_SEQUENCE_GATE` for what they mean and why `score()`
    cannot compute them itself.
    """
    if not bars or i >= len(bars) or level is None:
        return None
    lcb_on = ENABLE_LARGE_COUNTER_BODY if enable_large_counter_body is None else enable_large_counter_body
    mlc_on = (ENABLE_MULTI_LEVEL_CONFLUENCE if enable_multi_level_confluence is None
              else enable_multi_level_confluence)
    seq_on = ENABLE_SEQUENCE_GATE if enable_sequence_gate is None else enable_sequence_gate

    tripped = [name for name, fn in CHECKS.items() if fn(bars, i, level, is_long)]
    if lcb_on and large_counter_body(bars, i, level, is_long):
        tripped.append("large_counter_body")
    if seq_on and sequence_gate(entry_seq, is_84_reentry):
        tripped.append("sequence_gate")

    confl_br_ocr = has_confluence(bars, i, level, is_long)
    confl_ml = mlc_on and multi_level_confluence(bars, i, level, is_long, levels)
    confl = confl_br_ocr or confl_ml           # capped at one point -- see docstring
    net = len(tripped) - (1 if confl else 0)
    grade = "S" if net <= 0 else ("A" if net == 1 else "C")

    b = bars[i]
    e = _eps(bars, i)
    observations = {
        # the three branches of the old _grade_pa, demoted from veto to evidence
        "entry_bar_off_level": (b["l"] > level + e) if is_long else (b["h"] < level - e),
        "entry_bar_counter_coloured": (not _is_up(b)) if is_long else _is_up(b),
        "htf_opposed": (htf_bias in ("bullish", "bearish")
                        and (htf_bias == "bullish") != is_long),
    }
    return {"grade": grade, "tripped": tripped, "n_tripped": len(tripped),
            "confluence": confl, "confluence_br_ocr": confl_br_ocr,
            "confluence_multi_level": bool(confl_ml),
            "net": net, "observations": observations}
