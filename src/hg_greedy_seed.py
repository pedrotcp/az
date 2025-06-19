import argparse, random, itertools, json, tqdm
from common import mask

parser = argparse.ArgumentParser()
parser.add_argument("--seed", type=int, default=0)
parser.add_argument("--starts", type=int, default=200)
args = parser.parse_args()
random.seed(args.seed)

def greedy():
    uncovered=set(itertools.combinations(range(60),6))
    tickets=[]
    while uncovered:
        cand=random.sample(range(60),30)
        gain=sum(1 for c in itertools.combinations(cand,6) if c in uncovered)
        tickets.append(cand)
        uncovered.difference_update(itertools.combinations(cand,6))
    return tickets

best=[]
for _ in tqdm.tqdm(range(args.starts)):
    t=greedy()
    best.append((len(t),t))
best.sort(key=lambda x:x[0])
json.dump(best[0][1],open("seed.json","w"))
print("Greedy seed written → seed.json  (",best[0][0],"tickets )")
