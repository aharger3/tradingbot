"""g77_wrongchart_table.py -- print the per-card signal ledger, readable.

One block per graded card: his answer and minute, the card the deck built, and
every signal the engine had on that chart that morning with its arm, minute,
direction, both grades, whether it traded and for how much.
"""
from __future__ import annotations
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CENSUS = os.path.join(HERE, "g77_wrongchart_census.json")


def main():
    only = sys.argv[1:] or None
    d = json.load(open(CENSUS, encoding="utf-8"))
    for p in d["cards"]:
        if only and p["card_id"] not in only:
            continue
        print("=" * 96)
        print("%-18s  %s  bucket=%-3s  he said %-3s  his minute %s"
              % (p["card_id"], p["date"], p["bucket"],
                 "YES" if p["his_yes"] else "NO", p["his_minute"] or "(none)"))
        if p["his_note"]:
            print('   note: "%s"' % p["his_note"])
        print("   CARD: %s %s %s level=%s(%s) legacy=%s sgrade=%s traded=%s r=%s"
              % (p["card_setup"], p["card_et"], p["card_dir"], p["card_level"],
                 p["card_level_src"], p["card_legacy"], p["card_sgrade"],
                 p["card_traded"], p["card_r"]))
        print("   %d signals that morning, %d traded" % (p["n_signals"], p["n_traded"]))
        print("   %-4s %-6s %-5s %-4s %-3s %-6s %-6s %-22s %9s %8s %s"
              % ("", "et", "arm", "dir", "leg", "sgrade", "traded", "level", "entry", "r", "out"))
        for s in p["all_signals"]:
            print("   %-4s %-6s %-5s %-4s %-3s %-6s %-6s %-22s %9.2f %8s %s"
                  % ("CARD" if s["is_card"] else "",
                     s["et"], s["setup"], s["dir"], s["grade"], s["sgrade"],
                     "YES" if s["traded"] else "", (s["level"] or "")[:22],
                     s["entry"], s["r"] if s["traded"] else "", s["out"] if s["traded"] else ""))
        if p["closest_traded"]:
            ct = p["closest_traded"]
            print("   closest TRADED to his %s: %s %s %s on %s -> %+.0f min, %+.2fR ($%+.0f)"
                  % (p["his_minute"], ct["setup"], ct["et"], ct["dir"], ct["level"],
                     ct["delta"], ct["r"], ct["pnl"]))
        if p["card_delta"] is not None:
            print("   the CARD sat %+d min from his minute" % p["card_delta"])
    print("=" * 96)
    print(json.dumps(d["summary"], indent=1))


if __name__ == "__main__":
    main()
