import random

from .layouts import Layout, LAYOUTS
from .parameters import count_rooms, max_red_herrings
from .types import Crime, Sighting, Suspect, TimelineGrid, TIME_SLOTS, VICTIM_ID, WINDOW_LENGTH


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


# Picks the Sighting of a Case: An Innocent Suspect meets the Victim in a Room at a Time Slot before the Crime Slot (CG-16).
# After the meeting, both of them must still reach their Places at the Crime Slot, through one Door at most per Time Slot (CG-15).
# Returns None when no Innocent Suspect can meet the Victim in time, because then the Case cannot keep CG-16.
def pick_sighting(
    layout: Layout,
    suspects: tuple[Suspect, ...],
    places: dict[str, str],
    crime: Crime,
    rng: random.Random
) -> Sighting | None:
    distance_from_crime_room = layout.distances_from(crime.room_id)
    possible_sightings = []

    for suspect in suspects:
        if not suspect.is_murderer:
            distance_from_suspect_room = layout.distances_from(places[suspect.id])

            for time_slot in range(crime.slot):
                slots_left = crime.slot - time_slot

                # The Victim must reach the Crime Room, and the Witness their Place, within the Time Slots left.
                for room in layout.rooms:
                    # Choose a Room whose distance from the Crime Room and the Innocent's Crime Slot Room can be covered in remaining time.
                    if distance_from_crime_room[room.id] <= slots_left and distance_from_suspect_room[room.id] <= slots_left:
                        possible_sightings.append(Sighting(witness_id = suspect.id, time_slot = time_slot, room_id = room.id))

    if not possible_sightings:
        return None

    return rng.choice(possible_sightings)


# Places every Person at each Time Slot before the Crime Slot, and returns the Rooms of each Person ID from Time Slot 0 to the one just before the Crime Slot.
# It walks back in time from the Places at the Crime Slot, so every Person reaches their Place through the Doors of the House (CG-15).
def place_before_crime_slot(
    layout: Layout,
    places: dict[str, str],
    crime: Crime,
    rng: random.Random
) -> dict[str, tuple[str, ...]]:
    # 1. A Place outside the House has no Doors to walk through, so it is rejected.
    room_ids = [room.id for room in layout.rooms]

    for person_id, room_id in places.items():
        if room_id not in room_ids:
            raise ValueError(f"'{person_id}' is in the Room '{room_id}', which is not a Room of Layout '{layout.id}'.")

    # 2. Walk every Person back one Time Slot at a time: Each step stays in the Room or goes through one of its Doors (CG-15).
    # The Neighbors of a Room are sorted, because the order of a 'set' of strings changes between Python processes since sets don't have an iteration order.
    # Without the sorting, the same Seed could give another Case on another run (CG-1).
    earlier_rooms = {}

    for person_id, room_id in places.items():
        walk = [room_id]

        for _ in range(crime.slot):
            choices = [walk[-1]] + sorted(layout.neighbors(walk[-1]))
            walk.append(rng.choice(choices))

        # 3. The walk runs backward in time, so reverse it, and leave out the Place at the Crime Slot.
        earlier_rooms[person_id] = tuple(reversed(walk[1:]))

    return earlier_rooms


