"""Turn the ledger + the tap files into the two CSVs s2_confirm.py reads (PR #100, prereg-S2.md), plus the tap counts.

  python -m stock_cards.export_taps [--archive-pool]

  s2_taps.csv              sym,day,sig_t,side,stop,label,sig_close_ts,tap_ts  (+ card_id,latency_s,in_time)
                           label is S or notS. A tap counts for the test only if in_time (0..120 s after the bar closed);
                           s2_confirm applies the same rule itself. Skip taps are counted, never exported as labels.
  s2_candidates_iex_eligible.csv   candidates the live feed saw that were eligible for a card (fired + [clean]), window
                           09:35-10:58: sym,day,sig_t,side,stop.  USE THIS AS THE NULL POOL: cards are drawn only from
                           this set, and on the fit window it earns -0.09R against -0.32R for all candidates, so the
                           all-candidates null would hand every card a +0.22R head start (see stock-cards.md)
  s2_candidates_iex_all.csv        every candidate the live feed saw (the literal prereg-S2 pool; inflated, see above)
  s2_candidates_archive_{eligible,all}.csv  (--archive-pool) the same engine run on the Polygon archive bars of the days
                           we carded, which is how the fit-window pool was defined; available once OmenArchiveRetry
                           has filled the day (18:15 ET)
  tap_counts.json          cards, S, notS, skip, no tap, late, response rate: counting is allowed before the first look,
                           no R or excess is computed here

Reads the tap files; writes only to DATA_DIR/export. Computes nothing about outcomes.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from datetime import datetime
from pathlib import Path

from . import ledger
from .config import DATA_DIR, LABELS_CSV, TAP_WINDOW_SECONDS, load_watchlist

TAP_FIELDS = ["sym", "day", "sig_t", "side", "stop", "label", "sig_close_ts", "tap_ts", "card_id", "latency_s", "in_time"]
CAND_FIELDS = ["sym", "day", "sig_t", "side", "stop"]


def _read_csv(p: Path) -> list[dict]:
    try:
        with open(p, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return []


def read_taps(labels_csv: Path = LABELS_CSV) -> dict[str, dict]:
    """card_id -> {'label': 'S'|'notS'|'skip', 'tap_ts': iso}. First tap per card wins (the server enforces it too)."""
    out: dict[str, dict] = {}
    for p, forced in ((Path(labels_csv), None), (Path(labels_csv).with_name("skips.csv"), "skip")):
        for r in _read_csv(p):
            cid = r.get("candidate_id", "")
            if cid and cid not in out:
                out[cid] = {"label": forced or r.get("label", ""), "tap_ts": r.get("logged_at", "")}
    return out


def build_tap_rows(cards: list[dict], taps: dict[str, dict]) -> tuple[list[dict], dict]:
    rows, counts = [], {"cards": len(cards), "S": 0, "notS": 0, "skip": 0, "no_tap": 0, "late_or_early": 0}
    lat = []
    for c in cards:
        t = taps.get(c["card_id"])
        if t is None:
            counts["no_tap"] += 1
            continue
        if t["label"] == "skip":
            counts["skip"] += 1
            continue
        latency = (datetime.fromisoformat(t["tap_ts"]) - datetime.fromisoformat(c["sig_close_ts"])).total_seconds()
        in_time = 0 <= latency <= TAP_WINDOW_SECONDS
        counts[t["label"]] = counts.get(t["label"], 0) + 1
        if not in_time:
            counts["late_or_early"] += 1
        else:
            lat.append(latency)
        rows.append({"sym": c["sym"], "day": c["day"], "sig_t": c["sig_t"], "side": c["side"], "stop": c["stop"],
                     "label": t["label"], "sig_close_ts": c["sig_close_ts"], "tap_ts": t["tap_ts"],
                     "card_id": c["card_id"], "latency_s": round(latency, 1), "in_time": int(in_time)})
    in_time_n = sum(r["in_time"] for r in rows)
    counts["in_time_taps"] = in_time_n
    counts["response_in_time"] = round(in_time_n / len(cards), 3) if cards else None
    counts["median_latency_s"] = round(statistics.median(lat), 1) if lat else None
    return rows, counts


def _write(p: Path, fields: list[str], rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def candidate_rows(cands: list[dict], eligible_only: bool = False) -> list[dict]:
    from .policy import eligible, in_window
    seen, out = set(), []
    for c in cands:
        k = (c["sym"], c["day"], c["sig_t"], c["side"], c["stop"])
        if k in seen or not in_window(c["sig_t"]) or (eligible_only and not eligible(c)):
            continue
        seen.add(k)
        out.append(c)
    return out


def archive_pool(days: list[str], log=print) -> list[dict]:
    """Engine candidates on the Polygon archive bars for each day we carded (the fit-window definition)."""
    import polygon_feed as pf
    from .compare import _detect_day
    from .config import ARCHIVE
    from .run_day import build_contexts
    syms = load_watchlist()
    out = []
    for day in days:
        full = {}
        for s in syms:
            fp = ARCHIVE / s / f"{day}.csv"
            full[s] = [c for c in pf._read_csv(fp) if c.timestamp < "11:05:00"] if fp.exists() else []
        if not any(full.values()):
            log(f"archive has no bars for {day} yet; skipped")
            continue
        ctxs = build_contexts(syms, day, DATA_DIR / "export", log)
        out += _detect_day(syms, day, full, ctxs)
    return out


def main(argv=None, data_dir: Path = DATA_DIR, labels_csv: Path = LABELS_CSV) -> dict:
    ap = argparse.ArgumentParser(prog="python -m stock_cards.export_taps")
    ap.add_argument("--archive-pool", action="store_true", help="also write the archive-engine candidate pool")
    a = ap.parse_args(argv)
    cards = ledger.cards("live", None, data_dir)
    rows, counts = build_tap_rows(cards, read_taps(labels_csv))
    out = Path(data_dir) / "export"
    _write(out / "s2_taps.csv", TAP_FIELDS, rows)
    live_cands = ledger.candidates(None, data_dir)
    _write(out / "s2_candidates_iex_eligible.csv", CAND_FIELDS, candidate_rows(live_cands, True))
    _write(out / "s2_candidates_iex_all.csv", CAND_FIELDS, candidate_rows(live_cands, False))
    if a.archive_pool:
        arc = archive_pool(sorted({c["day"] for c in cards}))
        _write(out / "s2_candidates_archive_eligible.csv", CAND_FIELDS, candidate_rows(arc, True))
        _write(out / "s2_candidates_archive_all.csv", CAND_FIELDS, candidate_rows(arc, False))
    (out / "tap_counts.json").write_text(json.dumps(counts, indent=1), encoding="utf-8")
    print(json.dumps(counts))
    return counts


if __name__ == "__main__":
    main()
