"""Build the OMEN 9.0 overnight-swarm report.

Reuses build_bt2y_report.py's static-page shape (self-contained HTML, no
external assets, phone-readable) but not its per-trade facet dump: this page
is summary tables + per-arm JSON only, so it stays small regardless of book
size. Every table names its fill (signal-bar CLOSE entry, stop_rule fills,
signal_runner.min_risk_floor size gate, 1R=$1,000 unless stated) and the
script that produced it.

Sources: research/g154_rule_*.json (F5 rule sweep), research/g155/g156
refutation verdicts, research/g158_mid_candle_arms.json (F9), research/
g160_tweak_grid.json (O1), research/g171/g172/g173/g174 (funding ladder,
P1-P4), and research/g182_bugs_fixed.md (bug sweep).

Usage: python research/build_report_9_0.py [--out PATH]
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "research"

FILL_NOTE = (
    "Fill named once for the whole page: signal-bar CLOSE entry, "
    "stop_rule.stop_fill_price stops (disaster stop at DISASTER_STOP_R=1.0), "
    "size-gated on signal_runner.min_risk_floor, 1R = $1,000 unless an arm "
    "says otherwise. One-trade-a-day unit = research.omen_metrics."
    "first_of_day_arm. H1/H2 split at 2025-09-01. Book = research/"
    "bt2y_trades_retest_on.json, 498 sessions 2024-09-03..2026-09-02, "
    "RETEST_REQUIRED=1 (the shipped default)."
)


def load(name):
    p = RESEARCH / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def usd(v):
    if v is None:
        return "—"
    return f"${v:,.2f}"


def pct(v, nd=1):
    if v is None:
        return "—"
    return f"{v:.{nd}f}%"


# ---------------------------------------------------------------- Phase F --
RULE_SLUGS = [
    "entry-earlier-satisfiable-bar", "exhausted-overextended",
    "stop-placement-routed", "be-stop-after-enough-past-pt1",
    "ambiguous-stop-candidates", "displacement-graded-not-boolean",
    "scale-before-the-level", "scratch-exit-direction-match",
    "or-break-without-retest",
]

REFUTED_SLUGS = {
    "entry-earlier-satisfiable-bar", "exhausted-overextended",
    "stop-placement-routed", "be-stop-after-enough-past-pt1",
    "ambiguous-stop-candidates", "displacement-graded-not-boolean",
    "scale-before-the-level", "scratch-exit-direction-match",
}


# Hand-verified from the swarm's own F5/F6 refutation transcripts (each
# figure reproduced byte-for-byte by 3 independent refuters against the
# named script; g154_rule_*.json schemas vary too much to parse generically,
# so these are transcribed, not re-derived). Fill is the page-wide FILL_NOTE.
F5_HEADLINE = {
    "entry-earlier-satisfiable-bar": (33.93, -38.59, -145.33, 0.29, 30.5, 46.4),
    "exhausted-overextended": (33.94, 35.24, -36.30, 38.91, 30.5, 32.2),
    "stop-placement-routed": (33.93, 46.93, 9.73, 16.27, 30.5, 30.5),
    "be-stop-after-enough-past-pt1": (47.0, 65.0, 19.0, 18.0, 30.5, 30.5),
    "ambiguous-stop-candidates": (33.93, 29.94, -4.36, -3.62, 30.5, 31.7),
    "displacement-graded-not-boolean": (33.93, -36.03, -91.47, -47.78, 30.5, 38.3),
    "scale-before-the-level": (50.0, 93.0, 9.40, 76.50, 30.5, 30.5),
    "scratch-exit-direction-match": (33.93, 35.09, 1.89, 0.42, 30.5, 30.0),
    "or-break-without-retest": (33.93, 47.44, 8.56, 18.46, 30.5, 30.5),
}


def phase_f_rows():
    rows = []
    for slug in RULE_SLUGS:
        base_usd, cand_usd, h1d, h2d, p_before, p_after = F5_HEADLINE[slug]
        refuted = slug in REFUTED_SLUGS
        rows.append({
            "slug": slug,
            "script": f"research/g154_rule_{slug}.py",
            "baseline_usd": base_usd,
            "candidate_usd": cand_usd,
            "h1_delta": h1d,
            "h2_delta": h2d,
            "precision_before": p_before,
            "precision_after": p_after,
            "verdict": "REFUTED (3/3)" if refuted else "not formally refuted "
                       "(F7 forward-selection pick)",
        })
    return rows


def phase_f7():
    # F7's v0 uses the or-break-without-retest arm; figures transcribed from
    # research/g156_s_classifier_v0.md (whole-book, size-gated, 1R=$1,000).
    return {
        "baseline_usd": 33.93,
        "v0_usd": 47.44,
        "h1_delta": 8.56,
        "h2_delta": 18.46,
        "verdict": "Money delta REFUTED 3/3 (concentrated in 1-2 of 12-13 "
                   "changed sessions, placebo beats it ~7-9% of the time). "
                   "The 'honest zero' half — precision flat 30.5%, S recall "
                   "-0.3pp — was NOT refuted and is the real result. Shipped "
                   "as S_CLASSIFIER, default OFF.",
    }


def phase_f9():
    d = load("g158_mid_candle_arms.json")
    if d is None:
        return None
    return d.get("arms", {})


# ---------------------------------------------------------------- Phase O --
def phase_o1():
    d = load("g160_tweak_grid.json")
    if d is None:
        return None
    return {"n_arms": len(d.get("arms", [])), "arms": d.get("arms", [])[:40]}


# ---------------------------------------------------------------- Phase P --
def phase_p_funding():
    d = load("g174_funding_ladder.json")
    if d is None:
        return None
    return d


def render_phase_f(rows, f7, f9, f8):
    parts = [f"""
    <section id="phase-f">
      <h2>Phase F — rule mining (F5) and the S classifier (F7)</h2>
      <p class="deflabel">F5: 25 candidate rules mined from Austin's marks and
      the S/A/C ladder, swept as selection arms over the shipped
      RETEST_REQUIRED book. Each row below is the headline arm from its own
      script; 8 were formally declared survivors and every one of the 8 was
      refuted 3/3 by independent adversarial passes (F6). F7 then
      forward-selected the single best non-refuted candidate (or-break-
      without-retest) as S classifier v0 — shipped behind
      <code>S_CLASSIFIER</code>, default OFF.</p>
      <div class="tablewrap"><table>
        <thead><tr><th>rule</th><th>script</th><th>baseline $/day</th>
        <th>candidate $/day</th><th>H1 delta</th><th>H2 delta</th>
        <th>precision before→after</th><th>verdict (F6)</th></tr></thead>
        <tbody>
    """]
    for r in rows:
        parts.append(
            f"<tr><td>{esc(r['slug'])}</td><td class='mono'>{esc(r['script'])}"
            f"</td><td>{usd(r['baseline_usd'])}</td>"
            f"<td>{usd(r['candidate_usd'])}</td>"
            f"<td>{usd(r['h1_delta'])}</td><td>{usd(r['h2_delta'])}</td>"
            f"<td>{pct(r['precision_before'])} → {pct(r['precision_after'])}"
            f"</td><td>{esc(r['verdict'])}</td></tr>"
        )
    parts.append("</tbody></table></div>")

    if f7:
        parts.append(f"""
      <h3>F7 — S classifier v0 (research/g156_s_classifier_v0.md)</h3>
      <div class="tablewrap"><table><thead><tr><th>arm</th><th>$/day</th>
        <th>H1 delta</th><th>H2 delta</th></tr></thead><tbody>
        <tr><td>baseline (first_of_day_arm)</td><td>{usd(f7['baseline_usd'])}</td>
        <td>—</td><td>—</td></tr>
        <tr><td>v0 (S_CLASSIFIER=1)</td><td>{usd(f7['v0_usd'])}</td>
        <td>{usd(f7['h1_delta'])}</td><td>{usd(f7['h2_delta'])}</td></tr>
      </tbody></table></div>
      <p class="deflabel">{esc(f7['verdict'])}. Precision target &gt;39.5%,
      shipped flag holds precision flat at 30.5% (18/59) — the target is
      NOT met. S_CLASSIFIER defaults OFF in signal_runner.py.</p>
    """)

    if f9:
        parts.append("""
      <h3>F9 — mid-candle resting-limit arms (research/g158_mid_candle_arms.py)</h3>
      <p class="deflabel">Nothing here is shipped — read-only measurement of
      resting a limit at a fraction of the signal bar's own range, strictly
      after the signal bar, vs the shipped CLOSE fill.</p>
      <div class="tablewrap"><table><thead><tr><th>arm</th><th>$/day</th>
        <th>H1 $/day</th><th>H2 $/day</th><th>mean R</th>
        <th>green mo.</th></tr></thead><tbody>
    """)
        for name, a in f9.items():
            c = a.get("combined", {})
            h1 = a.get("H1", {})
            h2 = a.get("H2", {})
            parts.append(
                f"<tr><td>{esc(name)}</td><td>{usd(c.get('per_day'))}</td>"
                f"<td>{usd(h1.get('per_day'))}</td><td>{usd(h2.get('per_day'))}</td>"
                f"<td>{c.get('mean_r', '—')}</td>"
                f"<td>{c.get('months_green','—')}/{c.get('months','—')}</td></tr>"
            )
        parts.append("</tbody></table></div>")

    if f8:
        parts.append(f"""
      <h3>F8 — ML ceiling check (research/g157_ml_ceiling.md)</h3>
      <p class="deflabel">Logistic regression + gradient boosting on the 120
      judged day-cards' first candidates (5-fold CV grouped by month). Both
      scored near chance: logreg AUC 0.492, GBM AUC 0.426 — no learned edge
      over the rule engine on this corpus. Small-N (4 CV groups); not
      overclaimed as a ceiling on the full 1,057-mark corpus.</p>
    """)
    parts.append("</section>")
    return "".join(parts)


def render_phase_o(o1):
    if o1 is None:
        return ""
    arms = o1["arms"]
    rows = []
    for a in arms:
        rows.append(
            "<tr>"
            f"<td>{esc(a.get('day_policy',''))}</td>"
            f"<td>{esc(a.get('window_end',''))}</td>"
            f"<td>{esc(a.get('tier_policy',''))}</td>"
            f"<td>{esc(a.get('veto1d',''))}</td>"
            f"<td>{esc(a.get('classifier',''))}</td>"
            f"<td>{a.get('n_all','—')}</td><td>{a.get('ev_r_all','—')}</td>"
            f"<td>{a.get('ev_r_h1','—')}</td>"
            f"<td>{a.get('ev_r_h2','—')}</td>"
            f"<td>{usd(a.get('dollars_day_all'))}</td>"
            "</tr>"
        )
    return f"""
    <section id="phase-o">
      <h2>Phase O — the tweak grid (O1) and what shipped (O2)</h2>
      <p class="deflabel">research/g160_tweak_grid.py swept DAY_POLICY x
      ENTRY_WINDOW_END x FIRE_A_WHEN_NO_S x VETO_1D x S_CLASSIFIER as
      selection arms over the shipped book. Refuted 3x on multiplicity and a
      lookahead in the VETO_1D proxy (spy_trend reads the day's own close).
      Verdict stands even under the causal fix: no arm — baseline included —
      is positive in both H1 and H2. O2 wired the four flags into
      signal_runner.py/live_scanner.py with every default reproducing today's
      shipped behavior exactly (no grid winner shipped); FIRE_A_WHEN_NO_S and
      VETO_1D are read-only/stamped, not live gates.</p>
      <div class="tablewrap"><table><thead><tr>
        <th>day policy</th><th>window</th><th>tier</th><th>veto1d</th>
        <th>classifier</th><th>n</th><th>ev_r all</th><th>ev_r H1</th>
        <th>ev_r H2</th><th>$/day</th></tr></thead><tbody>
        {''.join(rows)}
      </tbody></table></div>
    </section>
    """


def render_phase_p(fd):
    if fd is None:
        return ""
    streams = fd.get("streams", {})
    recon = fd.get("denominator_reconciliation", {})
    rows = []
    for key, s in streams.items():
        for half in ("full", "H1", "H2"):
            h = s.get(half)
            if not h:
                continue
            rows.append(
                f"<tr><td>{esc(key)}</td><td>{esc(half)}</td>"
                f"<td>{h.get('n','—')}</td><td>{usd(h.get('per_day'))}</td>"
                f"<td>{h.get('mean_r','—')}</td><td>{pct(h.get('win_pct'))}</td>"
                f"<td>{h.get('green_months','—')}/{h.get('months','—')}</td>"
                f"<td>{usd(h.get('max_dd_dollars'))}</td></tr>"
            )
    pass_rows = "".join(
        f"<tr><td>{esc(r['rung'])}</td><td>{esc(r['firm'])}</td>"
        f"<td>{r['stream_n']}</td><td>{pct(r['all_starts_pass_pct'])}</td></tr>"
        for r in fd.get("all_starts_pass_rates", [])
    )
    drift_rows = "".join(
        f"<tr><td>{esc(k)}</td><td>{v.get('mean_r_now')}</td>"
        f"<td>{v.get('mean_r_needed')}</td><td>+{v.get('offset_r')}R</td>"
        f"<td>{pct(v.get('pass_pct_there'))}</td></tr>"
        for k, v in fd.get("drift_to_50pct", {}).items()
    )
    return f"""
    <section id="phase-p">
      <h2>Phase P — the funding ladder (P0-P4)</h2>
      <p class="deflabel">P1 futures-proxy: REFUTED — "0.0% rolling-252 pass
      rate" was a window=min(252,n) artifact (n=234 sessions = exactly one
      window); corrected all-starts pass rate is 12-27% per firm
      (research/g171_futures_proxy_arms.py + refuter re-runs), reproduced
      here at 26.9%/12.0%. Direction survives (money is near-zero/negative),
      the "fails every firm at 0.0%" headline does not.
      P2 Vanquish (S-only stream): not refuted — every risk level fails on
      trailing drawdown, classifier on/off identical.
      P3 Trade The Pool: all 8 real account/plan rows fail on daily-loss-limit
      or trailing-drawdown. Lucid: automation permission confirmed live but
      every primary spec page 403s — BLOCKED, not ranked.
      No rung on the ladder is fundable on tonight's book: the blocker is the
      edge (near-zero or negative mean R every stream, every half), not the
      account type.</p>
      <div class="tablewrap"><table><thead><tr><th>stream</th><th>period</th>
        <th>n</th><th>$/day</th><th>mean R</th><th>win%</th>
        <th>green months</th><th>max DD</th></tr></thead><tbody>{''.join(rows)}
      </tbody></table></div>
      <h3>Book size-gate reconciliation</h3>
      <div class="tablewrap"><table><thead><tr><th>arm</th><th>n</th>
        <th>$/day</th><th>mean R</th><th>green</th></tr></thead><tbody>
        <tr><td>{esc(recon.get('canonical_498_size_gated',{}).get('label',''))}</td>
        <td>{recon.get('canonical_498_size_gated',{}).get('n','—')}</td>
        <td>{usd(recon.get('canonical_498_size_gated',{}).get('per_day'))}</td>
        <td>{recon.get('canonical_498_size_gated',{}).get('mean_r','—')}</td>
        <td>{recon.get('canonical_498_size_gated',{}).get('green_months','—')}/25</td></tr>
        <tr><td>{esc(recon.get('legacy_pick_then_gate',{}).get('label',''))}</td>
        <td>{recon.get('legacy_pick_then_gate',{}).get('n','—')}</td>
        <td>{usd(recon.get('legacy_pick_then_gate',{}).get('per_day'))}</td>
        <td>{recon.get('legacy_pick_then_gate',{}).get('mean_r','—')}</td>
        <td>{recon.get('legacy_pick_then_gate',{}).get('green_months','—')}/25</td></tr>
      </tbody></table></div>
      <h3>All-starts eval pass rate (corrected; research/g171_refute3_reproduce.md)</h3>
      <div class="tablewrap"><table><thead><tr><th>rung</th><th>firm</th>
        <th>stream n</th><th>pass %</th></tr></thead><tbody>{pass_rows}
      </tbody></table></div>
      <h3>What it would take (research/g174_funding_ladder.py)</h3>
      <div class="tablewrap"><table><thead><tr><th>target</th>
        <th>mean R now</th><th>mean R needed</th><th>swing</th>
        <th>pass% there</th></tr></thead><tbody>{drift_rows}
      </tbody></table></div>
    </section>
    """


def lane_row(label, half):
    return (
        f"<tr><td>{esc(label)}</td><td>{half.get('n','—')}</td>"
        f"<td>{usd(half.get('per_day'))}</td><td>{half.get('mean_r','—')}</td>"
        f"<td>{pct(half.get('win_pct'))}</td>"
        f"<td>{half.get('green_months','—')}/{half.get('months','—')}</td></tr>"
    )


def render_lanes():
    """Three symbol-pool slices of the one-trade-a-day unit, side by side.
    Added in OMEN 9.0 wave 2 (W4, Austin's explicit ask): the core-10 slice
    is now measured by research/g174_funding_ladder.py alongside full/index
    on the identical unit, so this table is no longer missing a lane."""
    d = load("g174_funding_ladder.json") or {}
    streams = d.get("streams", {})
    core_syms = d.get("core_symbols", [])
    idx_syms = d.get("index_symbols", [])
    idx = streams.get("IDX_first_of_day", {})
    core = streams.get("CORE_first_of_day", {})
    full = streams.get("A_base_first_of_day", {})
    full_lbl = "full pool (29 symbols, universe.ALL_SYMS)"
    core_lbl = f"core {len(core_syms)} (universe.CORE_SYMBOLS)"
    idx_lbl = f"index {len(idx_syms)} (universe.INDEX_POOL)"
    rows = []
    for lbl, s in ((full_lbl, full), (core_lbl, core), (idx_lbl, idx)):
        for half_key, half_lbl in (("full", "full 2y"), ("H1", "H1"), ("H2", "H2")):
            rows.append(lane_row(f"{lbl} — {half_lbl}" if half_key != "full" else lbl,
                                  s.get(half_key, {})))
    return f"""
    <section id="lanes">
      <h2>Lane slices — one-trade-a-day unit</h2>
      <p class="deflabel">Three symbol-pool slices of the same
      first-of-day-arm construction (research.omen_metrics.first_of_day_arm),
      same fill, same H1/H2 split. Each is one definition, no overlap counted
      twice within a row: "full pool" = every symbol in universe.ALL_SYMS
      (29); "core {len(core_syms)}" = universe.CORE_SYMBOLS
      ({esc(', '.join(core_syms))} — his own watchlist split, historically
      called "core-10" though SPY's 2026-08-11 re-inclusion makes it
      {len(core_syms)}); "index {len(idx_syms)}" = universe.INDEX_POOL
      ({esc(', '.join(idx_syms))}). Core and index overlap on
      {esc(', '.join(sorted(set(core_syms) & set(idx_syms))) or 'none')} by
      construction — both pools are read straight off universe.py, not
      de-duplicated against each other. script: research/g174_funding_ladder.py.</p>
      <div class="tablewrap"><table><thead><tr><th>lane / period</th><th>n</th>
        <th>$/day</th><th>mean R</th><th>win%</th><th>green months</th>
        </tr></thead><tbody>
        {''.join(rows)}
      </tbody></table></div>
    </section>
    """


def render_bugs():
    n_confirmed = 15
    n_raw = 71
    return f"""
    <section id="bugs">
      <h2>Bug sweep (B1-B3)</h2>
      <p class="deflabel">{n_raw} raw findings triaged, {n_confirmed}
      confirmed and fixed with root-cause remedies and test coverage.
      Full list: research/g182_bugs_fixed.md.</p>
    </section>
    """


def build(out_path):
    rows = phase_f_rows()
    f7 = phase_f7()
    f9 = phase_f9()
    o1 = phase_o1()
    fd = phase_p_funding()

    body = f"""
    <header>
      <h1>OMEN 9.0 — overnight swarm report</h1>
      <p class="deflabel">Base f8740f80. Built by research/build_report_9_0.py.
      {FILL_NOTE}</p>
    </header>
    {render_lanes()}
    {render_phase_f(rows, f7, f9, None)}
    {render_phase_o(o1)}
    {render_phase_p(fd)}
    {render_bugs()}
    <footer><p class="deflabel">No category appears twice. Report:
    research/g190_report_build.md.</p></footer>
    """

    html = f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>OMEN 9.0 Report</title>
<style>
:root {{ color-scheme: light dark; }}
body {{ margin:0; padding:24px; font-family:-apple-system,Segoe UI,Arial,
  sans-serif; background:#0b0d12; color:#e8ecf1; line-height:1.5; }}
h1 {{ font-size:1.6rem; margin:0 0 8px; }}
h2 {{ font-size:1.25rem; margin-top:2.2rem; border-bottom:1px solid #2a3040;
  padding-bottom:6px; }}
h3 {{ font-size:1.05rem; margin-top:1.4rem; color:#9fb3d9; }}
.deflabel {{ color:#a6b0c3; font-size:0.92rem; max-width:900px; }}
.tablewrap {{ overflow-x:auto; margin:10px 0 18px; }}
table {{ border-collapse:collapse; width:100%; font-size:0.86rem;
  min-width:600px; }}
th, td {{ border:1px solid #2a3040; padding:6px 9px; text-align:right;
  white-space:nowrap; }}
th:first-child, td:first-child {{ text-align:left; white-space:normal; }}
thead th {{ background:#161a23; position:sticky; top:0; }}
tbody tr:nth-child(even) {{ background:#12151d; }}
.mono {{ font-family:ui-monospace,Consolas,monospace; font-size:0.82rem; }}
code {{ background:#161a23; padding:1px 5px; border-radius:3px; }}
footer {{ margin-top:2.5rem; }}
</style></head>
<body>
{body}
</body></html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path, len(html.encode("utf-8"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(RESEARCH / "omen-9-0-report.html"))
    args = ap.parse_args()
    path, size = build(Path(args.out))
    print(f"wrote {path} ({size/1024:.1f} KB)")
