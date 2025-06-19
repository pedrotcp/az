import itertools, random, multiprocessing, os, datetime, time
from bitarray import bitarray
from tqdm import tqdm
import pickle

TOTAL_NUMBERS = 60
DRAW_SIZE = 6
TICKET_SIZE = 30
COMBO_COUNT = 50063860  # C(60,6)
TARGET_COVERAGE = 0.95
MAX_TICKETS_PER_SET = 105
CANDIDATES_PER_BATCH = 64
WORKERS = min(multiprocessing.cpu_count(), 32)

# Create output folder
os.makedirs("sets", exist_ok=True)

# Global for shared memory
shared_coverage = None
coverage_lock = None

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

def init_worker(shared_array, lock):
    """Initialize worker with shared memory"""
    global shared_coverage, coverage_lock
    shared_coverage = shared_array
    coverage_lock = lock

def evaluate_candidate(seed):
    """Evaluate a candidate ticket"""
    if seed is None:
        return None
    
    random.seed(seed)
    candidate = tuple(sorted(random.sample(range(1, TOTAL_NUMBERS + 1), TICKET_SIZE)))
    
    new_covered = 0
    covered_indices = []
    
    # Check each 6-number combination
    for combo in itertools.combinations(candidate, DRAW_SIZE):
        idx = COMBO_INDEX.get(combo)
        if idx is not None:
            with coverage_lock:
                if not shared_coverage[idx]:
                    covered_indices.append(idx)
                    new_covered += 1
    
    return (new_covered, candidate, covered_indices)

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

def generate_set(set_number):
    """Generate a single ticket set"""
    print(f"\n[>] Generating Set {set_number+1}")
    
    # Create shared memory array
    manager = multiprocessing.Manager()
    shared_array = manager.list([False] * COMBO_COUNT)
    lock = manager.Lock()
    
    accepted = []
    last_covered = 0
    total_required = int(COMBO_COUNT * TARGET_COVERAGE)
    
    # Create worker pool
    with multiprocessing.Pool(
        processes=WORKERS,
        initializer=init_worker,
        initargs=(shared_array, lock)
    ) as pool:
        
        with tqdm(total=total_required, desc=f"Set {set_number+1}", unit="combos") as pbar:
            start_time = time.time()
            no_progress_count = 0
            
            while len(accepted) < MAX_TICKETS_PER_SET:
                # Generate random seeds
                seeds = [random.randint(0, 2**32) for _ in range(CANDIDATES_PER_BATCH)]
                
                # Evaluate candidates in parallel
                results = pool.map(evaluate_candidate, seeds)
                
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
                    no_progress_count += 1
                    if no_progress_count > 5:
                        print(f"    [!] No progress after {no_progress_count} batches")
                        if no_progress_count > 10:
                            break
                    continue
                
                no_progress_count = 0
                
                # Update shared coverage
                with lock:
                    for idx in best_indexes:
                        shared_array[idx] = True
                
                accepted.append(best_candidate)
                
                # Count covered
                with lock:
                    covered_now = sum(1 for x in shared_array if x)
                
                delta_count = covered_now - last_covered
                pbar.update(delta_count)
                last_covered = covered_now
                
                # Calculate stats
                elapsed = time.time() - start_time
                combos_per_sec = covered_now / elapsed if elapsed > 0 else 0
                remaining = max(0, total_required - covered_now)
                eta_sec = remaining / combos_per_sec if combos_per_sec > 0 else float("inf")
                eta_min = eta_sec / 60
                
                print(f"    [+] Best new coverage: {best_new_covered} | Total Tickets: {len(accepted)}")
                print(f"    [~] Speed: {int(combos_per_sec):,} combos/sec | ETA: {eta_min:.1f} min")
                
                if covered_now >= total_required:
                    break
    
    # Save results
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sets/bicho_set_{timestamp}_set{set_number+1}.txt"
    
    with open(filename, "w") as f:
        for t in accepted:
            f.write(",".join(map(str, t)) + "\n")
    
    # Verify coverage
    verified_covered, percent = verify_coverage(accepted)
    print(f"[✓] Set {set_number+1} saved as {filename}")
    print(f"    - Tickets: {len(accepted)}")
    print(f"    - Coverage: {verified_covered:,} combos ({percent:.6f}%)\n")

def main():
    """Main loop"""
    set_number = 0
    while True:
        generate_set(set_number)
        set_number += 1

if __name__ == "__main__":
    main()