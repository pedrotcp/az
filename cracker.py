import itertools, random, multiprocessing, os, datetime, time
import numpy as np
from multiprocessing import shared_memory
from bitarray import bitarray
from tqdm import tqdm
from math import comb

TOTAL_NUMBERS = 60
DRAW_SIZE = 6
TICKET_SIZE = 30
COMBO_COUNT = 50063860  # C(60,6)
TARGET_COVERAGE = 0.95
MAX_TICKETS_PER_SET = 105
CANDIDATES_PER_BATCH = 500  # Reduced for safety
WORKERS = min(multiprocessing.cpu_count(), 32)  # Limit workers

# Create output folder
os.makedirs("sets", exist_ok=True)

def combination_to_index(combo):
    """
    Convert a combination to its lexicographic index.
    combo should be a sorted tuple of numbers from 1-60.
    """
    index = 0
    k = len(combo)
    for i in range(k):
        if i == 0:
            # For the first position, count all combinations that start with a smaller number
            if combo[i] > 1:
                index += comb(TOTAL_NUMBERS - 1, k - 1)
                for j in range(2, combo[i]):
                    index += comb(TOTAL_NUMBERS - j, k - 1)
        else:
            # For subsequent positions, count combinations with smaller numbers at this position
            for j in range(combo[i-1] + 1, combo[i]):
                index += comb(TOTAL_NUMBERS - j, k - i - 1)
    return index

def init_worker(shm_name, shape):
    """Initialize worker with shared memory"""
    global worker_shm, worker_coverage
    worker_shm = shared_memory.SharedMemory(name=shm_name)
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
            idx = combination_to_index(combo)
            
            if 0 <= idx < COMBO_COUNT:  # Safety check
                byte_idx = idx // 8
                bit_idx = idx % 8
                
                # Check if bit is not set
                if byte_idx < len(worker_coverage) and not (worker_coverage[byte_idx] & (1 << bit_idx)):
                    covered_indices.append(idx)
                    new_covered += 1
        
        results.append((new_covered, candidate, covered_indices))
    
    return results

def verify_coverage(tickets):
    """Verify actual coverage of a ticket set"""
    check = bitarray(COMBO_COUNT)
    check.setall(False)
    
    count = 0
    for ticket in tickets:
        for combo in itertools.combinations(ticket, DRAW_SIZE):
            idx = combination_to_index(combo)
            if 0 <= idx < COMBO_COUNT:
                check[idx] = True
                count += 1
    
    covered = check.count(True)
    percent = covered / COMBO_COUNT * 100
    return covered, percent

