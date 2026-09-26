import re,sys
for f in sys.argv[2:]:
    for i,l in enumerate(open(f,encoding='utf-8',errors='replace'),1):
        if re.search(sys.argv[1],l): print(f"{f}:{i}: {l.rstrip()[:200]}")
