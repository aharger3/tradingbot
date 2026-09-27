"""v2-paper-harness reconciler + daily report (s12 build order #2, s12 s5).

Joins Lane L (paper_live.jsonl, real-time) against Lane R (paper_replay.jsonl, T+1
replay) on signal_id and writes paper_recon.jsonl plus a markdown daily report.
Lane L does not exist yet (s12: TopstepX practice account, step 4) -- when
paper_live.jsonl is absent or empty, every parity row reports "n/a (no Lane L yet)"
and only the Lane R coverage/signal blocks are real, exactly as s12 build order #2
specifies ("parity columns stay empty until L exists").

Usage: python reconcile.py [--replay paper_replay.jsonl] [--live paper_live.jsonl]
                            [--out paper_recon.jsonl] [--report report.md]
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_jsonl(path: Path):
    if not path.exists():
        return []
    out = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def build_report(r_rows, l_rows):
    r_by_id = {r["signal_id"]: r for r in r_rows}
    l_by_id = {r["signal_id"]: r for r in l_rows}

    matched_ids = sorted(set(r_by_id) & set(l_by_id))
    r_only = sorted(set(r_by_id) - set(l_by_id))
    l_only = sorted(set(l_by_id) - set(r_by_id))

    recon_rows = []
    for sid in matched_ids:
        r, l = r_by_id[sid], l_by_id[sid]
        recon_rows.append(dict(
            signal_id=sid,
            entry_diff_ticks=round(abs(r.get("entry_fill_px", 0) - l.get("entry_fill_px", 0)) / 0.25, 2),
            exit_reason_match=r.get("exit_reason") == l.get("exit_reason"),
            R_diff=round(abs(r.get("net_R", 0) - l.get("net_R", 0)), 4),
        ))
    for sid in r_only:
        recon_rows.append(dict(signal_id=sid, lane="R-only"))
    for sid in l_only:
        recon_rows.append(dict(signal_id=sid, lane="L-only"))

    by_sym_date = {}
    for r in r_rows:
        by_sym_date.setdefault(r["sym"], set()).add(r["date"])
    coverage = {sym: len(dates) for sym, dates in by_sym_date.items()}

    has_lane_l = len(l_rows) > 0
    total = len(r_by_id) or 1

    lines = []
    lines.append("# OMEN v2 paper-harness daily report\n")
    lines.append("## Coverage (Lane R, sessions with >=1 signal)\n")
    lines.append("| sym | sessions run |")
    lines.append("|---|---:|")
    for sym, n in coverage.items():
        lines.append(f"| {sym} | {n} |")
    lines.append("")
    lines.append("## Signal parity\n")
    if has_lane_l:
        lines.append("| L-only | R-only | matched | matched % |")
        lines.append("|---:|---:|---:|---:|")
        lines.append(f"| {len(l_only)} | {len(r_only)} | {len(matched_ids)} | {100*len(matched_ids)/total:.1f}% |")
    else:
        lines.append("n/a (no Lane L yet -- s12 step 4, TopstepX practice account not built)")
    lines.append("")
    lines.append("## Entry / exit / R parity (matched trades only)\n")
    if has_lane_l and matched_ids:
        diffs = [row["entry_diff_ticks"] for row in recon_rows if "entry_diff_ticks" in row]
        exit_match = [row["exit_reason_match"] for row in recon_rows if "exit_reason_match" in row]
        rdiffs = [row["R_diff"] for row in recon_rows if "R_diff" in row]
        med = sorted(diffs)[len(diffs)//2] if diffs else None
        lines.append(f"median entry diff: {med} ticks; max: {max(diffs) if diffs else None} ticks")
        lines.append(f"exit reason match: {100*sum(exit_match)/len(exit_match):.1f}%" if exit_match else "n/a")
        lines.append(f"median |R diff|: {sorted(rdiffs)[len(rdiffs)//2] if rdiffs else None}")
    else:
        lines.append("n/a (no Lane L yet)")
    lines.append("")
    lines.append("## P&L sanity (Lane R only, informational -- not a pass gate; see s12 s6)\n")
    if r_rows:
        net = sum(r.get("net_R", 0) for r in r_rows)
        lines.append(f"n={len(r_rows)} trades, sum net_R={net:.2f}, mean net_R={net/len(r_rows):.4f}")
    else:
        lines.append("no Lane R trades")
    lines.append("")

    report_md = "\n".join(lines)
    return recon_rows, report_md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", default=str(HERE / "paper_replay.jsonl"))
    ap.add_argument("--live", default=str(HERE / "paper_live.jsonl"))
    ap.add_argument("--out", default=str(HERE / "paper_recon.jsonl"))
    ap.add_argument("--report", default=str(HERE / "report.md"))
    args = ap.parse_args()

    r_rows = read_jsonl(Path(args.replay))
    l_rows = read_jsonl(Path(args.live))
    recon_rows, report_md = build_report(r_rows, l_rows)

    with open(args.out, "w") as f:
        for row in recon_rows:
            f.write(json.dumps(row) + "\n")
    with open(args.report, "w") as f:
        f.write(report_md)

    print(f"lane R rows={len(r_rows)} lane L rows={len(l_rows)} recon rows={len(recon_rows)}")
    print(f"wrote {args.out} and {args.report}")


if __name__ == "__main__":
    main()
