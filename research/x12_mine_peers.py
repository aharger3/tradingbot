#!/usr/bin/env python3
"""X12: mine Scarface (TonyMontana) and Jdub alert channels for how they actually
enter, exit, scale, and report results. Read-only over discord_data/*.json.

Usage: python research/x12_mine_peers.py [--dump PATTERNKEY]
"""
import json, re, sys, os, collections

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DD = os.path.join(ROOT, "discord_data")

CHANNELS = {
    "scarface-alerts": "TonyMontana",
    "jdub-alerts": "Jdub",
    "trading-floor": None,
    "trade-feedback": None,
    "live-sessions": None,
    "futures-alerts": None,
    "swing-ideas": None,
    "pre-market-live": None,
    "premarket-charts": None,
    "options-trade-reviews": None,
    "futures-trade-reviews": None,
    "youtube": None,
}

# --- pattern families -------------------------------------------------------
PAT = {
    # partial exit / scaling OUT of a position
    "scale_out": r"\b(trim(?:med|ming)?|took (?:some|half|partial|a little|most)|sold (?:half|some|a third|most|partial)|scal(?:e|ed|ing) out|partial(?:s|ly)?\b|took profit(?:s)? on (?:half|some)|runner(?:s)?|trailer(?:s)?|trail(?:ing)? (?:the )?(?:rest|stop)|left (?:a )?runner)",
    # adding TO an existing position (scale-in / pyramiding / averaging)
    "scale_in": r"\b(add(?:ed|ing)? (?:to|more|into|on)|added more|averag(?:e|ed|ing) (?:up|down|in)|avg(?:ed)? (?:up|down)|doubl(?:e|ed|ing) (?:down|up|my position)|pyramid|size(?:d)? up (?:into|on)|load(?:ed|ing) (?:up )?more)",
    # full exit
    "full_out": r"\b(out full|full(?:y)? out|all out|closed (?:the )?(?:full|entire|whole)|out of (?:the )?full|out (?:the )?rest|out completely|flat(?:tened)? (?:the )?position)",
    # stop
    "stopped": r"\b(stopped (?:out|full|the rest)?|stop(?:ped)? loss hit|hit my stop|took the stop|stop out)\b",
    # explicit stop placement
    "stop_set": r"\bstop (?:is )?(?:above|below|at|under|over)\b",
    # target / rr language
    "target": r"\b(target(?:ing|s)?|price target|pt \d|looking for (?:hod|lod|pdh|pdl)|tp\d?)\b",
    "rr": r"\b(\d+(?:\.\d+)?\s*(?:to|:)\s*1\s*(?:r|rr|risk)?|risk[ /-]?reward|\br[:/ ]?r\b|\d+r\b)",
    # dollars reported
    "dollars": r"\$\s?\d[\d,]*(?:\.\d+)?\s?(?:k\b)?",
    # win rate / record language
    "record": r"\b(\d+\s*(?:for|/)\s*\d+|win rate|winrate|green (?:day|week|month)|red (?:day|week|month)|\d+\s*(?:green|red)\s*(?:days|weeks|months))",
    # no-trade / discipline
    "no_entry": r"\b(no entry|no trade|didn'?t take|passed on|stayed out|sitting out|no setup)",
}
COMP = {k: re.compile(v, re.I) for k, v in PAT.items()}

def load(ch):
    p = os.path.join(DD, ch + ".json")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def main():
    dump = None
    if "--dump" in sys.argv:
        dump = sys.argv[sys.argv.index("--dump") + 1]
    dump_ch = None
    if "--ch" in sys.argv:
        dump_ch = sys.argv[sys.argv.index("--ch") + 1]

    rows = []
    for ch, author in CHANNELS.items():
        msgs = load(ch)
        for m in msgs:
            c = m.get("content") or ""
            if not c.strip():
                continue
            if author and m.get("author") != author:
                continue
            hits = [k for k, r in COMP.items() if r.search(c)]
            if hits:
                rows.append({"ch": ch, "ts": m["ts"], "author": m.get("author"),
                             "hits": hits, "content": c})

    by = collections.defaultdict(collections.Counter)
    for r in rows:
        for h in r["hits"]:
            by[r["ch"]][h] += 1

    if dump:
        for r in rows:
            if dump in r["hits"] and (dump_ch is None or r["ch"] == dump_ch):
                print(r["ts"][:16], "|", r["ch"], "|", r["author"], "|",
                      r["content"].replace("\n", " ~ ")[:400])
        return

    print("channel                    " + "".join("%-11s" % k[:10] for k in PAT))
    for ch in CHANNELS:
        if ch in by:
            print("%-26s" % ch + "".join("%-11d" % by[ch][k] for k in PAT))

if __name__ == "__main__":
    main()
