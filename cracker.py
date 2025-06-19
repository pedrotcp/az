import itertools, random, multiprocessing, os, datetime, time
from bitarray import bitarray
from tqdm import tqdm

TOTAL_NUMBERS = 60
DRAW_SIZE = 6
TICKET_SIZE = 30
COMBO_COUNT = 50063860  # C(60,6)
TARGET_COVERAGE = 0.95
MAX_TICKETS_PER_SET = 105
CANDIDATES_PER_BATCH = 128  # Reduced to ease memory load

# Precompute combo -> index
print("[+] Precomputing combo index...")
all_combos = list(itertools.combinations(range(1, TOTAL_NUMBERS + 1), DRAW_SIZE))
combo_index = {combo: idx for idx, combo in enumerate(all_combos)}
del all_combos

# Create output folder
os.makedirs("sets", exist_ok=True)

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

def worker_loop(task_queue, result_queue):
    while True:
        task = task_queue.get()
        if task == "STOP":
            break
        candidate = sorted(random.sample(range(1, TOTAL_NUMBERS + 1), TICKET_SIZE))
        six_combos = itertools.combinations(candidate, DRAW_SIZE)
        seen = set()
        for combo in six_combos:
            idx = combo_index.get(combo)
            if idx is not None:
                seen.add(idx)
        result_queue.put((candidate, list(seen)))  # Convert to list right before sending

def generate_set(set_number):
    print(f"\n[>] Generating Set {set_number+1}")
    coverage = bitarray(COMBO_COUNT)
    coverage.setall(False)
    accepted = []
    last_covered = 0
    total_required = int(COMBO_COUNT * TARGET_COVERAGE)

    task_queue = multiprocessing.Queue()
    result_queue = multiprocessing.Queue()

    workers = [multiprocessing.Process(target=worker_loop, args=(task_queue, result_queue)) for _ in range(multiprocessing.cpu_count())]
    for w in workers:
        w.start()

    with tqdm(total=total_required, desc=f"Set {set_number+1}", unit="combos") as pbar:
        start_time = time.time()
        while len(accepted) < MAX_TICKETS_PER_SET:
            for _ in range(CANDIDATES_PER_BATCH):
                task_queue.put("GO")

            best_new_covered = 0
            best_candidate = None
            best_indexes = []

            for _ in range(CANDIDATES_PER_BATCH):
                candidate, indexes = result_queue.get()
                new_covered = sum(1 for idx in indexes if not coverage[idx])
                if new_covered > best_new_covered:
                    best_new_covered = new_covered
                    best_candidate = candidate
                    best_indexes = indexes

            if best_new_covered == 0:
                continue

            for idx in best_indexes:
                coverage[idx] = True
            accepted.append(best_candidate)

            covered_now = coverage.count(True)
            delta = covered_now - last_covered
            pbar.update(delta)
            last_covered = covered_now

            elapsed = time.time() - start_time
            combos_per_sec = covered_now / elapsed if elapsed > 0 else 0
            remaining = max(0, total_required - covered_now)
            eta_sec = remaining / combos_per_sec if combos_per_sec > 0 else float("inf")
            eta_min = eta_sec / 60

            print(f"    [+] Best new coverage: {best_new_covered} | Total Tickets: {len(accepted)}")
            print(f"    [~] Speed: {int(combos_per_sec):,} combos/sec | ETA: {eta_min:.1f} min")

            if covered_now >= total_required:
                break

    for _ in workers:
        task_queue.put("STOP")
    for w in workers:
        w.join()

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
    set_number = 0
    while True:
        generate_set(set_number)
        set_number += 1

if __name__ == "__main__":
    main()
