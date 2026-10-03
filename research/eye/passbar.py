"""Pass bar for the blind eye test, as a pure function.

Encodes life-plan 07-money/omen/v3/blind-test-prereg.md (sha256 5b449c6e...b340, locked
2026-09-27, bar does not move once taps start). Nothing here reads files, bars or the frozen
engine: it takes a scored tap ledger (label + R per tap, R from the frozen orb1m.py next-open
fill, produced by eye_blind.core.scored_rows) and returns the verdict.

Prereg numbers, verbatim:
  metric     mean R per tap, S taps vs Not-S taps
  min sample n_S >= 30 (all Not-S taps used, no cap)
  test       two-sided permutation of the tap label on the S-vs-Not-S mean-R gap,
             10,000 shuffles, p < .05
  PASS       n_S >= 30 and mean R(S) >= +0.25 and p < .05
  FAIL       n_S >= 30 reached and (mean R(S) < +0.25 or p >= .05)
  INCONCLUSIVE   < 30 S taps after 60 blind sessions (Austin decides extend-or-kill; not a pass)
  PENDING    otherwise (fewer than 30 S taps, fewer than 60 sessions)
Addendum 2026-10-03 (implementation, no new threshold): the verdict freezes at the 30th S tap,
or at the 60th session while n_S < 30; later rows are ignored and only counted (n_post_lock).

Same permutation procedure and seed as eye_blind.core._evaluate, so the two agree to the digit.
Paper research only.
"""
from __future__ import annotations

import numpy as np

MIN_S_TAPS = 30
PASS_MEAN_R = 0.25
ALPHA = 0.05
N_SHUFFLES = 10_000
MAX_SESSIONS = 60
SEED = 7


def perm_p(r, is_s, n_shuffles: int = N_SHUFFLES, seed: int = SEED):
    """Two-sided permutation p on the S-vs-Not-S mean-R gap; None if either arm is empty."""
    r, is_s = np.asarray(r, float), np.asarray(is_s, bool)
    if not is_s.any() or is_s.all():
        return None
    gap = r[is_s].mean() - r[~is_s].mean()
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(n_shuffles):
        p = rng.permutation(is_s)
        hits += abs(r[p].mean() - r[~p].mean()) >= abs(gap) - 1e-12
    return float((hits + 1) / (n_shuffles + 1))


def lock_point(labels):
    """Rows used for the verdict: through the 30th S tap, else through the 60th session.
    Returns (n_rows, kind) with kind in S30 / SESSIONS60, or (None, None) while running."""
    n_s = 0
    for k, lab in enumerate(labels):
        n_s += lab == "S"
        if n_s >= MIN_S_TAPS:
            return k + 1, "S30"
        if k + 1 >= MAX_SESSIONS:
            return k + 1, "SESSIONS60"
    return None, None


def passbar(rows, n_shuffles: int = N_SHUFFLES, seed: int = SEED) -> dict:
    """rows: tap-ordered dicts {"label": "S" | "notS", "R": float}. Returns the verdict dict."""
    rows = list(rows)
    for x in rows:
        if x["label"] not in ("S", "notS"):
            raise ValueError(f"label must be S or notS, got {x['label']!r}")
    labels = [x["label"] for x in rows]
    k, kind = lock_point(labels)
    used = rows if k is None else rows[:k]
    r = np.array([x["R"] for x in used], float)
    is_s = np.array([x["label"] == "S" for x in used], bool)
    n_s, n_n = int(is_s.sum()), int((~is_s).sum())
    out = dict(verdict="PENDING", n_S=n_s, n_notS=n_n, n_post_lock=len(rows) - len(used),
               mean_R_S=float(r[is_s].mean()) if n_s else None,
               mean_R_notS=float(r[~is_s].mean()) if n_n else None, p_perm=None)
    if kind == "S30":
        out["p_perm"] = perm_p(r, is_s, n_shuffles, seed)
        ok = out["mean_R_S"] >= PASS_MEAN_R - 1e-12 and out["p_perm"] is not None and out["p_perm"] < ALPHA
        out["verdict"] = "PASS" if ok else "FAIL"
    elif kind == "SESSIONS60":
        out["verdict"] = "INCONCLUSIVE"
    return out
