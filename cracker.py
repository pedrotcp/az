import itertools, random, multiprocessing, os, datetime, time, mmap, tempfile
from bitarray import bitarray
from tqdm import tqdm
from functools import lru_cache

TOTAL_NUMBERS = 60
DRAW_SIZE = 6
TICKET_SIZE = 30
COMBO_COUNT = 50063860  # C(60,6)
TARGET_COVERAGE = 0.95
MAX_TICKETS_PER_SET = 105
CANDIDATES_PER_BATCH = 64
WORKERS = min(multiprocessing.cpu_count(), 32)  # Limit workers to reduce memory

# Create output folder
os.makedirs("sets", exist_ok=True)

@lru_cache(maxsize=10000)
def binomial(n, k):
    """Cached binomial coefficient calculation"""
    if k > n - k:
        k = n - k
    if k == 0:
        return 1
    
    result = 1
    for i in range(k):
        result = result * (n - i) // (i + 1)
    return result

def combo_to_index_fast(combo):
    """Fast combination to index conversion"""
    index = 0
    for i, num in enumerate(combo):
        if num > i:
            index += binomial(num, i + 1)
    return index

def verify_coverage(tickets):
    check = bitarray(COMBO_COUNT)
    check.setall(False)
    for ticket in tickets:
        for combo in itertools.combinations(ticket, DRAW_SIZE):
            idx = combo_to_index_fast(tuple(c - 1 for c in combo))
            check[idx] = True
    covered = check.count(True)
    percent = covered / COMBO_COUNT * 100
    return covered, percent

def worker_init(mmap_filename, mmap_size):
    """Initialize worker with memory-mapped file"""
    global worker_mmap, worker_coverage
    # Open the memory-mapped file in this worker
    with open(mmap_filename, 'r+b') as f:
        worker_mmap = mmap.mmap(f.fileno(), mmap_size)
    worker_coverage = bitarray()
    worker_coverage.frombytes(worker_mmap[:mmap_size])

def worker_cleanup():
    """Clean up worker resources"""
    global worker_mmap
    if 'worker_mmap' in globals():
        worker_mmap.close()

def evaluate_candidate_mmap(seed):
    """Evaluate a candidate using memory-mapped coverage"""
    if seed is None:
        return None
    
    random.seed(seed)
    candidate = sorted(random.sample(range(1, TOTAL_NUMBERS + 1), TICKET_SIZE))
    
    new_covered = 0
    covered_indices = []
    
    # Refresh coverage from mmap
    worker_coverage.clear()
    worker_coverage.frombytes(worker_mmap[:len(worker_coverage.tobytes())])
    
    for combo in itertools.combinations(candidate, DRAW_SIZE):
        idx = combo_to_index_fast(tuple(c - 1 for c in combo))
        if not worker_coverage[idx]:
            covered_indices.append(idx)
            new_covered += 1
    
    return (new_covered, candidate, covered_indices)

def generate_set(set_number):
    print(f"\n[>] Generating Set {set_number+1}")
    
    # Create memory-mapped file for coverage
    coverage_bytes = COMBO_COUNT // 8 + 1
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        mmap_filename = tmp.name
        tmp.write(b'\x00' * coverage_bytes)
    
    try:
        # Initialize coverage
        coverage = bitarray(COMBO_COUNT)
        coverage.setall(False)
        
        accepted = []
        last_covered = 0
        total_required = int(COMBO_COUNT * TARGET_COVERAGE)
        
        # Create pool with memory-mapped file
        with multiprocessing.Pool(
            processes=WORKERS,
            initializer=worker_init,
            initargs=(mmap_filename, coverage_bytes)
        ) as pool:
            
            with tqdm(total=total_required, desc=f"Set {set_number+1}", unit="combos") as pbar:
                start_time = time.time()
                batch_count = 0
                
                while len(accepted) < MAX_TICKETS_PER_SET:
                    # Update memory-mapped file
                    with open(mmap_filename, 'r+b') as f:
                        mm = mmap.mmap(f.fileno(), coverage_bytes)
                        mm[:] = coverage.tobytes()
                        mm.close()
                    
                    # Generate random seeds for reproducibility
                    seeds = [random.randint(0, 2**32) for _ in range(CANDIDATES_PER_BATCH)]
                    
                    # Evaluate candidates
                    results = pool.map(evaluate_candidate_mmap, seeds)
                    
                    # Find best candidate
                    best_new_covered = 0
                    best_candidate = None
                    best_indexes = []
                    
                    for result in results:
                        if result is None:
                            continue
                        new_covered, candidate, indexes = result
                        if new_covered > best_new_covered:
                            best_new_covered = new_covered
                            best_candidate = candidate
                            best_indexes = indexes
                    
                    if best_new_covered == 0:
                        # If no progress, try more candidates
                        batch_count += 1
                        if batch_count > 10:
                            print("    [!] No progress after 10 batches, stopping")
                            break
                        continue
                    
                    batch_count = 0
                    
                    # Update coverage
                    for idx in best_indexes:
                        coverage[idx] = True
                    accepted.append(best_candidate)
                    
                    covered_now = coverage.count(True)
                    delta_count = covered_now - last_covered
                    pbar.update(delta_count)
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
            
            # Ensure cleanup
            pool.map(lambda x: worker_cleanup(), range(WORKERS))
    
    finally:
        # Clean up memory-mapped file
        if os.path.exists(mmap_filename):
            os.unlink(mmap_filename)
    
    # Save results
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