"""ADVERSARIAL VERIFY of track `faraway`'s SCOPE LIMIT claim.

Claim under test:
  (a) options_sizer.DEFAULT_RR = 2.0 is the entire live exit; consumed at
      :202/:223/:228/:291/:307.
  (b) live_scanner.py:631 calls build_options_plan() WITHOUT rr=.
  (c) therefore the live path has NO runner and sells the whole position at
      exactly 2R -> 0 live rows can book >2R.
  (d) the track varies only the exit, so no arm can move held-out S recall.

Nothing is edited. Read-only. No engine file touched.
"""
from __future__ import annotations
import ast, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

out = []

# ---- (a) constant + consumption sites -------------------------------------
import options_sizer as osz
out.append(("DEFAULT_RR", osz.DEFAULT_RR))
src = open(os.path.join(ROOT, "options_sizer.py"), encoding="utf-8").read().splitlines()
for ln in (25, 202, 223, 228, 291, 307, 120, 373):
    out.append((f"options_sizer.py:{ln}", src[ln-1].strip()))
# is DEFAULT_RR env-overridable anywhere?
out.append(("DEFAULT_RR env-overridable",
            any("DEFAULT_RR" in l and "getenv" in l for l in src)))

# ---- reproduce the exit arithmetic myself ---------------------------------
for e, s in ((100.00, 99.50), (250.00, 248.00), (35.00, 34.90), (612.34, 609.11)):
    p = osz.build_options_plan("TEST", "call", e, s, max_loss=1000.0)
    risk = e - s
    out.append((f"call {e}/{s}",
                f"stock_target={p.stock_target} -> {(p.stock_target-e)/risk:.4f}R | "
                f"prem R=(tgt-entry)/(entry-stop)="
                f"{(p.target_premium-p.entry_premium)/(p.entry_premium-p.stop_premium):.4f} | "
                f"max_reward/max_loss={p.max_reward/p.max_loss:.4f}"))
    q = osz.build_options_plan("TEST", "put", e, e + (e - s), max_loss=1000.0)
    out.append((f"put  {e}", f"stock_target={q.stock_target} -> "
                f"{(e-q.stock_target)/risk:.4f}R"))

# ---- (b) AST: does ANY live call site pass rr= ? --------------------------
for f in ("live_scanner.py", "backtest_window.py", "omen_bot.py"):
    fp = os.path.join(ROOT, f)
    if not os.path.exists(fp):
        continue
    tree = ast.parse(open(fp, encoding="utf-8").read())
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and \
                n.func.id in ("build_options_plan", "build_futures_plan"):
            kws = sorted(k.arg for k in n.keywords if k.arg)
            out.append((f"{f}:{n.lineno} {n.func.id}",
                        f"kwargs={kws} | rr passed = {'rr' in kws}"))

# ---- (c) is there a runner in the live path? ------------------------------
import paper_trader as pt
out.append(("paper_trader.RULE6_ENABLED", pt.RULE6_ENABLED))
psrc = open(os.path.join(ROOT, "paper_trader.py"), encoding="utf-8").read()
out.append(("RULE6 env-overridable", "getenv" in psrc.split("RULE6_ENABLED")[1][:80]))
# the post-BE runner leg: what does it exit at?
out.append(("runner leg target", "stock_target (2R) — see paper_trader.py:201"))

# ---- book census: which book, and how many rows book >2R ------------------
bp = os.path.join(ROOT, "research", "bt2y_trades.json")
if os.path.exists(bp):
    b = json.load(open(bp, encoding="utf-8"))
    rows = b["trades"] if isinstance(b, dict) and "trades" in b else b
    out.append(("bt2y_trades.json rows", len(rows)))
    if isinstance(b, dict):
        out.append(("book meta", {k: v for k, v in b.items() if k != "trades"}))
    rr = [t.get("r_multiple", t.get("r", 0.0)) for t in rows]
    out.append(("rows with R > 2.0 (shipped ladder book)",
                sum(1 for x in rr if x is not None and x > 2.0)))
    out.append(("rows with R > 2.0 share",
                f"{sum(1 for x in rr if x is not None and x > 2.0)/len(rows):.4%}"))
    out.append(("max R in book", max(x for x in rr if x is not None)))

for k, v in out:
    print(f"{k:52} {v}")
