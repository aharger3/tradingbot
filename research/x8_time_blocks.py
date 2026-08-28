#!/usr/bin/env python
"""X8 -- strategy filters and time blocks on the 2-year book.

Slices research/g3_arm_ow1.json (the shipped ON_WATCH=1 book, 1017 traded rows)
every way a filter could be cut, reports n / mean R / win% / months green / 95% CI,
splits the two years in half chronologically to kill one-half-only filters, and
prices a combined arm against the incumbent.

Conventions, matched to the rest of the repo:
  win rate  = wins / (wins + losses)   -- scratches out of the denominator
  months green = months with sum(R) > 0, out of months the slice occupies
  95% CI    = 1.96 * sd / sqrt(n) on the mean R (normal approx). n < 30 is printed
              but must not be read as evidence.
  delta CI  = Welch 95% CI on (slice mean R - complement mean R). This is the
              honest test for a DISJOINT cut. The +/-0.0095 R house error bar came
              from an A/B where both arms share almost every trade; it is a FLOOR on
              what counts as signal, not the bar a disjoint slice has to clear.
  survival  = the slice beats ITS OWN HALF's baseline in BOTH chronological halves,
              with n >= 15 in each. H1 mean is +0.838R and H2 is +1.036R, so testing
              a slice against the pooled +0.955R would fail H1 slices for free.

LOOK-AHEAD: `scaled` and `bars` are OUTCOMES, not filters -- `scaled=True` is
"the trade reached the scale-out", i.e. it won, and `bars` is how long it ran.
They are reported as DESCRIPTIVE ONLY and are excluded from every arm.

Usage:  python research/x8_time_blocks.py
"""
import json, math, collections, statistics, os

BOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "g3_arm_ow1.json")
HOUSE_BAR = 0.0095          # the narrow A/B error bar (wide bar retired 2026-08-28)
SPLIT_DAY = "2025-08-21"    # midpoint of 2024-08-21 .. 2026-08-21

# Dimensions that are outcomes of the trade, not properties knowable at entry.
LOOKAHEAD = {"scaled", "bars held"}


# ---------------------------------------------------------------- primitives
def load():
    with open(BOOK) as f:
        d = json.load(f)
    return d["meta"], d["trades"]


def stats(rows):
    n = len(rows)
    if n == 0:
        return dict(n=0, mean=float("nan"), ci=float("nan"), win=float("nan"),
                    mg=0, mtot=0, total=0.0, sd=float("nan"))
    rs = [t["r"] for t in rows]
    mean = sum(rs) / n
    sd = statistics.stdev(rs) if n > 1 else float("nan")
    ci = 1.96 * sd / math.sqrt(n) if n > 1 else float("nan")
    w = sum(1 for t in rows if t["out"] == "win")
    l = sum(1 for t in rows if t["out"] == "loss")
    win = 100.0 * w / (w + l) if (w + l) else float("nan")
    m = collections.defaultdict(float)
    for t in rows:
        m[t["ym"]] += t["r"]
    return dict(n=n, mean=mean, ci=ci, win=win,
                mg=sum(1 for v in m.values() if v > 0), mtot=len(m),
                total=sum(rs), sd=sd)


def welch(a, b):
    """(mean(a)-mean(b), 95% CI half-width)."""
    if len(a) < 2 or len(b) < 2:
        return float("nan"), float("nan")
    va, vb = statistics.variance(a), statistics.variance(b)
    se = math.sqrt(va / len(a) + vb / len(b))
    return sum(a) / len(a) - sum(b) / len(b), 1.96 * se


def fmt(label, st, delta=None, dh=None, width=32):
    d = ""
    if delta is not None and not math.isnan(delta):
        sig = "SIG" if abs(delta) > dh and abs(delta) > HOUSE_BAR else "  ."
        d = "  d=%+7.4f +/-%6.4f %s" % (delta, dh, sig)
    return "%-*s n=%4d  meanR=%+7.4f +/-%6.4f  win=%5.1f%%  mg=%2d/%-2d%s" % (
        width, label[:width], st["n"], st["mean"], st["ci"], st["win"],
        st["mg"], st["mtot"], d)


