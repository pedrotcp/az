import itertools, random, os, datetime
from bitarray import bitarray
from tqdm import tqdm
from math import comb
from concurrent.futures import ProcessPoolExecutor, as_completed

TOTAL_NUMBERS = 60
DRAW_SIZE = 6
TICKET_SIZE = 30
COMBO_COUNT = comb(TOTAL_NUMBERS, DRAW_SIZE)
TICKETS_PER_SET = 105

POP_SIZE = 128          # Go nuts, but not so nuts you OOM!
N_GENERATIONS = 10     # Tweak for patience
MUTATION_RATE = 0.1     # Mutation per ticket per generation
N_CORES = None          # Set to None for "all available"; or an int to cap

def combo_to_index(combo):
    index = 0
    prev = 0
    for i, num in enumerate(combo):
        for j in range(prev+1, num):
            index += comb(TOTAL_NUMBERS-j, DRAW_SIZE-1-i)
        prev = num
    return index

def ticket_coverage(ticket):
    return set(combo_to_index(c) for c in itertools.combinations(ticket, DRAW_SIZE))

def individual_coverage(tickets):
    covered = set()
    for t in tickets:
        covered.update(ticket_coverage(t))
    return covered

def fitness(tickets):
    return len(individual_coverage(tickets))

def random_ticket():
    return sorted(random.sample(range(1, TOTAL_NUMBERS+1), TICKET_SIZE))

def random_individual():
    return [random_ticket() for _ in range(TICKETS_PER_SET)]

def crossover(parent1, parent2):
    cut = random.randint(1, TICKETS_PER_SET-1)
    child1 = parent1[:cut] + parent2[cut:]
    child2 = parent2[:cut] + parent1[cut:]
    return child1, child2

def mutate(individual):
    for i in range(TICKETS_PER_SET):
        if random.random() < MUTATION_RATE:
            t = set(individual[i])
            to_remove = random.choice(list(t))
            t.remove(to_remove)
            possible = set(range(1, TOTAL_NUMBERS+1)) - t
            t.add(random.choice(list(possible)))
            individual[i] = sorted(t)
    return individual

def parallel_fitness(population, n_workers=None):
    # Evaluate fitness in parallel!
    fitnesses = [None] * len(population)
    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(fitness, ind): idx for idx, ind in enumerate(population)}
        for f in tqdm(as_completed(futures), total=len(futures), desc="Fitness (parallel)", leave=False):
            idx = futures[f]
            fitnesses[idx] = f.result()
    return fitnesses

def run_genetic():
    print(f"[*] Genetic beast mode: {POP_SIZE} population, {N_GENERATIONS} generations, {N_CORES or os.cpu_count()} cores.")
    population = [random_individual() for _ in range(POP_SIZE)]
    best_tickets = None
    best_coverage = 0

    for gen in tqdm(range(N_GENERATIONS), desc="Evolving Generations", position=0):
        fitnesses = parallel_fitness(population, N_CORES)
        max_fit = max(fitnesses)
        if max_fit > best_coverage:
            best_coverage = max_fit
            best_tickets = population[fitnesses.index(max_fit)]
            print(f"    [Gen {gen}] New best: {best_coverage} unique combos ({best_coverage/COMBO_COUNT*100:.2f}%)")

        # Tournament selection
        selected = []
        for _ in range(POP_SIZE // 2):
            contenders = random.sample(population, 4)
            contenders.sort(key=fitness, reverse=True)
            selected.append(contenders[0])
            selected.append(contenders[1])

        # Next generation
        next_population = []
        while len(next_population) < POP_SIZE:
            p1, p2 = random.sample(selected, 2)
            c1, c2 = crossover(p1, p2)
            next_population.append(mutate(c1))
            if len(next_population) < POP_SIZE:
                next_population.append(mutate(c2))

        population = next_population

    print(f"\n[✓] Genetic search done.")
    print(f"    - Best coverage: {best_coverage} / {COMBO_COUNT} ({best_coverage/COMBO_COUNT*100:.4f}%)")
    return best_tickets

def save_tickets(tickets):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sets/genetic_bicho_set_{timestamp}.txt"
    os.makedirs("sets", exist_ok=True)
    with open(filename, "w") as f:
        for t in tickets:
            f.write(",".join(map(str, t)) + "\n")
    print(f"[✓] Tickets saved as {filename}")

if __name__ == "__main__":
    best = run_genetic()
    save_tickets(best)
