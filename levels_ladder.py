"""levels_ladder.py -- THE LADDER, precisely (MASTER SPEC section 1, exits lane).

Pure, deterministic, no I/O, no `Candle`, no network. One function,
`build_rungs`, turns a trade's entry/stop plus a causal pool of levels into 1
to 4 profit rungs, strictly monotonic in the trade's direction, weights
summing to 1.0. It never fetches a level -- the caller (backtest_week.py)
supplies `session_extreme` and `named_levels`, both already causal (computed
off `candles[:i + 1]`, never a bar after the entry bar).

Frozen contract, per the spec's section 1.1 -- this signature is the seam
between the engine (backtest_week.py) and this module and does not move
without a spec revision:

    Rung = namedtuple("Rung", "price weight name")
    build_rungs(entry, stop, direction, *,
               session_extreme, named_levels,
               weights=(0.30, 0.30, 0.30, 0.10),
               psych_step=1.00, psych_tol=("r", 0.25),
               pt4_mode="max", pt4_r=4.0, min_gap_r=0.20) -> list[Rung]

The four rungs, in the spec's own words:

  PT1  the near session extreme (as-of entry bar). Dropped if it sits inside
       `min_gap_r` of entry -- not clamped, dropped.
  PT2  the named level with the smallest R strictly beyond PT1. Absent when
       no named level qualifies -- roughly half the real book.
  PT3  2R, UNLESS a whole-dollar or named level sits within `psych_tol` of
       the 2R price ("2r level is trumped by HTF levels and whole psych
       number if one is close") -- then PT3 becomes that substitute. Always
       available; this is the ladder's backbone.
  PT4  the runner. `pt4_mode` "rmult" = entry +/- pt4_r*risk; "structure" =
       nearest named level beyond PT3 (falls back to rmult when there is
       none); "max" (default) = the further of the two.

Ordering is enforced, not assumed: build the candidate set, drop non-positive
R and near-duplicates (a min_gap_r-wide coalesce that favours the NEARER
rung), sort ascending by R, then renormalize the first k weights to sum to
1.0. PT3 (2R) is always >= min_gap_r beyond entry for any sane min_gap_r, so
k == 0 is asserted unreachable rather than guarded around.
"""
from __future__ import annotations

import math
from collections import namedtuple
from typing import Dict, List, Optional, Sequence, Tuple

Rung = namedtuple("Rung", "price weight name")

_Candidate = namedtuple("_Candidate", "label price name")


def _is_long(direction) -> bool:
    if isinstance(direction, str):
        return direction.strip().lower() in ("call", "long", "buy", "c")
    return bool(direction)


def _tol_abs(psych_tol: Tuple[str, float], risk: float, entry: float) -> float:
    """Convert `psych_tol` (unit, value) into an absolute price distance."""
    unit, value = psych_tol
    unit = (unit or "r").strip().lower()
    if unit == "r":
        return value * risk
    if unit == "c":
        return value
    if unit in ("pct", "%"):
        return value / 100.0 * entry
    raise ValueError("psych_tol unit must be one of 'r'/'c'/'pct', got %r" % (unit,))


def _psych_candidates(target_px: float, psych_step: float) -> List[float]:
    """The whole-dollar multiples of `psych_step` nearest `target_px`."""
    if psych_step <= 0:
        return []
    k = target_px / psych_step
    return [round(psych_step * math.floor(k), 10), round(psych_step * math.ceil(k), 10)]


def _nearest_named_beyond(px: float, named_levels: Dict[str, float],
                          long: bool) -> Optional[Tuple[str, float]]:
    """(name, price) of the named level with the smallest positive distance
    beyond `px` in the trade's direction, or None."""
    beyond = {name: price for name, price in named_levels.items()
             if price is not None and (price > px if long else price < px)}
    if not beyond:
        return None
    name = min(beyond, key=lambda n: abs(beyond[n] - px))
    return name, beyond[name]


