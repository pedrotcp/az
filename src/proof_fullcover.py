import json, numpy as np
from common import mask, covers_all

tickets=json.load(open("phaseC.json"))
tmasks=np.array([mask(t) for t in tickets],dtype=np.uint64)
assert covers_all(tmasks)
print("FULL COVER ✔  tickets:",len(tickets))
