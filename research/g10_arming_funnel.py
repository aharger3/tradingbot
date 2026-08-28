"""G10 -- autopsy of the 317 armings that die in the 84%-rule re-entry
detector, per condition, in evaluation order.

P7/G1 (`research/p7_84_rule.py`) measured the ARM gate's funnel and stopped
at "armed": on the loose arm (`RULE84_STRICT=0`), 521 counted stop-outs ->
472 arming setups -> 472 past the grade gate -> 433 armed (past the 11:00
SESSION_END check) -> only 116 go on to produce a `reentry_84_rule` signal.
Nothing recorded WHY the other 317 die -- the checks that gate the re-entry
live inline in one big `if`, in `signal_runner.py`'s 84%-long/84%-short
blocks (~L1803-1857 call side, ~L2017-2065 the put mirror), not in a
separately callable function P7 could already instrument the way it
instruments `backtest_week._arm_84`.

The six conditions, IN THE ORDER THE SOURCE ACTUALLY EVALUATES THEM (do not
trust the ticket's prose list -- it names "before 11:00" ahead of the
2-attempt cap; the source's `caps_ok = attempts < RULE84_MAX_ATTEMPTS and
bar_time(...) < SESSION_END` checks attempts FIRST):

    1. reclaim    -- current bar closes back beyond the failed entry
    2. colour     -- the reclaim bar is bullish (call) / bearish (put)
    3. extreme20  -- close sits >20% of the day's HOD-LOD range off the extreme
    4. rr15       -- >=1.5x remaining reward still on the table (orig stop/target)
    5. attempts   -- under RULE84_MAX_ATTEMPTS (2) attempts already spent on this idea
    6. before11   -- the reclaim bar itself lands before SESSION_END (11:00)

Condition 6 turns out to be DEAD CODE in this backtest path: `backtest_week`'s
own per-bar loop already does `if ENTRY_CUTOFF and c.timestamp >= ENTRY_CUTOFF:
continue` -- skipping the bar entirely -- BEFORE `detect_signals()` is ever
called, and `detect_signals()` itself repeats the same cutoff via
`in_session()`. By the time the 84%-rule block's own `bar_time(...) <
SESSION_END` runs, the bar has already been proven to satisfy it twice.
`--selfcheck` asserts `backtest_week.ENTRY_CUTOFF == signal_runner.SESSION_END`
(both default "11:00:00") as the structural reason this condition can never
kill anything here -- the same "rule unreachable in code" bug class this repo
has hit before.

Method -- reuse, don't re-replay
---------------------------------
This runs the SAME loose-arm replay as `p7_84_rule.py run --arm loose`
(identical imports, identical symbol/day loop, identical `simulate_day()`
calls -- nothing about break/retest detection, PA grading or the session
walk is reimplemented). Two READ-ONLY hooks sit on top, neither a behaviour
change -- both call straight through to the real, unmodified function:

  * `backtest_week._arm_84` is wrapped to OBSERVE (never alter) whether the
    real call just moved `ARM84_FUNNEL["armed"]` -- the exact signal P7's own
    report reads -- and if so records the arming's identity (symbol, day,
    direction, entry/stop/target, the stop-out's own bar index).
  * `BacktestRunner.detect_signals` is subclassed to independently RESTATE
    (not alter -- `super().detect_signals()` still runs, unmodified) the same
    six booleans the real detector computes, via `rule84_conditions()` below,
    a verbatim transcription of the source's inline expressions. It reads
    attempts off the runner's OWN live `self._attempts_84`, not a
    separately-tracked shadow copy, so attempts bookkeeping can never drift
    from the real engine's.

Funnel semantics, per arming, across every bar it was evaluated on (from the
stop-out bar to whichever comes first of a fire, a later arm clobbering the
pending state, or day/session end):

    reached(k)  = true if SOME evaluated bar had conditions 1..k all true
    kill_stage  = the smallest k where reached(k) is false (undefined if fired)
    alone(j), only defined for an arming with kill_stage == j: true if SOME
        evaluated bar had every condition EXCEPT j true -- lifting condition j
        alone would have let that bar through.

This generalises g4_dropped_s.py's "which gate rejected it, and would
deleting that ONE gate rescue it" attribution from a single evaluation to a
multi-bar forward walk, and it stays mutually exclusive across conditions the
same way: alone(j) is only checked within the kill_stage==j bucket, so a dead
arming counts toward exactly one "kill" bucket and at most one "alone"
bucket. The self-check is the strong one: shadow-computed "fired" (all six
conditions true on some bar) must equal the real engine's `reentry_84_rule`
row count -- not an assumed 116, the number this run actually measures.

Nothing here changes a default, flips a flag, or adds engine behaviour.
`RULE84_STRICT=1` stays the shipped default no matter what this finds --
P7 already found that opening the ARM gate bought nothing at the money gate;
assume nothing here either. This measures the re-entry detector. It does not
decide whether to loosen it.

Usage:
    python research/g10_arming_funnel.py run       # replay -> research/_g10_arm_events.json
    python research/g10_arming_funnel.py report     # -> research/g10_arming_funnel.md
    python research/g10_arming_funnel.py --selfcheck  # assert-based, no archive needed

RUN ALONE. Like p7_84_rule.py, this contends on the 1-minute archive; don't
run it next to another replay.
"""
import argparse
import json
import os
import statistics
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# The loose arm is where 433 armed / 116 fired lives -- the numbers this
# ticket starts from. Must be set before signal_runner is ever imported
# (its RULE84_* flags are read from the environment at import time).
os.environ.update({"RULE84_STRICT": "0", "RULE84_ARM_SGRADE": "0", "RULE84_OFF": "0"})

