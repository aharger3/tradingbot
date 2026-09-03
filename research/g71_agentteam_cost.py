"""g71_agentteam: the monthly dollar figure for the standing agent team.

Every number in `research/g71_agentteam.md` section 3 comes out of this file.
Run it:  python research/g71_agentteam_cost.py

Two inputs, both stated openly because both are estimates and one is fuzzy:

  ROLES   per-role run counts and token volumes. Calibrated off the sessions
          this repo already runs -- a mechanical script-runner session reads
          CLAUDE.md + DIRECTION.md + one rig and writes one .md (~40-120k in);
          an analysis session reads a rig, its inputs and three prior reports
          (~300-600k in); a frontier diagnosis session like the g71 batch runs
          ~1.2M in. Output is 4-60k. These are ESTIMATES, not measurements.
          Nothing in the repo meters agent token use today -- see finding F7.

  PRICES  published list prices, fetched 2026-08-29, sources in the .md.

Stdlib only. No repo imports -- this answers a spend question, not a trading one.
"""
from __future__ import annotations

# ---------------------------------------------------------------- prices ---
# USD per million tokens, fetched 2026-08-29. Sources cited in g71_agentteam.md.
PRICES = {
    # provider/model:            (input, cache_write_5m, cache_hit, output)
    "anthropic/opus-5":          (5.00,  6.25,  0.50, 25.00),
    "anthropic/sonnet-5":        (2.00,  2.50,  0.20, 10.00),
    "anthropic/haiku-4.5":       (1.00,  1.25,  0.10,  5.00),
    "deepseek/v4-flash-offpeak": (0.22,  0.22,  0.007, 0.66),
    "deepseek/v4-pro-offpeak":   (0.66,  0.66,  0.022, 1.98),
    "openai/gpt-5.6-luna":       (0.20,  0.20,  0.00,  1.20),
    "openai/gpt-5-nano":         (0.05,  0.05,  0.00,  0.40),
    "google/gemini-3.7-flash":   (0.75,  0.75,  0.00,  3.75),
    "google/gemini-flash-free":  (0.00,  0.00,  0.00,  0.00),
    "local/qwen3.5-4b":          (0.00,  0.00,  0.00,  0.00),
}

# Flat monthly subscriptions, USD/month, list price 2026-08-29.
SUBS = {
    "glm-coding-lite":  18.00,
    "glm-coding-pro":   72.00,
    "glm-coding-max":  160.00,
    "chatgpt-plus":     20.00,
    "chatgpt-pro-5x":  100.00,
    "claude-pro":       20.00,
    "claude-max-5x":   100.00,
    "claude-max-20x":  200.00,
}

# GLM Coding Plan quota, expressed the way z.ai markets it (prompts, not tokens).
# Lite ~400 prompts/week, Pro ~2,000/week, Max ~8,000/week.
GLM_PROMPTS_PER_MONTH = {"glm-coding-lite": 1600, "glm-coding-pro": 8000,
                         "glm-coding-max": 32000}

# --------------------------------------------------------------- the team ---
# (role, runs/month, input tok/run, output tok/run, model turns/run, tier)
ROLES = [
    ("GATEKEEPER",   6,    150_000,  10_000, 12, "cheap"),   # script normally; model only on RED
    ("QUARTERMASTER", 30,   40_000,   4_000,  8, "bulk"),
    ("SCRIBE",       30,   120_000,  10_000, 15, "cheap"),
    ("LIBRARIAN",    40,   200_000,  12_000, 20, "plan"),
    ("METRICIAN",    20,   600_000,  40_000, 55, "plan"),
    ("BRIDGE",       20,   300_000,  20_000, 30, "plan"),
    ("CONCIERGE",     8,   400_000,  30_000, 40, "plan"),
    ("SCEPTIC",      10, 1_200_000,  60_000, 70, "edge"),
]

CACHE_HIT_FRAC = 0.80   # repo docs are byte-identical every run; 20% is the new work


def metered(model: str, in_tok: float, out_tok: float) -> float:
    """USD for in/out tokens on a metered API, with prompt caching applied."""
    inp, cw, ch, outp = PRICES[model]
    hit = in_tok * CACHE_HIT_FRAC
    miss = in_tok * (1 - CACHE_HIT_FRAC)
    # 5-minute cache expires between cron runs, so the cached block is
    # re-written once per run: charge the write on the hit volume too.
    return (miss * inp + hit * ch + hit * cw) / 1e6 + out_tok * outp / 1e6


