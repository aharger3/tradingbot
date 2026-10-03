"""W9 blind stock deck: build. Paper research, not investment advice, no orders. Stock bars only (window A / NQ never touched).

  python w9_build.py OUTDIR PREREG_MD [--key-file F] [--judged FILE] [--dry-run]

Picks 8 decks x 40 cards of engine candidates from the fit window 2024-09-26..2026-09-25 on days where Austin marked NOTHING (any ticker),
cuts each chart at the decision bar (the signal bar's own bar is the last one drawn; nothing after it, no date, no ticker, % axis from the
session open), renders one small PNG per card, then seals the outcomes (frozen S2 sim) in sealed.bin.

Outcomes are computed only to be sealed; nothing here prints or logs a per-card R. Selection looks at whether a card is simulable and
has bars, never at its R. The build refuses to run unless the pre-registration file already contains the sha256 of this file, of
w9_blind.py, of s2_lib.py and of the judged-keys file, so the deck cannot be made with code the prereg did not name.
"""
import os, sys, csv, json, gzip, hashlib, secrets, argparse
from datetime import datetime, timezone
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "s2-stocks"))
import s2_lib as L
import w9_blind as W

SEED_SELECT = 20261009
N_DECKS, DECK_SIZE = W.N_DECKS, W.DECK_SIZE
SIG_LO, SIG_HI = 575, 630          # signal bar 09:35..10:30 ET
SYMDAY_CAP, MIN_GAP = 2, 10        # at most 2 cards per ticker-day, at least 10 minutes apart
MIN_RTH_COVERAGE = 0.8             # share of the 1-min bars 09:30..signal bar that must exist


def sha_file(fp):
    with open(fp, "rb") as f:
        return W.sha256(f.read())


def sha_text(fp):
    """sha256 of a text file with CRLF folded to LF, so the hash is the same whatever git did to line endings."""
    with open(fp, "rb") as f:
        return W.sha256(f.read().replace(bytes([13, 10]), bytes([10])))


def read_judged(fp):
    keys = [x.strip() for x in open(fp, encoding="utf-8") if x.strip()]
    return set(keys), {k.rsplit("_", 1)[1] for k in keys}


def load_tape_cands():
    """Engine candidates in the fit window, signal before 10:59, same filter as s2_lib.load_candidates (tape only; no label file)."""
    B = json.load(gzip.open(L.TAPE))["trades"]
    out = []
    for t in B:
        if t["et"] >= "10:59" or not (L.FIT0 <= t["day"] <= L.FIT1):
            continue
        out.append(dict(sym=t["sym"], day=t["day"], m=L.mins(t["et"]), side=1 if t["dir"] == "call" else -1,
                        stop=float(t["stop"]), level_px=t.get("level_px")))
    return out


