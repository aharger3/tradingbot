"""v2-paper-harness Lane R (s12 build order #1): T+1 replay of MES/MNQ on the frozen v2
engine (ocr1m.py, ORB+OCR confluence: zone=upper "higher in block", confirm=strong,
orb=True). Paper only. Honest fills inherited unchanged from the frozen engine's own
sim() (next-bar-open entry, intrabar stop, trade-through target, $ comm + 1 tick both
sides). Writes one JSONL row per traded signal to paper_replay.jsonl, schema per s12 s4.

Usage: python paper_replay.py [--out paper_replay.jsonl] [--cutoffs 630,645,660]
Refuses to run if ocr1m.py's hash has drifted from the frozen value (engine_lock.py).
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-t02-ocr-1m")
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s07-data")

from engine_lock import assert_frozen, EngineDriftError, ENGINE_PATH  # noqa: E402

SYMS = ("MES", "MNQ")
ZONE, CONFIRM, ORB = "upper", "strong", True
CUT_NAME = {630: "10:30", 645: "10:45", 660: "11:00"}


def contract_for(days, sym, date):
    return days[sym][date].get("contract", "NA")


def build_days(load_fut, sym):
    """Same day-array shape ocr1m.prep() uses, plus a per-day front-month contract."""
    df = load_fut(sym, "09:00", "11:00")
    days = {}
    for d, g in df.groupby("date"):
        mins = (g["ts"].dt.hour * 60 + g["ts"].dt.minute).to_numpy()
        if (mins == 570).sum() == 0:
            continue
        days[str(d)] = dict(
            m=mins,
            o=g.open.to_numpy(float),
            h=g.high.to_numpy(float),
            l=g.low.to_numpy(float),
            c=g.close.to_numpy(float),
            contract=str(g["contract"].iloc[0]) if "contract" in g.columns else "NA",
        )
    return days


def replay(out_path: Path, cutoffs, engine_sha: str):
    from omen_data import load_fut, SPEC  # frozen v2 loader (s07)
    import ocr1m  # the hash-checked frozen engine

    rows = []
    sessions_by_sym = {}
    for sym in SYMS:
        days = build_days(load_fut, sym)
        sessions_by_sym[sym] = sorted(days)
        sp = SPEC[sym]
        for cut in cutoffs:
            for date, a in days.items():
                best = None
                for side in (1, -1):
                    s = side
                    o, c = a["o"] * s, a["c"] * s
                    hh, ll = (a["h"], a["l"]) if s == 1 else (-a["l"], -a["h"])
                    sig = ocr1m.detect(o, hh, ll, c, a["m"], ZONE, CONFIRM, ORB, cut)
                    if sig:
                        ent, st, R = min(sig)
                        if best is None or ent < best[0]:
                            best = (ent, st, R, side, o, hh, ll, c)
                if best is None:
                    continue
                ent, st, R, side, o, hh, ll, c = best
                if R < 1.0:
                    continue
                e = o[ent] + ocr1m.TICK
                tgt = e + ocr1m.TGT * R
                x = ocr1m.sim(o, hh, ll, c, a["m"], ent, st, tgt)
                gross_pts = (x - e) / R  # in R
                net_R = gross_pts - sp["rt_comm"] / (sp["usd_pt"] * R)
                exit_reason = "target" if abs(x - tgt) < 1e-9 else ("stop" if abs((x + ocr1m.TICK) - st) < 1e-6 or (x <= st) else "cutoff")
                bar_hhmm = f"{a['m'][ent] // 60:02d}{a['m'][ent] % 60:02d}"
                level_name = "OCRblock"
                signal_id = f"{sym}_{date}_ORB+OCR_{level_name}_{bar_hhmm}_{CUT_NAME[cut]}"
                row = dict(
                    signal_id=signal_id,
                    lane="R",
                    engine_sha=engine_sha,
                    date=date,
                    sym=sym,
                    contract=a.get("contract", "NA"),
                    setup="ORB+OCR",
                    grade="S",
                    dir="long" if side > 0 else "short",
                    level_name=level_name,
                    window_cutoff=CUT_NAME[cut],
                    entry_bar_min=int(a["m"][ent]),
                    stop_px=round(float(side * st), 4),
                    stop_R_pts=round(float(R), 4),
                    entry_model_px=round(float(side * e), 4),
                    tgt_px=round(float(side * tgt), 4),
                    entry_fill_px=round(float(side * e), 4),
                    entry_slip_ticks=1,
                    fill_source="sim",
                    exit_px=round(float(side * x), 4),
                    exit_reason=exit_reason,
                    gross_R=round(float(gross_pts), 4),
                    net_R=round(float(net_R), 4),
                    comm_usd=sp["rt_comm"],
                )
                rows.append(row)

    with out_path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    coverage = {sym: len(sessions_by_sym[sym]) for sym in SYMS}
    return rows, coverage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "paper_replay.jsonl"))
    ap.add_argument("--cutoffs", default="630,645,660")
    args = ap.parse_args()

    try:
        engine_sha = assert_frozen()
    except EngineDriftError as e:
        print(str(e))
        sys.exit(1)

    cutoffs = [int(x) for x in args.cutoffs.split(",")]
    rows, coverage = replay(Path(args.out), cutoffs, engine_sha)
    print(f"engine={ENGINE_PATH.name} sha={engine_sha[:12]} rows={len(rows)} sessions={coverage}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
