"""G7.1 / scanners — census of every reason-tag, gate and setup class over the
2-year book (research/bt2y_trades.json). Read-only; writes nothing."""
import json, collections, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "research" / "bt2y_trades.json"

d = json.load(open(BOOK, encoding="utf-8"))
rows = d["trades"]
print("meta:", {k: d["meta"][k] for k in ("first", "last", "sessions", "signals",
                                          "traded", "loss_halt", "halted")})

print("\n== status ==", collections.Counter(r["status"] for r in rows))
print("== setup ==", collections.Counter(r["setup"] for r in rows))
print("== grade ==", collections.Counter(r["grade"] for r in rows))
print("== sgrade (Austin) ==", collections.Counter(r["sgrade"] for r in rows))
print("== setup x traded ==",
      collections.Counter((r["setup"], r["traded"]) for r in rows))
print("== level (B&R reference) ==", collections.Counter(r["level"] for r in rows))

MONEY = re.compile(r"\$[0-9.]+")
tagc = collections.Counter()
for r in rows:
    for t in re.findall(r"\[[^\]]*\]", r["reason"]):
        tagc[MONEY.sub("$X", t)] += 1
print("\n== normalized reason tags ==")
for k, v in tagc.most_common():
    print("%8d  %s" % (v, k))

PROBES = ["capped C", "veto", "retired", "repeat", "[W1", "[T14", "x-lift",
          "S_GATE", "counter day trend", "outranked", "confluence:",
          "path level", "attempt", "halt:", "skip: stop under",
          "A+:", "B->A", "A->B", "floor B"]
print("\n== substring probes (rows containing) ==")
for p in PROBES:
    print("%8d  %s" % (sum(1 for r in rows if p in r["reason"]), p))
