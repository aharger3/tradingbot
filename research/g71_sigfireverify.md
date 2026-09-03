# G71 adversarial verify — track `sigfire`'s "WATCH naming collision" claim

**Verdict: REFUTED as stated.** The naming collision is real, but the claim's stated
mechanism and every number attached to it are wrong, because it misses the branch that
sits two lines above the one it cites.

Script: `research/g71_sigfireverify_tier.py`. Book: `research/bt2y_trades.json`,
generated `2026-08-29T03:14:29`, 76,019 routed rows, 2,437 traded.

## What survives

- `live_scanner.py:579-580` reads exactly `if grade != "A+": return "WATCH"`; accept at
  `:585`. Citation correct.
- `signal_runner.py:501-503` defines `ON_WATCH` as a fill flag, consumed only at
  `signal_runner.py:1327` inside `fill_price` via `near_session_extreme` (`:1333`).
  Nothing in `live_scanner.py` reads `ON_WATCH`; nothing in `signal_runner.py` reads the
  tier string. **The two "watch"es are genuinely unrelated.** That half of the claim holds.
- The A+ branch is reachable, not dead: 7 A+ over all routed rows, 4 booked.
- Book currency: 2,437 is the current post-T23 book and **supersedes** the 2,595-trade
  post-T0 figure still printed at `DIRECTION.md:20` — see `research/t23_stack.md:76`
  (traded 2,595 → 2,437, −158) and `research/g71_ddverify.md:33`. Book mtime 03:14 sits
  after `3abeaa05` (03:07, T23 stack) and the only later commit is doc-only. The
  "wrong book" objection fails.
- No look-ahead: the emulation reads only `grade` and `setup`, both fixed at signal time.

## What breaks it

`live_scanner.py:577-578`, **above** the cited line:

```
577:    if getattr(sig["signal_type"], "value", "") == "reentry_84_rule":
578:        return "TRADE" if s.consecutive_losses < 2 else "WATCH"
579:    if grade != "A+":          # R12: no time floor -- the whole window trades
```

`reentry_84_rule` returns TRADE **at any grade** and never reaches `:579`. The exemption is
deliberate and documented twice more in the same function's caller —
`live_scanner.py:616` (`size_pct *= 2.0`) and `:625-628` (*"84% re-entries are exempt from
the per-symbol S cap, same as they are exempt from the grade check itself"*).
`omen_bot.py:55` defines `REENTRY_84_RULE = "reentry_84_rule"`; `backtest_2y.py:165` writes
`t.signal_type` into the book's `setup` field, so the two tokens are the same string.

| | claim | actual (`g71_sigfireverify_tier.py`) |
|---|---:|---:|
| booked trades the live path takes | 4 | **127** (4 A+ + 123 `reentry_84_rule`, 0 overlap) |
| booked trades demoted to WATCH | 2,433 | **2,310** |
| share demoted, booked pool | "99.9%" | **94.79%** |
| share demoted, all 76,019 routed | — | **99.48%** (not 99.99%) |
| routed `reentry_84_rule` rows | not counted | 388 |

The report counts those 388 rows itself at `research/g71_sigfire.md:42-43` and still writes
"every signal that is not `A+`" at `:179` and the headline "**4**" at `:208`. The live take
is understated by **31×**.

Caveat in the honest direction: the three session-state branches (`:574` R31 account halt,
`:581` `consecutive_losses >= 2`, `:583` `GOVERNOR_S_CAP`) are not reconstructable from a
book row, so 127 is an **upper** bound on live TRADEs and 2,310 a **lower** bound on
demotions. The claim asserts 2,433 demotions; the true figure is at most 2,310, so the
direction of the error is established regardless.

## Fix (NOT applied)

```diff
--- a/research/g71_sigfire_funnel.py
+++ b/research/g71_sigfire_funnel.py
@@
-# the live gate: live_scanner._tier promotes only grade == "A+"
-aplus = [r for r in traded if r["grade"] == "A+"]
-a_or_better = [r for r in traded if r["grade"] in ("A+", "A")]
-print("LIVE GATE (live_scanner._tier: TRADE iff grade == 'A+')")
-print("  traded rows graded A+              %7d" % len(aplus))
-print("  traded rows graded A+ or A         %7d" % len(a_or_better))
+# The live gate is NOT grade-only: live_scanner.py:577-578 returns TRADE for
+# reentry_84_rule at any grade, before the grade!="A+" test at :579 is reached.
+aplus = [r for r in traded if r["grade"] == "A+"]
+r84 = [r for r in traded if r["setup"] == "reentry_84_rule"]
+live = [r for r in traded if r["grade"] == "A+" or r["setup"] == "reentry_84_rule"]
+a_or_better = [r for r in traded if r["grade"] in ("A+", "A")]
+print("LIVE GATE (live_scanner._tier: TRADE iff grade=='A+' OR reentry_84_rule)")
+print("  traded rows graded A+              %7d" % len(aplus))
+print("  traded rows reentry_84_rule        %7d" % len(r84))
+print("  traded rows the LIVE path takes    %7d" % len(live))
+print("  traded rows demoted to WATCH       %7d" % (len(traded) - len(live)))
+print("  traded rows graded A+ or A         %7d" % len(a_or_better))
```

`research/g71_sigfire.md` rows 13, 179, 191-192, 208-210, 318 and 328-329 all carry the
grade-only number and need the same correction (4 → 127, 2,433 → 2,310, 99.9% → 94.8%).
