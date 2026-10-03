"""Blind-test core: pool loader, blind renderer, tap log, scorer.

Pre-reg (v3/blind-test-prereg.md, locked): metric = mean R per tap, next-open fill, frozen
research/agent_runs/rule-backtests-2/orb1m.py costs; S taps vs Not-S taps; n >= 30 S taps;
two-sided permutation of the tap label, 10,000 shuffles; PASS = S mean >= +0.25R and p < .05;
FAIL = n >= 30 S taps and not PASS; < 30 S taps after 60 blind sessions = INCONCLUSIVE.

Blindness: the viewer sees bars up to and including the decision bar, prices rebased to
percent-from-session-open, time-of-day only, no date, no absolute price, opaque session id.
Window A (>= 2019-09-26) and the 2024-09 fit window can never enter the pool: build_pool
refuses any bar dated outside window B unless window=None is passed (synthetic tests only).
"""
from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import random
import secrets
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
ORB1M_PATH = REPO / "research" / "agent_runs" / "rule-backtests-2" / "orb1m.py"
ET = "America/New_York"
WINDOW_B = ("2010-06-07", "2019-09-25")
MIN_POOL = 60
MIN_S_TAPS = 30
PASS_MEAN_R = 0.25
ALPHA = 0.05
N_SHUFFLES = 10_000
SPEC = {"MNQ": dict(usd_pt=2.0, rt_comm=1.24), "MES": dict(usd_pt=5.0, rt_comm=1.24)}
DEFAULT_CFG = dict(sym="MNQ", orn=5, cut="11:00", disp_k=1.0, trig="strong")


class WindowViolation(ValueError):
    """Bars outside window B were offered to the blind pool."""


# ---------------------------------------------------------------- frozen engine
_orb = None


