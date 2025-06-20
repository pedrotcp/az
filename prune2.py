import itertools
from math import comb
from bitarray import bitarray

TOTAL_NUMBERS = 60
DRAW_SIZE = 6
COMBO_COUNT = comb(TOTAL_NUMBERS, DRAW_SIZE)
COVERAGE_GOAL = 0.99  # 99%
gameset_file = "games/games.txt"

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
    tickets = [sorted(int(x) for x in line.strip().split(" ")) for line in f if line.strip()]

def tickets_coverage(tix):
    ba = bitarray(COMBO_COUNT)
    ba.setall(False)
    for t in tix:
        for c in itertools.combinations(t, DRAW_SIZE):
            idx = combo_to_index(c)
            ba[idx] = True
    return ba.count(True)

target_required = int(COVERAGE_GOAL * COMBO_COUNT)
print(f"Initial set: {len(tickets)} tickets | Coverage: {tickets_coverage(tickets)}/{COMBO_COUNT} ({tickets_coverage(tickets)/COMBO_COUNT*100:.4f}%)")

changed = True
pass_num = 1
while changed:
    changed = False
    print(f"\n[Pass {pass_num}] Starting optimization pass...")
    for ti, ticket in enumerate(tickets):
        # Can't go below DRAW_SIZE
        if len(ticket) <= DRAW_SIZE:
            continue
        print(f"  Processing ticket {ti+1}/{len(tickets)} (size: {len(ticket)})...", end="\r")
        for ni, number in enumerate(list(ticket)):  # Copy because we'll mutate
            new_ticket = ticket[:ni] + ticket[ni+1:]
            test_tickets = tickets[:ti] + [new_ticket] + tickets[ti+1:]
            combos = tickets_coverage(test_tickets)
            if combos >= target_required:
                print(f"  [-] Removed number {number} from ticket {ti} | New size: {len(new_ticket)} | Coverage: {combos/COMBO_COUNT*100:.4f}%")
                ticket.remove(number)
                changed = True
                break  # Remove only one number per ticket per pass for speed
    print(f"[Pass {pass_num}] Pass complete. Current coverage: {tickets_coverage(tickets)}/{COMBO_COUNT} ({tickets_coverage(tickets)/COMBO_COUNT*100:.4f}%)")
    pass_num += 1

print(f"\nOptimized set: {len(tickets)} tickets")
for i, t in enumerate(tickets):
    print(f"Ticket {i}: {len(t)} numbers")
print(f"Final coverage: {tickets_coverage(tickets)}/{COMBO_COUNT} ({tickets_coverage(tickets)/COMBO_COUNT*100:.4f}%)")

with open("numpruned_" + gameset_file, "w") as f:
    for t in tickets:
        f.write(",".join(map(str, t)) + "\n")
print(f"[✓] Saved number-pruned set as numpruned_{gameset_file}")
