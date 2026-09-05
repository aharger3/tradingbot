#!/usr/bin/env python3
"""OMEN 9.0 L6: the ntfy S push carries the whole order, not just the
stock-side numbers. Plain asserts, no pytest:
    python research/test_push_body.py

Per `research/execution_prep_2026-09.md`, no venue in this survey publishes a
pre-fillable deep link -- every manual execution path requires the human to
retype the order from what OMEN sends. This test pins that `_push_s_signal`'s
body contains every field the spec names: underlying, expiry, strike, right,
OCC symbol (when resolvable), contracts, entry, stop, target, the 1R dollar
figure, and the Alpaca paper order id (spec L3 -- shipped BLOCKED, so this
must render an honest placeholder rather than a fabricated id), all under
ntfy's 4 KB body limit.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import live_scanner as ls

FAILS = []


def check(cond, label):
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}")
        FAILS.append(label)


def _capture_push(rec):
    captured = {}

    def fake_push(title, body, **kw):
        captured["title"] = title
        captured["body"] = body
        return True

    orig = ls.notify_ntfy.push
    ls.notify_ntfy.push = fake_push
    try:
        ls._push_s_signal(rec)
    finally:
        ls.notify_ntfy.push = orig
    return captured["title"], captured["body"]


def _rec(**overrides):
    base = {
        "symbol": "TSLA", "direction": "call",
        "ts": "09:45:00", "setup": "break_and_retest",
        "entry": 245.10, "stop": 243.50, "target": 249.00,
        "contracts": 3, "tier": "TRADE",
        "level": "premarket high", "level_tf": "intraday",
        "max_loss": 1000.0,
        "expiration": "2026-09-05", "strike": 245.0,
        "occ_symbol": "TSLA260905C00245000",
        "alpaca_order_id": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. every spec-named field appears in the rendered body, resolved contract
# ---------------------------------------------------------------------------

_, body = _capture_push(_rec())
for label, needle in [
    ("underlying", "TSLA"),
    ("expiry", "2026-09-05"),
    ("strike", "245"),
    ("right (CALL)", "CALL"),
    ("OCC symbol", "TSLA260905C00245000"),
    ("contracts", "3 contracts"),
    ("entry", "245.10"),
    ("stop", "243.50"),
    ("target", "249.00"),
    ("1R dollars", "1,000"),
]:
    check(needle in body, f"(1) body carries {label} ({needle!r})")

# ---------------------------------------------------------------------------
# 2. Alpaca paper order id: present when the field carries one
# ---------------------------------------------------------------------------

_, body = _capture_push(_rec(alpaca_order_id="8f6a2b1c-0000-4444-9999-abcdef012345"))
check("8f6a2b1c-0000-4444-9999-abcdef012345" in body,
      "(2) a real Alpaca paper order id renders verbatim when present")

# ---------------------------------------------------------------------------
# 3. Alpaca paper order id: honest placeholder when absent (L3 blocked),
#    never a fabricated id and never a silently missing line
# ---------------------------------------------------------------------------

_, body = _capture_push(_rec(alpaca_order_id=None))
check("Alpaca" in body, "(3a) an Alpaca line still appears when no order id exists")
check("not placed" in body, "(3b) the placeholder is honest (\"not placed\"), not fabricated")

# ---------------------------------------------------------------------------
# 4. unresolved OCC contract: no listed contract, still no blank/crash
# ---------------------------------------------------------------------------

_, body = _capture_push(_rec(occ_symbol=""))
check("no listed contract" in body, "(4) an unresolved OCC symbol renders honestly, not blank")

# ---------------------------------------------------------------------------
# 5. stays under ntfy's 4 KB body limit
# ---------------------------------------------------------------------------

_, body = _capture_push(_rec())
check(len(body.encode("utf-8")) < 4096, f"(5) body is under 4KB (got {len(body.encode('utf-8'))} bytes)")

print()
if FAILS:
    print(f"{len(FAILS)} FAILED:")
    for f in FAILS:
        print(f"  - {f}")
    if __name__ == "__main__":
        sys.exit(1)
print("all checks passed")
