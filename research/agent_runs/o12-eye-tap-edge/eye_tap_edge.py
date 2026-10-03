"""O12: does Austin's eye have edge in real time?

Reads every S / Not-S tap the live eye loop recorded (eye_card/labels.csv, written by the
label server on :9135) plus the runner log (which cards were sent, when), and scores each
tapped candidate with the FROZEN orb1m.py fill, from the decision bar forward:
    entry = next bar's open + 1 tick against the trader, stop wins a same-bar tie,
    fixed 2R limit (1 tick through), flat at the cutoff bar's open, $1.24 RT per micro.
Both S and Not-S taps are scored on the same fill (the tap is the label, the fill is the
outcome), so S-vs-Not-S is "did the cards he called S do better than the cards he passed on".

Honesty rules (all enforced + tested):
  * taps from this machine (127.0.0.1 / ::1) are agent test taps -> excluded from the stats;
  * a candidate is scored once (first real tap); later taps on it are "repeat" and listed only;
  * a tap is `blind` only if it is the first exposure of that candidate AND the session date is
    outside the window he may have watched live (>= 2024-09-26); otherwise `remembered` or `repeat`;
  * reserved window A (NQ 2019-09-26..2024-09-25) is never loaded or scored;
  * permutation p is DAY-level: label blocks are swapped between days, never between trades
    on the same day (they share one market);
  * no network, no orders, no writes except what the caller asks for.

Usage:
    python eye_tap_edge.py --labels C:\\...\\eye_card\\labels.csv --log C:\\...\\logs\\eye_loop_replay.log
Bars come from omen_data.load_fut (not in git); pass --omen-data DIR or set OMEN_DATA_DIR.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import types
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ORB1M_PATH = REPO / "research" / "agent_runs" / "rule-backtests-2" / "orb1m.py"
ET = ZoneInfo("America/New_York")

WINDOW_A = ("2019-09-26", "2024-09-25")          # reserved, never scored
LIVE_WATCH_FROM = "2024-09-26"                    # E5 prereg: dates he may have watched live
LOOPBACK = ("127.", "::1")
CUT_LOOP = 60       # 10:30 ET: the cutoff eye_paper.DEFAULT_CUTOFF_MINUTE the live loop journals with
CUT_PREREG = 90     # 11:00 ET: the frozen orb1m cell used by the blind-test prereg
SPEC = {"MNQ": dict(usd_pt=2.0, rt_comm=1.24), "MES": dict(usd_pt=5.0, rt_comm=1.24)}
TICK = 0.25
N_PERM = 10_000

_CID = re.compile(r"^([A-Za-z])(\d{1,3})-(\d+)-(\d{8})$")
_SENT = re.compile(r"^\[(?P<ts>[^\]]+)\]\s+sent\s+(?P<cid>\S+)")


# ----------------------------------------------------------------------------- frozen engine
_orb = None


def load_orb1m():
    """Import the tracked, frozen orb1m.py without its untracked omen_data dependency."""
    global _orb
    if _orb is not None:
        return _orb
    if "omen_data" not in sys.modules:
        stub = types.ModuleType("omen_data")
        stub.SPEC = SPEC

        def _no_load(*a, **k):
            raise RuntimeError("stub: bars are supplied by eye_tap_edge")

        stub.load_fut = _no_load
        sys.modules["omen_data"] = stub
    spec = importlib.util.spec_from_file_location("orb1m_frozen_o12", ORB1M_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _orb = mod
    return mod


def orb1m_sha256() -> str:
    return hashlib.sha256(ORB1M_PATH.read_bytes()).hexdigest()


def score_fill(A, signal_minute: int, side: int, stop: float, cut: int = CUT_LOOP, sym: str = "MNQ"):
    """R of the frozen orb1m trade entered at the bar AFTER the decision bar.
    Returns None if there is no entry bar or the stop is degenerate (< 2 ticks)."""
    o = load_orb1m()
    i = int(signal_minute) + 1
    if i >= len(A["open"]) or np.isnan(A["open"][i]):
        return None
    entry = A["open"][i] + o.TICK * side
    dist = (entry - stop) * side
    if dist < 2 * o.TICK:
        return None
    spec = SPEC[sym]
    return float(o.run_trade(A, i, side, dist, cut, spec["usd_pt"], spec["rt_comm"])[0])


# ----------------------------------------------------------------------------- inputs
def parse_candidate_id(cid: str):
    """'S43-1-20260907' -> dict(grade='S', minute=43, seq=1, date='2026-09-07'), else None."""
    m = _CID.match(cid or "")
    if not m:
        return None
    d = m.group(4)
    return dict(grade=m.group(1).upper(), minute=int(m.group(2)), seq=int(m.group(3)),
                date=f"{d[:4]}-{d[4:6]}-{d[6:]}")


def _ts(s: str) -> datetime:
    t = datetime.fromisoformat(s)
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def read_taps(labels_csv) -> list[dict]:
    """Every row of the label server's CSV, label normalised to 'S' / 'notS', oldest first."""
    import csv
    p = Path(labels_csv)
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as fh:
        rows = [dict(candidate_id=r["candidate_id"], label="S" if r["label"] == "S" else "notS",
                     logged_at=_ts(r["logged_at"]), source_ip=r.get("source_ip", ""),
                     mode=r.get("mode", ""))
                for r in csv.DictReader(fh)]
    return sorted(rows, key=lambda r: r["logged_at"])


