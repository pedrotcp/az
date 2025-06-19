import os

def parse_numbers(line):
    # Handles both "9" and "09"
    return set(int(x.lstrip('0') or '0') for x in line.strip().split())

# Read all results (draws)
with open('results.txt', encoding='utf-8') as f:
    draws = [parse_numbers(line) for line in f if line.strip()]

# Get all .txt files in 'games' folder
game_files = [fn for fn in os.listdir('games') if fn.endswith('.txt')]

for game_file in sorted(game_files):
    # Read all tickets for this game file
    with open(os.path.join('games', game_file), encoding='utf-8') as f:
        tickets = [parse_numbers(line) for line in f if line.strip()]

    wins = 0
    for draw in draws:
        # If ANY ticket in the file contains ALL numbers in this draw, it's a win
        if any(draw.issubset(ticket) for ticket in tickets):
            wins += 1

    percent = 100 * wins / len(draws) if draws else 0
    print(f"{game_file}: {wins} / {len(draws)} draws won ({percent:.2f}%)")
