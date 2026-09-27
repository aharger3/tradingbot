# v3-eye2-candidates

Candidate generator for the OMEN "eye loop" (`a4-mantra.md` spec v3, `OMEN-SHIP-PLAN-v3.md`).

Scans 1-min MNQ/NQ bars, RTH 09:30-11:00 ET, Mon-Thu, for OR5 break -> displacement
(>=1.0 ATR) -> wick retest (no close-through) -> trigger-bar events, and emits **every**
one as a JSON candidate card (not just the first-of-day trade the v2/v3 backtest engines
grade) -- because the eye loop needs the one-off/two-off borderline cases too, for Austin
to tap S / not-S on.

## Run

```
python candidates.py MNQ 20 candidates_out.json
```

No live feed is wired up on this box; this replays the last N Mon-Thu sessions of the
recovered NQ 1-min data (sized as MNQ) via `research/agent_runs/v2-s07-data/omen_data.py`
on the main tradingbot checkout (read-only, absolute path -- same convention every v2/v3
script here already uses, since that restored data is untracked and a worktree doesn't
get a copy; see `RECOVERY.md`).

## Candidate JSON shape

```json
{
  "time": "2026-09-07T10:13:00-04:00",
  "instrument": "MNQ",
  "direction": "short",
  "level": 29612.25,
  "entry": 29609.75,
  "stop": 29617.25,
  "target_1r": 29602.25,
  "target_2r": 29594.75,
  "features": { "atr": ..., "displacement_atr": ..., "trigger_pin": ..., "ocr_trend_tag": ..., ... },
  "grade_hint": "S",
  "missing": []
}
```

`grade_hint` mirrors a4-mantra's S-grade gate: disp >=1.0 ATR, has a pin/strong trigger,
inside the 09:35-10:30 window, first signal of the day. 0 missing = S, 1 = one-off,
2 = two-off (a4-mantra: logged, never auto-traded, used as control arms).

`ocr_trend_tag` is a **simplified proxy** for a4-mantra's OCR row (EMA9 vs EMA20 slope
agreeing with trade direction) -- the real OCR definition needs order-block detection
this generator does not build. `shallow_retest` (<=0.35 ATR) is his-eye correlate
(ship-plan v3 s5), tracked as a feature only, not part of the S-grade gate.

## Result on this box (2026-09-26)

MNQ, last 20 Mon-Thu sessions (2026-08-24..2026-09-24): 40 candidates, 3 graded `S`.

## Not done here (out of scope / time-boxed)

- Live MNQ feed / phone-card push (ntfy) -- product idea's later stage.
- Real order-block OCR gate.
- Paper-trading only S-confirmed candidates (separate ticket, per OMEN-SHIP-PLAN-v3 B3).

Paper/research only. No orders are placed by this script.