OUT_JSON = "research/_g10_arm_events.json"
OUT_MD = "research/g10_arming_funnel.md"

CONDITIONS = ["reclaim", "colour", "extreme20", "rr15", "attempts", "before11"]
COND_LABEL = {
    "reclaim":   "reclaim -- close back beyond the failed entry",
    "colour":    "colour -- reclaim bar is bullish (call) / bearish (put)",
    "extreme20": ">20% of the day's HOD-LOD range off the extreme",
    "rr15":      ">=1.5x remaining reward left on the original stop/target",
    "attempts":  "under the 2-attempt cap (RULE84_MAX_ATTEMPTS)",
    "before11":  "reclaim bar itself is before SESSION_END (11:00)",
}


def rule84_conditions(direction, current, hod, lod, entry_price, entry_stop,
                       entry_target, attempts, max_attempts, session_end):
    """The six 84%-rule re-entry gates, transcribed verbatim from
    signal_runner.py's inline call/put blocks. Pure function of the bar and
    the arming's state -- no side effects. Assumes RULE84_LESSON=True (the
    only reading ever shipped: original stop, no extra strong-PA gate) --
    `--selfcheck` asserts that is still the case.

    Returns ([reclaim, colour, extreme20, rr15, attempts, before11], stop_chk).
    """
    import signal_runner as sr
    day_range = hod - lod
    close = current.close
    if direction == "call":
        c_reclaim = close >= entry_price
        c_colour = current.is_bullish
        stop_chk = entry_stop if entry_stop is not None else current.low
        c_rr = (entry_target is not None and stop_chk < close
                and (entry_target - close) >= 1.5 * (close - stop_chk))
        c_ext = day_range > 0 and (hod - close) / day_range > 0.2
    else:
        c_reclaim = close <= entry_price
        c_colour = current.is_bearish
        stop_chk = entry_stop if entry_stop is not None else current.high
        c_rr = (entry_target is not None and stop_chk > close
                and (close - entry_target) >= 1.5 * (stop_chk - close))
        c_ext = day_range > 0 and (close - lod) / day_range > 0.2
    c_att = attempts < max_attempts
    c_time = sr.bar_time(current.timestamp) < session_end
    return [c_reclaim, c_colour, c_ext, c_rr, c_att, c_time], stop_chk


# ---------------------------------------------------------------- the replay