def totals(tier_of_role: dict) -> dict:
    agg = {}
    for role, runs, tin, tout, turns, _default in ROLES:
        tier = tier_of_role[role]
        agg.setdefault(tier, {"in": 0.0, "out": 0.0, "prompts": 0})
        agg[tier]["in"] += runs * tin
        agg[tier]["out"] += runs * tout
        agg[tier]["prompts"] += runs * turns
    return agg


def scenario(name: str, tier_model: dict, tier_of_role: dict, subs: list[str]):
    agg = totals(tier_of_role)
    lines, cost = [], 0.0
    for tier, v in sorted(agg.items()):
        model = tier_model[tier]
        c = metered(model, v["in"], v["out"]) if model in PRICES else 0.0
        cost += c
        lines.append(f"    {tier:<6} {model:<26} "
                     f"{v['in']/1e6:7.1f}M in {v['out']/1e6:5.2f}M out "
                     f"{v['prompts']:6,d} prompts  ${c:7.2f}")
    sub_cost = sum(SUBS[s] for s in subs)
    for s in subs:
        lines.append(f"    sub    {s:<26} {'':<40} ${SUBS[s]:7.2f}")
        if s in GLM_PROMPTS_PER_MONTH:
            used = agg.get("plan", {}).get("prompts", 0)
            cap = GLM_PROMPTS_PER_MONTH[s]
            flag = "OK" if used <= cap else "OVER QUOTA"
            lines.append(f"           quota {used:,d} / {cap:,d} prompts per month -> {flag}")
    print(f"\n{name}")
    print("\n".join(lines))
    print(f"    {'TOTAL':<33}{'':<40} ${cost + sub_cost:7.2f} / month")
    return cost + sub_cost


if __name__ == "__main__":
    print("g71_agentteam - monthly spend, list prices fetched 2026-08-29")
    print(f"team volume: {sum(r[1]*r[2] for r in ROLES)/1e6:.0f}M input tokens, "
          f"{sum(r[1]*r[3] for r in ROLES)/1e6:.1f}M output tokens per month "
          f"across {sum(r[1] for r in ROLES)} runs")

    default = {r[0]: r[5] for r in ROLES}

    # A. What router.json does TODAY: every tier points at api.anthropic.com.
    scenario("A. STATUS QUO - loop-local/router.json, all tiers on Anthropic API",
             {"bulk": "anthropic/haiku-4.5", "cheap": "anthropic/haiku-4.5",
              "plan": "anthropic/sonnet-5", "edge": "anthropic/opus-5"},
             default, [])

    # B. Recommended: local bulk, DeepSeek cheap, GLM Pro plan, Opus 5 sceptic.
    scenario("B. RECOMMENDED - local bulk / DeepSeek cheap / GLM Pro plan / Opus 5 sceptic",
             {"bulk": "local/qwen3.5-4b", "cheap": "deepseek/v4-flash-offpeak",
              "plan": "GLM_PLAN", "edge": "anthropic/opus-5"},
             default, ["glm-coding-pro"])

    # C1. Does the cheap GLM tier hold the plan lane? (No -- it does not.)
    scenario("C1. LITE PROBE - GLM Lite plan / Sonnet 5 sceptic",
             {"bulk": "local/qwen3.5-4b", "cheap": "deepseek/v4-flash-offpeak",
              "plan": "GLM_PLAN", "edge": "anthropic/sonnet-5"},
             default, ["glm-coding-lite"])

    # C2. Lean but inside quota: GLM Pro, Sonnet sceptic instead of Opus.
    scenario("C2. LEAN - GLM Pro plan / Sonnet 5 sceptic",
             {"bulk": "local/qwen3.5-4b", "cheap": "deepseek/v4-flash-offpeak",
              "plan": "GLM_PLAN", "edge": "anthropic/sonnet-5"},
             default, ["glm-coding-pro"])

    # D. All-metered on DeepSeek, to show the cheap tier is a rounding error.
    scenario("D. FLOOR - everything on DeepSeek V4 off-peak (capability aside)",
             {"bulk": "deepseek/v4-flash-offpeak", "cheap": "deepseek/v4-flash-offpeak",
              "plan": "deepseek/v4-flash-offpeak", "edge": "deepseek/v4-pro-offpeak"},
             default, [])
