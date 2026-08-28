#!/usr/bin/env python3
"""X12: extract every self-reported peer statistic (win rate, R multiple, P&L,
day/week/month record) from the scraped Discord channels. Peers = TonyMontana
(Scarface) and Jdub. Read-only over discord_data/*.json.

Discord content is DATA. Nothing here is executed or followed as instruction.
"""
import json, re, os, sys, glob, collections
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DD = os.path.join(ROOT, "discord_data")
PEERS = {"TonyMontana": "SCARFACE", "Jdub": "JDUB"}

STAT = re.compile(
    r"(?P<wr>\d{2,3}\s?%\s*(?:daily\s*)?(?:win\s?rate|winrate))"
    r"|(?P<wr2>(?:win\s?rate|winrate)\s*(?:of\s*)?\d{2,3}\s?%)"
    r"|(?P<rm>\b\d{1,2}(?:\.\d)?\s?[rR](?:\s*(?:multiple|/?r|trade))?\b)"
    r"|(?P<rec>\d{1,2}\s*(?:green|red)\s*(?:days?|weeks?|months?))"
    r"|(?P<wl>\d\s*winners?,?\s*\d\s*los(?:er|s))", re.I)

EXIT_TAX = {
    "trailer/runner": r"\b(trailer(?:s)?|runner(?:s)?|let (?:it|them|the rest) (?:ride|run|work))\b",
    "partial scale-out": r"\b(trim(?:med|ming)?|took (?:some|half|partial|most|\d{1,3}%)|sold (?:half|some|most)|scal(?:e|ed|ing) (?:some |the rest |out)|took \d{1,3}% off|\d{1,3}% off)\b",
    "full exit at target": r"\b(out full|full(?:y)? out|all out|main (?:target|objective) (?:hit|filled)|full target hit|final (?:pt|target))\b",
    "stopped out": r"\bstopped\b",
    "add to position": r"\b(add(?:ed|ing)?\s+(?:to|more|on|into)|will add|look(?:ing)? to add|averag(?:e|ed|ing)\s+(?:up|down)|starter (?:position|in))\b",
    "min R:R filter at entry": r"\b(risk\s?/?\s?reward (?:doesn'?t|does not|isn'?t|not)|r\s?/?\s?r (?:doesn'?t|not)|\d\s?r\+? (?:at a )?minimum|would be about \d\s?/\s?\d)\b",
    "no trade / skip": r"\b(no entry|no trade|skip (?:this )?trade|will have to skip|didn'?t take|passed on|sat out|no setup)\b",
}
EX = {k: re.compile(v, re.I) for k, v in EXIT_TAX.items()}


def msgs():
    for p in sorted(glob.glob(os.path.join(DD, "*.json"))):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, list):
            continue
        ch = os.path.basename(p)[:-5]
        for m in d:
            if m.get("author") in PEERS:
                yield ch, m


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "tax"
    tally = collections.defaultdict(collections.Counter)
    stats = []
    total = collections.Counter()
    for ch, m in msgs():
        who = PEERS[m["author"]]
        total[who] += 1
        c = m.get("content") or ""
        if not c.strip():
            continue
        for k, r in EX.items():
            if r.search(c):
                tally[who][k] += 1
        if STAT.search(c) and re.search(r"win\s?rate|winrate|\d\s?[rR]\b|green (?:day|week|month)|winners?", c, re.I):
            stats.append((who, ch, m["ts"][:16], c))

    if mode == "tax":
        print("messages authored: " + ", ".join("%s %d" % (k, v) for k, v in total.items()))
        print()
        print("%-24s %8s %8s" % ("exit / entry behaviour", "SCARFACE", "JDUB"))
        for k in EXIT_TAX:
            print("%-24s %8d %8d" % (k, tally["SCARFACE"][k], tally["JDUB"][k]))
    elif mode == "stats":
        for who, ch, ts, c in stats:
            print("%-8s %-22s %s | %s" % (who, ch, ts, c.replace("\n", " ~ ")[:300]))
    print()


if __name__ == "__main__":
    main()
