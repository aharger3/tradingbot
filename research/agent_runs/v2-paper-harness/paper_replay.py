"""v2-paper-harness Lane R (s12 build order #1): T+1 replay of MNQ on the frozen
strategy OMEN-SHIP-PLAN-v3.md sec 2 picked -- orb1m.py's OR5 + displacement (>=1 ATR)
+ wick retest (no close-through) + strong-bar trigger, 10:30 cutoff, 2R, 1/day.
Paper only. Honest fills inherited unchanged from the frozen engine's own sim()
(next-bar-open entry +1 tick, intrabar stop -1 tick, trade-through target, flat at
cutoff open -1 tick, $ comm both sides). Writes one JSONL row per traded signal to
paper_replay.jsonl, schema per s12 s4.

FIXED 2026-09-26 (v3 b1): PR #34 replayed ocr1m.py (ORB+OCR confluence, MES+MNQ) --
struck by the v3 referee. OMEN-SHIP-PLAN-v3.md sec 1/6 says only MNQ / OR5 /
disp>=1 ATR / strong / 10:30 / 2R is even a live hypothesis; everything else
(OCR confluence, MES, 4-tier, other cutoffs) is dead out-of-sample. Replay that
one cell only, on orb1m.py.

Usage:
    python paper_replay.py                 # Lane R: real MNQ in-sample replay -> paper_replay.jsonl
    python paper_replay.py --oos           # out-of-sample run (QQQ proxy, 2024-01-02..2024-09-25,
                                            # x41.35 snapped -- same window/method as v3-t-mnq/mnq.py,
                                            # reused here rather than re-derived) -> oos.json
Refuses to run if orb1m.py's hash has drifted from the frozen value (engine_lock.py).
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-t01-orb-1m")
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s07-data")

from engine_lock import assert_frozen, EngineDriftError, ENGINE_PATH  # noqa: E402

SYM = "MNQ"
ORN, DISP_K, TRIG, CUTNAME, CUT = 5, 1.0, "strong", "10:30", 60  # orb1m.CUTS["10:30"]
QQQ_SCALE = 41.35
DATA_ARCHIVE_QQQ = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\data_archive\QQQ")
COMMISSION_RT_USD = 1.24  # per-micro round trip; same figure as omen_data.SPEC[*]["rt_comm"] / orb1m
MNQ_USD_PT = 2.0          # omen_data.SPEC["MNQ"]["usd_pt"]; 1 contract, so risk_usd = stop_R_pts * 2.0


def net_R(gross_R, risk_usd, comm_usd=COMMISSION_RT_USD):
    """R after the round-trip commission: gross_R - comm_usd / risk_usd. Mirrors orb1m.run_trade,
    which the v2 grid reference (trades_MNQ_OR5_1030_D1_strong.json) is scored with."""
    return gross_R - comm_usd / risk_usd


def _exit_reason(A, side, i, cut, x, tgt):
    """Reconstruct which branch of orb1m.sim() produced this exit price, without
    duplicating its stop/target logic -- only its (documented, trivial) flat-at-cutoff
    formula, so the honest-fill price itself always comes from the frozen sim()."""
    O, C = A["open"], A["close"]
    if abs(x - tgt) < 1e-9:
        return "target"
    if cut < 91 and not np.isnan(O[cut]):
        flat_px = O[cut] - 0.25 * side
    else:
        v = C[:cut][~np.isnan(C[:cut])]
        flat_px = v[-1] - 0.25 * side
    if abs(x - flat_px) < 1e-9:
        return "cutoff"
    return "stop"


def _one_cell(days, engine_sha, orb1m):
    """days: list of (date_str, day_arrays_dict). Returns list of s12-schema rows."""
    rows = []
    for d, A in days:
        s = orb1m.signal(A, ORN, CUT, DISP_K, TRIG)
        if not s:
            continue
        i, side, stop = s
        e = A["open"][i] + orb1m.TICK * side
        dist = (e - stop) * side
        if dist < 2 * orb1m.TICK:
            continue
        tgt = e + side * 2 * dist
        x = orb1m.sim(A, side, i, stop, tgt, CUT)
        gross_R = (x - e) * side / dist
        netR = net_R(gross_R, dist * MNQ_USD_PT)
        reason = _exit_reason(A, side, i, CUT, x, tgt)
        bar_hhmm = f"{(570 + i) // 60:02d}{(570 + i) % 60:02d}"
        signal_id = f"{SYM}_{d}_ORB5_D1.0_{TRIG}_{bar_hhmm}_{CUTNAME}"
        rows.append(dict(
            signal_id=signal_id, lane="R", engine_sha=engine_sha, date=d, sym=SYM,
            contract=A.get("contract", "NA"), setup="ORB5+disp+retest", grade="S",
            dir="long" if side > 0 else "short", level_name="ORB5",
            window_cutoff=CUTNAME, entry_bar_min=int(570 + i),
            stop_px=round(float(stop), 4), stop_R_pts=round(float(dist), 4),
            entry_model_px=round(float(e), 4), tgt_px=round(float(tgt), 4),
            entry_fill_px=round(float(e), 4), entry_slip_ticks=1, fill_source="sim",
            exit_px=round(float(x), 4), exit_reason=reason,
            gross_R=round(float(gross_R), 4), net_R=round(float(netR), 4),
            comm_usd=COMMISSION_RT_USD,
        ))
    return rows


def build_is_days(load_fut, orb1m):
    df = load_fut(SYM, "09:30", "11:01")
    contract_by_date = df.groupby("date")["contract"].first().astype(str).to_dict()
    days = []
    for d, g in df.groupby("date"):
        A = orb1m.day_arrays(g)
        A["contract"] = contract_by_date.get(d, "NA")
        days.append((str(d), A))
    return days


def replay(out_path: Path, engine_sha: str):
    from omen_data import load_fut  # frozen v2 loader (s07)
    import orb1m  # the hash-checked frozen engine

    days = build_is_days(load_fut, orb1m)
    rows = _one_cell(days, engine_sha, orb1m)
    with out_path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return rows, {SYM: len(days)}


def build_oos_days(end="2024-09-25"):
    """QQQ proxy, x41.35 snapped -- same construction v3-t-mnq/mnq.py used for its OOS
    window (2024-01-02..2024-09-25, the earliest period reachable on the PC's Polygon
    key). Reused here as-is per the reuse-don't-redo instruction."""
    import orb1m
    days = []
    for f in sorted(glob.glob(str(DATA_ARCHIVE_QQQ / "*.csv"))):
        d = os.path.basename(f)[:10]
        if d > end:
            break
        raw = pd.read_csv(f)
        ts = pd.to_datetime(raw["Datetime"], format="mixed", utc=True).dt.tz_convert("America/New_York")
        raw = raw.set_index(ts)
        raw.columns = [c.lower() for c in raw.columns]
        for k in ("open", "high", "low", "close"):
            raw[k] = np.round(raw[k] * QQQ_SCALE / orb1m.TICK) * orb1m.TICK
        t = raw.index.hour * 60 + raw.index.minute
        g = raw[(t >= 570) & (t < 960)].copy()
        if g.empty:
            continue
        A = orb1m.day_arrays(g.assign(ts=g.index))
        if np.isnan(A["open"][:5]).all():
            continue
        A["contract"] = "QQQx41.35"
        days.append((d, A))
    return days