def load_orb1m():
    """Import the frozen orb1m.py without its hard-coded omen_data dependency (not in git)."""
    global _orb
    if _orb is not None:
        return _orb
    if "omen_data" not in sys.modules:
        stub = types.ModuleType("omen_data")
        stub.SPEC = SPEC

        def _no_load(*a, **k):
            raise RuntimeError("stub: load bars via eye_blind")

        stub.load_fut = _no_load
        sys.modules["omen_data"] = stub
    spec = importlib.util.spec_from_file_location("orb1m_frozen", ORB1M_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _orb = mod
    return mod


def orb1m_sha256() -> str:
    return hashlib.sha256(ORB1M_PATH.read_bytes()).hexdigest()


# --------------------------------------------------------------------- loading
def load_bars_csv(path) -> pd.DataFrame:
    """CSV with open/high/low/close and either ts_ns (UTC ns, Massive format) or ts."""
    d = pd.read_csv(path)
    if "ts_ns" in d:
        d["ts"] = pd.to_datetime(d["ts_ns"], unit="ns", utc=True).dt.tz_convert(ET)
    else:
        d["ts"] = pd.to_datetime(d["ts"], utc=True).dt.tz_convert(ET)
    return d[["ts", "open", "high", "low", "close"]].sort_values("ts").reset_index(drop=True)


def _sid(salt: str, date: str) -> str:
    return hmac.new(salt.encode(), date.encode(), hashlib.sha256).hexdigest()[:10]


def build_pool(bars: pd.DataFrame, cfg: dict | None = None, window=WINDOW_B,
               seed: int | None = None, salt: str | None = None) -> dict:
    """Sessions (one per date) where the frozen orb1m signal fires; shuffled fixed order.
    bars: tz-aware ET `ts`, open/high/low/close, front-month RTH 1-min, one contract per session."""
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    o = load_orb1m()
    df = bars.copy()
    df["date"] = df["ts"].dt.strftime("%Y-%m-%d")
    if window is not None:
        bad = sorted(d for d in df["date"].unique() if not (window[0] <= d <= window[1]))
        if bad:
            raise WindowViolation(f"{len(bad)} dates outside window B {window}: first {bad[0]}, last {bad[-1]}")
    salt = salt or secrets.token_hex(8)
    cut = o.CUTS[cfg["cut"]]
    sessions = {}
    for date, g in df.groupby("date"):
        A = o.day_arrays(g)
        s = o.signal(A, cfg["orn"], cut, cfg["disp_k"], cfg["trig"])
        if not s:
            continue
        i, side, stop = s
        dist = (A["open"][i] + o.TICK * side - stop) * side
        if dist < 2 * o.TICK:  # same skip as the frozen grid
            continue
        sessions[_sid(salt, date)] = dict(
            date=date, side=int(side), i=int(i),
            A={k: [None if x != x else float(x) for x in v] for k, v in A.items()})
    order = sorted(sessions)
    random.Random(seed if seed is not None else secrets.randbits(32)).shuffle(order)
    return dict(version=1, window=list(window) if window else None, cfg=cfg, salt=salt,
                orb1m_sha256=orb1m_sha256(),
                built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ready=len(sessions) >= MIN_POOL, order=order, sessions=sessions)


def save_pool(pool: dict, path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(pool), encoding="utf-8")


def load_pool(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _arrays(sess):
    return {k: np.array([np.nan if x is None else x for x in v], float) for k, v in sess["A"].items()}


def _stop(A, i, side):
    """Frozen signal(): stop = decision-bar low/high -/+ 1 tick."""
    return (A["low"][i - 1] - 0.25) if side > 0 else (A["high"][i - 1] + 0.25)


# ------------------------------------------------------------------- rendering
def render_svg(sess: dict, cfg: dict) -> str:
    """Bars 0..i-1 (the decision bar is the last one). Percent-from-open axis, HH:MM only."""
    A = _arrays(sess)
    i, side, orn = sess["i"], sess["side"], cfg["orn"]
    idx = [k for k in range(i) if not np.isnan(A["open"][k])]
    base = A["open"][idx[0]]

    def pct(p):
        return (p / base - 1) * 100

    orh, orl = np.nanmax(A["high"][:orn]), np.nanmin(A["low"][:orn])
    level = orh if side > 0 else orl
    stop = _stop(A, i, side)
    vals = [pct(v) for k in idx for v in (A["high"][k], A["low"][k])] + [pct(level), pct(stop)]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.06 or 0.01
    lo, hi = lo - pad, hi + pad
    W, H, L, R, T, B = 360, 280, 46, 6, 8, 22

    def X(k):
        return L + (k + 0.5) * (W - L - R) / max(i, 1)

    def Y(v):
        return T + (hi - v) / (hi - lo) * (H - T - B)

    bw = max(1.0, (W - L - R) / max(i, 1) * 0.6)
    out = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="session chart">']
    for t in np.linspace(lo + pad, hi - pad, 5):
        out.append(f'<line class="g" x1="{L}" x2="{W-R}" y1="{Y(t):.1f}" y2="{Y(t):.1f}"/>'
                   f'<text class="t" x="{L-4}" y="{Y(t)+3:.1f}" text-anchor="end">{t:+.2f}%</text>')
    out.append(f'<rect class="or" x="{X(0)-bw/2:.1f}" y="{Y(pct(orh)):.1f}" '
               f'width="{X(min(orn, i)-1)-X(0)+bw:.1f}" height="{max(Y(pct(orl))-Y(pct(orh)), 1):.1f}"/>')
    for k in idx:
        o_, h_, l_, c_ = (pct(A[n][k]) for n in ("open", "high", "low", "close"))
        cls = "up" if c_ >= o_ else "dn"
        if k == i - 1:
            cls += " dec"
        out.append(f'<line class="{cls}" x1="{X(k):.1f}" x2="{X(k):.1f}" y1="{Y(h_):.1f}" y2="{Y(l_):.1f}"/>'
                   f'<rect class="{cls}" x="{X(k)-bw/2:.1f}" y="{Y(max(o_, c_)):.1f}" width="{bw:.1f}" '
                   f'height="{max(abs(Y(o_)-Y(c_)), 0.8):.1f}"/>')
    out.append(f'<line class="lv" x1="{L}" x2="{W-R}" y1="{Y(pct(level)):.1f}" y2="{Y(pct(level)):.1f}"/>'
               f'<line class="sl" x1="{L}" x2="{W-R}" y1="{Y(pct(stop)):.1f}" y2="{Y(pct(stop)):.1f}"/>')
    step = max(1, i // 6)
    for k in range(0, i, step):
        mm = 570 + k
        out.append(f'<text class="t" x="{X(k):.1f}" y="{H-6}" text-anchor="middle">{mm//60:02d}:{mm%60:02d}</text>')
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------------------ taps
def read_taps(path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def next_session(pool: dict, taps: list[dict]):
    done = {t["session_id"] for t in taps}
    return next((s for s in pool["order"] if s not in done), None)


def append_tap(path, pool: dict, session_id: str, label: str) -> dict:
    """Enforces fixed order (no skipping/cherry-picking) and one tap per session."""
    if label not in ("S", "notS"):
        raise ValueError("label must be S or notS")
    taps = read_taps(path)
    if session_id not in pool["sessions"]:
        raise KeyError("unknown session")
    if session_id in {t["session_id"] for t in taps}:
        raise FileExistsError("already tapped")
    if session_id != next_session(pool, taps):
        raise PermissionError("not the current session")
    row = dict(session_id=session_id, label=label, mode="PAPER", n_before=len(taps),
               tapped_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return row


# --------------------------------------------------------------------- scoring
def trade_r(sess: dict, cfg: dict) -> float:
    """R of the frozen orb1m trade (next-open +1 tick, stop wins same bar, $1.24 RT)."""
    o = load_orb1m()
    A, i, side = _arrays(sess), sess["i"], sess["side"]
    dist = (A["open"][i] + o.TICK * side - _stop(A, i, side)) * side
    spec = SPEC[cfg["sym"]]
    return float(o.run_trade(A, i, side, dist, o.CUTS[cfg["cut"]], spec["usd_pt"], spec["rt_comm"])[0])


def _stats(rs, dates):
    r = np.array(rs, float)
    if not len(r):
        return dict(n=0)
    order = np.argsort(dates, kind="stable")
    h = len(r) // 2
    top = np.sort(r)[::-1][:5]
    pos = r[r > 0].sum()
    return dict(n=int(len(r)), mean_R=float(r.mean()), win_pct=float((r > 0).mean() * 100),
                half1_R=float(r[order][:h].mean()) if h else None,
                half2_R=float(r[order][h:].mean()),
                top5_share=float(top[top > 0].sum() / pos) if pos > 0 else None)


def score(pool: dict, taps: list[dict], n_shuffles: int = N_SHUFFLES, seed: int = 7) -> dict:
    cfg = pool["cfg"]
    rows = [(t["label"], trade_r(pool["sessions"][t["session_id"]], cfg), pool["sessions"][t["session_id"]]["date"])
            for t in taps if t["session_id"] in pool["sessions"]]
    lab = np.array([r[0] == "S" for r in rows], bool)
    R = np.array([r[1] for r in rows], float)
    D = np.array([r[2] for r in rows])
    res = dict(n_taps=len(rows), S=_stats(R[lab], D[lab]), notS=_stats(R[~lab], D[~lab]),
               orb1m_sha256=pool["orb1m_sha256"], p_perm=None, gap=None)
    if lab.any() and (~lab).any():
        gap = R[lab].mean() - R[~lab].mean()
        rng = np.random.default_rng(seed)
        hits = 0
        for _ in range(n_shuffles):
            p = rng.permutation(lab)
            hits += abs(R[p].mean() - R[~p].mean()) >= abs(gap) - 1e-12
        res.update(gap=float(gap), p_perm=float((hits + 1) / (n_shuffles + 1)))
    if res["S"]["n"] >= MIN_S_TAPS:
        ok = res["S"]["mean_R"] >= PASS_MEAN_R and res["p_perm"] is not None and res["p_perm"] < ALPHA
        res["verdict"] = "PASS" if ok else "FAIL"
    elif len(rows) >= 60:
        res["verdict"] = "INCONCLUSIVE"
    else:
        res["verdict"] = "IN_PROGRESS"
    return res
