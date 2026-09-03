"""ADVERSARIAL VERIFY of research/g71_timing.md section 4 ("the load-bearing finding").

Claim under test: on the 9 held-out S days where the engine both SAW a setup
within +/-2 bars of Austin's typed minute AND traded it, entry bar - first-seen
bar is +1..+3, 9 of 9 same sign, sign test p = 0.0039.

This script re-derives the same 9 days but adds the three things the original
never checked:
  (a) do the "seen" signal and the "fired" entry belong to the SAME setup key?
  (b) is a NEGATIVE gap reachable at all, given how t4_engine_recall.run_day
      builds `all_sigs` (first bar of a contiguous run) vs `entries` (first
      FIRED bar of the same run)?
  (c) what does the RAW (undeduped) signal stream say about the same bars --
      i.e. did the engine really emit only one thing at his candle?

Marks are READ ONLY. No engine file touched.
"""
from __future__ import annotations
import json, os, sys, itertools

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
from t4_engine_recall import run_day, DEDUPE_BARS   # noqa: E402

PROBE = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")


def to_bar(hhmm):
    h, m = hhmm.replace(".", ":").split(":")[:2]
    return (int(h) - 9) * 60 + int(m) - 30


def key_of(rec):
    idea = (rec.get("stop_level")
            if rec["signal_type"] == "break_and_retest" else round(rec["stop"], 2))
    return (rec["signal_type"], rec["direction"], idea)


def main():
    print("DEDUPE_BARS as t4_engine_recall sees it = %r" % (DEDUPE_BARS,))
    cards = []
    for line in open(PROBE, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        ans = [a.lower() for a in ((o.get("answers") or {}).get("s") or [])]
        mn = (o.get("notes") or {}).get("min")
        if "s" in ans and mn:
            cards.append((o["symbol"], o["date"], mn.strip()))
    print("S cards with a typed minute: %d" % len(cards))

    rows = []
    for sym, day, mn in cards:
        his = to_bar(mn)
        entries, all_sigs, raw = run_day(sym, day)
        if entries is None:
            continue
        rows.append(dict(sym=sym, day=day, his=his, entries=entries,
                         all_sigs=all_sigs, raw=raw))

    print("\n=== the 9 'FIRED' days, opened up ===")
    hdr = ("%-6s %-11s %4s %5s %5s %4s  %-5s  %s"
           % ("sym", "day", "his", "seen", "fired", "gap", "same?", "detail"))
    print(hdr)
    gaps = []
    same_key = 0
    for r in rows:
        his = r["his"]
        fired_bars = sorted(e["bar"] for e in r["entries"])
        seen_bars = sorted(s["bar"] for s in r["all_sigs"])
        if not fired_bars or not seen_bars:
            continue
        nf = min(fired_bars, key=lambda b: abs(b - his))
        ns = min(seen_bars, key=lambda b: abs(b - his))
        if abs(nf - his) > 2 or abs(ns - his) > 2:
            continue
        fe = [e for e in r["entries"] if e["bar"] == nf][0]
        se = [s for s in r["all_sigs"] if s["bar"] == ns][0]
        ok = key_of(fe) == key_of(se)
        same_key += ok
        gaps.append(nf - ns)
        # raw stream for THIS fired key, around the window
        kraw = [x for x in r["raw"] if key_of(x) == key_of(fe)]
        first_raw = min(x["bar"] for x in kraw) if kraw else None
        run_desc = ",".join("%d:%s" % (x["bar"], x["status"])
                            for x in sorted(kraw, key=lambda x: x["bar"])
                            if abs(x["bar"] - his) <= 6)
        print("%-6s %-11s %4d %5d %5d %+4d  %-5s  firstraw_of_fired_key=%s | %s"
              % (r["sym"], r["day"], his, ns, nf, nf - ns,
                 "SAME" if ok else "DIFF", first_raw, run_desc))
    print("\nn=%d gaps=%s  same-key on %d of %d" %
          (len(gaps), gaps, same_key, len(gaps)))

    # ---- (b) reachability: can the gap ever be negative? ----
    print("\n=== reachability of a NEGATIVE gap ===")
    viol = 0
    for r in rows:
        by_key_first_any = {}
        by_key_first_fired = {}
        for s in r["all_sigs"]:
            by_key_first_any.setdefault(key_of(s), s["bar"])
        for e in r["entries"]:
            by_key_first_fired.setdefault(key_of(e), e["bar"])
        for k, fb in by_key_first_fired.items():
            ab = by_key_first_any.get(k)
            if ab is not None and fb < ab:
                viol += 1
    print("per-setup-key rows where the deduped FIRED bar precedes the deduped "
          "SEEN bar, across all %d cards: %d" % (len(rows), viol))

    # exhaustive: over every card, every (nearest-fired, nearest-signal) pair
    # inside a +/-2 window of ANY hypothetical 'his' bar 0..89, how often is the
    # gap negative?  This asks whether the sign test's H0 is even attainable.
    neg = pos = zero = 0
    for r in rows:
        fb = sorted(e["bar"] for e in r["entries"])
        sb = sorted(s["bar"] for s in r["all_sigs"])
        if not fb or not sb:
            continue
        for h in range(0, 90):
            nf = min(fb, key=lambda b: abs(b - h))
            ns = min(sb, key=lambda b: abs(b - h))
            if abs(nf - h) > 2 or abs(ns - h) > 2:
                continue
            g = nf - ns
            neg += g < 0; pos += g > 0; zero += g == 0
    print("over EVERY hypothetical his-bar 0..89 on all %d cards, the same "
          "estimator gives: negative %d / zero %d / positive %d"
          % (len(rows), neg, zero, pos))
    print("  -> P(gap<0) under the estimator's own support = %.4f"
          % (neg / max(1, neg + pos + zero)))

    # ---- (c) is '11 of 12 are X' independent of '9 of 9 positive'? ----
    print("\n=== is the X count a second fact, or the same one? ===")
    print("t4_engine_recall._route: status=='skipped_d' <=> grade==TradeGrade.D")
    print("omen_bot.TradeGrade: D = 'X' (alias, same member).  So 'graded X' and")
    print("'status skipped_d' are the SAME field printed twice.")
    n_within = n_x = 0
    for r in rows:
        his = r["his"]
        fb = sorted(e["bar"] for e in r["entries"])
        sb = sorted(s["bar"] for s in r["all_sigs"])
        if not fb or not sb:
            continue
        nf = min(fb, key=lambda b: abs(b - his)); ns = min(sb, key=lambda b: abs(b - his))
        if abs(nf - his) > 2 or abs(ns - his) > 2:
            continue
        for s in r["all_sigs"]:
            if abs(s["bar"] - his) <= 2:
                n_within += 1
                n_x += (s["status"] == "skipped_d")
    print("signals in all_sigs within +/-2 of his bar on the 9 days: %d, of which "
          "skipped_d/X: %d" % (n_within, n_x))
    return 0


if __name__ == "__main__":
    sys.exit(main())