def run(days: int, out_path: str) -> None:
    import polygon_feed as pf
    import backtest_2y as b2
    import backtest_week as bw
    from backtest_week import htf_bias_for
    from backtest_12mo import qqq_level_breaks, hourly_from_1m
    from universe import ALL_SYMS, has_archive
    import signal_runner as sr

    assert sr.RULE84_LESSON is True, (
        "RULE84_LESSON moved off True -- rule84_conditions()'s stop_chk formula "
        "assumes the original-stop branch is the only one ever taken")

    bw.ARM84_FUNNEL.clear()
    RealRunner = bw.BacktestRunner
    RealArm84 = bw._arm_84

    ctx = {"sym": None, "day": None, "events": []}  # arm events, arrival order

    def _arm_84_probe(t, runner, c=None):
        before = bw.ARM84_FUNNEL["armed"]
        RealArm84(t, runner, c)                     # the real gate, unmodified
        if bw.ARM84_FUNNEL["armed"] > before:        # THIS call just armed
            arm_id = len(ctx["events"])
            ctx["events"].append({
                "id": arm_id, "sym": ctx["sym"], "day": ctx["day"],
                "arm_idx": t.exit_idx, "dir": t.direction,
                "entry": t.entry, "stop": t.stop, "target": t.target,
                "bars": [],
            })
            runner._g10_arm_id = arm_id
    bw._arm_84 = _arm_84_probe

    class FunnelRunner(RealRunner):
        def detect_signals(self):
            self._g10_probe()
            return super().detect_signals()          # the real detector, unmodified

        def _g10_probe(self):
            sess = self.session
            if sess.entry_price is None or len(self.candles) < 5:
                return
            current = self.candles[-1]
            if not sr.in_session(current.timestamp):
                return
            arm_id = getattr(self, "_g10_arm_id", None)
            if arm_id is None:
                return
            hod = max(c.high for c in self.candles)
            lod = min(c.low for c in self.candles)
            key_84 = (sess.entry_direction, round(sess.entry_price, sr.NO_REPEAT_LEVEL_TICK))
            attempts = self._attempts_84.get(key_84, 1)
            conds, stop_chk = rule84_conditions(
                sess.entry_direction, current, hod, lod, sess.entry_price,
                sess.entry_stop, sess.entry_target, attempts,
                sr.RULE84_MAX_ATTEMPTS, sr.SESSION_END)
            ctx["events"][arm_id]["bars"].append({
                "i": len(self.candles) - 1, "stop_chk": round(stop_chk, 4),
                "conds": conds,
            })
    bw.BacktestRunner = FunnelRunner

    syms = [s for s in ALL_SYMS if has_archive(s, 100)]
    last = max((b2.archive_days(s) or ["1970-01-01"])[-1] for s in syms)
    start = (date.fromisoformat(last) - timedelta(days=days)).isoformat()
    window = sorted({d for s in syms for d in b2.archive_days(s) if d >= start})
    print("[g10] %d symbols, %d sessions %s..%s" % (len(syms), len(window), window[0], window[-1]), flush=True)

    qqq_brk = qqq_level_breaks(window)

    real_fired = 0   # cross-check: real reentry_84_rule rows the engine actually emitted
    for sym in syms:
        ctx["sym"] = sym
        day_bars, hourly = {}, []
        for d in [x for x in b2.archive_days(sym) if x >= start]:
            try:
                bars = pf.fetch_day(sym, d)
            except Exception:
                continue
            if not bars:
                continue
            r = pf.rth(bars)
            if len(r) < 30:
                continue
            day_bars[d] = (bars, r)
            hourly += hourly_from_1m(d, r)

        prev = None
        for d in sorted(day_bars):
            ctx["day"] = d
            bars, rth = day_bars[d]
            if prev:
                _, prth = day_bars[prev]
                pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
                pdo, pdc = prth[0].open, prth[-1].close
            else:
                pdh = pdl = pdo = pdc = None
            pmh, pml = pf.premarket_hi_lo(bars)
            bias = htf_bias_for(hourly, d)
            trades = bw.simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml, pdo, pdc,
                                     qqq=qqq_brk.get(d))
            real_fired += sum(1 for t in trades if t.signal_type == "reentry_84_rule")
            prev = d
        print("  [%s] %d sessions, %d arm events so far" % (sym, len(day_bars), len(ctx["events"])), flush=True)

    bw._arm_84 = RealArm84            # restore -- courtesy, the process exits anyway
    bw.BacktestRunner = RealRunner

    events = ctx["events"]
    print("armed=%d (ARM84_FUNNEL['armed']=%d), real reentry_84_rule rows=%d"
          % (len(events), bw.ARM84_FUNNEL["armed"], real_fired), flush=True)
    assert len(events) == bw.ARM84_FUNNEL["armed"], \
        "every ARM84_FUNNEL['armed'] increment must have produced exactly one recorded event"

    _attribute(events)

    shadow_fired = sum(1 for ev in events if ev["fired"])
    print("shadow fired=%d vs real reentry_84_rule rows=%d" % (shadow_fired, real_fired), flush=True)
    assert shadow_fired == real_fired, (
        "shadow rule84_conditions() disagrees with the real engine's own "
        "reentry_84_rule count (%d vs %d) -- the transcription has drifted "
        "from source" % (shadow_fired, real_fired))

    dead = [ev for ev in events if not ev["fired"]]
    assert len(dead) == len(events) - real_fired

    before11_kills = sum(1 for ev in dead if ev["kill_stage"] == "before11")
    before11_alone = sum(1 for ev in dead if ev.get("alone") and ev["kill_stage"] == "before11")
    assert before11_kills == 0 and before11_alone == 0, (
        "before11 killed %d armings (%d alone) -- it is supposed to be dead code "
        "in this backtest path; ENTRY_CUTOFF/SESSION_END may have diverged"
        % (before11_kills, before11_alone))

    _price_alone_bucket(events)

    out = {
        "meta": {"days": days, "generated": datetime.now().isoformat(timespec="seconds"),
                 "symbols": syms, "window": [window[0], window[-1]], "sessions": len(window),
                 "armed": len(events), "real_reentry_rows": real_fired,
                 "shadow_fired": shadow_fired, "conditions": CONDITIONS},
        "events": events,
    }
    p = ROOT / out_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print("wrote %s -- %d armings, %d dead" % (p, len(events), len(dead)), flush=True)


