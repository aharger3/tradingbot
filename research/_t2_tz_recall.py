"""T2 -- recompute chat-corpus recall with UTC timestamps (the target row).

Proves corpus_instances.jsonl `ts` is naive UTC via Discord snowflake decode,
restricts to trader channels, converts UTC->America/New_York, keeps rows in
the 09:30-11:00 ET scan window, then replays the OMEN engine over those
ticker-days using the stageh_replay.py pattern (wraps backtest_week.simulate_day,
stubs pf.fetch_day to [] on cache miss so the run is fully offline against
data_archive). Scoring reuses stageh_score.py's logic.

Writes research/corpus_tz_recall.md.
"""
import json, datetime, os, sys, pathlib, collections, random

ROOT = pathlib.Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from zoneinfo import ZoneInfo
import polygon_feed as pf
from backtest_week import simulate_day, htf_bias_for

UTC = ZoneInfo("UTC")
NY = ZoneInfo("America/New_York")
TRADER_CHANNELS = {"jdub-alerts", "scarface-alerts", "futures-alerts",
                   "premarket-charts", "swing-ideas"}
OPEN_MIN = 9 * 60 + 30
LOOKBACK = 6
ARCHIVE = ROOT / "data_archive"
INST = ROOT / "research" / "corpus_instances.jsonl"
OUT_REPLAY = ROOT / "research" / "corpus_tz_replay.jsonl"
OUT_CAND = ROOT / "research" / "corpus_tz_candidates.jsonl"
REPORT = ROOT / "research" / "corpus_tz_recall.md"

# ---- 1. load instances ----
rows = [json.loads(l) for l in INST.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
instances_total = len(rows)

# ---- 2. snowflake proof on 50 random rows ----
random.seed(42)
samp = random.sample(rows, 50)
snow_match = 0
for r in samp:
    ms = (int(r["msg_id"]) >> 22) + 1420070400000
    sf = datetime.datetime.fromtimestamp(ms / 1000, tz=UTC)
    stored = datetime.datetime.fromisoformat(r["ts"]).replace(tzinfo=UTC)
    if abs((sf - stored).total_seconds()) <= 2:
        snow_match += 1
assert snow_match == 50, f"snowflake proof failed: {snow_match}/50"
print(f"snowflake_utc_match: {snow_match}/50", flush=True)

# ---- 3. trader channels + ET window ----
trader = [r for r in rows if r["channel"] in TRADER_CHANNELS]
instances_trader = len(trader)

# each instance gets a trader direction/bias label from text for direction_agree
DIR_LONG = {"long", "call", "calls", "buy", "bull", "bullish"}
DIR_SHORT = {"short", "put", "puts", "sell", "bear", "bearish"}

def infer_dir(text):
    t = (text or "").lower()
    words = set(t.replace(",", " ").replace(".", " ").split())
    lo = bool(words & DIR_LONG)
    sh = bool(words & DIR_SHORT)
    if lo and not sh: return "long"
    if sh and not lo: return "short"
    return None

in_window = []  # (row, et_dt)
for r in trader:
    u = datetime.datetime.fromisoformat(r["ts"]).replace(tzinfo=UTC)
    e = u.astimezone(NY)
    if datetime.time(9, 30) <= e.time() < datetime.time(11, 0):
        in_window.append((r, e))
instances_in_et_window = len(in_window)

# ticker-days -> list of trader labels (direction + setup hint)
# a chat post on a weekend does not map to a trading session; restrict to weekdays
days = collections.defaultdict(list)
for r, e in in_window:
    session_date = e.strftime("%Y-%m-%d")
    if datetime.date.fromisoformat(session_date).weekday() >= 5:
        continue  # weekend -- no RTH session, no cached bars
    days[(r["symbol"], session_date)].append({
        "ticker": r["symbol"], "session_date": session_date,
        "direction": infer_dir(r.get("text", "")),
        "setup_label": None,  # chat instances carry no setup label
    })
ticker_days = len(days)
print(f"instances_trader_channels: {instances_trader}", flush=True)
print(f"instances_in_et_window: {instances_in_et_window}", flush=True)
print(f"ticker_days: {ticker_days}", flush=True)

# ---- 4. replay engine (stageh_replay pattern) ----
_missing = collections.Counter()
_real_fetch = pf.fetch_day

def fetch_cached_only(symbol, day_iso):
    if (ARCHIVE / symbol / f"{day_iso}.csv").exists():
        return _real_fetch(symbol, day_iso)
    _missing[symbol] += 1
    return []

pf.fetch_day = fetch_cached_only

covered = collections.defaultdict(set)
for (sym, d) in days:
    covered[sym].add(d)
all_syms = sorted(covered)

g_min = min(min(v) for v in covered.values())
g_max = max(max(v) for v in covered.values())

def trading_days(d0, d1):
    out, d, end = [], datetime.date.fromisoformat(d0), datetime.date.fromisoformat(d1)
    while d <= end:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out

all_weekdays = trading_days(
    (datetime.date.fromisoformat(g_min) - datetime.timedelta(days=120)).isoformat(), g_max)
wd_index = {d: i for i, d in enumerate(all_weekdays)}

def context_days_for(day):
    di = wd_index[day]
    return [all_weekdays[k] for k in range(max(0, di - LOOKBACK), di + 1)]

def hourly_from_1m(day, rth):
    y, m, dd = map(int, day.split("-"))
    by_hour = {}
    for c in rth:
        by_hour[int(c.timestamp[:2])] = c.close
    return [(datetime.datetime(y, m, dd, h), close) for h, close in sorted(by_hour.items())]

def load_days(sym, days):
    out = {}
    for d in sorted(days):
        try:
            b = pf.fetch_day(sym, d)
        except Exception:
            continue
        if not b:
            continue
        rth = pf.rth(b)
        if len(rth) >= 30:
            out[d] = (b, rth)
    return out

# QQQ key-level breaks over every context day any symbol needs
qqq_need = set()
for ds in covered.values():
    for d in ds:
        qqq_need.update(context_days_for(d))
qqq_bars = load_days("QQQ", qqq_need)
qqq_keys = sorted(qqq_bars)
qqq_brk = {}
for prev, d in zip(qqq_keys, qqq_keys[1:]):
    _, prth = qqq_bars[prev]
    pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
    b, rth = qqq_bars[d]
    pmh, pml = pf.premarket_hi_lo(b)
    ups = [l for l in (pdh, pmh) if l is not None]
    dns = [l for l in (pdl, pml) if l is not None]
    qqq_brk[d] = {"up": next((c.timestamp for c in rth if any(c.close > l for l in ups)), None),
                  "dn": next((c.timestamp for c in rth if any(c.close < l for l in dns)), None)}
print(f"qqq: {len(qqq_brk)} break days", flush=True)

fires = 0
skipped_days = 0
fired_days = set()
efire = collections.defaultdict(list)
with OUT_REPLAY.open("w", encoding="utf-8") as fh, OUT_CAND.open("w", encoding="utf-8") as cand:
    for si, sym in enumerate(all_syms, 1):
        need = set()
        for d in covered[sym]:
            need.update(context_days_for(d))
        day_bars = load_days(sym, need)
        hourly, prev, sym_fires = [], None, 0
        for d in sorted(day_bars):
            b, rth = day_bars[d]
            if prev:
                _, prth = day_bars[prev]
                pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
                pdo, pdc = prth[0].open, prth[-1].close
            else:
                pdh = pdl = pdo = pdc = None
            pmh, pml = pf.premarket_hi_lo(b)
            bias = htf_bias_for(hourly, d)
            if d in covered[sym]:
                for t in simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml, pdo, pdc,
                                      qqq=qqq_brk.get(d)):
                    cand.write(json.dumps({
                        "symbol": t.symbol, "day": t.day, "status": t.status,
                        "setup": t.signal_type, "grade": t.grade,
                        "direction": t.direction, "entry_time": t.entry_time,
                    }) + "\n")
                    if t.status != "fired":
                        continue
                    hh, mm, _ = t.entry_time.split(":")
                    rec = {
                        "symbol": t.symbol, "day": t.day,
                        "minute_i": int(hh) * 60 + int(mm) - OPEN_MIN,
                        "entry_time": t.entry_time, "direction": t.direction,
                        "grade": t.grade, "entry": t.entry, "stop": t.stop,
                        "target": t.target, "setup": t.signal_type,
                        "outcome": t.outcome, "exit_price": getattr(t, "exit_price", None),
                    }
                    fh.write(json.dumps(rec) + "\n")
                    efire[(t.symbol, t.day)].append(rec)
                    fires += 1
                    sym_fires += 1
                    fired_days.add((sym, d))
            hourly += hourly_from_1m(d, rth)
            prev = d
        missing_here = len(covered[sym] - set(day_bars))
        skipped_days += missing_here
        if si % 10 == 0 or si == len(all_syms):
            print(f"[{si}/{len(all_syms)} {sym}] loaded={len(day_bars)} "
                  f"skipped={missing_here} fires={sym_fires}", flush=True)

