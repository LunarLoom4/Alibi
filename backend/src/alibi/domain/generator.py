import random

from .layouts import Layout, LAYOUTS
from .parameters import count_rooms, max_red_herrings
from .types import Suspect


# Picks the House of a Case: One of the Layouts with the Number of Rooms that CG-2 gives for this Number of Suspects.
# The Case Generator passes its own seeded 'rng', so the same Seed always picks the same House (CG-1).
def pick_layout(num_suspects: int, rng: random.Random) -> Layout:
    # 'count_rooms' also rejects a Number of Suspects outside 5 to 10.
    layouts = LAYOUTS[count_rooms(num_suspects)]

    return rng.choice(layouts)


# Picks the Role of every Suspect: Which of them are the Murderers, and which Innocent Suspects are the Red Herrings.
# The Number of Murderers comes from the caller, because CG-12 lowers it when too many Seeds fail.
def pick_roles(num_suspects: int, num_murderers: int, rng: random.Random) -> tuple[Suspect, ...]:
    # 1. Draw the Number of Red Herrings. 'max_red_herrings' also rejects a Number of Murderers that this Number of Suspects does not allow.
    num_red_herrings = rng.randint(1, max_red_herrings(num_suspects, num_murderers))

    # 2. Draw the Murderers from every Suspect.
    suspect_ids = [f"suspect_{number}" for number in range(1, num_suspects + 1)]
    murderer_ids = set(rng.sample(suspect_ids, num_murderers))

    # 3. Draw the Red Herrings ONLY from the Innocent Suspects who are left (RH-1).
    innocent_ids = [suspect_id for suspect_id in suspect_ids if suspect_id not in murderer_ids]
    red_herring_ids = set(rng.sample(innocent_ids, num_red_herrings))

    # 4. Give every Suspect their Role, in the order of their IDs.
    suspects = []

    for suspect_id in suspect_ids:
        suspect = Suspect(
            id = suspect_id,
            is_murderer = suspect_id in murderer_ids,
            is_red_herring = suspect_id in red_herring_ids
        )
        suspects.append(suspect)

    return tuple(suspects)