def build_rungs(entry: float, stop: float, direction,
                *, session_extreme: Optional[float],
                named_levels: Dict[str, float],
                weights: Sequence[float] = (0.30, 0.30, 0.30, 0.10),
                psych_step: float = 1.00,
                psych_tol: Tuple[str, float] = ("r", 0.25),
                pt4_mode: str = "max",
                pt4_r: float = 4.0,
                min_gap_r: float = 0.20) -> List[Rung]:
    risk = abs(entry - stop)
    if risk <= 0:
        return []
    long = _is_long(direction)
    sign = 1.0 if long else -1.0
    named_levels = {k: v for k, v in (named_levels or {}).items() if v is not None}

    def R(px: float) -> float:
        return sign * (px - entry) / risk

    candidates: List[_Candidate] = []

    # ---- PT1: the near session extreme -------------------------------
    pt1_price = session_extreme if session_extreme is not None else entry
    if session_extreme is not None and R(pt1_price) >= min_gap_r:
        name = "session high (HOD as-of entry)" if long else "session low (LOD as-of entry)"
        candidates.append(_Candidate("PT1", pt1_price, name))

    # ---- PT2: nearest named level strictly beyond PT1 -----------------
    pt2 = _nearest_named_beyond(pt1_price, named_levels, long)
    if pt2 is not None:
        candidates.append(_Candidate("PT2", pt2[1], pt2[0]))

    # ---- PT3: 2R, subject to the precedence substitution (section 2) --
    raw_pt3 = entry + sign * 2.0 * risk
    tol = _tol_abs(psych_tol, risk, entry)
    subs = []  # (distance, kind_rank, |price-entry|, price, name)
    for name, price in named_levels.items():
        d = abs(price - raw_pt3)
        if d <= tol:
            subs.append((d, 0, abs(price - entry), price, name))
    for px in _psych_candidates(raw_pt3, psych_step):
        d = abs(px - raw_pt3)
        if d <= tol:
            subs.append((d, 1, abs(px - entry), px, "$%s whole number" % (
                ("%.2f" % px).rstrip("0").rstrip("."))))
    if subs:
        subs.sort(key=lambda x: (x[0], x[1], x[2]))
        _, _, _, pt3_price, pt3_name = subs[0]
    else:
        pt3_price, pt3_name = raw_pt3, "2R"
    candidates.append(_Candidate("PT3", pt3_price, pt3_name))

    # ---- PT4: the runner ------------------------------------------------
    rmult_price = entry + sign * pt4_r * risk
    rmult_name = "%sR runner" % (("%.1f" % pt4_r).rstrip("0").rstrip("."))
    structure = _nearest_named_beyond(pt3_price, named_levels, long)
    if pt4_mode == "rmult":
        pt4_price, pt4_name = rmult_price, rmult_name
    elif pt4_mode == "structure":
        pt4_price, pt4_name = (structure[1], structure[0]) if structure else (rmult_price, rmult_name)
    elif pt4_mode == "max":
        if structure is not None and R(structure[1]) > R(rmult_price):
            pt4_price, pt4_name = structure[1], structure[0]
        else:
            pt4_price, pt4_name = rmult_price, rmult_name
    else:
        raise ValueError("pt4_mode must be one of 'max'/'rmult'/'structure', got %r" % (pt4_mode,))
    candidates.append(_Candidate("PT4", pt4_price, pt4_name))

    # ---- assemble: drop non-positive R, sort ascending, coalesce -------
    live = [c for c in candidates if R(c.price) > 0]
    live.sort(key=lambda c: R(c.price))
    survivors: List[_Candidate] = []
    last_r = None
    for c in live:
        r = R(c.price)
        if last_r is None or r - last_r >= min_gap_r:
            survivors.append(c)
            last_r = r
        # else: a near-duplicate of the last KEPT (nearer) rung -- dropped.

    assert survivors, (
        "build_rungs produced zero rungs (entry=%r stop=%r direction=%r); "
        "PT3 is always >= min_gap_r beyond entry for a sane min_gap_r -- "
        "this should be unreachable" % (entry, stop, direction))

    k = len(survivors)
    base = list(weights[:k])
    total = sum(base) or 1.0
    renorm = [w / total for w in base]

    return [Rung(price=c.price, weight=renorm[j], name=c.name)
           for j, c in enumerate(survivors)]
