import json, glob, sys
best=999; file=None
for fn in glob.glob("res/*phaseC.json"):
    n=len(json.load(open(fn)))
    print(fn,n)
    if n<best:
        best,file=n,fn
print("SMALLEST",best,"tickets →",file)
