"""Bar availability for the mentor corpus (research/corpus_sf/*.jsonl).

READ-ONLY. Pulls nothing. Answers: for every distinct (symbol, session_date) a
mentor row claims, do we already hold 1-minute bars in data_archive/?

Cache layout and cost model come from polygon_feed.fetch_day(): one CSV per
(symbol, day) at data_archive/<SYM>/<DAY>.csv, and exactly one Polygon
aggregates request per missing pair, ever.
"""
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
ARCHIVE = ROOT / "data_archive"
CORPUS = ROOT / "research" / "corpus_sf"

from universe import ALL_SYMS  # noqa: E402
from chat_vocab import BAR_AVAILABILITY_FUTURES_SYMS as FUTURES_SYMS  # noqa: E402

# Files that carry trade-shaped rows (a symbol + a claim about a session).
# Excluded: questions/general_chat/tips/maxims (rule candidates, no session),
# live_sessions/reviews_jdub/premarket_charts (zero symbols by construction).
TRADE_FILES = [
    "scarface_alerts.jsonl",
    "jdub_alerts.jsonl",
    "futures_alerts.jsonl",
    "gains.jsonl",
    "misc.jsonl",
    "reviews_options.jsonl",
    "reviews_futures.jsonl",
    "pre_market_live.jsonl",
    "backtesting.jsonl",
]
# Rule/index files, counted for completeness but never asking for bars.
NONTRADE_FILES = [
    "questions.jsonl", "general_chat.jsonl", "tips.jsonl",
    "maxims_futures.jsonl", "live_sessions.jsonl", "reviews_jdub.jsonl",
    "premarket_charts.jsonl",
]

# NYSE full closures 2024-2026. Needed because "no symbol has this day cached"
# conflates a real holiday with an archive-wide gap: 2026-08-14 and 2026-08-18
# are weekdays absent from ALL 35 symbol dirs, and they are pullable, not shut.
NYSE_CLOSED = {
    "2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27",
    "2024-06-19", "2024-07-04", "2024-09-02", "2024-11-28", "2024-12-25",
    "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18",
    "2025-05-26", "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27",
    "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
}

CLAIM_FIELDS = ("direction", "setup", "level_name", "level_price",
                "entry", "stop", "target", "outcome", "r_multiple")


def load(fn):
    p = CORPUS / fn
    if not p.exists():
        return []
    # questions.jsonl carries raw newlines inside `quote`, so a per-line
    # json.loads dies on 9 rows. Stream-decode instead; the nine trade files
    # are all clean either way (verified: per-line count == stream count).
    txt = p.read_text(encoding="utf-8")
    dec, i, out = json.JSONDecoder(), 0, []
    while i < len(txt):
        while i < len(txt) and txt[i].isspace():
            i += 1
        if i >= len(txt):
            break
        obj, i = dec.raw_decode(txt, i)
        out.append(obj)
    return out


def session_date(row, src_file):
    """The ET calendar day the row is ABOUT, not always the day it was posted."""
    # reviews_futures states the reviewed day in the title
    td = row.get("trade_date")
    if td:
        return td[:10]
    sd = row.get("session_date")
    if sd:
        return sd[:10]
    ts = row.get("ts")
    if not ts:
        return None
    return ts[:10]


def is_claim(row):
    return any(row.get(f) not in (None, "", []) for f in CLAIM_FIELDS)