def read_sent_log(*log_paths) -> dict[str, list[datetime]]:
    """{candidate_id: [send times]} from runner log lines '[iso-ts] sent <cid> ...'."""
    out: dict[str, list[datetime]] = defaultdict(list)
    for lp in log_paths:
        p = Path(lp)
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _SENT.match(line)
            if m:
                out[m["cid"]].append(_ts(m["ts"]))
    for v in out.values():
        v.sort()
    return dict(out)


# ----------------------------------------------------------------------------- classification
def in_window_a(date: str) -> bool:
    return WINDOW_A[0] <= date <= WINDOW_A[1]


def classify_taps(taps: list[dict], sent: dict[str, list[datetime]]) -> list[dict]:
    """Adds `kind` to each tap:
       test      source is this machine (agent curl test), never a real tap
       repeat    candidate was already tapped, or its card had already been sent before (replay)
       remembered first exposure, but the date is inside the window he may have watched live
       blind     first exposure of a session dated before that window
    and `n_sends_before` / `n_taps_before` for the audit trail."""
    seen: dict[str, int] = defaultdict(int)
    out = []
    for t in taps:
        cid = t["candidate_id"]
        info = parse_candidate_id(cid)
        n_sends = sum(1 for s in sent.get(cid, []) if s <= t["logged_at"])
        n_prior = seen[cid]
        if t["source_ip"].startswith(LOOPBACK):
            kind = "test"
        else:
            if n_prior >= 1 or n_sends >= 2:
                kind = "repeat"
            elif info and info["date"] >= LIVE_WATCH_FROM:
                kind = "remembered"
            else:
                kind = "blind"
        if not t["source_ip"].startswith(LOOPBACK):
            seen[cid] += 1
        out.append(dict(t, kind=kind, n_sends_before=n_sends, n_taps_before=n_prior,
                        card_in_runner_log=cid in sent, info=info))
    return out


# ----------------------------------------------------------------------------- candidate lookup
def find_candidate(A, info: dict, instrument: str = "MNQ"):
    """Rebuild the card's candidate from the bars: same grade letter, same signal minute.
    Needs v3-eye2-candidates on sys.path."""
    import candidates as eye2
    hits = [c for c in eye2.detect_candidates(A, info["date"], instrument)
            if c.grade_hint[0].upper() == info["grade"] and c.features["minutes_after_open"] == info["minute"]]
    return hits[0] if hits else None


# ----------------------------------------------------------------------------- statistics
def _stats(rs) -> dict:
    r = np.asarray(rs, float)
    if not len(r):
        return dict(n=0, mean_R=None, win_pct=None)
    return dict(n=int(len(r)), mean_R=round(float(r.mean()), 4), win_pct=round(float((r > 0).mean() * 100), 1))


def day_permutation_p(rows: list[dict], n_perm: int = N_PERM, seed: int = 7):
    """Two-sided day-level permutation p for mean R(S) - mean R(Not-S).
    A day is one exchangeable block: its tuple of labels moves as a unit. Blocks are only
    swapped between days with the same number of candidates (so the S count stays honest)."""
    by_day: dict[str, list[tuple[bool, float]]] = defaultdict(list)
    for r in rows:
        by_day[r["date"]].append((r["label"] == "S", float(r["R"])))
    labs_all = [l for v in by_day.values() for l, _ in v]
    if not any(labs_all) or all(labs_all):
        return None, None
    # Only days with >= 2 distinct candidates keep a label pattern; group days by size.
    days = sorted(by_day)
    sizes = defaultdict(list)
    for d in days:
        sizes[len(by_day[d])].append(d)
    rs = {d: np.array([x[1] for x in by_day[d]]) for d in days}
    lab = {d: np.array([x[0] for x in by_day[d]]) for d in days}

    def gap(label_of):
        s = [rs[d][label_of[d]] for d in days]
        n = [rs[d][~label_of[d]] for d in days]
        s, n = np.concatenate(s), np.concatenate(n)
        if not len(s) or not len(n):
            return 0.0
        return s.mean() - n.mean()

    obs = gap(lab)
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(n_perm):
        shuffled = {}
        for _, ds in sizes.items():
            order = rng.permutation(len(ds))
            for k, d in enumerate(ds):
                shuffled[d] = lab[ds[order[k]]]
        hits += abs(gap(shuffled)) >= abs(obs) - 1e-12
    return float(obs), float((hits + 1) / (n_perm + 1))


def iso_week(ts: datetime) -> str:
    y, w, _ = ts.astimezone(ET).isocalendar()
    return f"{y}-W{w:02d}"


