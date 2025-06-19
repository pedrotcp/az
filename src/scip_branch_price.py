import json, itertools, numpy as np
from common import mask
import scipopt as sp

tickets=json.load(open("phaseB.json"))
tmasks=[mask(t) for t in tickets]

model=sp.Model()
vars=[model.addVar(vtype="B", obj=1, name=f"x{i}") for i in range(len(tickets))]
model.setObjective(None)               # minimise set later
model.setObjective(sum(vars),"minimize")

rows={}
def add_row(cm):
    if cm in rows: return
    cons=model.addCons(sum(vars[i] for i,tm in enumerate(tmasks) if (tm&cm)==cm)>=1)
    rows[cm]=cons

for cm in (mask(c) for c in itertools.islice(itertools.combinations(range(60),6),50_000)):
    add_row(cm)

def pricing():
    dual={cm: model.getDual(cons) for cm,cons in rows.items()}
    w=[0]*60
    for cm,val in dual.items():
        for j in range(60):
            if cm>>j & 1: w[j]+=val
    best=sorted(range(60),key=lambda j:-w[j])[:30]
    rc=1-sum(w[j] for j in best)
    cm=0
    for j in best: cm|=1<<j
    return rc,cm,best

iter=0
while True:
    iter+=1
    model.optimize()
    rc,cm,best=pricing()
    if rc>=-1e-6: break
    v=model.addVar(vtype="B", obj=1)
    tmasks.append(cm)
    for cmr,cons in rows.items():
        if (cm & cmr)==cmr:
            model.addCoef(cons,v,1)
    print("Iter",iter,"add column  obj=",model.getObjVal())

sel=[tickets[i] for i,v in enumerate(model.getBestSol(vars)) if v>0.5]
json.dump(sel,open("phaseC.json","w"))
print("Phase C tickets:",len(sel))
