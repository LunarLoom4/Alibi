import random

from .layouts import Layout, LAYOUTS
from .parameters import count_rooms, max_red_herrings
from .types import Crime, Suspect, TIME_SLOTS, VICTIM_ID, WINDOW_LENGTH


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

    # 3. The Window is WINDOW_LENGTH consecutive Time Slots that hold the Crime Slot and stay inside the Night.
    window_starts = []

    for window_start in range(crime_slot - (WINDOW_LENGTH - 1), crime_slot + 1):
        if window_start >= 0 and window_start + WINDOW_LENGTH <= len(TIME_SLOTS):
            window_starts.append(window_start)

    first_slot = rng.choice(window_starts)

    return Crime(slot = crime_slot, room_id = room_id, window = tuple(range(first_slot, first_slot + WINDOW_LENGTH)))


# Places every Person at the Crime Slot, and returns the Room ID of each Person ID.
# The Crime Room holds ONLY the Victim and the Murderers (CG-4), so no Innocent Suspect is in a Room with a Murderer (CG-5).
# The Innocent Suspects stand in groups of 2 or more in the other Rooms, so each of them has an alibi (CG-6).
def place_at_crime_slot(layout: Layout, suspects: tuple[Suspect, ...], crime: Crime, rng: random.Random) -> dict[str, str]:
    # 1. A Crime Room outside the House would leave the Victim nowhere, so it is rejected.
    room_ids = [room.id for room in layout.rooms]

    if crime.room_id not in room_ids:
        raise ValueError(f"The Crime Room '{crime.room_id}' is not a Room of Layout '{layout.id}'.")

    # 2. The Victim and every Murderer are in the Crime Room (CG-4).
    places = {VICTIM_ID: crime.room_id}

    for suspect in suspects:
        if suspect.is_murderer:
            places[suspect.id] = crime.room_id

    # 3. Pick how many groups the Innocent Suspects form, and a different Room outside the Crime Room for each group.
    other_room_ids = [room_id for room_id in room_ids if room_id != crime.room_id]
    innocent_ids = [suspect.id for suspect in suspects if not suspect.is_murderer]

    # The number of groups the Innocent Suspects can form is limited by the number of Non-Crime Rooms in the Layout.
    num_groups = rng.randint(1, min(len(innocent_ids) // 2, len(other_room_ids)))
    group_room_ids = rng.sample(other_room_ids, num_groups)

    # 4. Every group gets 2 Innocent Suspects first, so no Innocent Suspect is ever alone (CG-6).
    rng.shuffle(innocent_ids)

    for index, room_id in enumerate(group_room_ids):
        places[innocent_ids[2 * index]] = room_id
        places[innocent_ids[2 * index + 1]] = room_id

    # 5. Each Innocent Suspect who is left joins one of the groups at random.
    for innocent_id in innocent_ids[2 * num_groups:]:
        places[innocent_id] = rng.choice(group_room_ids)

    return places
