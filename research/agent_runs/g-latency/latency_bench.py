"""latency_bench.py -- OMEN eye-loop latency budget, measured on the PC with replay.

Stages (live-equivalent, per 1-min bar close):
  S0 cold start: imports + load_fut (eye_runner does this at 09:28)
  S1 bar close -> candidate: detect_candidates on bars-so-far (live must rerun per bar)
  S2 chart render (matplotlib PNG)
  S3 push: POST PNG to ntfy (to a throwaway bench topic, NOT Austin's phone topic)
  S4 tap -> label row: HTTP POST to a local Flask label server (temp CSV, bench port)
  S5 label -> runner: poll interval of eye_runner.sweep_labels (<=2 s sleep)
  S6 paper fill: eye_paper.run_confirmed (first call cold = full-history load)
Plus: R cost of tap delay -- honest entry = first bar open AFTER the tap,
not the signal+1 open eye_paper uses today. Paper only. Nothing is ordered.
"""
from __future__ import annotations

import json, os, statistics as st, subprocess, sys, tempfile, time, uuid
from pathlib import Path

T0 = time.perf_counter()
REPO = Path(__file__).resolve().parents[3]
for p in ("research/agent_runs/v3-eye2-candidates", "research/agent_runs/v3-eye4-paper",
          "research/agent_runs/v2-s07-data", ""):
    sys.path.insert(0, str(REPO / p))
import numpy as np                                   # noqa: E402
import requests                                      # noqa: E402
import candidates as eye2                            # noqa: E402
import eye_paper                                     # noqa: E402
from eye_card.chart import render_candidate_chart    # noqa: E402
from omen_data import load_fut                       # noqa: E402
sys.path.insert(0, str(REPO))
import eye_runner                                    # noqa: E402
T_IMPORT = time.perf_counter() - T0

OUT = Path(__file__).resolve().parent
res: dict = {"import_s": round(T_IMPORT, 3)}


