# P22 — The 11:00 boundary is manage-only

Rule ballot batch 02, row c7 (2026-08-27): *"no more looking, only managing a 10 percent position most of the time, unless got an s entry late in the 10 o clock window."*

## Claim 1: No new entries after 11:00 ET

**Code enforcement**: `backtest_week.py:553, 621–622`

```python
# Line 553
ENTRY_CUTOFF = "11:00:00"  # Scarface trades 9:30-11 only (volume/volatility); None = all day

# Lines 621-622
if ENTRY_CUTOFF and c.timestamp >= ENTRY_CUTOFF:
    continue  # skip signal detection, stay in management loop
```

**Data verification** (bt2y_trades.json, 45,175 trades):
- Latest entry time: **10:59 ET** on 2025-01-06
- Entries at or after 11:00 ET: **0**
- Entry time range: 09:35 to 10:59 (5 to 89 minutes after 09:30)

**Verdict**: Yes. Code and data agree: no entries fire at or after 11:00 ET.

---

## Claim 2: The runner tranche is 10%

**Shipped default** (`backtest_week.py` with `SCALE_PLAN="hod_then_runner_be"`):

`backtest_week.py:540–545` documents the F1 ladder exit:
> "hod_then_runner_be" = hod_then_runner + stop -> breakeven after the first scale

The P&L calculation at `backtest_week.py:475–477` shows:
```python
# F1 ladder: 50% filled at scale_level + 50% at exit_price
if self.scaled:
    ...
    return round((0.5 * scale_r + 0.5 * run_r) * risk_dollars, 2)
```

The shipped default splits as **50% at HOD/LOD + 50% at runner target**, not 10% runner.

**Alternative policy** (in `exit_lab.py:378–379`, test module):
```python
def policy_30_30_30_10(bars, entry_i, entry, stop, side, trail_method="atr"):
    return scale_out(bars, entry_i, entry, stop, side, [0.30, 0.30, 0.30, 0.10], trail_method)
```

The `30_30_30_10` policy has a **10% runner** (the last tranche in the list), but this is a reference policy in exit_lab.py, not the shipped backtest default.

**Verdict**: No. The shipped `SCALE_PLAN="hod_then_runner_be"` default uses 50% scale-out at HOD, 50% runner — not 10%. A 10% runner exists as `policy_30_30_30_10` in exit_lab.py (test/reference only).

---

## Summary

1. **No new entries after 11:00 ET**: Yes. Enforced at `backtest_week.py:621–622` via `ENTRY_CUTOFF="11:00:00"`. Data confirms 0 entries >= 11:00.
2. **Runner is 10%**: No. The shipped default uses 50/50 (50% HOD, 50% runner). The 10% runner policy is `policy_30_30_30_10` in exit_lab.py, a reference policy not in the main backtest.
