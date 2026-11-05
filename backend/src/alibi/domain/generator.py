import random

from .layouts import Layout, LAYOUTS
from .parameters import count_rooms, max_red_herrings
from .types import Crime, Suspect, TIME_SLOTS


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


# Picks the Crime of a Case: The Crime Slot, a Room of the House, and the Time-of-death Window around the Crime Slot (CG-13).
def pick_crime(layout: Layout, rng: random.Random) -> Crime:
    # 1. The Crime Slot is never the first Time Slot, because an Innocent Suspect saw the Victim alive before it (CG-16).
    crime_slot = rng.randint(1, len(TIME_SLOTS) - 1)

    # 2. The Crime can happen in any Room of the House.
    room_id = rng.choice([room.id for room in layout.rooms])

    # 3. The Window is 3 consecutive Time Slots that hold the Crime Slot and stay inside the Night.
    window_starts = []

    for window_start in range(crime_slot - 2, crime_slot + 1):
        if window_start >= 0 and window_start + 2 < len(TIME_SLOTS):
            window_starts.append(window_start)

    first_slot = rng.choice(window_starts)

    return Crime(slot = crime_slot, room_id = room_id, window = (first_slot, first_slot + 1, first_slot + 2))
