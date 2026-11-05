import random

from .layouts import Layout, LAYOUTS
from .parameters import count_rooms


# Picks the House of a Case: One of the Layouts with the Number of Rooms that CG-2 gives for this Number of Suspects.
# The Case Generator passes its own seeded 'rng', so the same Seed always picks the same House (CG-1).
def pick_layout(num_suspects: int, rng: random.Random) -> Layout:
    # 'count_rooms' also rejects a Number of Suspects outside 5 to 10.
    layouts = LAYOUTS[count_rooms(num_suspects)]

    return rng.choice(layouts)
