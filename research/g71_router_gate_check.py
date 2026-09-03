"""G7.1 / track `router` - would the router fix turn the recall gate red?

`research/regression_gate.py` scores through the same
`research/t4_engine_recall.CaptureRunner`. Fixing that class changes what the
gate sees, so the fix has to be checked against the gate BEFORE it is applied.
This runs `regression_gate.check()` with the delegating router monkeypatched in,
in this process only. No file is edited; baseline_3.8.json is read, never
written.

Usage:  python research/g71_router_gate_check.py
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import research.t4_engine_recall as t4
from research.g71_router_recall import _delegating_route
import regression_gate as rg          # research/ is on sys.path

t4.CaptureRunner._route = _delegating_route
rg.t4.CaptureRunner._route = _delegating_route
sys.exit(rg.check())