def run_oos(out_path: Path, engine_sha: str, nshuf=200):
    import orb1m
    days = build_oos_days()
    rows = _one_cell(days, engine_sha, orb1m)
    R = np.array([r["net_R"] for r in rows])
    dates = [d for d, _ in days]
    n = len(rows)
    result = dict(n=n, engine_sha=engine_sha, sym=SYM, cell=f"OR{ORN}_D{DISP_K}_{TRIG}_{CUTNAME}_2R",
                  window="2024-01-02..2024-09-25 (QQQ proxy x41.35)", sessions=len(days))
    if n:
        mid = dates[len(dates) // 2]
        h1 = np.array([r["date"] < mid for r in rows])
        result.update(
            R=float(R.mean()), win=float((R > 0).mean()),
            h1_n=int(h1.sum()), h1_R=float(R[h1].mean()) if h1.any() else None,
            h2_n=int((~h1).sum()), h2_R=float(R[~h1].mean()) if (~h1).any() else None,
        )
        rng = np.random.default_rng(7)
        sh = []
        by_date = {d: A for d, A in days}
        for _ in range(nshuf):
            rr = []
            for r in rows:
                i = (r["entry_bar_min"] - 570)
                while True:
                    dk = dates[int(rng.integers(len(dates)))]
                    Ak = by_date[dk]
                    if dk != r["date"] and not np.isnan(Ak["open"][i]):
                        break
                side = 1 if r["dir"] == "long" else -1
                dist = r["stop_R_pts"]
                e = Ak["open"][i] + orb1m.TICK * side
                stop = e - side * dist
                tgt = e + side * 2 * dist
                x = orb1m.sim(Ak, side, i, stop, tgt, CUT)
                rr.append(net_R((x - e) * side / dist, dist * MNQ_USD_PT))  # net, like R above
            sh.append(np.mean(rr) if rr else 0.0)
        sh = np.array(sh)
        result["shuffle_p"] = float((sh >= R.mean()).mean())
        result["shuffle_meanR"] = float(sh.mean())
    with out_path.open("w") as f:
        json.dump(result, f, indent=1)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "paper_replay.jsonl"))
    ap.add_argument("--oos", action="store_true", help="run the out-of-sample check instead of Lane R replay")
    ap.add_argument("--oos-out", default=str(HERE / "oos.json"))
    args = ap.parse_args()

    try:
        engine_sha = assert_frozen()
    except EngineDriftError as e:
        print(str(e))
        sys.exit(1)

    if args.oos:
        result = run_oos(Path(args.oos_out), engine_sha)
        print(f"engine={ENGINE_PATH.name} sha={engine_sha[:12]} OOS n={result['n']} "
              f"R={result.get('R')} p={result.get('shuffle_p')}")
        print(f"wrote {args.oos_out}")
        return

    rows, coverage = replay(Path(args.out), engine_sha)
    print(f"engine={ENGINE_PATH.name} sha={engine_sha[:12]} rows={len(rows)} sessions={coverage}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
