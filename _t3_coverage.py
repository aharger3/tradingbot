import json
from pathlib import Path
from collections import Counter, defaultdict

pairs=set()
for line in open('research/corpus_instances.jsonl'):
    r=json.loads(line); pairs.add((r['symbol'],r['day']))
spairs=sorted(pairs)
shard_of={p:i%4 for i,p in enumerate(spairs)}

recon={}
for line in open('/tmp/t3_recon_results.jsonl'):
    s,d,sh,out,reason=json.loads(line); recon[(s,d)]=(out,reason)

# per-shard
assigned=[0,0,0,0]
cached=[0,0,0,0]   # csv present, not fetched in T3 (i.e., present at T3 start)
fetched=[0,0,0,0]  # fetched during T3 recon (recovered)
skipped=[0,0,0,0]
skip_reasons=[Counter() for _ in range(4)]
covered=[0,0,0,0]

for p in spairs:
    k=shard_of[p]; s,d=p
    assigned[k]+=1
    csv=Path('data_archive')/s/(d+'.csv')
    if csv.exists():
        covered[k]+=1
        if p in recon and recon[p][0]=='fetched':
            fetched[k]+=1
        else:
            cached[k]+=1
    else:
        skipped[k]+=1
        out,reason=recon.get(p,('skip','unknown (no bar file)'))
        # normalize reason
        skip_reasons[k][reason]+=1

# merged skip reasons
merged_skips=Counter()
for c in skip_reasons: merged_skips+=c

def shard_md(i):
    L=[]
    L.append(f"# Corpus Bar Coverage - Shard {i} of 4")
    L.append("")
    L.append("Reconstructed at T3 (shard report was absent from the worktree).")
    L.append(f"Shard rule: distinct (symbol, day) pairs from corpus_instances.jsonl,")
    L.append(f"sorted ascending by (symbol, day); pairs whose zero-based index % 4 == {i-1}.")
    L.append("")
    L.append(f"- Assigned: {assigned[i-1]}")
    L.append(f"- Already cached (present at T3 start): {cached[i-1]}")
    L.append(f"- Newly fetched (T3 reconstruction): {fetched[i-1]}")
    L.append(f"- Skipped: {skipped[i-1]}")
    L.append(f"- Covered (cached + fetched): {covered[i-1]}")
    L.append("")
    L.append("## Skip reasons")
    L.append("")
    L.append("| reason | count |")
    L.append("|---|---|")
    for r,n in skip_reasons[i-1].most_common():
        L.append(f"| {r} | {n} |")
    L.append("")
    return "\n".join(L)

for i in range(1,5):
    Path(f"research/corpus_bar_coverage_{i}.md").write_text(shard_md(i))

# merged
L=[]
L.append("# Corpus Bar Coverage (merged, shards 1-4)")
L.append("")
L.append("Merged from the four shard reports research/corpus_bar_coverage_1..4.md.")
L.append("")
L.append("**Reconstruction note.** The four per-shard reports produced by T2.1-T2.4 were")
L.append("absent from this runner's worktree at T3 time (the shard runners write only their")
L.append("sentinel file; they do not commit research/ artifacts back to the repo). The cache")
L.append("directory `data_archive/` they populated WAS present, so coverage was reconstructed")
L.append("directly from it: **cached** = bars present in data_archive at T3 start;")
L.append("**fetched** = bars pulled during T3 reconstruction of the pairs that were still")
L.append("missing (281 weekday pairs the shards had not banked were recovered here);")
L.append("**skipped** = pairs Polygon has no bars for (weekends, holidays). The covered")
L.append("count below is the denominator T4 divides by.")
L.append("")
L.append("## Summed totals")
L.append("")
L.append("| metric | shard 1 | shard 2 | shard 3 | shard 4 | total |")
L.append("|---|---|---|---|---|---|")
def row(name, arr):
    L.append(f"| {name} | {arr[0]} | {arr[1]} | {arr[2]} | {arr[3]} | {sum(arr)} |")
row("Assigned", assigned)
row("Already cached", cached)
row("Newly fetched (T3)", fetched)
row("Covered (cached+fetched)", covered)
row("Skipped", skipped)
L.append("")
L.append(f"**Covered total: {sum(covered)}** of {sum(assigned)} assigned distinct (symbol, day) pairs.")
L.append("")
L.append("## Skip reasons (merged, grouped)")
L.append("")
L.append("| reason | count |")
L.append("|---|---|")
for r,n in merged_skips.most_common():
    L.append(f"| {r} | {n} |")
L.append("")
L.append(f"Total skipped: {sum(skipped)}")
L.append("")
Path("research/corpus_bar_coverage.md").write_text("\n".join(L))
print("assigned",assigned,sum(assigned))
print("cached",cached,sum(cached))
print("fetched",fetched,sum(fetched))
print("covered",covered,sum(covered))
print("skipped",skipped,sum(skipped))
print("skip reasons",dict(merged_skips))
