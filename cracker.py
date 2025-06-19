import itertools, random, multiprocessing, os, datetime, time, pickle
import numpy as np
from multiprocessing import shared_memory
from bitarray import bitarray
from tqdm import tqdm

TOTAL_NUMBERS = 60
DRAW_SIZE = 6
TICKET_SIZE = 30
COMBO_COUNT = 50063860  # C(60,6)
TARGET_COVERAGE = 0.95
MAX_TICKETS_PER_SET = 105
CANDIDATES_PER_BATCH = 1000  # Increased for better CPU utilization
WORKERS = multiprocessing.cpu_count()  # Use all cores

# Create output folder
os.makedirs("sets", exist_ok=True)

def create_combo_index():
    """Create and save combo index to disk (run once)"""
    print("[*] Creating combo index file...")
    all_combos = list(itertools.combinations(range(1, TOTAL_NUMBERS + 1), DRAW_SIZE))
    combo_index = {combo: idx for idx, combo in enumerate(all_combos)}
    
    with open('combo_index.pkl', 'wb') as f:
        pickle.dump(combo_index, f, protocol=pickle.HIGHEST_PROTOCOL)
    
    print(f"[+] Saved {len(combo_index)} combinations to combo_index.pkl")
    return combo_index

def load_combo_index():
    """Load combo index from disk"""
    if not os.path.exists('combo_index.pkl'):
        return create_combo_index()
    
    print("[*] Loading combo index from disk...")
    with open('combo_index.pkl', 'rb') as f:
        combo_index = pickle.load(f)
    print(f"[+] Loaded {len(combo_index)} combinations")
    return combo_index

# Load index once at module level
print("[*] Initializing combo index...")
COMBO_INDEX = load_combo_index()

def init_worker(shm_name, shape):
    """Initialize worker with shared memory"""
    global worker_shm, worker_coverage
    # Attach to existing shared memory
    worker_shm = shared_memory.SharedMemory(name=shm_name)
    # Create numpy array view of shared memory
    worker_coverage = np.ndarray(shape, dtype=np.uint8, buffer=worker_shm.buf)

def cleanup_worker():
    """Clean up worker resources"""
    global worker_shm
    if 'worker_shm' in globals():
        worker_shm.close()

def evaluate_candidates_batch(seeds):
    """Evaluate multiple candidates in one worker call"""
    results = []
    
    for seed in seeds:
        if seed is None:
            continue
            
        random.seed(seed)
        candidate = tuple(sorted(random.sample(range(1, TOTAL_NUMBERS + 1), TICKET_SIZE)))
        
        new_covered = 0
        covered_indices = []
        
        # Check each 6-number combination
        for combo in itertools.combinations(candidate, DRAW_SIZE):
            idx = COMBO_INDEX.get(combo)
            if idx is not None:
                byte_idx = idx // 8
                bit_idx = idx % 8
                
                # Check if bit is not set
                if not (worker_coverage[byte_idx] & (1 << bit_idx)):
                    covered_indices.append(idx)
                    new_covered += 1
        
        results.append((new_covered, candidate, covered_indices))
    
    return results

def verify_coverage(tickets):
    """Verify actual coverage of a ticket set"""
    check = bitarray(COMBO_COUNT)
    check.setall(False)
    
    for ticket in tickets:
        for combo in itertools.combinations(ticket, DRAW_SIZE):
            idx = COMBO_INDEX.get(combo)
            if idx is not None:
                check[idx] = True
    
    covered = check.count(True)
    percent = covered / COMBO_COUNT * 100
    return covered, percent