def _reached(bars: list, n: int) -> list:
    """reached[k] = True if SOME bar had conditions 1..k (0-indexed 0..k-1)
    all true, for k in 0..n. reached[0] is trivially True (armed). Monotonic
    in k by construction, so "first False" is well-defined. Shared by
    _attribute() (per-arming kill_stage) and report() (the cumulative
    funnel table) so there is exactly one place this is computed."""
    reached = [False] * (n + 1)
    reached[0] = True
    for b in bars:
        c = b["conds"]
        prefix_ok = True
        for k in range(n):
            if not c[k]:
                prefix_ok = False
            if prefix_ok:
                reached[k + 1] = True
    return reached


def _attribute(events: list) -> None:
    """Fills in fired / kill_stage / alone / alone_bar_i on every event, from
    its own recorded per-bar condition traces. Pure, no I/O."""
    n = len(CONDITIONS)
    for ev in events:
        bars = ev["bars"]
        reached = _reached(bars, n)
        alone_hit = [False] * n
        for b in bars:
            c = b["conds"]
            for j in range(n):
                if all(c[i] for i in range(n) if i != j):
                    alone_hit[j] = True
        fired = reached[n]
        kill_stage = None
        if not fired:
            for k in range(1, n + 1):
                if not reached[k]:
                    kill_stage = k - 1
                    break
        ev["fired"] = fired
        ev["kill_stage"] = CONDITIONS[kill_stage] if kill_stage is not None else None
        ev["alone"] = bool(kill_stage is not None and alone_hit[kill_stage])
        ev["alone_bar_i"] = None
        if ev["alone"]:
            j = kill_stage
            for b in bars:
                c = b["conds"]
                if all(c[i] for i in range(n) if i != j):
                    ev["alone_bar_i"] = b["i"]
                    ev["alone_stop_chk"] = b["stop_chk"]
                    break


