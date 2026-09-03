#!/usr/bin/env python3
"""Deterministic parser for discord_data/live-sessions.json.

CHANNEL REALITY (verified before writing a line of this parser):
  - 357 messages, one author ("Jdub"), 2024-03-31 .. 2026-08-19.
  - Every message is an INDEX POST: a session title naming one or more
    trading dates + the YouTube recording link(s) for those dates.
  - Zero ticker symbols appear in the whole channel (checked with a
    \\b[A-Z]{2,5}\\b scan over URL-stripped text -> the only hit is "OBS").
  - Zero attachments; embeds mirror the URLs already in `content`.
  - Only 4 messages carry a P&L annotation, e.g. "(-$2185)", "(+$4000)".

So the extractable judgement here is NOT setups/levels/entries -- the text
does not contain them. It is a session-date -> recording index, plus the
handful of day-level outcomes. Every field the text cannot support is null
by construction; nothing is inferred from prices, and no LLM is involved.

Extra (non-schema) fields are additive and carry the actual payload:
  kind, session_date, video_id, video_url, video_index, video_count,
  date_count, pnl_usd, trade_count, win_count, loss_count, no_trades,
  playlist_urls, other_urls.

Emits one row per (message x session_date x recording) pair.
Read-only on every Austin mark corpus. Writes only under research/corpus_sf/.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime

SRC = "discord_data/live-sessions.json"
OUT = "research/corpus_sf/live_sessions.jsonl"

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    # misspellings observed verbatim in the channel
    "febraury": 2, "apirl": 4, "septemeber": 9, "sept": 9,
}
MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))

# "April 22nd", "October 15", "May 9th"
DATE_RE = re.compile(r"\b(" + MONTH_RE + r")\s+(\d{1,2})(?:st|nd|rd|th)?\b", re.I)
# bare ordinal continuing the current month: "23rd", "28th"
ORD_RE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b")
RANGE_RE = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s*[-–]\s*(\d{1,2})(?:st|nd|rd|th)\b")

YT_ID_RE = re.compile(r"(?:youtu\.be/|youtube\.com/watch\?v=)([A-Za-z0-9_-]{11})")
YT_LIST_RE = re.compile(r"youtube\.com/playlist\?list=([A-Za-z0-9_-]+)")
URL_RE = re.compile(r"https?://\S+")

# "(-$2185)" "(+$4000)" "(+5500)" "(-800)"
PNL_RE = re.compile(r"\(\s*([+-])\s*\$?\s*([\d,]+)\s*\)")
TRADES_RE = re.compile(r"\b(\d+)\s+trades?\b", re.I)
WINS_RE = re.compile(r"\b(\d+)\s+wins?\b", re.I)
LOSS_RE = re.compile(r"\b(\d+)\s+loss(?:es)?\b", re.I)
NOTRADE_RE = re.compile(r"\bno\s+trades?\b", re.I)

SESSION_RE = re.compile(r"\blive\s+(?:trading\s+)?ses(?:s)?ions?\b|\blive\b\s*$", re.I)
QA_RE = re.compile(r"\bQ\s*&\s*A\b|answering questions", re.I)


def title_part(content):
    """Text with URLs, role pings and @everyone stripped -- the title."""
    t = URL_RE.sub(" ", content)
    t = re.sub(r"<@&\d+>", " ", t)
    t = re.sub(r"@everyone|@here", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def resolve_year(month, day, msg_dt):
    if not (1 <= day <= 31):
        return None
    for yr in (msg_dt.year, msg_dt.year - 1):
        try:
            cand = date(yr, month, day)
        except ValueError:
            continue
        delta = (msg_dt.date() - cand).days
        if -2 <= delta <= 120:  # posted same-day-ish, up to a season later
            return cand.isoformat()
    return None


def parse_session_dates(title, msg_dt):
    """Month-name anchored dates plus bare ordinals that continue the run.

    Handles "March 26th, 27th, 30th, 31st, April 1st, 2nd" and
    "December 15th-16th". Year inferred from the message timestamp: a title
    date is never in the future relative to the post, and posts lag the
    session by days, never by more than a season.
    """
    out = []
    anchors = list(DATE_RE.finditer(title))
    if not anchors:
        return out
    for i, a in enumerate(anchors):
        end = anchors[i + 1].start() if i + 1 < len(anchors) else len(title)
        month = MONTHS[a.group(1).lower()]
        days = [int(a.group(2))]
        tail = title[a.end():end]
        days += [int(m.group(1)) for m in ORD_RE.finditer(tail)]
        # a "15th-16th" range leaves the 2nd number without an ordinal suffix
        days += [int(m.group(2)) for m in RANGE_RE.finditer(title[a.start():end])]
        for d in days:
            iso = resolve_year(month, d, msg_dt)
            if iso and iso not in out:
                out.append(iso)
    return out


def parse_videos(content):
    """(recording ids in order, playlist urls, non-youtube urls)."""
    ids = []
    for m in YT_ID_RE.finditer(content):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    lists = ["https://www.youtube.com/playlist?list=" + m.group(1)
             for m in YT_LIST_RE.finditer(content)]
    other = [u for u in URL_RE.findall(content) if "youtu" not in u]
    return ids, lists, other


def parse_pnl(title):
    m = PNL_RE.search(title)
    if not m:
        return None
    val = float(m.group(2).replace(",", ""))
    return -val if m.group(1) == "-" else val


def outcome_from(pnl, wins, losses):
    """Only a stated result becomes an outcome. Mixed days stay null."""
    if pnl is not None:
        if pnl > 0:
            return "win"
        if pnl < 0:
            return "loss"
        return "be"
    if wins is not None and losses is not None:
        if wins and not losses:
            return "win"
        if losses and not wins:
            return "loss"
        return None  # "1 Win & 1 Loss" is not one outcome -- do not guess
    return None


def classify(title, ids, lists):
    if lists and not ids:
        return "playlist_index"
    if QA_RE.search(title):
        return "qa_session"
    if SESSION_RE.search(title):
        return "live_session"
    if ids:
        return "recording_link"
    return "other"


def build_rows(msgs, src_name):
    rows, skipped = [], []
    seen_videos = {}          # video_id -> first msg_id that carried it
    prev = None               # (msg, dates, ids) of the last kept message
    for m in msgs:
        content = m.get("content") or ""
        title = title_part(content)
        ts = m["ts"]
        try:
            msg_dt = datetime.fromisoformat(ts)
        except ValueError:
            skipped.append((m, "unparseable ts"))
            continue

        ids, lists, other = parse_videos(content)
        if not ids and not lists:  # embeds mirror content; only a fallback
            ids, lists, other2 = parse_videos(" ".join(m.get("embeds") or []))
            other = other or other2

        dates = parse_session_dates(title, msg_dt)

        # A bare-URL message is a continuation of the post above it: Jdub
        # sometimes sends the title and the link as two messages (2024-10-02).
        # Bind only when the previous post named dates and carried no link at
        # all, and the counts line up exactly.
        continued_from = None
        if not dates and ids and not title and prev is not None:
            p_msg, p_dates, p_ids = prev
            gap = (msg_dt - datetime.fromisoformat(p_msg["ts"])).total_seconds()
            if (p_dates and not p_ids and len(p_dates) == len(ids)
                    and p_msg.get("author") == m.get("author") and 0 <= gap <= 900):
                dates = list(p_dates)
                continued_from = p_msg["id"]
        pnl = parse_pnl(title)
        tc = TRADES_RE.search(title)
        wc = WINS_RE.search(title)
        lc = LOSS_RE.search(title)
        no_trades = bool(NOTRADE_RE.search(title))
        trade_count = 0 if no_trades else (int(tc.group(1)) if tc else None)
        wins = int(wc.group(1)) if wc else None
        losses = int(lc.group(1)) if lc else None
        kind = classify(title, ids, lists)

        if not dates and not ids and not lists:
            skipped.append((m, "no session date and no recording link"))
            continue

        aligned = len(ids) > 0 and len(dates) == len(ids)
        if aligned:
            # 1:1 in title order. Alignment IS the evidence -- it does not
            # depend on the title using the words "Live Session".
            pairs = list(zip(dates, ids, range(len(ids))))
        elif dates:
            # Counts disagree (a missing link, or one extra video from an
            # adjacent day he did not name). Attach nothing -- the mapping is
            # unknowable -- but never drop a recording: the unbound videos are
            # emitted below as dateless rows.
            pairs = [(d, None, None) for d in dates]
            pairs += [(None, v, i) for i, v in enumerate(ids)]
        else:
            # a playlist post, or a bare link that could not be bound
            pairs = [(None, v, i) for i, v in enumerate(ids)] or [(None, None, None)]

        single = len(dates) <= 1
        for sess_date, vid, vidx in pairs:
            if sess_date and vid:
                conf = "high"
            elif sess_date or vid:
                conf = "medium"
            else:
                conf = "low"
            if pnl is not None and not single:
                conf = "medium"  # P&L not attributable to one of many days
            wkd = None
            weekend = None
            lag = None
            if sess_date:
                sd = date.fromisoformat(sess_date)
                wkd = sd.isoformat() and sd.weekday()
                weekend = wkd >= 5
                lag = (msg_dt.date() - sd).days
                # the market is shut at the weekend: the title has a typo, or
                # the year inference picked wrong. Do not trust the date.
                if weekend or lag > 21:
                    conf = "medium" if conf == "high" else conf
            rows.append({
                "src": src_name,
                "msg_id": m["id"],
                "ts": ts,
                "author": m.get("author"),
                "symbol": None,
                "direction": None,
                "setup": None,
                "level_price": None,
                "level_name": None,
                "entry": None,
                "stop": None,
                "target": None,
                "outcome": outcome_from(pnl if single else None, wins, losses),
                "r_multiple": None,
                "quote": content,
                "image_urls": list(m.get("attachments") or []),
                "confidence": conf,
                # --- extra, channel-specific payload ---
                "kind": kind,
                "session_date": sess_date,
                "video_id": vid,
                "video_url": ("https://youtu.be/" + vid) if vid else None,
                "video_index": vidx,
                "video_count": len(ids),
                "date_count": len(dates),
                "pnl_usd": pnl if single else None,
                "trade_count": trade_count,
                "win_count": wins,
                "loss_count": losses,
                "no_trades": True if no_trades else None,
                "playlist_urls": lists or None,
                "other_urls": other or None,
                "session_weekday": wkd,
                "session_is_weekend": weekend or None,
                "post_lag_days": lag,
                "continued_from_msg_id": continued_from,
                "repost_of_msg_id": seen_videos.get(vid) if vid else None,
            })
        for v in ids:
            seen_videos.setdefault(v, m["id"])
        prev = (m, dates, ids)
    return rows, skipped


def main():
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    msgs = json.load(open(os.path.join(repo, SRC), encoding="utf-8"))
    rows, skipped = build_rows(msgs, "discord_data/live-sessions.json")
    out = os.path.join(repo, OUT)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    sess = sorted({r["session_date"] for r in rows if r["session_date"]})
    vids = {r["video_id"] for r in rows if r["video_id"]}
    msg_ids = {r["msg_id"] for r in rows}
    print("messages           %d" % len(msgs))
    print("messages extracted %d" % len(msg_ids))
    print("messages skipped   %d" % len(skipped))
    print("rows               %d" % len(rows))
    print("distinct sessions  %d  %s .. %s" % (len(sess), sess[0], sess[-1]))
    print("distinct videos    %d" % len(vids))
    for c in ("high", "medium", "low"):
        print("  conf %-7s%d" % (c, sum(1 for r in rows if r["confidence"] == c)))
    print("rows w/ outcome    %d" % sum(1 for r in rows if r["outcome"]))
    print("rows w/ pnl        %d" % sum(1 for r in rows if r["pnl_usd"] is not None))
    print("rows w/ video      %d" % sum(1 for r in rows if r["video_id"]))
    print("rows w/ date       %d" % sum(1 for r in rows if r["session_date"]))
    print("rows date+video    %d" % sum(1 for r in rows if r["session_date"] and r["video_id"]))
    print("weekend dates      %d" % sum(1 for r in rows if r["session_is_weekend"]))
    print("reposted videos    %d" % sum(1 for r in rows if r["repost_of_msg_id"]))
    print("continuation rows  %d" % sum(1 for r in rows if r["continued_from_msg_id"]))
    if "--skips" in sys.argv:
        for m, why in skipped:
            print("SKIP", m["id"], m["ts"], "|", why, "|", (m.get("content") or "")[:130])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