def update_shared_coverage(shm, indices):
    """Update shared memory coverage with new indices"""
    coverage_array = np.ndarray((COMBO_COUNT // 8 + 1,), dtype=np.uint8, buffer=shm.buf)
    
    for idx in indices:
        byte_idx = idx // 8
        bit_idx = idx % 8
        coverage_array[byte_idx] |= (1 << bit_idx)

def count_coverage(shm):
    """Count total coverage from shared memory"""
    coverage_array = np.ndarray((COMBO_COUNT // 8 + 1,), dtype=np.uint8, buffer=shm.buf)
    return sum(bin(byte).count('1') for byte in coverage_array)

def generate_set(set_number):
    """Generate a single ticket set"""
    print(f"\n[>] Generating Set {set_number+1}")
    
    # Create shared memory for coverage
    shm_size = COMBO_COUNT // 8 + 1
    shm = shared_memory.SharedMemory(create=True, size=shm_size)
    
    try:
        # Initialize shared memory to zeros
        coverage_array = np.ndarray((shm_size,), dtype=np.uint8, buffer=shm.buf)
        coverage_array[:] = 0
        
        accepted = []
        last_covered = 0
        total_required = int(COMBO_COUNT * TARGET_COVERAGE)
        
        # Create worker pool with shared memory
        with multiprocessing.Pool(
            processes=WORKERS,
            initializer=init_worker,
            initargs=(shm.name, (shm_size,))
        ) as pool:
            
            with tqdm(total=total_required, desc=f"Set {set_number+1}", unit="combos") as pbar:
                start_time = time.time()
                no_progress_count = 0
                iteration = 0
                
                while len(accepted) < MAX_TICKETS_PER_SET:
                    iteration += 1
                    
                    # Split candidates among workers
                    seeds_per_worker = CANDIDATES_PER_BATCH // WORKERS
                    seed_batches = []
                    
                    for w in range(WORKERS):
                        worker_seeds = [random.randint(0, 2**32) 
                                      for _ in range(seeds_per_worker)]
                        seed_batches.append(worker_seeds)
                    
                    # Evaluate candidates in parallel
                    all_results = pool.map(evaluate_candidates_batch, seed_batches)
                    
                    # Flatten results and find best candidate
                    best_new_covered = 0
                    best_candidate = None
                    best_indexes = []
                    
                    for worker_results in all_results:
                        for new_covered, candidate, indexes in worker_results:
                            if new_covered > best_new_covered:
                                best_new_covered = new_covered
                                best_candidate = candidate
                                best_indexes = indexes
                    
                    if best_new_covered == 0:
                        no_progress_count += 1
                        if no_progress_count > 5:
                            print(f"    [!] No progress after {no_progress_count} batches")
                            if no_progress_count > 10:
                                break
                        continue
                    
                    no_progress_count = 0
                    
                    # Update shared coverage
                    update_shared_coverage(shm, best_indexes)
                    accepted.append(best_candidate)
                    
                    # Count covered (every 5 iterations to reduce overhead)
                    if iteration % 5 == 0:
                        covered_now = count_coverage(shm)
                        delta_count = covered_now - last_covered
                        pbar.update(delta_count)
                        last_covered = covered_now
                        
                        # Calculate stats
                        elapsed = time.time() - start_time
                        combos_per_sec = covered_now / elapsed if elapsed > 0 else 0
                        remaining = max(0, total_required - covered_now)
                        eta_sec = remaining / combos_per_sec if combos_per_sec > 0 else float("inf")
                        eta_min = eta_sec / 60
                        
                        print(f"    [+] Ticket {len(accepted)}: +{best_new_covered} combos")
                        print(f"    [~] Speed: {int(combos_per_sec):,} combos/sec | ETA: {eta_min:.1f} min")
                        print(f"    [~] Candidates/sec: {int(iteration * CANDIDATES_PER_BATCH / elapsed):,}")
                        
                        if covered_now >= total_required:
                            break
                
                # Final coverage count
                if last_covered < total_required:
                    covered_now = count_coverage(shm)
                    pbar.update(covered_now - last_covered)
            
            # Cleanup workers
            pool.map(lambda x: cleanup_worker(), range(WORKERS))
    
    finally:
        # Clean up shared memory
        shm.close()
        shm.unlink()
    
    # Save results
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sets/bicho_set_{timestamp}_set{set_number+1}.txt"
    
    with open(filename, "w") as f:
        for t in accepted:
            f.write(",".join(map(str, t)) + "\n")
    
    # Verify coverage
    verified_covered, percent = verify_coverage(accepted)
    print(f"\n[✓] Set {set_number+1} saved as {filename}")
    print(f"    - Tickets: {len(accepted)}")
    print(f"    - Coverage: {verified_covered:,} combos ({percent:.6f}%)")
    print(f"    - Time: {datetime.timedelta(seconds=int(time.time() - start_time))}\n")

def main():
    """Main loop"""
    print(f"\n[*] Starting lottery ticket generator")
    print(f"    - Workers: {WORKERS}")
    print(f"    - Target coverage: {TARGET_COVERAGE * 100}%")
    print(f"    - Candidates per batch: {CANDIDATES_PER_BATCH}")
    
    set_number = 0
    while True:
        generate_set(set_number)
        set_number += 1

if __name__ == "__main__":
    main()