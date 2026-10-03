"""Econ calendar helper: 10:00 ET news flag + FOMC staleness check (free feeds).

Report-only: never rewrites news_days.json. stdlib only.
Usage: python econ_calendar.py  -> writes news_week.json, prints today's flag + STALE line.
"""
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
ET = ZoneInfo("America/New_York")
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
UA = {"User-Agent": "Mozilla/5.0 (econ_calendar.py)"}
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def http_fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def fetch_ff_week(fetch=http_fetch) -> list:
    return json.loads(fetch(FF_URL))


def _hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def window_events(events, start="08:00", end="11:00", impacts=("High", "Medium"),
                  country="USD") -> list:
    """Events in [start, end] ET for country/impacts; adds et_date, et_time."""
    lo, hi = _hm(start), _hm(end)
    out = []
    for e in events:
        if e.get("country") != country or e.get("impact") not in impacts:
            continue
        try:
            dt = datetime.fromisoformat(e["date"]).astimezone(ET)
        except (KeyError, ValueError):
            continue
        mins = dt.hour * 60 + dt.minute
        if lo <= mins <= hi:
            out.append({**e, "et_date": dt.date().isoformat(), "et_time": dt.strftime("%H:%M")})
    return sorted(out, key=lambda x: (x["et_date"], x["et_time"]))


def news_flag(day_iso: str, events) -> list:
    """'HH:MM title (impact)' for events already window-filtered (see window_events)."""
    if events and "et_date" not in events[0]:
        events = window_events(events)
    return [f"{e['et_time']} {e['title']} ({e['impact']})"
            for e in events if e["et_date"] == day_iso]


def _decision_day(year: int, month_txt: str, dates_txt: str):
    m = re.match(r"\s*(\d+)\s*-\s*(\d+)", dates_txt.replace("*", ""))
    if not m:
        return None
    d1, d2 = int(m.group(1)), int(m.group(2))
    parts = [MONTHS.get(p.strip()[:3].lower()) for p in re.split(r"[/-]", month_txt) if p.strip()]
    if not parts or None in parts:
        return None
    month = parts[-1]  # decision (2nd) day falls in the last month named
    return date(year, month, d2).isoformat()


def fetch_fomc_dates(fetch=http_fetch) -> list:
    html = fetch(FOMC_URL)
    heads = list(re.finditer(r"(\d{4}) FOMC Meetings", html))
    out = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(html)
        sec = html[h.end():end]
        pairs = re.findall(
            r'fomc-meeting__month[^>]*>(.*?)</div>.*?fomc-meeting__date[^>]*>(.*?)</div>',
            sec, re.S)
        for mon, dts in pairs:
            d = _decision_day(int(h.group(1)), re.sub(r"<.*?>", "", mon), re.sub(r"<.*?>", "", dts))
            if d:
                out.append(d)
    return sorted(set(out))


def stale_report(fomc_dates, news_days: dict) -> dict:
    have = set(news_days.get("by_type", {}).get("FOMC", []))
    win = news_days.get("window", "")
    m = re.search(r"\.\.(\d{4}-\d{2}-\d{2})", win)
    wend = m.group(1) if m else None
    missing = [d for d in fomc_dates if d not in have and (not wend or d <= wend)]
    beyond = [d for d in fomc_dates if wend and d > wend]
    return {"window_end": wend, "missing_in_news_days": missing, "beyond_window": beyond}


def main() -> int:
    today = date.today().isoformat()
    evs = window_events(fetch_ff_week())
    (ROOT / "news_week.json").write_text(json.dumps(
        {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "fetched_date": today, "source": FF_URL, "events": evs}, indent=1))
    flag = news_flag(today, evs)
    print(f"TODAY {today}: " + ("; ".join(flag) if flag else "no High/Medium USD events 08:00-11:00 ET"))
    fomc = fetch_fomc_dates()
    print("FOMC decision days:", ", ".join(fomc))
    try:
        nd = json.loads((ROOT / "news_days.json").read_text())
    except (OSError, ValueError):
        nd = {}
    r = stale_report(fomc, nd)
    print(f"STALE: news_days window ends {r['window_end']}; "
          f"FOMC missing from news_days.json: {r['missing_in_news_days'] or 'none'}; "
          f"fed dates beyond window: {r['beyond_window'] or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