# Places every Person at each Time Slot after the Crime Slot, and returns the Rooms of each Person ID up to the last Time Slot.
# After the Crime Slot, a move is no longer limited to one Door per Time Slot (CG-15): A Person can be in any allowed Room at the next Time Slot.
# a. The Victim stays in the Crime Room until the end of the Night (CG-3).
# b. A Murderer can go to any Room, the Crime Room included, and the Murderers can split up (CG-19).
# c. An Innocent Suspect never enters the Crime Room, because whoever found the Body would call the Police at once (CG-18).
#    So they ONLY reach the Rooms they can walk to from their Place at the Crime Slot without passing through the Crime Room.
def place_after_crime_slot(
    layout: Layout,
    suspects: tuple[Suspect, ...],
    places: dict[str, str],
    crime: Crime,
    rng: random.Random
) -> dict[str, tuple[str, ...]]:
    # 1. A Crime Room outside the House would leave the Victim nowhere, and a Suspect needs a Place in the House to move on from.
    # So both are rejected.
    room_ids = [room.id for room in layout.rooms]

    if crime.room_id not in room_ids:
        raise ValueError(f"The Crime Room '{crime.room_id}' is not a Room of Layout '{layout.id}'.")

    for suspect in suspects:
        if places.get(suspect.id) not in room_ids:
            raise ValueError(f"'{suspect.id}' has no Place in a Room of Layout '{layout.id}' at the Crime Slot.")

    num_later_slots = len(TIME_SLOTS) - 1 - crime.slot

    # 2. The Victim stays in the Crime Room (CG-3).
    later_rooms = {VICTIM_ID: (crime.room_id,) * num_later_slots}

    # 3. Pick the Rooms each Suspect may be in, in the order of the House, so the same Seed gives the same Case (CG-1).
    for suspect in suspects:
        if suspect.is_murderer:
            allowed_room_ids = room_ids

        else:
            reachable_room_ids = layout.reachable_rooms(places[suspect.id], crime.room_id)
            allowed_room_ids = [room_id for room_id in room_ids if room_id in reachable_room_ids]

        # 4. Draw one of those Rooms for each Time Slot after the Crime Slot.
        rooms = []

        for _ in range(num_later_slots):
            rooms.append(rng.choice(allowed_room_ids))

        later_rooms[suspect.id] = tuple(rooms)

    return later_rooms


# Builds the Timeline Grid of a Case: The Room of every Person at every Time Slot of the Night.
# The Places at the Crime Slot come first, because they decide the solution (CG-11), and the rest of the Night is built around them.
def build_timeline(layout: Layout, suspects: tuple[Suspect, ...], crime: Crime, rng: random.Random) -> TimelineGrid:
    # 1. Place every Person at the Crime Slot (CG-4, CG-5, CG-6).
    places = place_at_crime_slot(layout, suspects, crime, rng)

    # 2. Walk every Person back from their Place through the Doors of the House (CG-15).
    earlier_rooms = place_before_crime_slot(layout, places, crime, rng)

    # 3. Place every Person after the Crime Slot: The Victim stays in the Crime Room (CG-3), and no Innocent Suspect enters it (CG-18).
    later_rooms = place_after_crime_slot(layout, suspects, places, crime, rng)

    # 4. Join the three parts into one Row of Room IDs for each Person, from the first to the last Time Slot.
    # The Rows follow the order of the IDs, the Victim first, so the order of the Rows never tells who the Murderers are.
    locations = {}

    for person_id in [VICTIM_ID] + [suspect.id for suspect in suspects]:
        locations[person_id] = earlier_rooms[person_id] + (places[person_id],) + later_rooms[person_id]

    return TimelineGrid(locations = locations)


# Finds the Witnesses of a Case: Every Innocent Suspect who saw the Victim alive, with the Time Slots when they did (CG-16).
# To see the Victim, a Suspect must be in the same Room at the same Time Slot (KN-3), and the Victim is alive ONLY before the Crime Slot.
# Each sighting tells the Detectives that the Crime came later, so the Witnesses help them find the Crime Slot.
def find_witnesses(grid: TimelineGrid, suspects: tuple[Suspect, ...], crime: Crime) -> dict[str, tuple[int, ...]]:
    witnesses = {}

    for suspect in suspects:
        # CG-16 asks ONLY for Innocent Suspects: A Murderer lies about the Time-of-death Window (LI-2), so the Detectives cannot trust their sighting.
        if not suspect.is_murderer:
            sighting_slots = []

            for time_slot in range(crime.slot):
                if grid.room_of(suspect.id, time_slot) == grid.room_of(VICTIM_ID, time_slot):
                    sighting_slots.append(time_slot)

            if sighting_slots:
                witnesses[suspect.id] = tuple(sighting_slots)

    return witnesses
