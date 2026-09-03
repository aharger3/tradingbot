"""g73_mentorbook_why.py — why do the mentors "average higher"? Test (f) first.

Austin, 2026-08-29: "we need to figure out why scarface and jdub average higher."

Six candidate explanations. This rig quantifies each, and it tests the sixth --
survivorship -- first and hardest, because if it holds the other five are moot.

  (f) SURVIVORSHIP  reporting rate, dollar-sign census, and a tape test of the
                    claimed outcomes on the ONE channel where the post minute
                    is the call minute (scarface-alerts is a live alert room;
                    post-your-gains is retrospective by construction and is
                    excluded from the tape test for exactly that reason).
  (a) DAY SELECTION OMEN's own book on mentor-called symbol-days vs everywhere
                    else, with a bootstrap CI on the DIFFERENCE, not two CIs
                    eyeballed side by side.
  (b) SYMBOL SEL.   re-weight OMEN's book to the mentors' symbol mix.
  (c) ENTRY TIMING  the synthetic bracket's result by minute-of-session.
  (d) EXITS         how much of the available favourable excursion (MFE) a
                    2R bracket leaves on the table.
  (e) SIZING        what the corpus can and cannot say about position size.

Reads research/g73_mentorbook_data.json (written by
research/g73_mentorbook_replay.py -- run that first) plus the pooled corpus and
the two-year book. Writes research/g73_mentorbook_why.json. Read-only on every
mark and mentor file.

Run: python research/g73_mentorbook_why.py
"""
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

POOL = ROOT / "research" / "corpus_sf" / "pooled_trades.jsonl"
BOOK = ROOT / "research" / "bt2y_trades.json"
DATA = ROOT / "research" / "g73_mentorbook_data.json"
OUT = ROOT / "research" / "g73_mentorbook_why.json"
RISK = 1000.0

# Channels where the message is posted AT the moment of the call, so the post
# minute can be used as an entry minute. Everything else is retrospective
# ("Today's P/L", a review, a chat comment after the fact) and a synthetic
# trade entered at its timestamp measures nothing about the mentor's trade.
LIVE_ALERT_SRC = {"scarface_alerts.jsonl", "jdub_alerts.jsonl",
                  "futures_alerts.jsonl", "pre_market_live.jsonl"}


def boot_diff(a, b, n=10000, seed=73):
    """95% CI on mean(a) - mean(b), and a two-sided permutation p-value."""
    if len(a) < 5 or len(b) < 5:
        return None
    rng = random.Random(seed)
    obs = statistics.fmean(a) - statistics.fmean(b)
    ds = sorted(statistics.fmean(rng.choices(a, k=len(a)))
                - statistics.fmean(rng.choices(b, k=len(b))) for _ in range(n))
    pool = a + b
    hits = 0
    for _ in range(n):
        rng.shuffle(pool)
        d = statistics.fmean(pool[:len(a)]) - statistics.fmean(pool[len(a):])
        if abs(d) >= abs(obs):
            hits += 1
    return dict(diff=round(obs, 4), ci=[round(ds[int(.025 * n)], 4),
                                        round(ds[int(.975 * n)], 4)],
                p=round((hits + 1) / (n + 1), 4))


def agg(rs):
    if not rs:
        return dict(n=0)
    return dict(n=len(rs), win=round(sum(1 for r in rs if r > 0) / len(rs) * 100, 1),
                mean_r=round(statistics.fmean(rs), 4),
                dollars=round(statistics.fmean(rs) * RISK, 2))


