"""VENDORED from PR #40 (branch omen-v3-eye2-candidates, v3-eye2-candidates/candidates.py), unchanged below this docstring.
Used only for detect_candidates() on real NQ bars (every OR5 break+retest+trigger event, not just the first)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from dataclasses import dataclass, asdict

import numpy as np

# v2-s07-data (omen_data.py) and its underlying CSVs under t01-orb5/fut are
# restored-but-untracked research data on the main tradingbot checkout (see
# RECOVERY.md 2026-09-26) -- they are not in git history, so a worktree does
# not get a copy. Read-only imports point at the main checkout's absolute
# path, same convention orb1m.py and every v2/v3 script already uses; this
# worktree never writes there.
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s07-data")

TICK = 0.25
OR_MINUTES = 5          # OR5 per a4-mantra
WINDOW_END_MIN = 90     # 09:30 + 90 = 11:00, task window end
S_CUTOFF_MIN = 60       # 09:30 + 60 = 10:30, mantra's S entry/flat cutoff
RETEST_MAX_BARS = 30
DISP_K = 1.0            # displacement >= 1.0 ATR
RETEST_SHALLOW_ATR = 0.35  # a4 "shallow retest <=0.35 ATR" (S-quality signal, not the base gate)


def pin(o, h, l, c, side):
    rng = h - l
    if rng <= 0:
        return False
    body = abs(c - o)
    if side > 0:
        wick = min(o, c) - l
        return wick >= 2 * body and wick >= 0.5 * rng and (c - l) >= 0.66 * rng
    wick = h - max(o, c)
    return wick >= 2 * body and wick >= 0.5 * rng and (h - c) >= 0.66 * rng


def strong_bar(o, h, l, c, side):
    if pin(o, h, l, c, side):
        return True
    rng = h - l
    if rng <= 0:
        return False
    body = (c - o) * side
    ext = (c - l) if side > 0 else (h - c)
    return body >= 0.6 * rng and ext >= 0.75 * rng


def ema(values, span):
    """Simple EMA over a 1-D array that may contain leading/interior NaNs."""
    out = np.full(len(values), np.nan)
    alpha = 2.0 / (span + 1)
    prev = None
    for i, v in enumerate(values):
        if np.isnan(v):
            continue
        prev = v if prev is None else alpha * v + (1 - alpha) * prev
        out[i] = prev
    return out


def day_arrays(g):
    """g: a per-date DataFrame from omen_data.load_fut, ts already restricted to the session."""
    m = ((g["ts"].dt.hour * 60 + g["ts"].dt.minute) - 570).to_numpy()
    full = np.full(WINDOW_END_MIN + 1, np.nan)
    arr = {}
    for k in ("open", "high", "low", "close"):
        a = full.copy()
        ok = (m >= 0) & (m <= WINDOW_END_MIN)
        a[m[ok]] = g[k].to_numpy()[ok]
        arr[k] = a
    return arr


@dataclass
class Candidate:
    time: str
    instrument: str
    direction: str
    level: float
    entry: float
    stop: float
    target_1r: float
    target_2r: float
    features: dict
    grade_hint: str
    missing: list


def _fmt_time(date, minute_after_930):
    hh = 9 + (30 + minute_after_930) // 60
    mm = (30 + minute_after_930) % 60
    return f"{date}T{hh:02d}:{mm:02d}:00-04:00"


def detect_candidates(A, date, instrument="MNQ", window_end=WINDOW_END_MIN,
                       s_cutoff=S_CUTOFF_MIN, orn=OR_MINUTES, disp_k=DISP_K):
    """Scan one session's minute arrays for every break+retest+trigger event.

    Mirrors orb1m.signal()'s state machine but does not stop at the first
    valid setup, and does not require the trigger to be pin/strong to emit a
    candidate -- weak-trigger retests are logged as `missing` >=1 (one-off)
    so they can still be tapped by Austin.
    """
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    close9 = ema(C, 9)
    close20 = ema(C, 20)
    out = []
    if np.isnan(H[:orn]).all():
        return out
    orh, orl = np.nanmax(H[:orn]), np.nanmin(L[:orn])
    rngs = H - L
    state = None  # [side, level, break_idx, maxexc, displaced]
    first_signal_emitted = False

    def new_break(j):
        if C[j] > orh:
            return [1, orh, j, H[j] - orh, False]
        if C[j] < orl:
            return [-1, orl, j, orl - L[j], False]
        return None

    for j in range(orn, window_end):
        if np.isnan(C[j]):
            continue
        prev = rngs[max(0, j - 14):j]
        atr = np.nanmean(prev) if np.sum(~np.isnan(prev)) >= 3 else np.nan

        if state is None:
            state = new_break(j)
            if state:
                state[4] = disp_k == 0 or state[3] >= disp_k * atr
            continue

        side, lvl, bi, exc, disp = state
        close_through = (C[j] - lvl) * side <= 0
        if close_through:
            # void; may re-arm on this same bar
            state = new_break(j)
            if state:
                state[4] = disp_k == 0 or state[3] >= disp_k * atr
            continue

        touched = (L[j] <= lvl + TICK) if side > 0 else (H[j] >= lvl - TICK)
        if touched and disp and j > bi and j + 1 <= window_end and not np.isnan(O[j + 1]):
            trig_pin = pin(O[j], H[j], L[j], C[j], side)
            trig_strong = strong_bar(O[j], H[j], L[j], C[j], side)
            has_trigger = trig_pin or trig_strong
            entry = O[j + 1] + TICK * side
            stop = (L[j] - TICK) if side > 0 else (H[j] + TICK)
            dist = (entry - stop) * side
            if dist >= 2 * TICK:
                minutes_after_open = j
                in_s_window = minutes_after_open <= s_cutoff
                retest_depth_atr = (abs(C[j] - lvl) / atr) if (atr and not np.isnan(atr) and atr > 0) else None
                disp_atr = (exc / atr) if (atr and not np.isnan(atr) and atr > 0) else None
                gap_dir = bool((O[orn] - C[0]) * side > 0) if not np.isnan(O[orn]) and not np.isnan(C[0]) else None
                t9, t20 = close9[j], close20[j]
                ocr_trend_tag = bool(not np.isnan(t9) and not np.isnan(t20) and (t9 - t20) * side > 0)

                missing = []
                if not has_trigger:
                    missing.append("trigger")
                if disp_atr is None or disp_atr < 1.0:
                    missing.append("displacement>=1.0ATR")
                if not in_s_window:
                    missing.append("inside_10:30_window")
                if first_signal_emitted:
                    missing.append("first_signal_of_day")
                # NOTE: a4-mantra's S-grade gate is {level, break, disp, retest/no-close-through,
                # strong trigger, inside window, first signal}. Shallow retest (<=0.35 ATR) is a
                # correlate his eye adds (ship-plan v3 s5), not part of the mechanical gate -- kept
                # here as a feature only, not scored into `missing`.
                shallow = retest_depth_atr is not None and retest_depth_atr <= RETEST_SHALLOW_ATR

                if len(missing) == 0:
                    grade_hint = "S"
                elif len(missing) == 1:
                    grade_hint = "one-off"
                elif len(missing) == 2:
                    grade_hint = "two-off"
                else:
                    grade_hint = "candidate"

                cand = Candidate(
                    time=_fmt_time(date, j),
                    instrument=instrument,
                    direction="long" if side > 0 else "short",
                    level=round(float(lvl), 2),
                    entry=round(float(entry), 2),
                    stop=round(float(stop), 2),
                    target_1r=round(float(entry + side * dist), 2),
                    target_2r=round(float(entry + side * 2 * dist), 2),
                    features=dict(
                        atr=round(float(atr), 4) if atr is not None and not np.isnan(atr) else None,
                        displacement_atr=round(float(disp_atr), 3) if disp_atr is not None else None,
                        bars_to_break=int(bi - orn),
                        retest_bars_after_break=int(j - bi),
                        retest_depth_atr=round(float(retest_depth_atr), 3) if retest_depth_atr is not None else None,
                        shallow_retest=bool(shallow),
                        trigger_pin=bool(trig_pin),
                        trigger_strong=bool(trig_strong),
                        gap_in_direction=gap_dir,
                        ocr_trend_tag=ocr_trend_tag,
                        minutes_after_open=int(minutes_after_open),
                        inside_s_window=bool(in_s_window),
                        first_signal_of_day=not first_signal_emitted,
                        or_high=round(float(orh), 2),
                        or_low=round(float(orl), 2),
                        stop_dist_pts=round(float(dist), 2),
                    ),
                    grade_hint=grade_hint,
                    missing=missing,
                )
                out.append(cand)
                first_signal_emitted = True
            # re-arm after logging: keep tracking same break for further retests up to 30 bars
        exc = max(exc, (H[j] - lvl) if side > 0 else (lvl - L[j]))
        state[3] = exc
        if not disp and not np.isnan(atr) and exc >= disp_k * atr:
            state[4] = True
        if j - bi > RETEST_MAX_BARS:
            state = None
    return out


def run(instrument="MNQ", n_sessions=20, out_path=None):
    from omen_data import load_fut  # noqa: E402  (path inserted above)

    df = load_fut(instrument, "09:30", "11:01")
    sessions = sorted(df["date"].unique())
    # Mon-Thu only (weekday 0-3); OMEN mantra excludes Friday
    sessions = [d for d in sessions if d.weekday() <= 3]
    take = sessions[-n_sessions:]
    all_cands = []
    for d in take:
        g = df[df["date"] == d]
        A = day_arrays(g)
        all_cands.extend(detect_candidates(A, str(d), instrument))
    payload = [asdict(c) for c in all_cands]
    if out_path:
        Path(out_path).write_text(json.dumps(payload, indent=1))
    return payload, take


if __name__ == "__main__":
    inst = sys.argv[1] if len(sys.argv) > 1 else "MNQ"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    out = sys.argv[3] if len(sys.argv) > 3 else "candidates_out.json"
    cands, sessions_used = run(inst, n, out)
    s_count = sum(1 for c in cands if c["grade_hint"] == "S")
    print(f"{inst}: {len(sessions_used)} sessions ({sessions_used[0]}..{sessions_used[-1]}), "
          f"{len(cands)} candidates, {s_count} grade_hint=S -> {out}")
