import numpy as np, numba as nb

def mask(nums):
    v = 0
    for x in nums:
        v |= 1 << (x - 1)
    return v

@nb.njit
def covers_all(tmask):
    for a in range(60):
        for b in range(a+1,60):
            for c in range(b+1,60):
                for d in range(c+1,60):
                    for e in range(d+1,60):
                        for f in range(e+1,60):
                            m=(1<<a)|(1<<b)|(1<<c)|(1<<d)|(1<<e)|(1<<f)
                            hit=False
                            for tm in tmask:
                                if (tm & m)==m:
                                    hit=True; break
                            if not hit:
                                return False
    return True