def main():
    pool = [json.loads(l) for l in POOL.open(encoding="utf-8") if l.strip()]
    bk = json.loads(BOOK.read_text(encoding="utf-8"))
    book = bk["trades"]
    data = json.loads(DATA.read_text(encoding="utf-8"))
    res = {"generated_by": "research/g73_mentorbook_why.py"}

    # =====================================================================
    # (f) SURVIVORSHIP
    # =====================================================================
    f = {}

    # f1 — the dollar-sign census. Every stated dollar figure in 112k messages.
    pnl = [r["pnl_usd"] for r in pool if r.get("pnl_usd") is not None]
    pos = [p for p in pnl if p > 0]
    f["dollar_census"] = dict(
        stated_dollar_figures=len(pnl), positive=len(pos),
        negative=sum(1 for p in pnl if p < 0), zero=sum(1 for p in pnl if p == 0),
        min=min(pnl) if pnl else None, median=statistics.median(pnl) if pnl else None,
        max=max(pnl) if pnl else None,
        note="a coin that lands heads this many times in a row is not a coin",
        p_if_half_were_losers=round(0.5 ** len(pnl), 12) if pnl else None)

    # f2 — reporting rate. A live alert room posts the entry; the follow-up is
    # optional, and optional is where the bias lives.
    rr = {}
    for src in sorted({r["primary_src"] for r in pool}):
        g = [r for r in pool if r["primary_src"] == src]
        oc = Counter(r.get("outcome") for r in g)
        stated = oc["win"] + oc["loss"] + oc["be"]
        rr[src] = dict(instances=len(g), followed_up=stated,
                       report_rate=round(stated / len(g) * 100, 1),
                       never_mentioned_again=len(g) - stated,
                       win=oc["win"], loss=oc["loss"], be=oc["be"],
                       claimed_win_rate=round(oc["win"] / (oc["win"] + oc["loss"]) * 100, 1)
                       if oc["win"] + oc["loss"] else None,
                       live_alert_room=src in LIVE_ALERT_SRC)
    f["reporting_rate_by_channel"] = rr

    # f3 — the tape test, live alert rooms only.
    synth = data["_synth_rows"]
    live = [s for s in synth if s["src"] in LIVE_ALERT_SRC]
    cw = [s["r"] for s in live if s["claimed"] == "win"]
    cl = [s["r"] for s in live if s["claimed"] == "loss"]
    un = [s["r"] for s in live if s["claimed"] is None]
    f["tape_test_live_rooms"] = dict(
        claimed_win=agg(cw), claimed_loss=agg(cl), never_mentioned_again=agg(un),
        all_calls=agg(cw + cl + un + [s["r"] for s in live if s["claimed"] == "be"]),
        win_vs_unreported=boot_diff(cw, un),
        win_vs_loss=boot_diff(cw, cl),
        claimed_win_rate=round(len(cw) / (len(cw) + len(cl)) * 100, 1) if cw + cl else None,
        tape_win_rate_all_calls=agg([s["r"] for s in live])["win"],
        reads=("if claimed wins beat the tape and claimed losses lose on the "
               "tape, the mentor is telling the truth about what he reports; "
               "if the calls he never mentions again look like the losses, the "
               "high average is what he leaves out, not what he does"))

    # f4 — the same test on the retrospective channel, shown so nobody quotes it
    retro = [s for s in synth if s["src"] not in LIVE_ALERT_SRC]
    f["tape_test_retrospective_channels_INVALID"] = dict(
        claimed_win=agg([s["r"] for s in retro if s["claimed"] == "win"]),
        claimed_loss=agg([s["r"] for s in retro if s["claimed"] == "loss"]),
        why_invalid=("post-your-gains and chat posts land after the trade is "
                     "over, so a bracket entered at the post minute is not the "
                     "mentor's trade. Reported for completeness, not evidence."))

    # f5 — what the claimed win rate becomes once the silence is scored
    live_sf = [s for s in synth if s["src"] == "scarface_alerts.jsonl"]
    if live_sf:
        c_w = sum(1 for s in live_sf if s["claimed"] == "win")
        c_l = sum(1 for s in live_sf if s["claimed"] == "loss")
        silent = [s for s in live_sf if s["claimed"] is None]
        tape_w = sum(1 for s in silent if s["r"] > 0)
        f["scarface_win_rate_reconstructed"] = dict(
            claimed=round(c_w / (c_w + c_l) * 100, 1) if c_w + c_l else None,
            claimed_n=c_w + c_l,
            with_silence_scored_by_tape=round((c_w + tape_w) /
                                              (c_w + c_l + len(silent)) * 100, 1),
            silent_calls=len(silent), silent_that_worked_on_tape=tape_w,
            omen_one_trade_a_day_win_rate=data["A_omen_on_mentor_days"]["otd_all"]["win"])
    res["f_survivorship"] = f

    # =====================================================================
    # (a) DAY SELECTION — is a mentor-called symbol-day a better day for OMEN?
    # =====================================================================
    called = set()
    bsyms, first, last = set(bk["meta"]["symbols"]), bk["meta"]["first"], bk["meta"]["last"]
    for r in pool:
        if r.get("instrument") == "futures":
            continue
        s, d = r.get("symbol"), r.get("trade_date")
        if s in bsyms and d and first <= d <= last:
            called.add((s, d))
    on = [t["r"] for t in book if t["traded"] and (t["sym"], t["day"]) in called]
    off = [t["r"] for t in book if t["traded"] and (t["sym"], t["day"]) not in called]
    res["a_day_selection"] = dict(on_mentor_days=agg(on), elsewhere=agg(off),
                                  difference=boot_diff(on, off),
                                  reads="positive and significant = they pick better days")

    # =====================================================================
    # (b) SYMBOL SELECTION — reweight OMEN's book to the mentors' symbol mix
    # =====================================================================
    mix = Counter(r["symbol"] for r in pool
                  if r.get("instrument") != "futures" and r.get("symbol") in bsyms)
    tot = sum(mix.values())
    per_sym = defaultdict(list)
    for t in book:
        if t["traded"]:
            per_sym[t["sym"]].append(t["r"])
    base = statistics.fmean([r for rs in per_sym.values() for r in rs])
    num = den = 0.0
    for sym, w in mix.items():
        if per_sym.get(sym):
            num += w / tot * statistics.fmean(per_sym[sym])
            den += w / tot
    res["b_symbol_selection"] = dict(
        omen_book_mean_r=round(base, 4),
        reweighted_to_mentor_symbol_mix=round(num / den, 4) if den else None,
        lift=round(num / den - base, 4) if den else None,
        mentor_top_symbols=mix.most_common(10),
        reads="lift is what trading their symbol mix alone would be worth")

    # =====================================================================
    # (c) ENTRY TIMING
    # =====================================================================
    res["c_entry_timing"] = dict(
        synthetic_by_slot=data["D_timing"]["synth_by_slot"],
        mentor_median_minute_after_open=data["D_timing"]["mentor_median_min_after_open"],
        omen_median_minute_after_open=data["D_timing"]["omen_median_min_after_open"],
        mentor_pct_in_first_90=data["D_timing"]["mentor_pct_in_first_90"],
        omen_pct_in_first_90=data["D_timing"]["omen_pct_in_first_90"])

    # =====================================================================
    # (d) EXITS — how much favourable excursion a 2R bracket walks away from
    # =====================================================================
    mfes = [s["mfe"] for s in synth]
    res["d_exits"] = dict(
        n=len(mfes), mean_mfe_r=round(statistics.fmean(mfes), 3),
        median_mfe_r=round(statistics.median(mfes), 3),
        pct_reaching_1R=round(sum(1 for m in mfes if m >= 1) / len(mfes) * 100, 1),
        pct_reaching_2R=round(sum(1 for m in mfes if m >= 2) / len(mfes) * 100, 1),
        pct_reaching_4R=round(sum(1 for m in mfes if m >= 4) / len(mfes) * 100, 1),
        perfect_exit_mean_r=round(statistics.fmean(mfes), 3),
        bracket_mean_r=data["B_synthetic_mentor_trade"]["all"]["mean_r"],
        reads=("perfect_exit is an oracle -- it sells the exact high of the "
               "session after the call. It is the ceiling on every exit idea, "
               "not an achievable number."))

    # =====================================================================
    # (e) SIZING
    # =====================================================================
    r_rows = [r for r in pool if r.get("r_multiple") is not None]
    res["e_sizing"] = dict(
        instances_with_a_stated_entry=sum(1 for r in pool if r.get("entry") is not None),
        instances_with_a_stated_stop=sum(1 for r in pool if r.get("stop") is not None),
        instances_with_a_stated_R=len(r_rows),
        instances_with_a_stated_dollar=len(pnl),
        of_3547=len(pool),
        verdict=("not measurable. Risk per trade is never stated, so a dollar "
                 "figure cannot be turned into an R and cannot be compared to "
                 "OMEN's 1R = $1,000."))

    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("wrote", OUT)
    print("\n(f) dollar census:", f["dollar_census"])
    print("(f) scarface report rate:",
          rr.get("scarface_alerts.jsonl", {}).get("report_rate"), "%")
    print("(f) tape test live rooms:")
    for k in ("claimed_win", "claimed_loss", "never_mentioned_again", "all_calls"):
        print("   ", f"{k:24s}", f["tape_test_live_rooms"][k])
    print("    win vs unreported:", f["tape_test_live_rooms"]["win_vs_unreported"])
    print("(f) reconstructed:", f.get("scarface_win_rate_reconstructed"))
    print("\n(a) day selection:", res["a_day_selection"]["difference"])
    print("(b) symbol reweight lift:", res["b_symbol_selection"]["lift"])
    print("(d) exits:", res["d_exits"])


if __name__ == "__main__":
    main()
