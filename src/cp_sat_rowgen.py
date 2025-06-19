import json, random, itertools, numpy as np, tqdm
from ortools.linear_solver import pywraplp
from common import mask

SEED_ROWS=50_000
TIME=60
THREADS=64    # matches F64s core count

tickets=[json.load(open("seed.json"))][0]
tmasks=np.array([mask(t) for t in tickets],dtype=np.uint64)

solver=pywraplp.Solver.CreateSolver("SAT")
solver.SetNumThreads(THREADS)
solver.parameters.max_time_in_seconds=TIME
x=[solver.BoolVar(f"x{i}") for i in range(len(tickets))]
solver.Minimize(solver.Sum(x))

rows={}
def add_row(cm):
    if cm in rows: return
    c=solver.Constraint(1,solver.infinity())
    for i,tm in enumerate(tmasks):
        if (tm & cm)==cm: c.SetCoefficient(x[i],1)
    rows[cm]=c

for combo in random.sample(list(itertools.combinations(range(60),6)),SEED_ROWS):
    add_row(mask(combo))

while True:
    solver.Solve()
    chosen=[v.solution_value()>0.5 for v in x]
    merged=0
    for i,keep in enumerate(chosen):
        if keep: merged|=tmasks[i]
    miss=None
    for a,b,c,d,e,f in itertools.combinations(range(60),6):
        cm=(1<<a)|(1<<b)|(1<<c)|(1<<d)|(1<<e)|(1<<f)
        if (merged & cm)!=cm:
            miss=cm; break
    if miss is None: break
    add_row(miss)

sel=[tickets[i] for i,keep in enumerate(chosen) if keep]
json.dump(sel,open("phaseB.json","w"))
print("Phase B tickets:",len(sel))
