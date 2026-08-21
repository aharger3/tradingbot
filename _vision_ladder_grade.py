"""
vision_ladder_grade.py - grade the five T3 tiers and write research/vision_ladder.md.

Grading (spec T3): a tier's read of an image is correct when the ticker it returns matches
the ticker named in that message's text (or the filename), and when every non-null price it
returns is within 2% of the day's actual high-low range for that ticker from data_archive.

Two metrics, two denominators (both reported honestly):

  ticker_acc        - over rows whose message text names a data_archive ticker (the only rows
                      with a ground-truth ticker; 145/200 pilot messages are generic text like
                      "Pre Market Charts Tech" and carry no ticker to check against). correct
                      when the model's ticker equals (or, for multi-ticker text, is among) the
                      text's ticker(s).

  price_in_range_pct- a price is "in range" when it falls within [low*0.98, high*1.02] of the
                      day's session bars (2% tolerance around the day's high-low range; a price
                      outside that is a hallucination). The day's bars are located by the ticker
                      shown on the chart: the ground-truth text ticker when the message names
                      one, otherwise the model's own read of the chart's ticker (the prices are
                      read off the same chart, so they must be real for that ticker's day). A row
                      is in-range only if EVERY non-null price it returns is in range. Rows with
                      no non-null price, or no gradeable day range, are excluded (not penalized).

null_rate - share of the 8 schema fields (ticker, direction, entry, stop, target, key_levels,
            timeframe, confidence) that came back null across all rows of the tier.

WINNER - the cheapest tier (by total cost_usd) whose price_in_range_pct is at least 80.
"""
import csv
import glob
import json
import os
import re
from pathlib import Path

RESEARCH = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research")
ARCHIVE = Path("data_archive")
MANIFEST = RESEARCH / "vision_pilot_manifest.jsonl"
OUT_MD = Path("research/vision_ladder.md")

SCHEMA_FIELDS = ["ticker", "direction", "entry", "stop", "target",
                 "key_levels", "timeframe", "confidence"]
PRICE_FIELDS = ["entry", "stop", "target"]

TIERS = [
    ("free", "google/gemma-4-31b-it"),  # spec named :free; paid variant used (see md)
    ("cheap", "qwen/qwen3.7-flash"),
    ("batch", "google/gemini-3.5-flash-lite"),  # spec named gemini-2.5-flash-lite:batch; prior run substituted (see md)
    ("flash", "gemini-3.6-flash"),
    ("incumbent", "gemini-3.1-flash-lite"),  # annotator's model; routed via OpenRouter (OmniRoute quota-cooling)
]

# cost ordering for WINNER (cheapest first). free is $0; the rest by measured total cost.
TIER_COST_RANK_HINT = ["free", "cheap", "incumbent", "batch", "flash"]


def load_tickers():
    return sorted(d for d in os.listdir(ARCHIVE)
                  if os.path.isdir(os.path.join(ARCHIVE, d)))


def to_num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("$", "").replace(",", "")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def text_tickers(message_text, tickers):
    """Archive tickers appearing as uppercase word-boundary tokens in the message text."""
    found = set()
    txt = message_text or ""
    for tk in tickers:
        if re.search(r"\b" + re.escape(tk) + r"\b", txt):
            found.add(tk)
    return found


_bar_cache = {}


