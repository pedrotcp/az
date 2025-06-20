import itertools
from math import comb
from bitarray import bitarray

TOTAL_NUMBERS = 60
DRAW_SIZE = 6
COMBO_COUNT = comb(TOTAL_NUMBERS, DRAW_SIZE)
COVERAGE_GOAL = 0.90  
gameset_file = "games/games.txt"  # <---- your file here

def combo_to_index(combo):
    index = 0
    prev = 0
    for i, num in enumerate(combo):
        for j in range(prev+1, num):
            index += comb(TOTAL_NUMBERS-j, DRAW_SIZE-1-i)
        prev = num
    return index

# Load tickets
with open(gameset_file) as f:
    tickets = [sorted(int(x) for x in line.strip().split(",")) for line in f if line.strip()]

def tickets_coverage(tix):
    ba = bitarray(COMBO_COUNT)
    ba.setall(False)
    for t in tix:
        for c in itertools.combinations(t, DRAW_SIZE):
            idx = combo_to_index(c)
            ba[idx] = True
    return ba.count(True)

# Initial full coverage
target_combos = tickets_coverage(tickets)
target_required = int(COVERAGE_GOAL * COMBO_COUNT)
print(f"Initial set: {len(tickets)} tickets | Coverage: {target_combos}/{COMBO_COUNT} ({target_combos/COMBO_COUNT*100:.4f}%)")

# Prune
changed = True
while changed:
    changed = False
    for i in range(len(tickets) - 1, -1, -1):
        test_tickets = tickets[:i] + tickets[i+1:]
        combos = tickets_coverage(test_tickets)
        if combos >= target_required:
            print(f"  [-] Removed ticket {i} | New ticket count: {len(test_tickets)} | Coverage: {combos/COMBO_COUNT*100:.4f}%")
            tickets.pop(i)
            changed = True

print(f"\nPruned set: {len(tickets)} tickets | Coverage: {tickets_coverage(tickets)}/{COMBO_COUNT} ({tickets_coverage(tickets)/COMBO_COUNT*100:.4f}%)")

# Save reduced set
with open("pruned_" + gameset_file, "w") as f:
    for t in tickets:
        f.write(",".join(map(str, t)) + "\n")
print(f"[✓] Saved pruned set as pruned_{gameset_file}")