def summarize(rows: list[dict], n_perm: int = N_PERM, seed: int = 7) -> dict:
    """rows: dicts with label ('S'/'notS'), R, date, week."""
    S = [r["R"] for r in rows if r["label"] == "S"]
    N = [r["R"] for r in rows if r["label"] != "S"]
    gap, p = day_permutation_p(rows, n_perm, seed) if rows else (None, None)
    weeks = {}
    for wk in sorted({r["week"] for r in rows}):
        w = [r for r in rows if r["week"] == wk]
        weeks[wk] = dict(S=_stats([r["R"] for r in w if r["label"] == "S"]),
                         notS=_stats([r["R"] for r in w if r["label"] != "S"]))
    return dict(n=len(rows), n_days=len({r["date"] for r in rows}), S=_stats(S), notS=_stats(N),
                gap_R=None if gap is None else round(gap, 4), p_perm_day=p, by_week=weeks)


# ----------------------------------------------------------------------------- driver
def analyse(labels_csv, log_paths, bars_for, instrument: str = "MNQ", cut: int = CUT_LOOP,
            n_perm: int = N_PERM, finder=None) -> dict:
    """bars_for(date) -> day_arrays dict (91 minutes from 09:30) or None. Never called for window A."""
    finder = finder or find_candidate
    taps = classify_taps(read_taps(labels_csv), read_sent_log(*log_paths))
    detail, scored, first_seen = [], [], set()
    for t in taps:
        row = dict(candidate_id=t["candidate_id"], label=t["label"], tap_at_et=t["logged_at"].astimezone(ET).isoformat(timespec="seconds"),
                   source_ip=t["source_ip"], kind=t["kind"], n_sends_before=t["n_sends_before"],
                   card_in_runner_log=t["card_in_runner_log"], status="", R=None, week=iso_week(t["logged_at"]))
        info = t["info"]
        row["date"] = info["date"] if info else None
        if t["kind"] == "test":
            row["status"] = "excluded: agent test tap from this machine"
        elif info is None:
            row["status"] = "excluded: unparseable candidate id"
        elif in_window_a(info["date"]):
            row["status"] = "excluded: reserved window A, not loaded"
        elif t["candidate_id"] in first_seen:
            row["status"] = "repeat tap on an already-scored candidate (listed, not re-counted)"
        else:
            A = bars_for(info["date"])
            cand = finder(A, info, instrument) if A is not None else None
            if A is None:
                row["status"] = "excluded: no bars for that date"
            elif cand is None:
                row["status"] = "excluded: candidate not reproducible from bars"
            else:
                side = 1 if cand.direction == "long" else -1
                r = score_fill(A, cand.features["minutes_after_open"], side, cand.stop, cut, instrument)
                if r is None:
                    row["status"] = "excluded: degenerate stop / no entry bar"
                else:
                    row.update(R=round(r, 4), status="scored")
                    first_seen.add(t["candidate_id"])
                    scored.append(row)
        detail.append(row)
    res = dict(orb1m_sha256=orb1m_sha256(), cut_minute=cut, instrument=instrument,
               n_rows_in_labels_csv=len(taps), n_test=sum(1 for t in taps if t["kind"] == "test"),
               n_real=sum(1 for t in taps if t["kind"] != "test"), taps=detail,
               all_scored=summarize(scored, n_perm))
    for kind in ("blind", "remembered"):
        res[f"{kind}_only"] = summarize([r for r in scored if r["kind"] == kind], n_perm)
    return res


def _bars_loader(omen_data_dir: str | None, instrument: str):
    d = omen_data_dir or None
    if d:
        sys.path.insert(0, d)
    import candidates as eye2
    from omen_data import load_fut          # not in git: lives next to the recovered NQ files
    df = load_fut(instrument, "09:30", "11:01")
    ds = df["date"].astype(str)
    df = df[~((ds >= WINDOW_A[0]) & (ds <= WINDOW_A[1]))]      # window A dropped the moment the file is read
    cache = {}

    def bars_for(date):
        if in_window_a(date):
            raise RuntimeError("window A is reserved")
        if date not in cache:
            g = df[df["date"].astype(str) == date]
            cache[date] = eye2.day_arrays(g) if not g.empty else None
        return cache[date]
    return bars_for


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--labels", required=True)
    ap.add_argument("--log", action="append", required=True, help="runner log(s) with 'sent <cid>' lines")
    ap.add_argument("--omen-data", default=None, help="dir containing omen_data.py")
    ap.add_argument("--instrument", default="MNQ")
    ap.add_argument("--cut", type=int, default=CUT_LOOP, help="cutoff minute after 09:30 (60=10:30, 90=11:00)")
    ap.add_argument("--perm", type=int, default=N_PERM)
    ap.add_argument("--out", default=None, help="write JSON here")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(REPO / "research" / "agent_runs" / "v3-eye2-candidates"))
    res = analyse(a.labels, a.log, _bars_loader(a.omen_data, a.instrument), a.instrument, a.cut, a.perm)
    txt = json.dumps(res, indent=1, default=str)
    if a.out:
        Path(a.out).write_text(txt, encoding="utf-8")
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