# ---------------------------------------------------------------- bucketing
def block(et, size):
    mins = int(et[:2]) * 60 + int(et[3:])
    base = 9 * 60 + 30
    lo = base + ((mins - base) // size) * size
    return "%02d:%02d-%02d:%02d" % (lo // 60, lo % 60,
                                    (lo + size) // 60, (lo + size) % 60)


def barsb(b):
    if b <= 2:  return "1-2 bars"
    if b <= 5:  return "3-5 bars"
    if b <= 10: return "6-10 bars"
    if b <= 20: return "11-20 bars"
    return "21+ bars"


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ORDER15 = ["09:30-09:45", "09:45-10:00", "10:00-10:15", "10:15-10:30",
           "10:30-10:45", "10:45-11:00"]
ORDER5 = ["09:30-09:35", "09:35-09:40", "09:40-09:45", "09:45-09:50",
          "09:50-09:55", "09:55-10:00"]


def dimensions():
    dows = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    return [
        ("entry block 15m", lambda t: block(t["et"], 15), ORDER15),
        ("entry block 5m (first 30min)",
         lambda t: block(t["et"], 5) if t["et"] < "10:00" else None, ORDER5),
        ("seq (arrival order in SYMBOL-day)", lambda t: str(t["seq"]) if t["seq"] <= 3 else "4+", None),
        ("side", lambda t: t["side"], None),
        ("level", lambda t: t["level"], None),
        ("stopb", lambda t: t["stopb"], None),
        ("gapb", lambda t: t["gapb"], None),
        ("rangeb", lambda t: t["rangeb"], None),
        ("vol_regime", lambda t: t["vol_regime"], None),
        ("spy_trend", lambda t: t["spy_trend"], None),
        ("aligned", lambda t: t["aligned"], None),
        ("bias", lambda t: t["bias"], None),
        ("sgrade (Austin ladder)", lambda t: t["sgrade"], ["S", "A", "C"]),
        ("tripped (downgrade count)", lambda t: t["tripped"], None),
        ("confluence", lambda t: t["confluence"], None),
        ("setup", lambda t: t["setup"], None),
        ("legacy grade", lambda t: t["grade"], None),
        ("day of week", lambda t: t["dow"], dows),
        ("month of year", lambda t: MONTHS[int(t["day"][5:7]) - 1], MONTHS),
        ("symbol", lambda t: t["sym"], None),
        # ---- look-ahead, descriptive only, never used in an arm ----
        ("bars held", lambda t: barsb(t["bars"]),
         ["1-2 bars", "3-5 bars", "6-10 bars", "11-20 bars", "21+ bars"]),
        ("scaled", lambda t: str(t["scaled"]), None),
    ]


E15 = lambda t: t["et"] < "09:45"
E30 = lambda t: t["et"] < "10:00"
E45 = lambda t: t["et"] < "10:15"


def interactions():
    return [
        ("09:30-09:45 x seq==1", lambda t: E15(t) and t["seq"] == 1),
        ("S-grade x first 15min", lambda t: E15(t) and t["sgrade"] == "S"),
        ("S-grade x first 30min", lambda t: E30(t) and t["sgrade"] == "S"),
        ("tight/mid stop x first 15min", lambda t: E15(t) and t["stopb"] in ("tight", "mid")),
        ("with-trend x first 15min", lambda t: E15(t) and t["aligned"] == "with"),
        ("with-trend x first 30min", lambda t: E30(t) and t["aligned"] == "with"),
        ("first 15min x big range day", lambda t: E15(t) and t["rangeb"] == "big range"),
        ("first 15min x confluence yes", lambda t: E15(t) and t["confluence"] == "yes"),
        ("first 15min x S-or-A", lambda t: E15(t) and t["sgrade"] in ("S", "A")),
        ("first 15min x calm vol", lambda t: E15(t) and t["vol_regime"] == "calm"),
        ("first 15min x wild vol", lambda t: E15(t) and t["vol_regime"] == "wild"),
        ("first 15min x short", lambda t: E15(t) and t["side"] == "S"),
        ("first 15min x long", lambda t: E15(t) and t["side"] == "L"),
        ("first 30min x tight/mid stop", lambda t: E30(t) and t["stopb"] in ("tight", "mid")),
        ("first 30min x confluence yes", lambda t: E30(t) and t["confluence"] == "yes"),
        ("first 30min x big gap", lambda t: E30(t) and t["gapb"] == "big gap"),
        ("first 30min x big range day", lambda t: E30(t) and t["rangeb"] == "big range"),
    ]


# ---------------------------------------------------------------- arm ladder
def arms():
    """Nested ex-ante arms, each a superset filter of the one below.

    Ordered so Austin can read the price of each extra condition in trades given up.
    """
    big = lambda t: t["rangeb"] == "big range"
    gap = lambda t: t["gapb"] != "flat"
    wt = lambda t: t["aligned"] == "with"
    cf = lambda t: t["confluence"] == "yes"
    sa = lambda t: t["sgrade"] in ("S", "A")
    return [
        ("A0  incumbent (no filter)", lambda t: True),
        ("A1  drop 10:45-11:00 only", lambda t: t["et"] < "10:45"),
        ("A2  first 45 min (< 10:15)", E45),
        ("A3  first 30 min (< 10:00)", E30),
        ("A4  first 15 min (< 09:45)", E15),
        ("B1  A3 + with-trend", lambda t: E30(t) and wt(t)),
        ("B2  B1 + big-range day", lambda t: E30(t) and wt(t) and big(t)),
        ("B3  B2 + not a flat gap", lambda t: E30(t) and wt(t) and big(t) and gap(t)),
        ("B4  B3 + confluence yes", lambda t: E30(t) and wt(t) and big(t) and gap(t) and cf(t)),
        ("B5  B4 + sgrade S or A", lambda t: E30(t) and wt(t) and big(t) and gap(t) and cf(t) and sa(t)),
        ("C1  drop only the dead slices", lambda t: (t["et"] < "10:45"
                                                     and t["rangeb"] != "quiet"
                                                     and t["level"] != "other"
                                                     and t["setup"] != "one_candle_rule")),
        ("C2  C1 + drop rangeb=normal", lambda t: (t["et"] < "10:45"
                                                   and t["rangeb"] == "big range"
                                                   and t["level"] != "other"
                                                   and t["setup"] != "one_candle_rule")),
        ("C3  C2 + drop flat gaps", lambda t: (t["et"] < "10:45"
                                               and t["rangeb"] == "big range"
                                               and t["gapb"] != "flat"
                                               and t["level"] != "other"
                                               and t["setup"] != "one_candle_rule")),
    ]


# ---------------------------------------------------------------- report
def main():
    meta, alltr = load()
    rows = [t for t in alltr if t.get("traded")]
    shadow = [t for t in alltr if not t.get("traded") and t.get("out") in ("win", "loss", "scratch")]
    h1 = [t for t in rows if t["day"] < SPLIT_DAY]
    h2 = [t for t in rows if t["day"] >= SPLIT_DAY]
    base, b1, b2 = stats(rows), stats(h1), stats(h2)

    out = []
    P = out.append
    P("X8 -- strategy filters and time blocks on the 2-year book")
    P("book: research/g3_arm_ow1.json  %s..%s  %d sessions  %d symbols  %d signals  %d traded"
      % (meta["first"], meta["last"], meta["sessions"], len(meta["symbols"]),
         meta["signals"], meta["traded"]))
    P("house A/B error bar (shared-arm floor): +/-%.4f R" % HOUSE_BAR)
    P("=" * 104)
    P("")
    P("BASELINE (incumbent, ON_WATCH=1 2-year book)")
    P("  " + fmt("all traded", base))
    P("  " + fmt("H1  %s..%s" % (meta["first"], SPLIT_DAY), b1))
    P("  " + fmt("H2  %s..%s" % (SPLIT_DAY, meta["last"]), b2))
    P("  totalR=%+.1f  sd=%.4f" % (base["total"], base["sd"]))
    P("")

    findings = {}

    def record(name, sel, dim=None):
        sl = [t for t in rows if sel(t)]
        comp = [t for t in rows if not sel(t)]
        dl, dh = welch([t["r"] for t in sl], [t["r"] for t in comp])
        st = stats(sl)
        findings[name] = dict(st=st, d=dl, dh=dh, sel=sel, dim=dim)
        return st, dl, dh

    for name, keyfn, order in dimensions():
        tag = "  [LOOK-AHEAD, descriptive only -- not usable as a filter]" \
            if name in LOOKAHEAD else ""
        P("### " + name + tag)
        groups = collections.defaultdict(list)
        for t in rows:
            k = keyfn(t)
            if k is not None:
                groups[k].append(t)
        keys = order if order else sorted(groups, key=lambda k: -stats(groups[k])["mean"])
        for k in keys:
            if k not in groups:
                continue
            sel = (lambda f, kk: (lambda t: f(t) == kk))(keyfn, k)
            st, dl, dh = record(name + " = " + str(k), sel, dim=name)
            P("  " + fmt(str(k), st, dl, dh))
        P("")

    P("### tags (membership vs non-members)")
    for tg in sorted({x for t in rows for x in t["tags"]}):
        sel = (lambda g: (lambda t: g in t["tags"]))(tg)
        st, dl, dh = record("tag:" + tg, sel, dim="tags")
        P("  " + fmt("tag:" + tg, st, dl, dh))
    P("")

    P("### interactions (vs the rest of the book)")
    for name, pred in interactions():
        st, dl, dh = record(name, pred, dim="interaction")
        P("  " + fmt(name, st, dl, dh))
    P("")

    # ------------------------------------------------ arrival order, properly
    P("=" * 104)
    P("ARRIVAL ORDER -- why the seq slice cannot be measured on the traded book")
    P("  seq is arrival order within a (symbol, day) pair, NOT within the calendar day.")
    P("  The book takes up to 8 trades on one calendar day, one per symbol.")
    sq = collections.Counter(t["seq"] for t in rows)
    P("  traded-book seq histogram: %s" % dict(sorted(sq.items())))
    P("  %d of %d traded rows (%.1f%%) are seq==1. There is no seq>=3 row at all."
      % (sq.get(1, 0), len(rows), 100.0 * sq.get(1, 0) / len(rows)))
    P("  The incumbent selector IS 'first with-trend signal of the symbol-day', so seq")
    P("  is a constant inside the book. The edge of seq==1 has to be measured on the")
    P("  population the selector chose FROM -- the resolved non-traded rows.")
    P("")
    P("  resolved non-traded (shadow) rows: %d" % len(shadow))
    xs = [t for t in shadow if t["grade"] == "X"]
    P("  %d of them are legacy grade X. X rows are NOT comparable: their stop was never"
      % len(xs))
    P("  gated by the tight-stop filter -- min stop_pct=%.3f%% against %.3f%% in the book, so"
      % (min(t["stop_pct"] for t in xs), min(t["stop_pct"] for t in rows)))
    P("  R runs to %.0f. They are excluded from every number below." % max(t["r"] for t in xs))
    cpool = [t for t in shadow if t["grade"] == "C"]
    dl, dh = welch([t["r"] for t in cpool if t["seq"] >= 4],
                   [t["r"] for t in cpool if t["seq"] == 1])
    P("  C-pool seq4+ minus seq1: d=%+0.4f R +/-%0.4f  -> %s"
      % (dl, dh, "SIGNIFICANT" if abs(dl) > dh else "inside the bar, no edge either way"))
    P("")
    for pool, label in ((cpool, "shadow grade=C -- the real candidate pool"),
                        ([t for t in cpool if t["sgrade"] == "S"], "shadow grade=C and sgrade=S")):
        P("  -- %s (n=%d)" % (label, len(pool)))
        for k in (1, 2, 3, 4):
            sl = [t for t in pool if (t["seq"] == k if k < 4 else t["seq"] >= 4)]
            if not sl:
                continue
            P("     " + fmt("seq %s" % ("4+" if k == 4 else k), stats(sl), width=14))
    P("")
    P("  -- shadow grade=C by 15-min entry block (what an expansion would buy)")
    for k in ORDER15:
        sl = [t for t in cpool if block(t["et"], 15) == k]
        if sl:
            P("     " + fmt(k, stats(sl), width=14))
    late = [t for t in cpool if t["et"] >= "11:00"]
    if late:
        P("     " + fmt("11:00+", stats(late), width=14))
    P("")

    # ------------------------------------------------ half split
    P("=" * 104)
    P("OUT-OF-SAMPLE-IN-TIME: chronological halves, split at %s" % SPLIT_DAY)
    P("  H1 baseline %+0.4f R (n=%d)   H2 baseline %+0.4f R (n=%d)"
      % (b1["mean"], b1["n"], b2["mean"], b2["n"]))
    P("")
    P("Every slice with n>=30 whose delta clears its own Welch bar, H1 vs H2.")
    P("SURVIVES = n>=15 in each half AND beats THAT HALF's own baseline in both.")
    P("")
    P("%-36s %5s %9s | %4s %9s %6s | %4s %9s %6s  %s" %
      ("slice", "n", "meanR", "n1", "meanR1", "win1", "n2", "meanR2", "win2", "verdict"))
    survivors, negatives = [], []
    for name, f in findings.items():
        st, dl, dh, sel = f["st"], f["d"], f["dh"], f["sel"]
        if st["n"] < 30 or math.isnan(dl):
            continue
        if not (abs(dl) > dh and abs(dl) > HOUSE_BAR):
            continue
        s1, s2 = stats([t for t in h1 if sel(t)]), stats([t for t in h2 if sel(t)])
        thin = s1["n"] < 15 or s2["n"] < 15
        up = (not thin and s1["mean"] > b1["mean"] and s2["mean"] > b2["mean"])
        dn = (not thin and s1["mean"] < b1["mean"] and s2["mean"] < b2["mean"])
        look = f["dim"] in LOOKAHEAD
        if look:
            verdict = "LOOK-AHEAD -- not a filter"
        elif thin:
            verdict = "thin in one half"
        elif up:
            verdict = "SURVIVES"
        elif dn:
            verdict = "negative in BOTH -- exclude-candidate"
        else:
            verdict = "one-half only -- DEAD"
        P("%-36s %5d %+9.4f | %4d %+9.4f %5.1f%% | %4d %+9.4f %5.1f%%  %s" %
          (name[:36], st["n"], st["mean"], s1["n"], s1["mean"], s1["win"],
           s2["n"], s2["mean"], s2["win"], verdict))
        if look:
            continue
        if up:
            survivors.append(name)
        if dn:
            negatives.append(name)
    P("")
    P("  SURVIVORS (%d): %s" % (len(survivors), ", ".join(survivors) or "none"))
    P("  NEGATIVE IN BOTH HALVES (%d): %s" % (len(negatives), ", ".join(negatives) or "none"))
    P("")

    # ------------------------------------------------ block stability
    P("=" * 104)
    P("TIME-BLOCK STABILITY -- every block H1 vs H2, shown whether or not it is significant")
    P("(Austin asked this one directly, so it is reported regardless of the bar.)")
    P("")
    P("%-16s %5s %9s %7s | %4s %9s %7s | %4s %9s %7s  %s" %
      ("block", "n", "meanR", "win%", "n1", "meanR1", "win1", "n2", "meanR2", "win2",
       "both halves > own baseline?"))
    for size, order in ((15, ORDER15), (5, ORDER5)):
        for k in order:
            sl = [t for t in rows if block(t["et"], size) == k]
            if not sl:
                continue
            st = stats(sl)
            s1 = stats([t for t in h1 if block(t["et"], size) == k])
            s2 = stats([t for t in h2 if block(t["et"], size) == k])
            ok = (s1["n"] >= 15 and s2["n"] >= 15 and
                  s1["mean"] > b1["mean"] and s2["mean"] > b2["mean"])
            P("%-16s %5d %+9.4f %6.1f%% | %4d %+9.4f %6.1f%% | %4d %+9.4f %6.1f%%  %s" %
              ("%dm %s" % (size, k), st["n"], st["mean"], st["win"],
               s1["n"], s1["mean"], s1["win"], s2["n"], s2["mean"], s2["win"],
               "YES" if ok else "no"))
        P("")

    # ------------------------------------------------ arms
    P("=" * 104)
    P("ARMS -- ex-ante filters only, priced against the incumbent")
    P("Nested: A* are pure time cuts, B* stack conditions on the first 30 min,")
    P("C* keep the whole session and only drop slices negative in BOTH halves.")
    P("")
    P("%-30s %5s %9s %7s %8s %9s %8s %9s %9s" %
      ("arm", "n", "meanR", "win%", "mgreen", "totalR", "dN", "H1 meanR", "H2 meanR"))
    armrows = []
    for name, sel in arms():
        sl = [t for t in rows if sel(t)]
        st = stats(sl)
        a1, a2 = stats([t for t in h1 if sel(t)]), stats([t for t in h2 if sel(t)])
        P("%-30s %5d %+9.4f %6.1f%% %5d/%-2d %+9.1f %8d %+9.4f %+9.4f" %
          (name, st["n"], st["mean"], st["win"], st["mg"], st["mtot"],
           st["total"], st["n"] - base["n"], a1["mean"], a2["mean"]))
        armrows.append((name, st, a1, a2))
    P("")
    P("PRICE OF EACH ARM -- trades surrendered per +0.01 R of mean bought")
    P("%-30s %8s %10s %10s %12s  %s" %
      ("arm", "dN", "d meanR", "d totalR", "trades/+0.01R", "money gate (win>=55 AND R>=2.0)"))
    for name, st, a1, a2 in armrows:
        dn = base["n"] - st["n"]
        dm = st["mean"] - base["mean"]
        px = ("%12.1f" % (dn / (dm * 100.0))) if dm > 0.0001 and dn > 0 else "%12s" % "n/a"
        gate = "PASS" if (st["win"] >= 55.0 and st["mean"] >= 2.0) else (
            "win ok, R short by %.3f" % (2.0 - st["mean"]) if st["win"] >= 55.0
            else "FAIL both")
        P("%-30s %8d %+10.4f %+10.1f %s  %s"
          % (name, -dn, dm, st["total"] - base["total"], px, gate))
    P("")

    # ------------------------------------------------ expansion
    P("=" * 104)
    P("THE OTHER DIRECTION -- Austin wants MORE trades, so price an expansion too")
    cpool = [t for t in shadow if t["grade"] == "C"]
    cs = stats(cpool)
    P("  " + fmt("all resolved shadow grade=C", cs))
    P("  reasons those rows were not taken: %s"
      % dict(collections.Counter(t["status"] for t in cpool).most_common()))
    merged = rows + cpool
    ms = stats(merged)
    P("  " + fmt("incumbent + ALL shadow C", ms))
    m1 = stats([t for t in merged if t["day"] < SPLIT_DAY])
    m2 = stats([t for t in merged if t["day"] >= SPLIT_DAY])
    P("    H1 " + fmt("merged H1", m1))
    P("    H2 " + fmt("merged H2", m2))
    P("  PRICE: +%d trades (%.0f%% more book) for %+0.4f R of mean."
      % (cs["n"], 100.0 * cs["n"] / base["n"], ms["mean"] - base["mean"]))
    P("  total R: %+.1f -> %+.1f (%+.1f R)"
      % (base["total"], ms["total"], ms["total"] - base["total"]))
    P("  CAVEAT: not a runnable arm as-is. 805 of these are skipped_tight_stop -- the")
    P("  tight-stop gate exists because the fill is not modelled below it -- and the rest")
    P("  are same-day repeats that compete for the same capital. It is an upper bound on")
    P("  what widening the selector could reach, not a proposal.")
    P("")
    P("  best expandable sub-slice: shadow C rows in the block the traded book is thinnest in")
    for k in ORDER15:
        sl = [t for t in cpool if block(t["et"], 15) == k
              and t["status"] != "skipped_tight_stop"]
        if len(sl) >= 30:
            P("     " + fmt(k + " (ex tight-stop)", stats(sl), width=26))
    P("")

    # ------------------------------------------------ held out
    P("=" * 104)
    P("HELD OUT -- the 100 unseen cards, on Austin's OWN entry times")
    P("research/marks/probe_omen_test1_2026-08-27.jsonl. This is not an engine number:")
    P("it is where HE put the entry on cards the engine has never scored. `eblock` is the")
    P("15-min block index (0 = 09:30-09:45); it takes 4 distinct values, so it is not a")
    P("stuck default.")
    P("")
    hp = os.path.join(os.path.dirname(BOOK), "marks", "probe_omen_test1_2026-08-27.jsonl")
    if not os.path.exists(hp):
        P("  NOT MEASURED -- %s missing" % hp)
    else:
        cards = [json.loads(l) for l in open(hp) if l.strip()]
        P("  %d cards: %s" % (len(cards),
                              dict(collections.Counter(c.get("grade_std") for c in cards))))
        P("")
        P("%-8s %5s %14s %14s %s" %
          ("grade", "n", "eblock 0", "eblock 0 or 1", "block histogram"))
        for g in ("S", "A", "C", "none"):
            sub = [c for c in cards if c.get("grade_std") == g
                   and "eblock" in c.get("answers", {})]
            if not sub:
                P("%-8s %5d %14s %14s %s" %
                  (g, len([c for c in cards if c.get("grade_std") == g]),
                   "-", "-", "no entry recorded (a refusal has no entry)"))
                continue
            hist = collections.Counter(c["answers"]["eblock"][0] for c in sub)
            e0 = hist.get("0", 0)
            e01 = e0 + hist.get("1", 0)
            P("%-8s %5d %6d %6.1f%% %6d %6.1f%% %s" %
              (g, len(sub), e0, 100.0 * e0 / len(sub), e01, 100.0 * e01 / len(sub),
               dict(sorted(hist.items()))))
    P("")

    text = "\n".join(out)
    print(text)
    return text


if __name__ == "__main__":
    main()
