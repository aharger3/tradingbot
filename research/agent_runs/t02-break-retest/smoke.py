import bt, numpy as np
S=bt.sessions("ES"); ds=sorted(S); print(len(S), ds[0], ds[-1])
D=ds[5]; s=S[D]; print(D, s["tk"], s["pdh"], s["pdl"], s["onh"], s["onl"], s["o"][0], s["h"][:5].max(), s["l"][:5].min())
tot=0
for ls in ("ALL","PRE","OR"):
    n=sum(1 for D in S if bt.signals(S[D],ls)); print(ls, "days w/ signal", n)
for D in ds[:15]:
    sg=bt.signals(S[D],"ALL")
    if sg:
        t=bt.trade(S[D],sg[0],"LVL",2,"ES"); print(D, sg[0], t)
