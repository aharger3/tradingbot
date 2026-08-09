"""T4 geometry sweep: for each (window, confirm_gap, need_leave, eps_mult) combo,
flip omen_bot's BREAK_RETEST_* knobs in a FRESH subprocess (so the import picks
it up), run research/t4_experiment.py, and parse S recall + dropped + precision.
Tolerance (retest_tol_mult / DETECT_WIDE) stays OFF throughout.
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OB = os.path.join(ROOT, "omen_bot.py")

CONFIGS = [
    ("baseline",            {"BREAK_RETEST_WINDOW": 12, "BREAK_RETEST_CONFIRM_GAP": 3, "BREAK_RETEST_NEED_LEAVE": True}),
    ("no_leave",            {"BREAK_RETEST_WINDOW": 12, "BREAK_RETEST_CONFIRM_GAP": 3, "BREAK_RETEST_NEED_LEAVE": False}),
    ("gap6",                {"BREAK_RETEST_WINDOW": 12, "BREAK_RETEST_CONFIRM_GAP": 6, "BREAK_RETEST_NEED_LEAVE": True}),
    ("gap9",                {"BREAK_RETEST_WINDOW": 12, "BREAK_RETEST_CONFIRM_GAP": 9, "BREAK_RETEST_NEED_LEAVE": True}),
    ("win20",               {"BREAK_RETEST_WINDOW": 20, "BREAK_RETEST_CONFIRM_GAP": 3, "BREAK_RETEST_NEED_LEAVE": True}),
    ("win20+gap6",          {"BREAK_RETEST_WINDOW": 20, "BREAK_RETEST_CONFIRM_GAP": 6, "BREAK_RETEST_NEED_LEAVE": True}),
    ("no_leave+gap6",       {"BREAK_RETEST_WINDOW": 12, "BREAK_RETEST_CONFIRM_GAP": 6, "BREAK_RETEST_NEED_LEAVE": False}),
    ("no_leave+win20",      {"BREAK_RETEST_WINDOW": 20, "BREAK_RETEST_CONFIRM_GAP": 3, "BREAK_RETEST_NEED_LEAVE": False}),
    ("no_leave+win20+gap6", {"BREAK_RETEST_WINDOW": 20, "BREAK_RETEST_CONFIRM_GAP": 6, "BREAK_RETEST_NEED_LEAVE": False}),
    ("no_leave+win20+gap9", {"BREAK_RETEST_WINDOW": 20, "BREAK_RETEST_CONFIRM_GAP": 9, "BREAK_RETEST_NEED_LEAVE": False}),
    ("no_leave+win30+gap9", {"BREAK_RETEST_WINDOW": 30, "BREAK_RETEST_CONFIRM_GAP": 9, "BREAK_RETEST_NEED_LEAVE": False}),
]


def patch(config):
    src = open(OB).read()
    for key, val in config.items():
        if isinstance(val, bool):
            rep = "True" if val else "False"
            src = re.sub(rf"{key}\s*=\s*(True|False)", f"{key} = {rep}", src, count=1)
        else:
            src = re.sub(rf"{key}\s*=\s*\d+", f"{key} = {val}", src, count=1)
    open(OB, "w").write(src)


def run_one():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, os.path.join(HERE, "t4_experiment.py")],
                       capture_output=True, text=True, env=env, cwd=ROOT)
    out = p.stdout
    m = re.search(r"S any-signal recall: (\d+)/77", out)
    d = re.search(r"DROPPED any_signal: \[(.*?)\]", out)
    ds = re.search(r"DROPPED s_grade: \[(.*?)\]", out)
    gm = re.search(r"GAINED s_grade fired: \[(.*?)\]", out)
    pm = re.search(r"precision ([\d.]+)", out)
    nbr = re.search(r"no_break_retest S marks now with any signal \((\d+)/30\)", out)
    # also capture A/X
    ax = re.search(r"\(A (\d+)/60, X (\d+)/22\)", out)
    return {
        "S": int(m.group(1)) if m else None,
        "A": int(ax.group(1)) if ax else None,
        "X": int(ax.group(2)) if ax else None,
        "dropped_any": d.group(1) if d and d.group(1).strip() else "",
        "dropped_s": ds.group(1) if ds and ds.group(1).strip() else "",
        "gained_s": gm.group(1) if gm and gm.group(1).strip() else "",
        "precision": float(pm.group(1)) if pm else None,
        "nbr": int(nbr.group(1)) if nbr else None,
        "ok": p.returncode == 0,
    }


def main():
    baseline_src = open(OB).read()
    results = []
    for name, cfg in CONFIGS:
        patch(cfg)
        r = run_one()
        results.append((name, cfg, r))
        print(f"{name:22s} S={r['S']}/77 A={r['A']}/60 X={r['X']}/22  nbr={r['nbr']}/30  prec={r['precision']}  dropAny='{r['dropped_any']}' dropS='{r['dropped_s']}' gainS='{r['gained_s']}'")
    # restore baseline source
    open(OB, "w").write(baseline_src)
    print("\nrestored baseline omen_bot.py")
    json.dump([{n: r} for n, c, r in results],
              open(os.path.join(HERE, "_t4_sweep.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
