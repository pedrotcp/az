import itertools, random, os, datetime, time
from bitarray import bitarray
from tqdm import tqdm
from math import comb

TOTAL_NUMBERS = 60
DRAW_SIZE = 6
TICKET_SIZE = 30
COMBO_COUNT = comb(TOTAL_NUMBERS, DRAW_SIZE)
TICKETS_PER_SET = 105

POP_SIZE = 64        # FEEL FREE to push even higher
N_GENERATIONS = 200  # Tune for your patience
MUTATION_RATE = 0.1  # Per-ticket, per-generation

def combo_to_index(combo):
    index = 0
    prev = 0
    for i, num in enumerate(combo):
        for j in range(prev+1, num):
            index += comb(TOTAL_NUMBERS-j, DRAW_SIZE-1-i)
        prev = num
    return index

def ticket_coverage(ticket):
    "Returns set of combo indices covered by a ticket."
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
    "Single-point crossover, ticket-wise."
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

def run_genetic():
    print(f"[*] Starting genetic search with population {POP_SIZE}, {N_GENERATIONS} generations.")
    population = [random_individual() for _ in range(POP_SIZE)]
    best_tickets = None
    best_coverage = 0

    for gen in tqdm(range(N_GENERATIONS), desc="Evolving Generations", position=0):
        fitnesses = []
        for ind in tqdm(population, desc=f"Generation {gen} Fitness", position=1, leave=False):
            fitnesses.append(fitness(ind))
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

