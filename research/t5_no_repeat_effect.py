"""omen-3.9 T5: measure the no-repeat idea-key rule WITHOUT arming it.

Replays the 159 v2 marks twice through the engine's REAL _route -- once with
ENFORCE_NO_REPEAT False (today's behaviour) and once with it forced True
in-process -- and reports:

  repeat_entries_suppressed  engine entries (fired, deduped) the rule drops
  baseline_marks_lost        marked trades (any tier) the engine currently
                             fires on that would go silent under the rule

The rule (signal_runner._route): once an idea_key -- (symbol, direction, level
NAME) -- has been accepted this session, a later accepted entry on the same
idea is skipped with [skip: repeat idea], UNLESS it is
SignalType.REENTRY_84_RULE, the armed 84% re-entry, which is the sanctioned
second bite at the same idea by definition. ENFORCE_NO_REPEAT ships False, so
this script is a measurement, not a behaviour change -- the production engine
is byte-identical until Austin arms the flag.

Reuses t4_engine_recall's archive + level reconstruction (rth_candles,
prior_day_levels, premarket_extremes, htf_bias) so the engine sees the same
structure live_scanner would feed it. The fired set produced here with the flag
off matches CaptureRunner in t4 / the regression gate exactly, because the
skip grade serialises as "X" (TradeGrade.D.value == "X") and base _route's
_SKIP_GRADES and CaptureRunner's `!= TradeGrade.D.value` agree on it. The 84%
re-entry is not armed in a detection-only replay, so it never appears as a
fired entry here -- it is named only to document the one exemption.
"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)        # t4_engine_recall, levels
sys.path.insert(0, ROOT)        # signal_runner, omen_bot
import t4_engine_recall as t4
import signal_runner as sr

MARKS = t4.MARKS
DEDUPE_BARS = t4.DEDUPE_BARS
ENTRY_CUTOFF = t4.ENTRY_CUTOFF
TOL = t4.TOL


def _day_setup(marks):
    """Load candles + reconstructed levels once per marked (symbol, day), so
    the two passes (flag off / flag on) share the file reads."""
    setup = {}
    for (sym, day) in sorted({(m["symbol"], m["day"]) for m in marks}):
        candles = t4.rth_candles(sym, day)
        if not candles:
            continue
        pdh, pdl, pdo, pdc = t4.prior_day_levels(sym, day)
        pmh, pml = t4.premarket_extremes(sym, day)
        setup[(sym, day)] = {
            "candles": candles, "pdh": pdh, "pdl": pdl, "pdo": pdo, "pdc": pdc,
            "pmh": pmh, "pml": pml, "htf": t4.htf_bias(sym, day),
        }
    return setup


def _replay(setup, flag):
    """Replay every marked day bar-by-bar through the real _route with
    sr.ENFORCE_NO_REPEAT = flag. Returns (flat_entries, entries_by_pair), where
    each entry is a fired, deduped record carrying its bar."""
    sr.ENFORCE_NO_REPEAT = flag
    entries = []
    by_pair = defaultdict(list)
    for (sym, day), s in setup.items():
        candles = s["candles"]
        runner = sr.SignalRunner(post_to_discord=False, symbol=sym,
                                 log_signals=False)
        runner.pdh, runner.pdl = s["pdh"], s["pdl"]
        runner.pmh, runner.pml = s["pmh"], s["pml"]
        runner.pd_open, runner.pd_close = s["pdo"], s["pdc"]
        runner.htf_bias = s["htf"]
        runner.qqq_breaks = None
        seen = {}  # (signal_type, direction, idea) -> last fired bar (30-bar dedupe)
        for i in range(5, len(candles)):
            c = candles[i]
            if ENTRY_CUTOFF and c.timestamp >= ENTRY_CUTOFF:
                continue
            runner.candles = candles[: i + 1]
            for sig in runner.detect_signals():
                # Same idea key as t4's dedupe: the level NAME for B&R, the
                # rounded stop price otherwise. _fired_ideas inside _route keys
                # on idea_key() (symbol, direction, level NAME) -- the no-repeat
                # skip is already applied there; this is only the production
                # 30-bar dedupe on what survives.
                idea = (sig.get("stop_level_name")
                        if sig["signal_type"].value == "break_and_retest"
                        else round(sig["stop"], 2))
                key = (sig["signal_type"].value, sig["direction"], idea)
                if key in seen and i - seen[key] < DEDUPE_BARS:
                    seen[key] = i
                    continue
                seen[key] = i
                rec = {"symbol": sym, "day": day, "bar": i,
                       "signal_type": sig["signal_type"].value,
                       "direction": sig["direction"], "grade": sig["grade"],
                       "stop_level": sig.get("stop_level_name"),
                       "entry": sig["entry"], "stop": sig["stop"]}
                entries.append(rec)
                by_pair[(sym, day)].append(rec)
    return entries, by_pair


def _entry_id(e):
    return (e["symbol"], e["day"], e["bar"], e["signal_type"],
            e["direction"], e["stop_level"])


def _marks_hit(marks, by_pair):
    """Set of "symbol|day|entry_i" for marks with a fired engine entry within
    TOL bars -- the marks the engine currently takes."""
    hit = set()
    for m in marks:
        bars = [e["bar"] for e in by_pair.get((m["symbol"], m["day"]), [])]
        if any(abs(b - m["entry_i"]) <= TOL for b in bars):
            hit.add(f"{m['symbol']}|{m['day']}|{m['entry_i']}")
    return hit


def main():
    marks = [json.loads(l) for l in open(MARKS) if l.strip()]
    setup = _day_setup(marks)

    base_entries, base_by_pair = _replay(setup, flag=False)
    nr_entries, nr_by_pair = _replay(setup, flag=True)

    base_ids = set(map(_entry_id, base_entries))
    nr_ids = set(map(_entry_id, nr_entries))
    # no-repeat only ever removes; the subset check is a sanity guard.
    assert nr_ids <= base_ids, "no-repeat added entries -- should be impossible"
    suppressed = base_ids - nr_ids

    base_marks = _marks_hit(marks, base_by_pair)
    nr_marks = _marks_hit(marks, nr_by_pair)
    lost = base_marks - nr_marks

    lost_tier = defaultdict(int)
    lost_examples = []
    for m in marks:
        key = f"{m['symbol']}|{m['day']}|{m['entry_i']}"
        if key in lost:
            lost_tier[m["tier"]] += 1
            if len(lost_examples) < 12:
                lost_examples.append(key + f" (tier {m['tier']})")

    repeat_entries_suppressed = len(suppressed)
    baseline_marks_lost = len(lost)

    print(f"days replayed (archive present): {len(setup)}")
    print(f"baseline fired entries:  {len(base_entries)}")
    print(f"no-repeat fired entries: {len(nr_entries)}")
    print(f"repeat_entries_suppressed: {repeat_entries_suppressed}")
    print(f"baseline marks hit (any tier): {len(base_marks)}")
    print(f"no-repeat marks hit (any tier): {len(nr_marks)}")
    print(f"baseline_marks_lost: {baseline_marks_lost}")
    print(f"lost marks by tier: {dict(lost_tier)}")
    if lost_examples:
        print("lost mark examples: " + "; ".join(lost_examples))


if __name__ == "__main__":
    main()