def pct(xs):
    xs = sorted(xs)
    return {"n": len(xs), "p50_ms": round(1e3 * xs[len(xs) // 2], 1),
            "p95_ms": round(1e3 * xs[int(0.95 * (len(xs) - 1))], 1), "max_ms": round(1e3 * xs[-1], 1)}


# S0 -- data load (eye_runner loads twice: pick_replay_date->eye2.run + main)
t = time.perf_counter(); df = load_fut("MNQ", "09:30", "11:01"); res["load_fut_s"] = round(time.perf_counter() - t, 3)
t = time.perf_counter(); eye2.run("MNQ", n_sessions=1); res["pick_replay_date_s"] = round(time.perf_counter() - t, 3)

sessions = [d for d in sorted(df["date"].unique()) if d.weekday() <= 3]
days = {str(d): eye2.day_arrays(g) for d, g in df.groupby("date") if d.weekday() <= 3}

# S1 -- per-bar detection on bars-so-far (live cost), last 20 sessions
det = []
for d in list(days)[-20:]:
    A = days[d]
    for m in range(6, 91):
        B = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in A.items()}
        for k in ("open", "high", "low", "close"):
            B[k][m + 1:] = np.nan
        t = time.perf_counter(); eye2.detect_candidates(B, d, "MNQ"); det.append(time.perf_counter() - t)
res["S1_detect_per_bar"] = pct(det)

# all candidates, full history (for S2 sample + R-decay study)
allc = []
for d, A in days.items():
    for c in eye2.detect_candidates(A, d, "MNQ"):
        allc.append((d, A, c))
res["candidates_total"] = len(allc)

# S2 -- chart render
rend = []
tmp = Path(tempfile.mkdtemp())
for k, (d, A, c) in enumerate(allc[-15:]):
    m = c.features["minutes_after_open"]
    cc = eye_runner.to_chart_candidate(c, f"B{k}")
    bars = eye_runner.bars_from_day_array(A, m)
    t = time.perf_counter(); render_candidate_chart(cc, bars, tmp / f"b{k}.png"); rend.append(time.perf_counter() - t)
res["S2_render"] = pct(rend)
png = (tmp / "b0.png").read_bytes()
res["png_kb"] = round(len(png) / 1024, 1)

# S3 -- ntfy POST with PNG (throwaway topic; no push reaches Austin)
topic = f"omen-latbench-{uuid.uuid4().hex[:10]}"
posts, fails, sess = [], [], requests.Session()
for k in range(6):
    t = time.perf_counter()
    try:
        r = sess.post(f"https://ntfy.sh/{topic}", data=png, headers={"Title": "bench", "Filename": "b.png"}, timeout=(5, 10))
        posts.append(time.perf_counter() - t); fails.append(r.status_code)
    except Exception as e:
        fails.append(f"{type(e).__name__}@{time.perf_counter() - t:.1f}s")
    time.sleep(1.0)
res["S3_ntfy_post_png"] = pct(posts) if posts else None
res["S3_attempts"] = fails
t = time.perf_counter()
try:
    requests.get("https://ntfy.sh/v1/health", timeout=(5, 5)); res["S3_health_s"] = round(time.perf_counter() - t, 3)
except Exception as e:
    res["S3_health_s"] = f"{type(e).__name__}"

# S4 -- label server round trip (bench copy on port 9199, temp CSV)
env = dict(os.environ, EYE_LABELS_CSV=str(tmp / "labels.csv"), EYE_LABEL_TOKEN="bench", EYE_LABEL_PORT="9199")
srv = subprocess.Popen([sys.executable, "-m", "eye_card.server"], cwd=str(REPO), env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(60):
        try:
            requests.get("http://127.0.0.1:9199/healthz", timeout=1); break
        except Exception:
            time.sleep(0.25)
    lab = []
    for k in range(20):
        t = time.perf_counter()
        requests.post(f"http://127.0.0.1:9199/label?id=B{k}&label=S&token=bench", timeout=5)
        lab.append(time.perf_counter() - t)
    res["S4_label_http_localhost"] = pct(lab)
    # same via the Tailscale IP the phone uses
    lab2 = []
    try:
        for k in range(10):
            t = time.perf_counter()
            requests.post(f"http://100.66.129.60:9199/label?id=T{k}&label=S&token=bench", timeout=5)
            lab2.append(time.perf_counter() - t)
        res["S4_label_http_tailscale_ip"] = pct(lab2)
    except Exception as e:
        res["S4_label_http_tailscale_ip"] = f"error {type(e).__name__}"
finally:
    srv.terminate()

# S5 -- runner poll: eye_runner sleeps min(2.0, ...) between sweeps at speed 1
res["S5_poll_worst_s"] = 2.0
res["tap_ts_resolution_s"] = 1.0  # labels.logged_at uses timespec='seconds'

# S6 -- paper fill, cold (first S tap triggers full-history load) then warm
eye_paper._bars_cache.clear()
d, A, c = next(x for x in allc if x[2].grade_hint == "S")
from datetime import datetime, timedelta
now = datetime.now().astimezone()
pc = eye_runner.to_paper_candidate(c, "X", d, now)
tap = {"candidate_id": "X", "grade": "S", "tap_ts": (now + timedelta(seconds=20)).isoformat()}
t = time.perf_counter(); eye_paper.run_confirmed(pc, tap); res["S6_fill_cold_s"] = round(time.perf_counter() - t, 3)
t = time.perf_counter(); eye_paper.run_confirmed(pc, tap); res["S6_fill_warm_ms"] = round(1e3 * (time.perf_counter() - t), 2)

# R cost of tap delay: entry at signal+1+k (k = whole minutes of human delay)
TICK = eye2.TICK
spec = eye_paper.SPEC["MNQ"]


def trade_r(A, c, k):
    side = 1 if c.direction == "long" else -1
    i0 = c.features["minutes_after_open"] + 1
    i = i0 + k
    O, H, L = A["open"], A["high"], A["low"]
    if i >= 60 or i >= len(O) or np.isnan(O[i]):
        return None, "no_bar"
    # while waiting, did price already hit the stop? then the card is dead -> no trade
    for j in range(i0, i):
        if (side > 0 and L[j] <= c.stop) or (side < 0 and H[j] >= c.stop):
            return 0.0, "stopped_before_entry"
    entry = O[i] + TICK * side
    if (entry - c.stop) * side < 2 * TICK:
        return 0.0, "past_stop"
    sim = eye_paper.sim_flat_2r(A, i, side, entry, c.stop, 60, spec["usd_pt"], spec["rt_comm"])
    if sim is None:
        return 0.0, "degenerate"
    # express in ORIGINAL planned risk units so rows are comparable across k
    dist0 = (c.entry - c.stop) * side
    return sim[0] * ((entry - c.stop) * side) / dist0, "ok"


S = [(d, A, c) for d, A, c in allc if c.grade_hint == "S"]
dates = sorted({d for d, _, _ in S}); mid = dates[len(dates) // 2]
rows = {}
for k in (0, 1, 2, 3):
    rs = [trade_r(A, c, k) for d, A, c in S]
    rows[k] = [(d, r) for (d, _, _), (r, why) in zip(S, rs) if r is not None]
base = dict(rows[0])
rng = np.random.default_rng(7)
decay = {}
for k in (0, 1, 2, 3):
    pairs = [(d, r, base[d]) for d, r in rows[k] if d in base]
    diff = np.array([r - b for _, r, b in pairs])
    H1 = [r for d, r, _ in pairs if d < mid]; H2 = [r for d, r, _ in pairs if d >= mid]
    p = None
    if k and len(diff) and np.any(diff):
        obs = diff.mean()
        perm = np.array([(diff * rng.choice([-1, 1], len(diff))).mean() for _ in range(5000)])
        p = float((perm <= obs).mean())  # one-sided: delay hurts
    decay[k] = {"n": len(pairs), "meanR": round(float(np.mean([r for _, r, _ in pairs])), 3),
                "H1": round(float(np.mean(H1)), 3) if H1 else None,
                "H2": round(float(np.mean(H2)), 3) if H2 else None,
                "delta_vs_k0": round(float(diff.mean()), 3) if len(diff) else None, "perm_p": p}
res["S_trades_R_by_delay_min"] = decay
res["split_date"] = mid
(OUT / "latency_results.json").write_text(json.dumps(res, indent=1, default=str))
print(json.dumps(res, indent=1, default=str))
