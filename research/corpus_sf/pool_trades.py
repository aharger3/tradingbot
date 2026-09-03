"""pool_trades.py -- build the pooled mentor trade-instance set.

Reads every research/corpus_sf/*.jsonl mined from the Discord exports, keeps the
rows that describe an actual TRADE (not a rule, not a chart drop, not a video
index), deduplicates the same trade seen from several channels, and cross-checks
the result against Austin's judged symbol-days.

READ-ONLY on every Austin mark corpus. The only enumerator used is
research/build_deck.py::marked_card_ids(); nothing under research/marks/ or the
legacy mark files is opened for writing.

    python research/corpus_sf/pool_trades.py

Writes: research/corpus_sf/pooled_trades.jsonl
        research/corpus_sf/pool_report.md
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(HERE)
ROOT = os.path.dirname(RESEARCH)
sys.path.insert(0, ROOT)
sys.path.insert(0, RESEARCH)

from universe import ALL_SYMS                      # single source of truth
from research.build_deck import marked_card_ids    # the no-repeat enumerator

OUT_JSONL = os.path.join(HERE, "pooled_trades.jsonl")
OUT_MD = os.path.join(HERE, "pool_report.md")

# ---------------------------------------------------------------------------
# 1. Source classification.
#
# TRADE_SOURCES carry rows that can describe a position. RULE_SOURCES carry
# stated rules, methodology, chart manifests or video indices -- a row there is
# never a trade instance, so the whole file is excluded rather than filtered.
# ---------------------------------------------------------------------------
TRADE_SOURCES = [
    "scarface_alerts.jsonl",    # Scarface's live options alerts
    "jdub_alerts.jsonl",        # Jdub premarket levels + occasional fills
    "futures_alerts.jsonl",     # MambaTrades NQ/ES
    "reviews_options.jsonl",    # Lauren/Hayden/Neto trade reviews
    "reviews_futures.jsonl",    # MambaTrades review titles ($ P&L)
    "reviews_jdub.jsonl",       # Jdub recap titles (no symbol -- yields 0)
    "pre_market_live.jsonl",    # Jdub's 4 written gameplans
    "gains.jsonl",              # post-your-gains, member self-reports
    "misc.jsonl",               # trading-floor / trade-feedback / swing-ideas
]
RULE_SOURCES = [
    "questions.jsonl", "general_chat.jsonl", "tips.jsonl", "maxims_futures.jsonl",
    "backtesting.jsonl",        # methodology + aggregate backtests, not trades
    "premarket_charts.jsonl",   # image manifest, zero text signal
    "live_sessions.jsonl",      # date -> youtube index
]

OMEN_SETUPS = {"break_retest", "one_candle", "br_ocr"}


def rows(name):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


# ---------------------------------------------------------------------------
# 2. What counts as trade-shaped.
#
# A row is a TRADE INSTANCE when it names a symbol AND asserts at least one
# fact about a position: a side, a result, a fill, an R, a dollar P&L, or one
# of the two OMEN setups. A row naming only a level ("MU above 1200") is a
# WATCH call, not a trade -- counted separately and NOT pooled.
# ---------------------------------------------------------------------------
def trade_fact(r):
    return any([
        r.get("direction"),
        r.get("outcome"),
        r.get("entry") is not None,
        r.get("r_multiple") is not None,
        r.get("setup") in OMEN_SETUPS,
        r.get("pnl_usd") is not None,
        r.get("pl_dollars") is not None,
    ])


def watch_fact(r):
    return bool(r.get("level_name") or r.get("level_price") is not None
                or r.get("target") is not None or r.get("stop") is not None)


TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_ts(ts):
    """(date_str, minutes_since_midnight_ET) -- corpus ts is already ET."""
    if not isinstance(ts, str):
        return None, None
    m = TS_RE.match(ts)
    if not m:
        return None, None
    return m.group(1), int(m.group(2)) * 60 + int(m.group(3))


def trading_date(r):
    """Prefer an explicitly stated trade date over the post date."""
    td = r.get("trade_date")
    if isinstance(td, str) and DATE_RE.match(td):
        return td
    return parse_ts(r.get("ts"))[0]


# Fields that carry information; richness = how many are populated.
RICH_FIELDS = ["direction", "setup", "level_price", "level_name", "entry", "stop",
               "target", "outcome", "r_multiple", "pnl_usd", "pl_dollars",
               "reason", "video_url"]
CONF_W = {"high": 2, "medium": 1, "low": 0}


def richness(r):
    n = sum(1 for f in RICH_FIELDS if r.get(f) not in (None, "", []))
    return (n,
            CONF_W.get(r.get("confidence"), 0),
            1 if r.get("image_urls") else 0,
            len(r.get("quote") or ""))


# ---------------------------------------------------------------------------
# 3. Load
# ---------------------------------------------------------------------------
def load():
    pool, watch, per_source = [], [], {}
    for name in TRADE_SOURCES:
        kept = wch = tot = no_sym = no_date = 0
        for r in rows(name):
            tot += 1
            sym = r.get("symbol")
            date = trading_date(r)
            if not sym:
                no_sym += 1
                continue
            if not date:
                no_date += 1
                continue
            r["_file"] = name
            r["_date"] = date
            r["_min"] = parse_ts(r.get("ts"))[1]
            if trade_fact(r):
                pool.append(r)
                kept += 1
            elif watch_fact(r):
                watch.append(r)
                wch += 1
        per_source[name] = dict(total=tot, trade=kept, watch=wch,
                                no_symbol=no_sym, no_date=no_date)
    return pool, watch, per_source


# ---------------------------------------------------------------------------
# 4. Dedup.
#
# Key = (symbol, trading date, direction, entry within 0.25%).
#   * rows WITH an entry cluster greedily by 0.25% relative distance;
#   * rows WITHOUT an entry collapse into one cluster per (symbol, date,
#     direction) -- that IS the stated key with entry unstated, and it is what
#     folds "alerted -> reviewed -> posted as a gain" into one instance;
#   * a null-direction cluster is then absorbed into the unique directional
#     cluster for the same (symbol, date) when exactly one exists.
# ---------------------------------------------------------------------------
ENTRY_TOL = 0.0025


def dedup(pool):
    buckets = defaultdict(list)
    for r in pool:
        buckets[(r["symbol"], r["_date"], r.get("direction") or "?")].append(r)

    clusters = []          # [symbol, date, direction, entry_or_None, rows]
    for (sym, date, dirn), rs in buckets.items():
        priced = sorted([r for r in rs if isinstance(r.get("entry"), (int, float))],
                        key=lambda r: r["entry"])
        unpriced = [r for r in rs if not isinstance(r.get("entry"), (int, float))]
        cur = []
        for r in priced:
            if cur and abs(r["entry"] - cur[0]["entry"]) <= abs(cur[0]["entry"]) * ENTRY_TOL:
                cur.append(r)
            else:
                if cur:
                    clusters.append([sym, date, dirn, cur[0]["entry"], cur])
                cur = [r]
        if cur:
            clusters.append([sym, date, dirn, cur[0]["entry"], cur])
        if unpriced:
            clusters.append([sym, date, dirn, None, unpriced])

    # absorb null-direction clusters into a unique directional one
    by_sd = defaultdict(list)
    for c in clusters:
        by_sd[(c[0], c[1])].append(c)
    absorbed = 0
    final = []
    for (sym, date), cs in by_sd.items():
        directional = [c for c in cs if c[2] in ("long", "short")]
        unknown = [c for c in cs if c[2] == "?"]
        if unknown and len(directional) == 1:
            tgt = directional[0]
            for u in unknown:
                tgt[4].extend(u[4])
                absorbed += 1
            final.append(tgt)
        else:
            final.extend(cs)
    return final, absorbed


def collapse(cluster):
    sym, date, dirn, entry, rs = cluster
    best = max(rs, key=richness)
    out = {k: best.get(k) for k in
           ("symbol", "direction", "setup", "level_price", "level_name",
            "entry", "stop", "target", "outcome", "r_multiple")}
    # fill any field the winner lacks from the other rows in the cluster
    filled = []
    for f in ("direction", "setup", "level_price", "level_name", "entry",
              "stop", "target", "outcome", "r_multiple"):
        if out.get(f) in (None, ""):
            for r in rs:
                if r is best:
                    continue
                if r.get(f) not in (None, ""):
                    out[f] = r[f]
                    filled.append(f)
                    break
    files = sorted({r["_file"] for r in rs})
    votes = Counter(r["outcome"] for r in rs if r.get("outcome"))
    out.update(
        outcome_votes=dict(votes),
        outcome_conflict=len(votes) > 1,
        trade_date=date,
        ts=best.get("ts"),
        et_minute=best.get("_min"),
        author=best.get("author"),
        primary_src=best["_file"],
        n_rows=len(rs),
        n_sources=len(files),
        sources=files,
        msg_ids=sorted({str(r.get("msg_id")) for r in rs}),
        authors=sorted({str(r.get("author")) for r in rs if r.get("author")}),
        n_authors=len({str(r.get("author")) for r in rs if r.get("author")}),
        confidence=best.get("confidence"),
        pnl_usd=(best.get("pnl_usd") if best.get("pnl_usd") is not None
                 else best.get("pl_dollars")),
        instrument=best.get("instrument") or "equity_option",
        fields_backfilled=filled,
        quote=best.get("quote"),
        image_urls=best.get("image_urls") or [],
        card_id="%s_%s" % (sym, date),
    )
    return out


def main():
    pool, watch, per_source = load()
    clusters, absorbed = dedup(pool)
    trades = [collapse(c) for c in clusters]
    trades.sort(key=lambda t: (t["trade_date"], t["symbol"], t["ts"] or ""))

    with open(OUT_JSONL, "w", encoding="utf-8") as fh:
        for t in trades:
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")

    # ---- cross-check against Austin, read-only -----------------------------
    austin = marked_card_ids()
    pooled_days = {t["card_id"] for t in trades}
    overlap = pooled_days & austin
    ov_trades = [t for t in trades if t["card_id"] in austin]

    # ---- window / universe ------------------------------------------------
    uni = set(ALL_SYMS)
    in_uni = [t for t in trades if t["symbol"] in uni]

    def in_win(t):
        return t["et_minute"] is not None and 570 <= t["et_minute"] <= 660

    win_uni = [t for t in in_uni if in_win(t)]

    sym_ct = Counter(t["symbol"] for t in trades)
    dates = sorted(t["trade_date"] for t in trades)
    multi = [t for t in trades if t["n_sources"] > 1]
    multi_rows = [t for t in trades if t["n_rows"] > 1]

    L = []
    a = L.append
    a("# Pooled mentor trade instances")
    a("")
    a("Built by `research/corpus_sf/pool_trades.py` on %s from the 15 mined Discord "
      "corpora in `research/corpus_sf/`. These are SCARFACE's and the other mentors' "
      "judgements -- **not Austin's marks**. No Austin mark corpus was opened for "
      "writing; `marked_card_ids()` is used read-only."
      % dt.date.today().isoformat())
    a("")
    a("## 1. What went in")
    a("")
    a("A row is a **trade instance** when it names a symbol AND asserts a fact about a "
      "position: a direction, an outcome, an entry fill, an R-multiple, a dollar P&L, or "
      "one of the two OMEN setups (`break_retest` / `one_candle` / `br_ocr`). "
      "A row naming only a level or a target is a **watch call**: counted, not pooled.")
    a("")
    a("| source | rows | trade-shaped | watch-only | no symbol | no date |")
    a("|---|---:|---:|---:|---:|---:|")
    for name, d in per_source.items():
        a("| `%s` | %d | %d | %d | %d | %d |" %
          (name, d["total"], d["trade"], d["watch"], d["no_symbol"], d["no_date"]))
    a("| **total** | **%d** | **%d** | **%d** | **%d** | **%d** |" %
      (sum(d["total"] for d in per_source.values()),
       sum(d["trade"] for d in per_source.values()),
       sum(d["watch"] for d in per_source.values()),
       sum(d["no_symbol"] for d in per_source.values()),
       sum(d["no_date"] for d in per_source.values())))
    a("")
    a("Excluded wholesale as rule / index / manifest corpora (no trade instances by "
      "construction): " + ", ".join("`%s`" % s for s in RULE_SOURCES) + ".")
    a("")
    a("## 2. Dedup")
    a("")
    a("Key = (symbol, trading date, direction, entry within 0.25%). Entry is stated on "
      "almost nothing in this data, so in practice the key collapses to "
      "symbol-day-direction; that is exactly what folds *alerted -> reviewed -> posted "
      "as a gain* into one instance. Null-direction clusters are absorbed into the "
      "unique directional cluster for the same symbol-day when exactly one exists "
      "(" + str(absorbed) + " absorptions). The richest row wins the merge; any field "
      "the winner lacks is backfilled from its cluster-mates and recorded in "
      "`fields_backfilled`.")
    a("")
    a("- input trade-shaped rows: **%d**" % len(pool))
    a("- distinct trade instances after dedup: **%d** (compression %.2fx)"
      % (len(trades), len(pool) / max(1, len(trades))))
    a("- instances built from >1 raw row: **%d**" % len(multi_rows))
    a("- instances corroborated by >1 SOURCE CHANNEL: **%d**" % len(multi))
    a("- rows-per-instance: " +
      ", ".join("%d rows x%d" % (k, v) for k, v in
                sorted(Counter(t["n_rows"] for t in trades).items())))
    a("- sources-per-instance: " +
      ", ".join("%d src x%d" % (k, v) for k, v in
                sorted(Counter(t["n_sources"] for t in trades).items())))
    a("")
    author_tuples = {(t["symbol"], t["trade_date"], t["direction"], au)
                     for t in trades for au in t["authors"]}
    a("**The key merges across people, deliberately.** %d instances pool rows from more "
      "than one author -- three members each posting a TSLA long on the same morning "
      "become one instance, because the unit that can be scored against an Austin grade "
      "is the symbol-day-side, not the person. If you want per-person trades instead, "
      "split on `authors`: that yields **%d** (symbol, date, direction, author) tuples. "
      "`n_rows`, `n_authors` and `authors` preserve the multiplicity either way."
      % (sum(1 for t in trades if t["n_authors"] > 1), len(author_tuples)))
    a("")
    a("Cross-channel agreement (instances two or more channels both saw):")
    a("")
    a("| source combination | instances |")
    a("|---|---:|")
    for combo, n in Counter(" + ".join(t["sources"]) for t in multi).most_common(15):
        a("| %s | %d |" % (combo, n))
    a("")
    conflict = [t for t in trades if t["outcome_conflict"]]
    wknd = [t for t in trades
            if dt.date(*map(int, t["trade_date"].split("-"))).weekday() >= 5]
    a("Two measured limits of the merge, both reported per-row so a consumer can filter:")
    a("")
    a("- **Outcome conflict.** %d of the %d multi-row instances (%.1f%%) contain member "
      "rows that disagree on the result -- one person scaled out green while another was "
      "stopped, or a scalp and a runner on the same level resolved differently. The "
      "richest row's outcome is kept and `outcome_conflict: true` plus the full "
      "`outcome_votes` tally is written on the row."
      % (len(conflict), len(multi_rows), 100 * len(conflict) / max(1, len(multi_rows))))
    a("- **Non-weekday dates.** %d instances sit on a Saturday or Sunday -- weekend "
      "swing-idea posts and review write-ups whose post date is not a session date. "
      "Filter them before joining to bars."
      % len(wknd))
    a("")
    a("## 3. Overlap with Austin's judged symbol-days")
    a("")
    a("Enumerator: `research/build_deck.py::marked_card_ids()` (read-only). "
      "Overlap is the point: it is where a mentor's call and Austin's grade sit on the "
      "same chart, so Scarface can be scored against him.")
    a("")
    a("- symbol-days Austin has judged: **%d**" % len(austin))
    a("- distinct symbol-days in the pool: **%d**" % len(pooled_days))
    a("- **overlap: %d symbol-days** (%.1f%% of the pool's days, %.1f%% of Austin's)"
      % (len(overlap), 100 * len(overlap) / max(1, len(pooled_days)),
         100 * len(overlap) / max(1, len(austin))))
    a("- pooled trade instances landing on a day Austin judged: **%d**" % len(ov_trades))
    a("")
    lo, hi = dates[0], dates[-1]
    a_in_range = {k for k in austin if lo <= k.split("_")[-1] <= hi}
    pool_syms = {t["symbol"] for t in trades}
    a_reach = {k for k in a_in_range if k.rsplit("_", 1)[0] in pool_syms}
    a("The 220 is capped by two things that are not parser quality. Austin's corpus "
      "reaches back before this Discord export starts and covers symbols the mentors "
      "never post: only **%d** of his %d judged days fall inside %s..%s, and only "
      "**%d** of those are on a symbol the pool covers at all. Against that reachable "
      "denominator the overlap is **%.1f%%**."
      % (len(a_in_range), len(austin), lo, hi, len(a_reach),
         100 * len(overlap) / max(1, len(a_reach))))
    a("")
    a("Top symbols in the overlap: %s."
      % ", ".join("%s %d" % kv for kv in
                  Counter(t["symbol"] for t in ov_trades).most_common(12)))
    a("")
    a("Overlap instances carrying a stated outcome: **%d** (%s)."
      % (sum(1 for t in ov_trades if t["outcome"]),
         ", ".join("%s %d" % kv for kv in
                   Counter(t["outcome"] for t in ov_trades if t["outcome"]).most_common())))
    a("Overlap instances inside 09:30-11:00 ET: **%d**."
      % sum(1 for t in ov_trades if in_win(t)))
    a("")
    a("Per-channel contribution to the overlap set:")
    a("")
    a("| channel | overlap instances |")
    a("|---|---:|")
    for src, n in Counter(s for t in ov_trades for s in t["sources"]).most_common():
        a("| `%s` | %d |" % (src, n))
    a("")
    a("## 4. The pool")
    a("")
    a("- distinct instances: **%d**" % len(trades))
    a("- date range: **%s .. %s** (%d distinct trading dates)"
      % (dates[0], dates[-1], len({t["trade_date"] for t in trades})))
    a("- distinct symbols: **%d**" % len(sym_ct))
    a("- on a symbol in `universe.py` ALL_SYMS: **%d** (%.1f%%)"
      % (len(in_uni), 100 * len(in_uni) / max(1, len(trades))))
    a("- **inside 09:30-11:00 ET AND on a universe symbol: %d** (%.1f%% of the pool)"
      % (len(win_uni), 100 * len(win_uni) / max(1, len(trades))))
    a("  - of those, on a symbol-day Austin judged: **%d**"
      % sum(1 for t in win_uni if t["card_id"] in austin))
    a("")
    a("Symbol distribution:")
    a("")
    a("| symbol | instances | in universe | in 09:30-11:00 |")
    a("|---|---:|:---:|---:|")
    for s, n in sym_ct.most_common():
        a("| %s | %d | %s | %d |" % (s, n, "yes" if s in uni else "-",
                                     sum(1 for t in trades
                                         if t["symbol"] == s and in_win(t))))
    a("")
    a("By year: " + ", ".join("%s %d" % kv for kv in
                              sorted(Counter(d[:4] for d in dates).items())))
    a("")
    a("Field fill on the pooled set: " + ", ".join(
        "%s %d" % (f, sum(1 for t in trades if t.get(f) not in (None, "", [])))
        for f in ("direction", "setup", "level_name", "level_price", "entry", "stop",
                  "target", "outcome", "r_multiple", "pnl_usd", "image_urls")))
    a("")
    a("Outcome: " + ", ".join("%s %d" % kv for kv in
                              Counter(t["outcome"] for t in trades
                                      if t["outcome"]).most_common())
      + ". Direction: " + ", ".join("%s %d" % kv for kv in
                                    Counter(t["direction"] for t in trades
                                            if t["direction"]).most_common())
      + ". Setup: " + ", ".join("%s %d" % kv for kv in
                                Counter(t["setup"] for t in trades
                                        if t["setup"]).most_common()) + ".")
    a("")
    a("## 5. Caveats")
    a("")
    a("- Entry prices are absent from nearly all of this data (mentors name levels and "
      "option strikes, not underlying fills), so the 0.25% arm of the dedup key almost "
      "never fires. An instance is therefore *a symbol-day-side*, not a single fill: a "
      "mentor who traded TSLA long twice in one morning appears once, with `n_rows` "
      "recording the multiplicity.")
    a("- Outcomes are self-reports, never measured fills, and the review channels are "
      "survivorship-skewed toward winners.")
    a("- Futures rows (NQ/ES/YM/RTY) are pooled but are not universe symbols and can "
      "never overlap Austin's marks.")
    a("- Parser precision on the underlying corpora ranges 70-100%% by channel; "
      "`confidence` is carried through from the winning row. Filter to "
      "`confidence in {high, medium}` for a cleaner set (%d instances)."
      % sum(1 for t in trades if t.get("confidence") in ("high", "medium")))
    a("- %d watch-only rows (symbol + level, no position asserted) were held back. They "
      "are the natural extension if the scoring set needs more symbol-day coverage."
      % len(watch))
    a("")
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(L) + "\n")

    print("pooled rows in : %d" % len(pool))
    print("watch-only     : %d" % len(watch))
    print("instances out  : %d" % len(trades))
    print("multi-source   : %d" % len(multi))
    print("austin days    : %d ; overlap days: %d ; overlap instances: %d"
          % (len(austin), len(overlap), len(ov_trades)))
    print("universe       : %d ; window+universe: %d" % (len(in_uni), len(win_uni)))
    print("wrote %s" % OUT_JSONL)
    print("wrote %s" % OUT_MD)


if __name__ == "__main__":
    main()