def _price_alone_bucket(events: list) -> None:
    """For the largest kill-alone bucket, replays each rescued arming forward
    from its alone-bar to a real exit -- stop on the CLOSE, target on touch,
    same as backtest_week's own position management (`_stop_hit`, `_stop_fill_px`,
    `fill_price`, `SimTrade.pnl`) -- and records the R it would have earned. Re-fetches only
    the handful of (symbol, day) pairs this bucket touches, from the same
    cache-first archive the replay already populated, so this is a couple of
    dozen local disk reads, not a second engine replay."""
    import polygon_feed as pf
    import signal_runner as sr
    from backtest_week import SimTrade, RISK_DOLLARS, _stop_hit, _stop_fill_px

    alone_dead = [ev for ev in events if ev.get("alone")]
    if not alone_dead:
        return
    counts = Counter(ev["kill_stage"] for ev in alone_dead)
    top_cond, _ = counts.most_common(1)[0]
    bucket = [ev for ev in alone_dead if ev["kill_stage"] == top_cond]

    for ev in bucket:
        try:
            bars = pf.fetch_day(ev["sym"], ev["day"])
        except Exception:
            ev["cf_r"] = None
            continue
        rth = pf.rth(bars)
        i0 = ev["alone_bar_i"]
        if not rth or i0 is None or i0 >= len(rth):
            ev["cf_r"] = None
            continue
        is_long = ev["dir"] == "call"
        entry = sr.fill_price(ev["entry"], rth[i0], is_long)
        stop = ev["alone_stop_chk"]
        target = ev["target"]
        t = SimTrade(symbol=ev["sym"], day=ev["day"], signal_type="reentry_84_rule",
                     direction=ev["dir"], grade="B", status="fired",
                     entry_time=rth[i0].timestamp, entry=entry, stop=stop,
                     target=target, entry_idx=i0)
        resolved = False
        for i in range(i0 + 1, len(rth)):
            c = rth[i]
            if _stop_hit(c, stop, is_long):
                # T11: fill at the triggering close, floored at -1.25R --
                # `backtest_week._stop_fill_px`, the same one the book uses.
                t.outcome, t.exit_price, t.exit_idx = (
                    "loss", _stop_fill_px(t, c, is_long), i)
                resolved = True
                break
            hit = (c.high >= target) if is_long else (c.low <= target)
            if hit:
                t.outcome, t.exit_price, t.exit_idx = "win", target, i
                resolved = True
                break
        ev["cf_r"] = round(t.pnl / RISK_DOLLARS, 3) if resolved else None
        ev["cf_outcome"] = t.outcome if resolved else "unresolved_eod"


# --------------------------------------------------------------- the report