def update_shared_coverage(shm, indices):
    """Update shared memory coverage with new indices"""
    coverage_array = np.ndarray((COMBO_COUNT // 8 + 1,), dtype=np.uint8, buffer=shm.buf)
    
    for idx in indices:
        if 0 <= idx < COMBO_COUNT:  # Safety check
            byte_idx = idx // 8
            bit_idx = idx % 8
            if byte_idx < len(coverage_array):
                coverage_array[byte_idx] |= (1 << bit_idx)

def count_coverage(shm):
    """Count total coverage from shared memory"""
    coverage_array = np.ndarray((COMBO_COUNT // 8 + 1,), dtype=np.uint8, buffer=shm.buf)
    return sum(bin(byte).count('1') for byte in coverage_array)

def generate_set(set_number):
    """Generate a single ticket set"""
    print(f"\n[>] Generating Set {set_number+1}")
    
    # Test the index function
    if set_number == 0:
        print("[*] Testing index function...")
        test1 = combination_to_index((1, 2, 3, 4, 5, 6))
        test2 = combination_to_index((55, 56, 57, 58, 59, 60))
        print(f"    First combo (1,2,3,4,5,6): index {test1}")
        print(f"    Last combo (55,56,57,58,59,60): index {test2}")
        print(f"    Expected max index: {COMBO_COUNT - 1}")
        if test2 >= COMBO_COUNT:
            print("[!] ERROR: Index calculation exceeds bounds!")
            return
    
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
        
        # Create worker pool
        with multiprocessing.Pool(
            processes=WORKERS,
            initializer=init_worker,
            initargs=(shm.name, (shm_size,))
        ) as pool:
            
            with tqdm(total=total_required, desc=f"Set {set_number+1}", unit="combos") as pbar:
                start_time = time.time()
                no_progress_count = 0
                iteration = 0
                candidates_evaluated = 0
                
                while len(accepted) < MAX_TICKETS_PER_SET:
                    iteration += 1
                    
                    # Split candidates among workers
                    seeds_per_worker = max(1, CANDIDATES_PER_BATCH // WORKERS)
                    seed_batches = []
                    
                    for w in range(WORKERS):
                        worker_seeds = [random.randint(0, 2**32) 
                                      for _ in range(seeds_per_worker)]
                        seed_batches.append(worker_seeds)
                    
                    candidates_evaluated += sum(len(batch) for batch in seed_batches)
                    
                    # Evaluate candidates in parallel
                    all_results = pool.map(evaluate_candidates_batch, seed_batches)
                    
                    # Find best candidate
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
                        if no_progress_count > 10:
                            print(f"    [!] No progress after {no_progress_count} batches, stopping")
                            break
                        continue
                    
                    no_progress_count = 0
                    
                    # Update shared coverage
                    update_shared_coverage(shm, best_indexes)
                    accepted.append(best_candidate)
                    
                    # Update progress
                    covered_now = last_covered + best_new_covered
                    pbar.update(best_new_covered)
                    last_covered = covered_now
                    
                    # Detailed stats every 5 tickets
                    if len(accepted) % 5 == 0:
                        actual_covered = count_coverage(shm)
                        elapsed = time.time() - start_time
                        combos_per_sec = actual_covered / elapsed if elapsed > 0 else 0
                        candidates_per_sec = candidates_evaluated / elapsed if elapsed > 0 else 0
                        
                        print(f"\n    [+] Ticket {len(accepted)}: +{best_new_covered} new combos")
                        print(f"    [~] Total coverage: {actual_covered:,} / {COMBO_COUNT:,}")
                        print(f"    [~] Speed: {int(combos_per_sec):,} combos/sec")
                        print(f"    [~] Evaluating: {int(candidates_per_sec):,} candidates/sec")
                        
                        # Adjust if actual count differs from estimate
                        if abs(actual_covered - covered_now) > 1000:
                            covered_now = actual_covered
                            pbar.n = covered_now
                            pbar.refresh()
                    
                    if covered_now >= total_required:
                        break
                
                # Final accurate count
                final_covered = count_coverage(shm)
                pbar.n = final_covered
                pbar.refresh()
            
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
    print("\n[*] Verifying coverage...")
    verified_covered, percent = verify_coverage(accepted)
    elapsed_total = time.time() - start_time
    
    print(f"\n[✓] Set {set_number+1} saved as {filename}")
    print(f"    - Tickets: {len(accepted)}")
    print(f"    - Coverage: {verified_covered:,} combos ({percent:.6f}%)")
    print(f"    - Time: {datetime.timedelta(seconds=int(elapsed_total))}")
    print(f"    - Candidates evaluated: {candidates_evaluated:,}\n")

def main():
    """Main loop"""
    print(f"\n[*] Starting lottery ticket generator")
    print(f"    - Workers: {WORKERS}")
    print(f"    - Target coverage: {TARGET_COVERAGE * 100}%")
    print(f"    - Candidates per batch: {CANDIDATES_PER_BATCH}")
    print(f"    - Memory usage: ~{(COMBO_COUNT // 8 + 1) / 1024 / 1024:.1f} MB shared memory")
    print(f"    - No combo index needed - calculating on the fly")
    
    set_number = 0
    while True:
        generate_set(set_number)
        set_number += 1

if __name__ == "__main__":
    main()