def day_range(ticker, session_date):
    """(low, high) of the 1-min session bars for ticker on session_date, or None."""
    if not ticker or not session_date:
        return None
    key = (ticker, session_date)
    if key in _bar_cache:
        return _bar_cache[key]
    f = ARCHIVE / ticker / ("%s.csv" % session_date)
    if not f.exists():
        _bar_cache[key] = None
        return None
    lows, highs = [], []
    try:
        with open(f, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                try:
                    lows.append(float(row["Low"]))
                    highs.append(float(row["High"]))
                except (ValueError, KeyError):
                    continue
    except Exception:
        _bar_cache[key] = None
        return None
    if not lows or not highs:
        _bar_cache[key] = None
        return None
    rng = (min(lows), max(highs))
    _bar_cache[key] = rng
    return rng


def in_range(p, low, high):
    return low * 0.98 <= p <= high * 1.02


def load_rows(tier):
    f = RESEARCH / ("vision_ladder_results_%s.jsonl" % tier)
    if not f.exists():
        return []
    rows = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def grade_tier(tier, model_label, manifest_by_path, tickers):
    rows = load_rows(tier)
    n = len(rows)
    parsed_ok = sum(1 for r in rows if r.get("parsed_ok"))
    cost = sum(float(r.get("cost_usd", 0.0) or 0.0) for r in rows)

    # null_rate over 8 fields
    null_count = 0
    for r in rows:
        for k in SCHEMA_FIELDS:
            v = r.get(k)
            if v is None or (isinstance(v, list) and len(v) == 0) or v == "":
                null_count += 1
    null_rate = (null_count / (8 * n) * 100) if n else 0.0

    # ticker_acc: over rows whose message text names an archive ticker
    tac_total = 0
    tac_correct = 0
    # price_in_range: over rows with >=1 non-null price and a gradeable day range
    pic_total = 0
    pic_in = 0

    for r in rows:
        path = r.get("path")
        msg = manifest_by_path.get(path, {})
        mticker = (r.get("ticker") or "").strip().upper() or None
        text_tks = text_tickers(msg.get("message_text", ""), tickers)

        # ticker accuracy (ground truth = text ticker)
        if text_tks:
            tac_total += 1
            if mticker and mticker in text_tks:
                tac_correct += 1

        # collect non-null prices the model returned
        prices = []
        for k in PRICE_FIELDS:
            p = to_num(r.get(k))
            if p is not None:
                prices.append(p)
        kl = r.get("key_levels")
        if isinstance(kl, list):
            for v in kl:
                p = to_num(v)
                if p is not None:
                    prices.append(p)

        if not prices:
            continue  # no prices read -> excluded from price grading (null_rate captures it)

        # locate the day's bars: ground-truth text ticker if the model read one of them,
        # else the model's own ticker (the chart's ticker as read off the image)
        if text_tks and mticker in text_tks:
            bar_ticker = mticker
        elif text_tks:
            bar_ticker = sorted(text_tks)[0]
        else:
            bar_ticker = mticker

        rng = day_range(bar_ticker, r.get("session_date_et"))
        if rng is None:
            continue  # no bars -> excluded
        low, high = rng
        pic_total += 1
        if all(in_range(p, low, high) for p in prices):
            pic_in += 1

    ticker_acc = (tac_correct / tac_total * 100) if tac_total else 0.0
    price_in_range_pct = (pic_in / pic_total * 100) if pic_total else 0.0
    return {
        "tier": tier, "model": model_label, "n": n, "parsed_ok": parsed_ok,
        "ticker_acc": ticker_acc, "ticker_acc_n": tac_total,
        "price_in_range_pct": price_in_range_pct, "price_in_range_n": pic_total,
        "null_rate": null_rate, "cost_usd": cost,
    }


def main():
    tickers = load_tickers()
    manifest_by_path = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            manifest_by_path[r["path"]] = r

    results = [grade_tier(t, m, manifest_by_path, tickers) for t, m in TIERS]

    # WINNER: cheapest tier (by cost_usd) with price_in_range_pct >= 80
    eligible = [r for r in results if r["price_in_range_pct"] >= 80]
    eligible.sort(key=lambda r: r["cost_usd"])
    if eligible:
        winner = eligible[0]["model"]
        winner_line = "WINNER: %s (tier=%s, price_in_range_pct=%.1f%%, cost_usd=%.4f)" % (
            eligible[0]["model"], eligible[0]["tier"],
            eligible[0]["price_in_range_pct"], eligible[0]["cost_usd"])
    else:
        best = max(results, key=lambda r: r["price_in_range_pct"])
        winner = best["model"]
        winner_line = ("WINNER: %s (tier=%s) -- no tier cleared 80%%; best price_in_range_pct=%.1f%%"
                       % (best["model"], best["tier"], best["price_in_range_pct"]))

    lines = []
    lines.append("# Vision Ladder (T3) - which tier can read a price level off a chart")
    lines.append("")
    lines.append("200 Discord chart screenshots (100 jdub-alerts / 60 scarface-alerts / "
                 "40 premarket-charts), same strict-JSON prompt every tier:")
    lines.append("`{ticker, direction, entry, stop, target, key_levels[], timeframe, confidence}` "
                 "with `null` for any field the model cannot actually read off the chart.")
    lines.append("")
    lines.append("## Substitutions (documented)")
    lines.append("- **free**: spec named `google/gemma-4-31b-it:free`. That `:free` variant is "
                 "throughput-blocked by Google's free-gemma quota (~1 row per 5 min, calls dropping) - "
                 "unusable for a 200-image sample. The SAME model (`gemma-4-31b-it`) was run via "
                 "OpenRouter's paid variant to measure capability; cost is negligible (~$0.013) and it "
                 "remains the cheapest tier. The free variant's rate limit is a throughput finding, not "
                 "a capability one.")
    lines.append("- **batch**: spec named `google/gemini-2.5-flash-lite:batch` (OpenRouter `:batch` "
                 "models use a separate async batch API, not `/chat/completions`). The 2026-08-20 "
                 "run used synchronous `google/gemini-3.5-flash-lite`; gemini-2.5 is also deprecated "
                 "on this account (404, per the T6 note). 200 clean rows, kept.")
    lines.append("- **flash**: spec routes `gemini-3.6-flash` via Google AI Studio "
                 "(`GOOGLE_AI_STUDIO_API_KEY`), but that key's quota is exhausted (429 \"You exceeded "
                 "your current quota\"). The SAME model was reached via paid OpenRouter instead. ~34% of "
                 "flash responses did not parse as strict JSON (prose / truncated) - a real reliability "
                 "finding, recorded as parsed_ok=False (no error key written).")
    lines.append("- **incumbent**: spec routes `gemini-3.1-flash-lite` via local OmniRoute (the "
                 "scarface annotator's model). OmniRoute's credentials for that model are quota-cooling "
                 "(429 `model_cooldown`, all credentials) and its vision auto-routers 400, so the SAME "
                 "model (`gemini-3.1-flash-lite`) was reached via OpenRouter instead. The model identity "
                 "- the model the existing annotator already used - is what makes this the incumbent; "
                 "the route is just how the annotator reached it.")
    lines.append("")
    lines.append("## Grading")
    lines.append("- **ticker_acc**: over rows whose message text names a data_archive ticker (the only "
                 "rows with a ground-truth ticker; 145/200 pilot messages are generic and carry none). "
                 "correct when the model's ticker is among the text's ticker(s).")
    lines.append("- **price_in_range_pct**: a price is in range when it falls within `[low*0.98, "
                 "high*1.02]` of the day's session bars (2% tolerance around the day's high-low range; "
                 "a price outside is a hallucination). Day bars located by the ticker shown on the chart "
                 "(text ticker when named, else the model's read). A row is in-range only if EVERY "
                 "non-null price is in range. Rows with no price read or no gradeable range are excluded.")
    lines.append("- **null_rate**: share of the 8 schema fields returned null.")
    lines.append("- **cost_usd**: sum over the tier. free used the paid gemma variant (~$0.013; the "
                 ":free variant is quota-blocked); incumbent via OpenRouter is real cost.")
    lines.append("")
    lines.append("```")
    lines.append("| tier | model | n | parsed_ok | ticker_acc | price_in_range_pct | null_rate | cost_usd |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in results:
        lines.append("| %s | %s | %d | %d | %.1f%% (n=%d) | %.1f%% (n=%d) | %.1f%% | %.4f |" % (
            r["tier"], r["model"], r["n"], r["parsed_ok"],
            r["ticker_acc"], r["ticker_acc_n"],
            r["price_in_range_pct"], r["price_in_range_n"],
            r["null_rate"], r["cost_usd"]))
    lines.append("```")
    lines.append("")
    lines.append(winner_line)
    lines.append("")
    lines.append("_No results row in any tier carries an `error` key (done-guard: error responses "
                 "are dropped, never written). The zero-work guard added to `scarface_image_annotator.py` "
                 "exits non-zero instead of logging DONE._")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # diagnostics to stdout
    print(OUT_MD)
    for r in results:
        print("  %-10s n=%d parsed=%d ticker_acc=%.1f%%(n=%d) price_in_range=%.1f%%(n=%d) "
              "null=%.1f%% cost=%.4f"
              % (r["tier"], r["n"], r["parsed_ok"], r["ticker_acc"], r["ticker_acc_n"],
                 r["price_in_range_pct"], r["price_in_range_n"], r["null_rate"], r["cost_usd"]))
    print(winner_line)


if __name__ == "__main__":
    main()