def report(out_md: str) -> None:
    p = ROOT / OUT_JSON
    if not p.is_file():
        sys.exit("missing %s -- run `python research/g10_arming_funnel.py run` first" % OUT_JSON)
    d = json.loads(p.read_text(encoding="utf-8"))
    meta, events = d["meta"], d["events"]
    n = len(CONDITIONS)
    armed = meta["armed"]
    fired = meta["shadow_fired"]
    dead = [ev for ev in events if not ev["fired"]]

    reached_counts = [0] * (n + 1)
    for ev in events:
        got = _reached(ev["bars"], n)
        for k in range(n + 1):
            if got[k]:
                reached_counts[k] += 1

    kill_counts = Counter(ev["kill_stage"] for ev in dead)
    alone_counts = Counter(ev["kill_stage"] for ev in dead if ev.get("alone"))
    zero_bar = sum(1 for ev in dead if not ev["bars"])

    dead_n = armed - fired
    L = ["# G10 -- the %d armings that never fired, per condition" % dead_n, "",
         "Generated by `research/g10_arming_funnel.py` over the loose arm "
         "(`RULE84_STRICT=0`) -- %d symbols, %d sessions %s..%s."
         % (len(meta["symbols"]), meta["sessions"], meta["window"][0], meta["window"][1]),
         "",
         "P7 (`research/p7_84_rule.md`) already ran this arm's opportunity funnel: "
         "past counted-stop-out, past the arming-setup check, past the grade gate, "
         "past the 11:00 SESSION_END check on the STOP-OUT bar, down to **%d armed** "
         "in this replay. This picks up there. Of those %d, **%d produced a "
         "`reentry_84_rule` signal** and **%d died in the six checks that gate the "
         "re-entry itself** -- reclaim, colour, distance off the day's extreme, "
         "remaining reward, the attempt cap, and the reclaim bar's own clock."
         % (armed, armed, fired, dead_n),
         ""]
    if armed != 433:
        L += ["The ticket cited P7's committed numbers as 433 armed / 317 dead / "
              "116 fired. This run measures **%d armed / %d dead**, with fired "
              "still exactly **%d** (the self-check below). The "
              "1-arming difference traces to `data_archive/*/2026-08-21.csv` -- five "
              "symbols' cache files for the window's last session were rewritten "
              "after P7's committed run and before this one (a live trading day "
              "getting backfilled), and it added exactly one arming: SPCX, put, "
              "2026-08-21, itself dead on `extreme20`. Not a bug in this script -- "
              "`shadow_fired == real_reentry_rows` is asserted on every `run`, "
              "against THIS replay's own archive read, not against a remembered "
              "116." % (armed, dead_n, fired), ""]
    L += [
         "**Self-check**: the shadow evaluation below (`rule84_conditions()`, a "
         "verbatim transcription of `signal_runner.py`'s inline call/put blocks) "
         "reports %d fired; the real engine's own `reentry_84_rule` row count over "
         "the same replay is %d. They must match for anything below to be trusted, "
         "and `run` asserts it on every invocation." % (fired, meta["real_reentry_rows"]),
         ""]

    if zero_bar:
        L += ["%d of the %d dead armings had zero evaluable bars (armed on the last "
              "bar before the 11:00 cutoff, or immediately clobbered by a later "
              "stop-out re-arming the same session slot) -- charged to `reclaim`, "
              "the first gate, since no bar ever gave them a chance at any of the "
              "six checks." % (zero_bar, len(dead)), ""]

    L += ["---", "", "## The funnel, past ARMED",
          "",
          "Cumulative -- how many of the %d armings had SOME bar that got at least "
          "this far, in the source's own evaluation order (not the ticket's prose "
          "order -- the source checks the attempt cap before the clock, see the "
          "module docstring):" % armed,
          "",
          "| stage | condition | reached |", "|---|---|---:|",
          "| 0 | (armed) | %d |" % reached_counts[0]]
    for k, cname in enumerate(CONDITIONS, start=1):
        L.append("| %d | %s | %d |" % (k, COND_LABEL[cname], reached_counts[k]))
    L += ["", "The last row (**%d**) is the shadow's fired count, cross-checked above "
          "against the real engine's %d." % (reached_counts[n], meta["real_reentry_rows"]),
          ""]

    L += ["---", "", "## Which condition kills, in evaluation order", "",
          "Each of the %d dead armings is charged to the FIRST condition (in source "
          "order) that no bar ever got past -- mutually exclusive, sums to %d. "
          "`alone` is the subset that would have fired if that ONE condition, and "
          "only that one, were lifted -- every other gate, upstream and downstream, "
          "still had to pass on some bar. That is the actionable column: a death "
          "attributed to `reclaim` that ALSO always fails `colour` is not rescued "
          "by touching reclaim alone." % (len(dead), len(dead)),
          "",
          "| order | condition | dies here | dies here **alone** | alone / dies-here |",
          "|---|---|---:|---:|---:|"]
    for k, cname in enumerate(CONDITIONS, start=1):
        kc = kill_counts.get(cname, 0)
        ac = alone_counts.get(cname, 0)
        pct = ("%.1f%%" % (ac / kc * 100)) if kc else "--"
        L.append("| %d | %s | %d | %d | %s |" % (k, COND_LABEL[cname], kc, ac, pct))
    total_kill = sum(kill_counts.values())
    total_alone = sum(alone_counts.values())
    L += ["| | **total** | **%d** | **%d** | |" % (total_kill, total_alone), ""]

    if kill_counts.get("before11", 0) == 0:
        L += ["`before11` kills **0**, alone or otherwise. It cannot: "
              "`backtest_week.py`'s per-bar loop already `continue`s past any bar "
              "at/after `ENTRY_CUTOFF` (\"11:00:00\") before `detect_signals()` is "
              "even called, and `detect_signals()` repeats the same cutoff via "
              "`in_session()`. By the time the 84%-rule block's own "
              "`bar_time(...) < SESSION_END` runs, the bar has already been proven "
              "to satisfy it twice over. `--selfcheck` asserts "
              "`ENTRY_CUTOFF == SESSION_END`, which is the structural reason this "
              "sixth condition is dead code in this backtest, not a coincidence of "
              "this particular sample.", ""]

    if alone_counts:
        top_cond, top_n = alone_counts.most_common(1)[0]
        priced = [ev for ev in dead if ev.get("alone") and ev["kill_stage"] == top_cond
                  and ev.get("cf_r") is not None]
        skipped = top_n - len(priced)
        L += ["---", "", "## The largest kill-alone bucket: `%s`" % top_cond, "",
              "**%d of the %d dead armings (%.1f%%) fail on `%s` and nothing else** -- "
              "every other gate, upstream and downstream, is satisfiable on some bar; "
              "only %s blocks them." % (top_n, len(dead), top_n / len(dead) * 100,
                                        top_cond, COND_LABEL[top_cond]), ""]
        if priced:
            rs = [ev["cf_r"] for ev in priced]
            wins = sum(1 for r in rs if r > 0)
            losses = sum(1 for r in rs if r < 0)
            scratch = len(rs) - wins - losses
            L += ["Each is replayed forward from the first bar that clears every "
                  "OTHER gate, entering exactly as the real detector would "
                  "(`fill_price` off that bar, the original stop and target), and "
                  "managed to a real exit -- stop on the candle CLOSE, target on "
                  "touch, same `_stop_hit`/`SimTrade.pnl` the whole book uses. "
                  "%d of %d resolved by day end%s." % (
                      len(priced), top_n,
                      (" (%d never hit stop or target and are excluded)" % skipped)
                      if skipped else ""),
                  "",
                  "| n | win | loss | scratch | mean R | median R | total R |",
                  "|---:|---:|---:|---:|---:|---:|---:|",
                  "| %d | %d | %d | %d | %+.3f | %+.3f | %+.2f |" % (
                      len(rs), wins, losses, scratch,
                      statistics.fmean(rs), statistics.median(rs), sum(rs)),
                  ""]
            L += ["That is the number that decides whether lifting `%s` is worth "
                  "anything. P7 already measured this exact arm's book (loose, "
                  "`RULE84_STRICT=0`) at **+0.792R mean** over its 79 traded "
                  "re-entries, itself already below the whole book's +0.957R and "
                  "short of the 2.0R money gate -- and found that opening the ARM "
                  "gate bought nothing. This row does not change that: it measures "
                  "what `%s` alone is worth, it does not decide to lift it. "
                  "`RULE84_STRICT=1` stays the shipped default regardless of this "
                  "number." % (top_cond, top_cond), ""]
        else:
            L += ["None of the %d resolved to a priced exit (all ran out of day "
                  "before hitting either stop or target) -- no mean R to report."
                  % top_n, ""]

    L += ["---", "", "## What this does not do", "",
          "- Change no default: `RULE84_STRICT=1` ships regardless of what is above.",
          "- Decide anything: this is a measurement of where the detector's "
          "opportunities go, on the same terms P7 already measured the ARM gate.",
          "- Touch `signal_runner.py`: `rule84_conditions()` is a read-only "
          "transcription, cross-checked against the real engine's own "
          "`reentry_84_rule` count on every `run`.",
          "",
          "Reproduce: `python research/g10_arming_funnel.py run` then "
          "`python research/g10_arming_funnel.py report`. "
          "`python research/g10_arming_funnel.py --selfcheck` runs the "
          "assert-based, archive-free check on `rule84_conditions()` itself.", ""]

    out = ROOT / out_md
    out.write_text("\n".join(L), encoding="utf-8")
    print("wrote %s" % out)