def main():
    # ---- archive index + trading-day calendar -----------------------------
    have = defaultdict(set)
    for d in sorted(ARCHIVE.iterdir()):
        if d.is_dir():
            have[d.name] = {f.stem for f in d.glob("*.csv")}
    trading_days = set()
    for s in have.values():
        trading_days |= s

    # ---- pool the rows ----------------------------------------------------
    rows = []
    per_file = {}
    for fn in TRADE_FILES:
        rs = load(fn)
        per_file[fn] = len(rs)
        for r in rs:
            r["_src_file"] = fn
            rows.append(r)

    nontrade_n = {fn: len(load(fn)) for fn in NONTRADE_FILES}

    # ---- classify ---------------------------------------------------------
    pairs = defaultdict(lambda: {"rows": 0, "claim_rows": 0, "files": Counter(),
                                 "post_date_only": False})
    n_no_symbol = n_no_date = 0
    claim_rows_total = 0
    # rows whose date is a POST date on a review channel (trade day unknown)
    POST_DATE_UNSAFE = {"reviews_options.jsonl"}

    for r in rows:
        sym = r.get("symbol")
        if not sym:
            n_no_symbol += 1
            continue
        d = session_date(r, r["_src_file"])
        if not d:
            n_no_date += 1
            continue
        c = is_claim(r)
        claim_rows_total += int(c)
        k = (sym.upper(), d)
        e = pairs[k]
        e["rows"] += 1
        e["claim_rows"] += int(c)
        e["files"][r["_src_file"]] += 1
        if r["_src_file"] in POST_DATE_UNSAFE and not r.get("trade_date"):
            e["post_date_only"] = True

    # ---- bucket every pair ------------------------------------------------
    buckets = Counter()
    detail = defaultdict(list)
    for (sym, d), e in pairs.items():
        try:
            dt = date.fromisoformat(d)
        except ValueError:
            buckets["bad_date"] += 1
            continue
        if sym in FUTURES_SYMS:
            b = "futures_not_fetchable"
        elif dt.weekday() >= 5:
            b = "weekend_no_session"
        elif d in NYSE_CLOSED:
            b = "market_holiday"
        elif d in have.get(sym, ()):
            b = "have_bars"
        else:
            b = "need_pull"
        buckets[b] += 1
        detail[b].append((sym, d, e))

    # ---- pull cost --------------------------------------------------------
    need = detail["need_pull"]
    need_by_sym = Counter(s for s, _, _ in need)
    need_in_universe = sum(n for s, n in need_by_sym.items() if s in ALL_SYMS)
    need_new_sym = sum(n for s, n in need_by_sym.items() if s not in ALL_SYMS)

    # rows covered by each bucket
    rows_in = {b: sum(e["rows"] for _, _, e in v) for b, v in detail.items()}
    claims_in = {b: sum(e["claim_rows"] for _, _, e in v) for b, v in detail.items()}

    out = {
        "per_file_rows": per_file,
        "nontrade_rows": nontrade_n,
        "pooled_rows": len(rows),
        "rows_no_symbol": n_no_symbol,
        "rows_no_date": n_no_date,
        "claim_rows_total": claim_rows_total,
        "distinct_pairs": len(pairs),
        "buckets": dict(buckets),
        "rows_in": rows_in,
        "claims_in": claims_in,
        "need_by_symbol": need_by_sym.most_common(),
        "need_in_universe": need_in_universe,
        "need_new_symbols": need_new_sym,
        "archive_symbols": len(have),
        "archive_files": sum(len(v) for v in have.values()),
        "trading_days_known": len(trading_days),
        "trading_day_range": (min(trading_days), max(trading_days)),
        "futures_pairs_by_sym": Counter(s for s, _, _ in detail["futures_not_fetchable"]).most_common(),
        "weekend_by_file": Counter(f for _, _, e in detail["weekend_no_session"] for f in e["files"]).most_common(),
        "holiday_dates": sorted(Counter(d for _, d, _ in detail["market_holiday"]).items()),
        "archive_wide_gap_days": sorted({d for _, d, _ in detail["need_pull"]
                                         if d not in trading_days}),
        "need_by_year": Counter(d[:4] for _, d, _ in need).most_common(),
        "have_by_year": Counter(d[:4] for _, d, _ in detail["have_bars"]).most_common(),
    }
    # per-file pair coverage
    fc = {}
    for fn in TRADE_FILES:
        tot = hav = nd = 0
        for b, v in detail.items():
            for sym, d, e in v:
                if fn in e["files"]:
                    tot += 1
                    if b == "have_bars":
                        hav += 1
                    elif b == "need_pull":
                        nd += 1
        fc[fn] = (tot, hav, nd)
    out["per_file_pairs"] = fc
    # date-unsafe
    out["post_date_only_pairs"] = sum(1 for e in pairs.values() if e["post_date_only"])
    # Polygon history depth risk: the free tier is 2y, Starter is 5y.
    cutoff2y = "2024-08-29"
    out["need_pull_older_than_2y"] = sum(1 for _, d, _ in need if d < cutoff2y)
    out["oldest_need_pull"] = min((d for _, d, _ in need), default=None)
    out["need_confidence_mix"] = Counter(
        r.get("confidence") for r in rows
        if r.get("symbol") and (r["symbol"].upper(), session_date(r, r["_src_file"]))
        in {(s, d) for s, d, _ in need}).most_common()
    # Manifest for a future pull job. Written, not executed. One line per
    # (symbol, day) that has no data_archive CSV and is a real equity session.
    man = CORPUS / "bar_pull_manifest.jsonl"
    with open(man, "w", encoding="utf-8") as f:
        for sym, d, e in sorted(need):
            f.write(json.dumps({
                "symbol": sym, "date": d,
                "in_universe": sym in ALL_SYMS,
                "corpus_rows": e["rows"], "claim_rows": e["claim_rows"],
                "src_files": sorted(e["files"]),
            }))
            f.write(chr(10))
    out["manifest"] = str(man)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
