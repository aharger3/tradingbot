"""Run the declared mamba cells (declared.json) on the fit window. usage: python run.py
Writes result_N1.json, result_N2.json, result_ES_twins.json, trades_N1.csv, trades_N2.csv, trades_ES_twins.csv, run_meta.json."""
import csv, hashlib, json, os, sys, time
import numpy as np
import mentor3 as r

m = r.m
HERE = os.environ.get("MR3_OUT", os.path.dirname(os.path.abspath(__file__)))     # MR3_OUT / MR3_FUT / MR3_NDRAW: smoke tests only
FUT = os.environ.get("MR3_FUT", m.FUT)
NDRAW = int(os.environ.get("MR3_NDRAW", 2000))
SEED = 7


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def evaluate(days, variants, spec, split):
    trades, summ = {}, {}
    for v, fn in variants.items():
        tr, sk = m.build_trades(days, fn, spec)
        trades[v] = tr
        summ[v] = m.summarize(tr, split, sk)
        print(f"  {v}: n={summ[v]['n']} meanR={summ[v]['meanR']} (skip {sk})", flush=True)
    return trades, summ


def primary_of(summ, names):
    ok = [v for v in names if summ[v]["n"] >= 30]
    return max(ok, key=lambda v: (summ[v]["meanR"], summ[v]["n"])) if ok else None


def write_csv(name, rows):
    if rows:
        with open(os.path.join(HERE, name), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)


def main():
    t0 = time.time()
    SRC = os.path.dirname(os.path.abspath(__file__))
    meta = dict(mentor3_sha256=sha(os.path.join(SRC, "mentor3.py")), declared_sha256=sha(os.path.join(SRC, "declared.json")),
                run_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    print(meta, flush=True)
    nq_all, es_all = r.load_fut("NQ", fut=FUT), r.load_fut("ES", fut=FUT)
    nq, es = r.align(nq_all, es_all)
    dates = sorted(nq)
    print(f"NQ sessions {len(nq_all)}, ES sessions {len(es_all)}, aligned with all four levels {len(dates)}: {dates[0]} .. {dates[-1]}", flush=True)
    assert dates[0] > m.RESERVED_END
    split = dates[len(dates) // 2]
    days_nq, days_es = r.pair(nq, es), r.pair(es, nq)

    n1, n2 = r.n1_variants(r.SPEC_NQ), r.n2_variants(r.SPEC_NQ)
    allv = {**n1, **n2}
    print("trading NQ", flush=True)
    trades, summ = evaluate(days_nq, allv, r.SPEC_NQ, split)

    # descriptive: how often does the divergence exist at all (raw triggers, conflicts)
    diag = {}
    for lv in ("ON", "PD"):
        any_trig = conflict = 0
        for A in days_nq:
            t = r.smt_triggers(A, A["x"], lv)
            if t:
                any_trig += 1
                j = t[0][0]
                conflict += sum(1 for x in t if x[0] == j) > 1
        diag[f"N1_{lv}"] = dict(days_with_trigger=any_trig, first_bar_conflicts=conflict)
    diag["days_near_key_level"] = int(sum(r.near_key_level(A) for A in days_nq))

    sessions = {"NQ": nq}
    sh = m.shuffle_means({v: t for v, t in trades.items() if t}, sessions, r.SPEC_NQ, ndraw=NDRAW, seed=SEED)
    for v in allv:
        summ[v]["shuffle_p"] = m.perm_p(summ[v]["meanR"], sh[v]) if v in sh else None
        summ[v]["shuffle_mean_R"] = float(np.mean(sh[v])) if v in sh else None
        summ[v]["clears_std_bar"] = m.clears_std(summ[v], summ[v]["shuffle_p"])

    fams = {"N1": list(n1), "N2": list(n2)}
    prim = {k: primary_of(summ, v) for k, v in fams.items()}
    ok_all = [v for v in allv if summ[v]["n"] >= 30]
    joint = np.max(np.vstack([sh[v] for v in ok_all]), axis=0) if ok_all else None
    results = {}
    for k, names in fams.items():
        ok = [v for v in names if summ[v]["n"] >= 30]
        p = prim[k]
        fw = m.perm_p(summ[p]["meanR"], np.max(np.vstack([sh[v] for v in ok]), axis=0)) if p else None
        fw_joint = m.perm_p(summ[p]["meanR"], joint) if p else None
        res = dict(candidate=k, sessions=len(dates), split=split, first_last=[dates[0], dates[-1]],
                   variants={v: summ[v] for v in names}, primary=p,
                   primary_clears_std_bar=bool(p and summ[p]["clears_std_bar"]),
                   family_wise_p_primary=fw, family_wise_p_primary_both_candidates=fw_joint,
                   ndraw=NDRAW, seed=SEED, diag=diag)
        results[k] = res
        json.dump(res, open(os.path.join(HERE, f"result_{k}.json"), "w"), indent=1)
        write_csv(f"trades_{k}.csv", [dict(variant=v, **t) for v in names for t in trades[v]])

    # ES replication of each candidate's primary variant (declared; report only, not in the family)
    twins, twin_rows = {}, []
    es_variants = {**r.n1_variants(r.SPEC_ES), **r.n2_variants(r.SPEC_ES)}
    for k, p in prim.items():
        if not p:
            twins[k] = None
            continue
        print("trading ES twin of", p, flush=True)
        tr, sm = evaluate(days_es, {p: es_variants[p]}, r.SPEC_ES, split)
        sm = sm[p]
        if tr[p]:
            shp = m.shuffle_means({p: tr[p]}, {"ES": es}, r.SPEC_ES, ndraw=NDRAW, seed=SEED)[p]
            sm["shuffle_p"] = m.perm_p(sm["meanR"], shp)
            sm["clears_std_bar"] = m.clears_std(sm, sm["shuffle_p"])
        twins[k] = dict(variant=p, **sm)
        twin_rows += [dict(candidate=k, variant=p, **t) for t in tr[p]]
    json.dump(twins, open(os.path.join(HERE, "result_ES_twins.json"), "w"), indent=1)
    write_csv("trades_ES_twins.csv", twin_rows)
    meta["seconds"] = round(time.time() - t0)
    json.dump(meta, open(os.path.join(HERE, "run_meta.json"), "w"), indent=1)
    for k, res in results.items():
        print(k, "primary", res["primary"], "clears", res["primary_clears_std_bar"], "fw", res["family_wise_p_primary"],
              "fw_both", res["family_wise_p_primary_both_candidates"])


if __name__ == "__main__":
    main()