# ------------------------------------------------------------------ bars
def full_day_bars(sym, day):
    """all 1-min bars of the file (04:00-20:00 ET): dict m,O,H,L,C,V arrays, or None."""
    fp = os.path.join(L.ARCH, sym, day + ".csv")
    if not os.path.exists(fp):
        return None
    rows = []
    with open(fp, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                ts = r["Datetime"]
                rows.append((int(ts[11:13]) * 60 + int(ts[14:16]), float(r["Open"]), float(r["High"]), float(r["Low"]), float(r["Close"]), float(r["Volume"] or 0)))
            except (ValueError, KeyError):
                continue
    if not rows:
        return None
    a = np.array(sorted(rows))
    return dict(m=a[:, 0].astype(int), O=a[:, 1], H=a[:, 2], L=a[:, 3], C=a[:, 4], V=a[:, 5])


def prev_close(sym, day):
    d = os.path.join(L.ARCH, sym)
    prior = [x for x in os.listdir(d) if x.endswith(".csv") and x[:-4] < day]
    if not prior:
        return None
    b = full_day_bars(sym, max(prior)[:-4])
    if b is None:
        return None
    rth = b["m"] < 960
    return float(b["C"][rth][-1]) if rth.any() else None


def cut_bars(bars, m_sig, lo=480):
    """08:00 ET .. the signal bar, inclusive. Nothing after the decision bar can reach the picture."""
    k = (bars["m"] >= lo) & (bars["m"] <= m_sig)
    return {x: bars[x][k] for x in ("m", "O", "H", "L", "C", "V")}


def make_check(sim_fn=None):
    """-> check(c): enrich a candidate with its sealed outcome, or None if it cannot be a card (no bars / gaps / not simulable).
    Looks at simulability only; the value of R is stored for sealing and never inspected."""
    sim_fn = sim_fn or L.sim

    def check(c):
        day = L.load_day(c["sym"], c["day"])
        if day is None:
            return None
        i = c["m"] - L.RTH0
        if i < 1 or not np.isfinite(day["O"][i]) or not np.isfinite(day["C"][i]):
            return None
        if np.isfinite(day["O"][: i + 1]).mean() < MIN_RTH_COVERAGE:
            return None
        res = sim_fn(day, c["m"], c["side"], c["stop"])
        if res is None:
            return None
        return dict(r=float(res[0]), how=res[1])
    return check


# ------------------------------------------------------------------ selection
def select_cards(pool, check, seed, n_total, symday_cap=SYMDAY_CAP, min_gap=MIN_GAP):
    """Round-robin over days in a seeded random order, one random acceptable candidate per day per round, so every day contributes
    the same number of cards (+-1). Acceptable = passes check() and respects the per-ticker-day cap and spacing."""
    rng = np.random.default_rng(seed)
    pool = sorted(pool, key=lambda c: (c["day"], c["sym"], c["m"], c["side"]))
    by_day = {}
    for c in pool:
        by_day.setdefault(c["day"], []).append(c)
    days = sorted(by_day)
    order = {d: [int(x) for x in rng.permutation(len(by_day[d]))] for d in days}
    ptr = {d: 0 for d in days}
    taken, chosen = {}, []
    while len(chosen) < n_total:
        progressed = False
        for di in rng.permutation(len(days)):
            d = days[di]
            while ptr[d] < len(order[d]):
                c = by_day[d][order[d][ptr[d]]]
                ptr[d] += 1
                ms = taken.get((c["sym"], d), [])
                if len(ms) >= symday_cap or any(abs(c["m"] - m) < min_gap for m in ms):
                    continue
                info = check(c)
                if info is None:
                    continue
                taken.setdefault((c["sym"], d), []).append(c["m"])
                chosen.append({**c, **info})
                progressed = True
                break
            if len(chosen) >= n_total:
                break
        if not progressed:
            raise ValueError("pool exhausted at %d of %d cards" % (len(chosen), n_total))
    return chosen


# ------------------------------------------------------------------ chart
def render_card(path, bars, c, pclose):
    """One PNG. % axis from the 09:30 open; times HH:MM only; ticker, date, grade, outcome and absolute price are never drawn."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    b = cut_bars(bars, c["m"])
    rth = b["m"] >= 570
    if not rth.any():
        raise ValueError("no regular-session bar")
    o = float(b["O"][rth][0])
    pct = lambda p: (np.asarray(p, float) / o - 1.0) * 100.0
    x = b["m"] - 480
    last_close = float(b["C"][-1])
    risk = abs(last_close - c["stop"])
    tgt = last_close + c["side"] * 2.0 * risk
    fig = plt.figure(figsize=(6.4, 4.0), dpi=90)
    ax = fig.add_axes([0.09, 0.27, 0.80, 0.62])
    axv = fig.add_axes([0.09, 0.08, 0.80, 0.14], sharex=ax)
    up = b["C"] >= b["O"]
    col = np.where(up, "#1a9850", "#d73027")
    ax.vlines(x, pct(b["L"]), pct(b["H"]), colors=col, linewidth=0.8)
    ax.bar(x, np.abs(pct(b["C"]) - pct(b["O"])), bottom=np.minimum(pct(b["C"]), pct(b["O"])), width=0.7, color=col, linewidth=0)
    x_end = x[-1] + 14
    orb = (b["m"] >= 570) & (b["m"] < 575)
    if orb.any():
        ax.fill_between([570 - 480, x_end], pct(b["L"][orb].min()), pct(b["H"][orb].max()), color="#888", alpha=0.12, linewidth=0)
        ax.text(0.01, 0.97, "grey band = first 5 min range", transform=ax.transAxes, fontsize=7, va="top", color="#666")
    ax.hlines(pct(c["stop"]), x[-1], x_end, colors="#d73027", linestyles="--", linewidth=1.2)
    ax.hlines(pct(tgt), x[-1], x_end, colors="#1a9850", linestyles=":", linewidth=1.2)
    ax.text(x_end, pct(c["stop"]), " stop", color="#d73027", fontsize=7, va="center")
    ax.text(x_end, pct(tgt), " 2R", color="#1a9850", fontsize=7, va="center")
    if c.get("level_px"):
        ax.axhline(pct(c["level_px"]), color="#4575b4", linewidth=0.8, alpha=0.8)
        ax.text(x[0], pct(c["level_px"]), "level", color="#4575b4", fontsize=7, va="bottom")
    ys = [pct(b["L"]).min(), pct(b["H"]).max(), pct(c["stop"]), pct(tgt)]
    lo, hi = min(ys), max(ys)
    pad = (hi - lo) * 0.06 or 0.1
    ax.set_ylim(lo - pad, hi + pad)
    if pclose and lo - pad <= pct(pclose) <= hi + pad:
        ax.axhline(pct(pclose), color="#999", linewidth=0.8, linestyle="-.")
        ax.text(x[0], pct(pclose), "prev close", color="#777", fontsize=7, va="bottom")
    ax.axvline(570 - 480, color="#555", linewidth=0.6, alpha=0.6)
    ax.set_xlim(x[0] - 1, x_end + 12)
    ax.set_ylabel("% from the 09:30 open", fontsize=8)
    ax.tick_params(labelsize=7, labelbottom=False)
    v = b["V"]
    axv.bar(x, v / v.max() if v.max() > 0 else v, width=0.7, color=col, linewidth=0)
    axv.set_yticks([])
    ticks = [t for t in range(480, int(c["m"]) + 1) if t % 30 == 0]
    axv.set_xticks([t - 480 for t in ticks])
    axv.set_xticklabels(["%02d:%02d" % divmod(t, 60) for t in ticks], fontsize=7)
    sig = "%02d:%02d" % divmod(int(c["m"]), 60)
    fig.text(0.09, 0.93, "%s setup  |  decision at the close of the %s bar  |  stop %.2f%% away" % ("LONG" if c["side"] > 0 else "SHORT", sig, risk / last_close * 100),
             fontsize=9, weight="bold")
    fig.savefig(path, format="png")
    plt.close(fig)


# ------------------------------------------------------------------ build
def build(outdir, prereg_fp, judged_fp, key_file=None, dry_run=False, cands=None, check=None, bars_fn=None, pclose_fn=None,
          n_decks=N_DECKS, deck_size=DECK_SIZE, min_s=W.MIN_S):
    judged_keys, judged_days = read_judged(judged_fp)
    cands = cands if cands is not None else load_tape_cands()
    pool = [c for c in cands if c["day"] not in judged_days and "%s_%s" % (c["sym"], c["day"]) not in judged_keys and SIG_LO <= c["m"] <= SIG_HI]
    if dry_run:
        return dict(pool_candidates=len(pool), pool_days=len({c["day"] for c in pool}))
    here = os.path.join(HERE, "w9_blind.py"), os.path.join(HERE, "w9_build.py"), os.path.join(HERE, "..", "s2-stocks", "s2_lib.py"), judged_fp
    hashes = {os.path.basename(p): sha_text(p) for p in here}
    pre = open(prereg_fp, encoding="utf-8").read()
    missing = [n for n, h in hashes.items() if h not in pre]
    if missing:
        raise SystemExit("refusing to build: the pre-registration does not contain the sha256 of " + ", ".join(missing))
    kf = key_file or os.environ.get("W9_SEAL_KEY_FILE") or W.DEFAULT_KEY_FILE
    if os.path.exists(kf):
        raise SystemExit("refusing to overwrite an existing seal key: " + kf)
    n_total = n_decks * deck_size
    chosen = select_cards(pool, check or make_check(), SEED_SELECT, n_total)
    rng = np.random.default_rng(SEED_SELECT + 1)
    chosen = [chosen[i] for i in rng.permutation(len(chosen))]
    ids = set()
    for k, c in enumerate(chosen):
        while True:
            cid = "W9-" + secrets.token_hex(4)
            if cid not in ids:
                ids.add(cid)
                break
        c["id"], c["deck"], c["pos"] = cid, k // deck_size + 1, k % deck_size + 1
        c["sig_t"] = "%02d:%02d" % divmod(c["m"], 60)
    info = dict(pool_candidates=len(pool), pool_days=len({c["day"] for c in pool}), n_cards=len(chosen), n_card_days=len({c["day"] for c in chosen}))
    os.makedirs(os.path.join(outdir, "img"), exist_ok=True)
    bars_fn = bars_fn or full_day_bars
    pclose_fn = pclose_fn or prev_close
    pub = []
    for c in chosen:
        fp = os.path.join(outdir, "img", c["id"] + ".png")
        render_card(fp, bars_fn(c["sym"], c["day"]), c, pclose_fn(c["sym"], c["day"]))
        pub.append(dict(id=c["id"], deck=c["deck"], pos=c["pos"], img="img/%s.png" % c["id"], img_sha256=sha_file(fp)))
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    os.makedirs(os.path.dirname(kf), exist_ok=True)
    with open(kf, "wb") as f:
        f.write(key)
    payload = dict(cards=[{k: c[k] for k in ("id", "deck", "pos", "sym", "day", "sig_t", "side", "stop", "r", "how")} for c in chosen])
    token, commitment = W.seal(payload, key)
    with open(os.path.join(outdir, "sealed.bin"), "wb") as f:
        f.write(token)
    man = dict(version=1, experiment="W9 blind stock deck", n_decks=n_decks, deck_size=deck_size, min_s=min_s, cards=pub,
               commitment=commitment, sealed_sha256=W.sha256(token), prereg_sha256=sha_file(prereg_fp), code_sha256=hashes,
               seed=SEED_SELECT, fit_window=[L.FIT0, L.FIT1], built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), **info)
    with open(os.path.join(outdir, "deck.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1)
    for fn in ("w9_blind.py",):
        with open(os.path.join(HERE, fn), "rb") as src, open(os.path.join(outdir, fn), "wb") as dst:
            dst.write(src.read())
    return info


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("prereg")
    ap.add_argument("--key-file", default=None)
    ap.add_argument("--judged", default=os.path.join(HERE, "judged_marks_keys.txt"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    print(json.dumps(build(a.outdir, a.prereg, a.judged, a.key_file, a.dry_run)))
