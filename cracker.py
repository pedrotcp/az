import itertools, random, multiprocessing, os, datetime, time
from bitarray import bitarray
from tqdm import tqdm

TOTAL_NUMBERS = 60
DRAW_SIZE = 6
TICKET_SIZE = 30
COMBO_COUNT = 50063860  # C(60,6)
TARGET_COVERAGE = 0.98
MAX_TICKETS_PER_SET = 100
MAX_SETS = 3
NEW_COVER_THRESHOLD = int(os.getenv("NEW_COVER_THRESHOLD", 50000))

# Precompute combo → index
print("[+] Precomputing combo index...")
all_combos = list(itertools.combinations(range(1, TOTAL_NUMBERS + 1), DRAW_SIZE))
combo_index = {combo: idx for idx, combo in enumerate(all_combos)}
del all_combos

# Create output folder
os.makedirs("sets", exist_ok=True)

# These will be re-initialized inside each set
coverage = None
accepted = None
lock = None

def process_candidate(_):
    candidate = sorted(random.sample(range(1, TOTAL_NUMBERS + 1), TICKET_SIZE))
    six_combos = itertools.combinations(candidate, DRAW_SIZE)
    local_new = []

    for combo in six_combos:
        idx = combo_index.get(combo)
        if idx is not None:
            local_new.append(idx)

    new_covered = 0
    with lock:
        for idx in local_new:
            if not coverage[idx]:
                coverage[idx] = True
                new_covered += 1

        if new_covered >= NEW_COVER_THRESHOLD and len(accepted) < MAX_TICKETS_PER_SET:
            accepted.append(candidate)
            return new_covered
    return 0

def verify_coverage(tickets):
    check = bitarray(COMBO_COUNT)
    check.setall(False)
    for ticket in tickets:
        for combo in itertools.combinations(ticket, DRAW_SIZE):
            idx = combo_index.get(combo)
            if idx is not None:
                check[idx] = True
    covered = check.count(True)
    percent = covered / COMBO_COUNT * 100
    return covered, percent

def generate_set(set_number):
    global coverage, accepted, lock
    print(f"\n[>] Generating Set {set_number+1}/{MAX_SETS}")

    coverage = bitarray(COMBO_COUNT)
    coverage.setall(False)
    accepted = []
    lock = multiprocessing.Lock()
    last_covered = 0
    total_required = int(COMBO_COUNT * TARGET_COVERAGE)

    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        with tqdm(total=total_required, desc=f"Set {set_number+1}", unit="combos") as pbar:
            start_time = time.time()
            while True:
                results = pool.map(process_candidate, range(64))

                newly_accepted = sum(1 for r in results if r > 0)
                rejected = len(results) - newly_accepted

                covered_now = coverage.count(True)
                delta = covered_now - last_covered
                pbar.update(delta)
                last_covered = covered_now

                elapsed = time.time() - start_time
                combos_per_sec = covered_now / elapsed if elapsed > 0 else 0
                remaining = max(0, total_required - covered_now)
                eta_sec = remaining / combos_per_sec if combos_per_sec > 0 else float("inf")
                eta_min = eta_sec / 60

                print(f"    [+] Accepted: {newly_accepted} | Rejected: {rejected} | Total: {len(accepted)}")
                print(f"    [~] Speed: {int(combos_per_sec):,} combos/sec | ETA: {eta_min:.1f} min")

                if covered_now >= total_required or len(accepted) >= MAX_TICKETS_PER_SET:
                    break

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sets/bicho_set_{timestamp}_set{set_number+1}.txt"
    with open(filename, "w") as f:
        for t in accepted:
            f.write(",".join(map(str, t)) + "\n")

    verified_covered, percent = verify_coverage(accepted)
    print(f"[✓] Set {set_number+1} saved as {filename}")
    print(f"    - Tickets: {len(accepted)}")
    print(f"    - Coverage: {verified_covered:,} combos ({percent:.6f}%)\n")

def main():
    for i in range(MAX_SETS):
        generate_set(i)

if __name__ == "__main__":
    main()
