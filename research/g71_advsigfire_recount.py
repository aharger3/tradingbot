import json, collections, pathlib
p = pathlib.Path(__file__).resolve().parents[1] / "research/bt2y_trades.json"
d = json.loads(p.read_text(encoding="utf-8"))
meta, rows = d["meta"], d["trades"]
print("meta:", {k: meta[k] for k in meta if k != "symbols"})
print("len(rows)", len(rows))
print("meta.signals == len(rows):", meta["signals"] == len(rows))
st = collections.Counter(r.get("status") for r in rows)
for k, v in st.most_common():
    print(" status", k, v, "%.2f%%" % (100*v/len(rows)))
gr = collections.Counter(r.get("grade") for r in rows)
print("grade:", dict(gr))
print("traded true:", sum(1 for r in rows if r.get("traded")))
print("meta.traded", meta.get("traded"), "meta.halted", meta.get("halted"))
# grade X share
nx = sum(1 for r in rows if r.get("grade") == "X")
print("grade X:", nx, "%.2f%%" % (100*nx/len(rows)))
# cross: status vs grade
cx = collections.Counter((r.get("status"), r.get("grade")) for r in rows)
for k,v in cx.most_common(12): print("  ", k, v)
# halted
h = sum(1 for r in rows if r.get("halted"))
print("rows with halted flag:", h)