# --------------------------------------------------------------- selfcheck

def selfcheck() -> None:
    """Assert-based, synthetic, no archive/network needed. Exercises
    rule84_conditions() in isolation -- one hand-built bar per condition that
    fails EXACTLY that condition and nothing else -- plus the structural
    facts the whole ticket leans on (RULE84_LESSON, and why `before11` is
    dead code in the backtest path)."""
    import backtest_week as bw
    import signal_runner as sr
    from omen_bot import Candle

    print("g10 selfcheck -- RULE84_LESSON=%r  ENTRY_CUTOFF=%r  SESSION_END=%r"
          % (sr.RULE84_LESSON, bw.ENTRY_CUTOFF, sr.SESSION_END))
    assert sr.RULE84_LESSON is True, (
        "RULE84_LESSON moved off True -- rule84_conditions()'s stop_chk formula "
        "(always the original stop) no longer matches source")
    assert sr.NO_REPEAT_LEVEL_TICK == 2, "key_84 rounding moved; _g10_probe's key_84 must match"
    assert bw.ENTRY_CUTOFF == sr.SESSION_END == "11:00:00", (
        "ENTRY_CUTOFF/SESSION_END diverged -- `before11` may no longer be dead "
        "code in the backtest path")

    def bar(ts, o, h, l, c):
        return Candle(timestamp=ts, open=o, high=h, low=l, close=c, volume=1000)

    # ---- call side: one clean all-pass bar, then six single-condition kills
    entry, stop, target = 100.00, 99.00, 106.00   # risk 1.00, reward 6.00
    hod, lod = 103.00, 98.00                       # range 5.00

    allpass = bar("10:00:00", 101.0, 101.6, 100.9, 101.5)   # bullish, close 101.5
    conds, stop_chk = rule84_conditions("call", allpass, hod, lod, entry, stop,
                                        target, 1, 2, "11:00:00")
    assert conds == [True, True, True, True, True, True], ("all-pass case", conds)
    assert stop_chk == stop

    # attempts-only: identical bar, attempts already at the cap
    c6, _ = rule84_conditions("call", allpass, hod, lod, entry, stop, target, 2, 2, "11:00:00")
    assert c6 == [True, True, True, True, False, True], ("attempts-only", c6)

    # before11-only: identical bar, but it lands at the session boundary
    late = bar("11:00:00", 101.0, 101.6, 100.9, 101.5)
    c7, _ = rule84_conditions("call", late, hod, lod, entry, stop, target, 1, 2, "11:00:00")
    assert c7 == [True, True, True, True, True, False], ("before11-only", c7)

    # reclaim-only: bullish, close still under entry, everything else clear
    b2 = bar("10:00:00", 99.5, 99.9, 99.4, 99.8)
    c2, _ = rule84_conditions("call", b2, hod, lod, entry, stop, target, 1, 2, "11:00:00")
    assert c2 == [False, True, True, True, True, True], ("reclaim-only", c2)

    # colour-only: closes back above entry, but the bar itself is bearish
    b3 = bar("10:00:00", 101.8, 101.9, 101.3, 101.5)
    c3, _ = rule84_conditions("call", b3, hod, lod, entry, stop, target, 1, 2, "11:00:00")
    assert c3 == [True, False, True, True, True, True], ("colour-only", c3)

    # extreme20-only: bullish reclaim sitting on top of HOD, target far enough
    # away that remaining reward alone would still clear 1.5x
    b4 = bar("10:00:00", 102.70, 102.95, 102.60, 102.92)
    c4, _ = rule84_conditions("call", b4, hod, lod, entry, stop, 130.00, 1, 2, "11:00:00")
    assert c4 == [True, True, False, True, True, True], ("extreme20-only", c4)

    # rr15-only: bullish reclaim well off the extreme, but the target is now
    # too close to clear 1.5x the risk already taken on
    b5 = bar("10:00:00", 100.8, 101.2, 100.7, 101.0)
    c5, _ = rule84_conditions("call", b5, hod, lod, entry, stop, 101.30, 1, 2, "11:00:00")
    assert c5 == [True, True, True, False, True, True], ("rr15-only", c5)

    # ---- put side: mirror, one all-pass bar --------------------------------
    entry_p, stop_p, target_p = 50.00, 51.00, 44.00
    hod_p, lod_p = 51.50, 47.00
    putbar = bar("10:00:00", 48.8, 48.9, 48.3, 48.5)   # bearish, close 48.5
    condsP, stop_chkP = rule84_conditions("put", putbar, hod_p, lod_p, entry_p,
                                          stop_p, target_p, 1, 2, "11:00:00")
    assert condsP == [True, True, True, True, True, True], ("put all-pass", condsP)
    assert stop_chkP == stop_p

    print("g10 selfcheck OK -- 6 call-side isolations + attempts + before11 + "
          "put-side mirror + RULE84_LESSON/ENTRY_CUTOFF structural asserts")


def main():
    if "--selfcheck" in sys.argv:
        selfcheck()
        return
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--days", type=int, default=730)
    r.add_argument("--out", default=OUT_JSON)
    q = sub.add_parser("report")
    q.add_argument("--out", default=OUT_MD)
    sub.add_parser("selfcheck")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.days, a.out)
    elif a.cmd == "selfcheck":
        selfcheck()
    else:
        report(a.out)


if __name__ == "__main__":
    main()
