"""Prop-firm rule-drift watcher (R109).

Fetches each firm's official rules/pricing page(s), extracts price / drawdown /
daily-loss / consistency with regexes, writes rules_snapshot.json, and alerts
(stdout + optional ntfy via NTFY_TOPIC env) when an extracted field changes
versus the previous snapshot. A field only alerts when both old and new values
are non-null, so a flaky regex never pages; a field going null is reported as
"unreadable" in the snapshot only.

Usage: python scripts/rule_drift_watcher.py [--snapshot rules_snapshot.json] [--no-ntfy]
Exit code: 0 = no change, 1 = >=1 alert.
"""
import argparse, hashlib, html, json, os, re, sys, time, urllib.request

FIELDS = ("price", "dd", "dll", "consistency")

# (firm, [urls], {field: [regexes; group 1 is the value]})  -- 50K plan terms
FIRMS = [
    ("Topstep", ["https://help.topstep.com/en/articles/8284197-trading-combine-parameters"],
     {"consistency": [r"below (\d+)% of your Profit Target"]}),
    ("Topstep-site", ["https://www.topstep.com/topstep-prop"],
     {"price": [r"\$50K Buying Power \$(\d+) \$\d+ /month"]}),
    ("MFFU", ["https://help.myfundedfutures.com/en/articles/13134709-rapid-plan-50k-a-comprehensive-look"],
     {"dd": [r"Maximum Loss Limit \(EOD\) \$([\d,]+)"],
      "dll": [r"Daily Loss Limit (None|\$[\d,]+)"],
      "consistency": [r"Consistency (\d+)% \(Eval Only\)"]}),
    ("MFFU-price", ["https://myfundedfutures.com/plans/rapid"],
     {"price": [r"Based on current promotions \$(\d+)"], "dd": [r"Max Drawdown \$([\d,]+)"]}),
    ("Alpha", ["https://alpha-futures.com"],
     {"price": [r"50K Standard Eval \$(\d+)"]}),
    ("Bulenox", ["https://bulenox.com/accounts-pricing"],
     {"price": [r"Profit target \$3,000 Drawdown up to \$2,500 .{0,80}?\$(\d+) one-time"],
      "dd": [r"Profit target \$3,000 Drawdown up to \$([\d,]+)"]}),
    ("TPT", ["https://takeprofittrader.com"],
     {"price": [r"\$(\d+)\s*/\s*month", r"\$(\d+)\s*(?:per|a) month"]}),
    ("Lucid", ["https://support.lucidtrading.com/en/articles/11404728-other-activities"],
     {}),  # no numeric rules on this page; hash only (automation policy)
    ("Alpha-rules", ["https://help.alpha-futures.com/en/articles/9508585-prohibited-trading-practices"],
     {}),
]


def fetch_text(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode("utf8", "ignore")
    raw = re.sub(r"(?s)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw))


def extract(text, patterns):
    out = {f: None for f in FIELDS}
    for field, pats in patterns.items():
        for p in pats:
            m = re.search(p, text)
            if m:
                out[field] = m.group(1).replace(",", "")
                break
    return out


def run(fetch=fetch_text):
    snap = {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "firms": {}}
    for firm, urls, pats in FIRMS:
        text, err = "", None
        try:
            text = " ".join(fetch(u) for u in urls)
        except Exception as e:  # network/403: record, never crash
            err = f"{type(e).__name__}: {e}"[:200]
        rec = extract(text, pats)
        rec.update(urls=urls, ok=err is None, error=err,
                   text_sha256=hashlib.sha256(text.encode()).hexdigest() if text else None)
        snap["firms"][firm] = rec
    return snap


def diff(old, new):
    alerts = []
    for firm, rec in new["firms"].items():
        prev = old.get("firms", {}).get(firm)
        if not prev:
            continue
        for f in FIELDS:
            a, b = prev.get(f), rec.get(f)
            if a is not None and b is not None and a != b:
                alerts.append(f"{firm} {f}: {a} -> {b}")
    return alerts


def main(argv=None, fetch=fetch_text):
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default="rules_snapshot.json")
    ap.add_argument("--no-ntfy", action="store_true")
    a = ap.parse_args(argv)
    old = {}
    if os.path.exists(a.snapshot):
        with open(a.snapshot) as fh:
            old = json.load(fh)
    new = run(fetch)
    alerts = diff(old, new)
    with open(a.snapshot, "w") as fh:
        json.dump(new, fh, indent=2, sort_keys=True)
    ok = sum(1 for r in new["firms"].values() if r["ok"])
    print(f"wrote {a.snapshot}: {len(new['firms'])} firms, {ok} fetched ok")
    for line in alerts:
        print("ALERT", line)
    topic = os.environ.get("NTFY_TOPIC")
    if alerts and topic and not a.no_ntfy:
        req = urllib.request.Request(f"https://ntfy.sh/{topic}", data="\n".join(alerts).encode(),
                                     headers={"Title": "Prop rule drift"})
        urllib.request.urlopen(req, timeout=15)
    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())
