"""Adversarial recount of the g82 stop-provenance claims.

Reads every mark corpus READ-ONLY and counts, independently:
  1. how many distinct Austin notes ratify "a stop fires on the candle CLOSE, not a wick"
  2. how many of those live in the batch05 sitting the report calls 2026-08-11
  3. whether the four quoted austin_marks_v7 lines (343/357/363/374) are verbatim
  4. whether ballot batch01 q1/q3 and batch02 a2/a3/b9/b3 say what the report says

Nothing is written to any mark file. Run: python research/g82_verify_0.py
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.abspath(__file__))

CORPORA = [
    "austin_marks_v7.jsonl",
    "blind_marks_all.jsonl",
    "recovered_reviews.jsonl",
    "marks_clean.jsonl",
]

# a note counts only if it ties a CLOSE to a STOP / invalidation-exit,
# not merely mentions the word "close" (which also means "near").
CLOSE_WORD = re.compile(r"\bclos(e|es|ed|ing)\b", re.I)
STOP_WORD  = re.compile(r"\bstop(s|ped|ping|\s*out|\s*loss)?\b", re.I)


def notes_from(path):
    out = []
    if not os.path.exists(path):
        return out
    for i, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        txt = " ".join(
            str(d.get(k, "")) for k in
            ("note", "notes", "review", "text", "comment", "answer_note", "why")
        ).strip()
        out.append((i, d, txt))
    return out


def main():
    hits, batch_counts = [], {}
    for fn in CORPORA:
        p = os.path.join(ROOT, fn)
        for i, d, txt in notes_from(p):
            if not txt:
                continue
            if CLOSE_WORD.search(txt) and STOP_WORD.search(txt):
                hits.append((fn, i, d.get("batch", ""), d.get("id", ""), txt))
                b = (fn, d.get("batch", ""))
                batch_counts[b] = batch_counts.get(b, 0) + 1

    print("=== close+stop co-occurring notes, per file/batch ===")
    for (fn, b), n in sorted(batch_counts.items(), key=lambda kv: -kv[1]):
        print("  %-28s batch=%-14s %d" % (fn, b or "(none)", n))
    print("  TOTAL candidate notes: %d" % len(hits))

    b05 = [h for h in hits if h[2] == "batch05_84"]
    print("\n=== batch05_84 (the sitting the report dates 2026-08-11) ===")
    for fn, i, b, cid, txt in b05:
        print("  line %-5d %-28s %s" % (i, cid, txt[:130]))
    print("  batch05_84 count: %d   (report claims 8)" % len(b05))

    print("\n=== verbatim check of the four quoted lines ===")
    v7 = open(os.path.join(ROOT, "austin_marks_v7.jsonl"),
              encoding="utf-8").read().splitlines()
    want = {
        343: "stop out happens when candle CLOSES below the level",
        357: "stop outs only happen when candle closes by the way",
        363: "stop out would've been 5 candles later because thats when the close below happened",
        374: "your entry never closed below the stop so no need 84 percent rule",
    }
    for n, frag in want.items():
        note = json.loads(v7[n - 1]).get("note", "")
        print("  line %d: %s" % (n, "MATCH" if frag in note else "NO MATCH"))

    print("\n=== does any corpus carry a grading DATE field? ===")
    keys = set()
    for fn in CORPORA:
        for i, d, txt in notes_from(os.path.join(ROOT, fn)):
            keys |= set(d.keys())
    datekeys = sorted(k for k in keys if any(
        w in k.lower() for w in ("date", "time", "graded", "at", "when")))
    print("  date-ish keys present anywhere:", datekeys or "(none)")

    print("\n=== ballots ===")
    for fn, wanted in (("rule_ballot_batch01.jsonl", {"q1", "q3", "q7", "q8"}),
                       ("rule_ballot_batch02.jsonl", {"a2", "a3", "b3", "b9"})):
        for i, d, txt in notes_from(os.path.join(ROOT, fn)):
            q = str(d.get("q", ""))
            if q in wanted:
                print("  %s line %-3d %-4s rule=%-32s ans=%-22s %s"
                      % (fn, i, q, d.get("rule", ""), str(d.get("answer", ""))[:22],
                         txt[:150]))

    print("\n=== code constants (money-relevant) ===")
    for path, pat in (("stop_rule.py", r"^DISASTER_STOP_R"),
                      ("backtest_week.py", r"^(STOP_ON_CLOSE|TARGET_ON_CLOSE|DISASTER_R)")):
        fp = os.path.join(os.path.dirname(ROOT), path)
        for n, line in enumerate(open(fp, encoding="utf-8").read().splitlines(), 1):
            if re.match(pat, line):
                print("  %s:%d  %s" % (path, n, line.strip()))


if __name__ == "__main__":
    main()
