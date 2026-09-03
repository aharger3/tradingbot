"""G7.4 / ocrgates -- price every one-candle-rule gate arm on the two-year book.

Each arm is a full two-year rebuild with ONE thing changed, run by
research/g74_ocrgates_arm.py, which prices in-process and writes a few KB of
stats instead of a 138 MB book. Arms are built in PARALLEL (the engine is
single-threaded and the box has cores going spare); `--jobs` caps how many.

The arithmetic is the G7.2 board's, imported not re-typed
(research/g72_suppress_price.stats / shipped_rows / oneaday_rows), so every
number here means what it meant when the board was written.

Every arm also gets a paired day-level bootstrap against `head` on
dollars-per-day, because on this project the error bar has repeatedly been
wider than the arms.

1R = $1,000. Writes research/g74_ocrgates_price.json.

Usage:  python research/g74_ocrgates_price.py [--arms head,nomax,...] [--jobs 4]
"""
import argparse, json, os, random, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_ARMS = ["head", "pre_r3r4", "demote_only", "flat50", "relfloor", "nomax",
                "wideretest", "xlift_ocr", "nohtf", "merits", "allmerits"]
FIELDS = ["trades", "win_pct", "mean_r", "per_day", "months_green", "months",
          "weeks_green", "worst_drawdown", "total_dollars"]


def launch(arm, path, days):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    cmd = [sys.executable, str(ROOT / "research" / "g74_ocrgates_arm.py"),
           "--arm", arm, "--out", str(path), "--days", str(days)]
    return subprocess.Popen(cmd, cwd=str(ROOT), env=env, text=True, errors="replace",
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def paired_boot(base, arm, days, n=10000, seed=17):
    rnd = random.Random(seed)
    diffs = [arm.get(d, 0.0) - base.get(d, 0.0) for d in days]
    k = len(diffs)
    outs = sorted(sum(diffs[rnd.randrange(k)] for _ in range(k)) / k
                  for _ in range(n))
    return round(outs[int(0.025 * n)], 0), round(outs[int(0.975 * n)], 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arms", default=",".join(DEFAULT_ARMS))
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--out", default=str(ROOT / "research" / "g74_ocrgates_price.json"))
    args = ap.parse_args()

    wd = Path(args.workdir) if args.workdir else Path(tempfile.gettempdir()) / "g74_ocrgates"
    wd.mkdir(parents=True, exist_ok=True)
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]

    todo, running, res = list(arms), {}, {}
    while todo or running:
        while todo and len(running) < args.jobs:
            a = todo.pop(0)
            p = wd / ("g74_%s.json" % a)
            print("  launch %s" % a, flush=True)
            running[a] = (launch(a, p, args.days), p)
        for a, (proc, p) in list(running.items()):
            if proc.poll() is None:
                continue
            out = proc.communicate()[0] or ""
            tail = [l for l in out.splitlines() if "apiKey" not in l][-1:]
            print("  done   %s   %s" % (a, tail[0].strip() if tail else ""), flush=True)
            if proc.returncode != 0:
                raise SystemExit("arm %s failed (exit %d)\n%s"
                                 % (a, proc.returncode, out[-2000:]))
            res[a] = json.load(open(p, encoding="utf-8"))
            p.unlink(missing_ok=True)
            del running[a]
        if running:
            import time
            time.sleep(3)

    base = res.get("head")
    if base:
        days = base["days"]
        for a in arms:
            if a == "head":
                continue
            res[a]["oad_per_day_delta_ci95"] = paired_boot(
                base["oad_by_day"], res[a]["oad_by_day"], days)
            res[a]["all_per_day_delta_ci95"] = paired_boot(
                base["ship_by_day"], res[a]["ship_by_day"], days)

    slim = {a: {k: v for k, v in r.items()
                if k not in ("days", "oad_by_day", "ship_by_day")}
            for a, r in res.items()}
    json.dump(slim, open(args.out, "w", encoding="utf-8"), indent=2)

    for view in ("shipped", "one_a_day", "ocr_slice", "ocr_alone_slice"):
        print("\n=== %s ===" % view.upper())
        print("  %-12s" % "arm" + "".join("%13s" % f for f in FIELDS))
        for a in arms:
            s = res[a][view]
            print("  %-12s" % a + "".join("%13s" % s.get(f, "-") for f in FIELDS))
    print("\n=== paired day-level 95% CI on dollars/day vs head ===")
    print("  %-12s %24s %24s" % ("arm", "one-a-day", "all-trades"))
    for a in arms:
        if a == "head":
            continue
        o, t = res[a]["oad_per_day_delta_ci95"], res[a]["all_per_day_delta_ci95"]
        print("  %-12s %24s %24s"
              % (a, "$%d .. $%d" % o, "$%d .. $%d" % t))
    print("\nwrote %s" % args.out)


if __name__ == "__main__":
    main()