engine_fired_days = len(fired_days)
print(f"engine_fired_days: {engine_fired_days} fires={fires} skipped={skipped_days}", flush=True)

# ---- 5. score (stageh_score pattern) ----
hit = [k for k in days if k in efire]
recall_pct = 100 * len(hit) / len(days) if days else 0.0

# direction agreement on days where both exist (only trader rows with a dir)
dirmatch = 0
dirtotal = 0
for k in hit:
    tdirs = {(m["direction"]) for m in days[k] if m["direction"]}
    if not tdirs:
        continue
    edirs = {"long" if e["direction"] == "call" else "short" for e in efire[k]}
    dirtotal += 1
    if tdirs & edirs:
        dirmatch += 1
direction_agree = f"{dirmatch}/{dirtotal}"

# ---- 6. report ----
REPORT.write_text(
    f"# T2 -- chat-corpus recall with UTC timestamps\n\n"
    f"Snowflake proof: 50 random rows, "
    f"`(int(msg_id)>>22)+1420070400000` ms decoded as UTC vs stored `ts`, "
    f"matched to within 2s. All 50 passed -- `ts` is naive UTC.\n\n"
    f"Trader channels: {', '.join(sorted(TRADER_CHANNELS))}. "
    f"UTC->America/New_York, keep ET time in 09:30-11:00 (OMEN scan window). "
    f"Engine replayed offline against data_archive "
    f"(pf.fetch_day stubbed to [] on cache miss).\n\n"
    f"```\n"
    f"snowflake_utc_match: 50/50\n"
    f"instances_total: {instances_total}\n"
    f"instances_trader_channels: {instances_trader}\n"
    f"instances_in_et_window: {instances_in_et_window}\n"
    f"ticker_days: {ticker_days}\n"
    f"engine_fired_days: {engine_fired_days}\n"
    f"recall_pct: {recall_pct:.1f}\n"
    f"direction_agree: {direction_agree}\n"
    f"prior_claimed_recall_pct: 0.0\n"
    f"```\n",
    encoding="utf-8")
print(f"recall_pct: {recall_pct:.1f} direction_agree: {direction_agree}", flush=True)
print(f"wrote {REPORT}", flush=True)
