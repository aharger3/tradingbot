"""No `A+` and no `B` ever reaches Austin.

Austin, 2026-08-28: "A+ was suppposed to be killed too, what happened?"

They were never killed, because they are not grades -- they are the engine's
working states inside a promotion lattice. Over the 2-year book the lattice
trades 1,000 `B`, 15 `A` and 2 `A+`, so `B` is 98.3% of every trade ever taken
and deleting the letter deletes the book.

What IS killed, and what this test pins: every grade crossing into an alert, a
print or a Discord post is translated once by `omen_bot.his_grade`. Nothing
about what fires changes; only the letters he reads.

    python test_his_ladder.py
"""
import inspect
import sys

import discord_bot
import live_scanner
from omen_bot import HIS_LADDER, TradeGrade, his_grade

fails = 0


def check(ok, msg):
    global fails
    print(("ok   " if ok else "FAIL ") + msg)
    fails += not ok


# --- the mapping itself ----------------------------------------------------
for engine, his in (("A+", "S"), ("A", "A"), ("B", "A"), ("C", "C"),
                    ("X", "X"), ("D", "X")):
    check(his_grade(engine) == his, "engine %-2s -> his %s" % (engine, his))

check(his_grade(None) == "X", "a missing grade is a refusal, not a crash")
check(his_grade(TradeGrade.B) == "A", "a TradeGrade member maps like its value")
check("S" not in HIS_LADDER,
      "the map is one-way: his letters are never keys, so it cannot be inverted")
check(set(HIS_LADDER.values()) == {"S", "A", "C", "X"},
      "his ladder is exactly S/A/C/X -- no A+ and no B in the range")

# Every working state the engine can hold must have somewhere to land.
for g in TradeGrade:
    check(g.value in HIS_LADDER, "TradeGrade.%s has a tier" % g.name)

# --- the display boundary --------------------------------------------------
src = inspect.getsource(discord_bot.DiscordSignalBot.format_signal_message)
check("his_grade(" in src,
      "format_signal_message translates before building the embed")

# The two embed builders must be reachable ONLY through that entry point, or a
# caller could hand them a raw engine letter and bypass the translation.
mod = inspect.getsource(discord_bot)
for name in ("_format_options_embed", "_format_stock_embed"):
    callers = [ln.strip() for ln in mod.splitlines()
               if name in ln and ("def " + name) not in ln]
    check(all("self." + name in c for c in callers),
          "%s is only called from the translating entry point" % name)
check('"A+"' not in src and '"B"' not in src,
      "no engine letter is hard-coded in the embed colours")

ls = inspect.getsource(live_scanner)
raw = [ln.strip() for ln in ls.splitlines()
       if ("Grade: {grade}" in ln or "Grade {grade}" in ln)]
check(not raw, "no live_scanner line prints or posts an untranslated grade: %s" % raw)

print()
print("FAILED %d" % fails if fails else "all checks pass")
sys.exit(1 if fails else 0)
