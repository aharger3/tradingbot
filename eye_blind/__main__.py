"""python -m eye_blind build --bars FILE.csv [--seed N] | score | serve"""
from __future__ import annotations

import argparse
import json
import os

from . import app as appmod
from . import core


def main():
    ap = argparse.ArgumentParser(prog="eye_blind")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--bars", required=True, help="window-B 1-min CSV (ts_ns or ts, open/high/low/close)")
    b.add_argument("--seed", type=int)
    sub.add_parser("score")
    sub.add_parser("serve")
    a = ap.parse_args()
    if a.cmd == "build":
        pool = core.build_pool(core.load_bars_csv(a.bars), seed=a.seed)
        core.save_pool(pool, appmod.POOL)
        print(f"pool: {len(pool['sessions'])} sessions, ready={pool['ready']} (need {core.MIN_POOL}) -> {appmod.POOL}")
    elif a.cmd == "score":
        print(json.dumps(core.score(core.load_pool(appmod.POOL), core.read_taps(appmod.TAPS)), indent=1))
    else:
        appmod.create_app().run(host="0.0.0.0", port=int(os.environ.get("EYE_BLIND_PORT", 9136)))


if __name__ == "__main__":
    main()
