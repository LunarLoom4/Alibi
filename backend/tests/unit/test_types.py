import random
import pytest
from dataclasses import FrozenInstanceError

from alibi.domain.layouts import Layout, LAYOUTS
from alibi.domain.parameters import MIN_SUSPECTS, MAX_SUSPECTS, count_rooms
from alibi.domain.types import Crime, Suspect, TimelineGrid, TIME_SLOTS, VICTIM_ID, WINDOW_LENGTH


# Every Role that a Suspect can be given, whether the Rules allow it or not.
ALL_POSSIBLE_ROLES = [
    pytest.param(False, False, True,  id = "Innocent"),
    pytest.param(False, True,  True,  id = "Innocent Red Herring"),
    pytest.param(True,  False, True,  id = "Murderer"),
    pytest.param(True,  True,  False, id = "Murderer AND Red Herring"),
]

# Defining a Test Function to check that a Suspect is created ONLY with a Role that the Rules allow.
@pytest.mark.parametrize("is_murderer, is_red_herring, allowed", ALL_POSSIBLE_ROLES)
def test_suspect_is_created_only_with_an_allowed_role(is_murderer: bool, is_red_herring: bool, allowed: bool):
    if allowed:
        suspect = Suspect(id = "suspect_1", is_murderer = is_murderer, is_red_herring = is_red_herring)

        assert suspect.id == "suspect_1"
        assert suspect.is_murderer == is_murderer
        assert suspect.is_red_herring == is_red_herring

        # A frozen Suspect keeps their Role for the whole Case.
        with pytest.raises(FrozenInstanceError):
            suspect.is_murderer = not is_murderer

    else:
        with pytest.raises(ValueError):
            Suspect(id = "suspect_1", is_murderer = is_murderer, is_red_herring = is_red_herring)


# Every Role that the Rules allow.
ALLOWED_ROLES = [
    pytest.param(False, False, id = "Innocent"),
    pytest.param(False, True,  id = "Innocent Red Herring"),
    pytest.param(True,  False, id = "Murderer"),
]

# Defining a Test Function to check that no Suspect can take the Victim's ID, whatever their allowed Role.
@pytest.mark.parametrize("is_murderer, is_red_herring", ALLOWED_ROLES)
def test_suspect_never_has_the_victim_id(is_murderer: bool, is_red_herring: bool):
    with pytest.raises(ValueError):
        Suspect(id = VICTIM_ID, is_murderer = is_murderer, is_red_herring = is_red_herring)


# Every allowed Number of Suspects. The Grid tests below run once for each of them.
SUSPECT_COUNTS = range(MIN_SUSPECTS, MAX_SUSPECTS + 1)

# Number of random Grids that each Grid test builds for every Layout.
GRIDS_PER_LAYOUT = 20

# Helper function to build a Timeline Grid that puts the Victim and every Suspect in a random Room at every Time Slot.
# The Grid ignores the Doors (CG-15) and lets the Victim move after the Crime (CG-3).
# These tests check ONLY how the Grid stores and reads its Rooms.
def random_grid(layout: Layout, num_suspects: int, seed: int) -> TimelineGrid:
    rng = random.Random(seed)
    room_ids = [room.id for room in layout.rooms]
    person_ids = [VICTIM_ID] + [f"suspect_{number}" for number in range(1, num_suspects + 1)]
    locations = {}

    # Pick a random Room for each Person at each Time Slot. The same Seed always gives the same Grid.
    for person_id in person_ids:
        rooms = []
        for _ in TIME_SLOTS:
            rooms.append(rng.choice(room_ids))

        locations[person_id] = tuple(rooms)

    return TimelineGrid(locations = locations)


# Defining a Test Function to check that every Person, the Victim included, needs exactly one Room for each Time Slot (CG-3).
@pytest.mark.parametrize("tested_person_id", [VICTIM_ID, "suspect_1"])
@pytest.mark.parametrize("row_length", range(len(TIME_SLOTS) + 2))
def test_cg3_grid_needs_one_room_per_time_slot(row_length: int, tested_person_id: str):
    locations = {VICTIM_ID: ("hall",) * len(TIME_SLOTS), "suspect_1": ("hall",) * len(TIME_SLOTS)}
    locations[tested_person_id] = ("hall",) * row_length

    if row_length == len(TIME_SLOTS):
        grid = TimelineGrid(locations = locations)

        assert grid.locations[tested_person_id] == locations[tested_person_id]

    else:
        with pytest.raises(ValueError):
            TimelineGrid(locations = locations)

# Defining a Test Function to check that a Timeline Grid always holds the Victim.
def test_grid_needs_the_victim():
    with pytest.raises(ValueError):
        TimelineGrid(locations = {"suspect_1": ("hall",) * len(TIME_SLOTS)})

# Defining a Test Function to check that a Row must be a tuple, because a list could still be changed later.
def test_grid_rejects_a_row_that_is_not_a_tuple():
    with pytest.raises(TypeError):
        TimelineGrid(locations = {VICTIM_ID: ["hall"] * len(TIME_SLOTS)})

# Defining a Test Function to check that the Grid never changes after it is made, as the Ground Truth must not.
def test_grid_cannot_change_after_it_is_made():
    locations = {VICTIM_ID: ("hall",) * len(TIME_SLOTS)}
    grid = TimelineGrid(locations = locations)

    # 1. A change to the caller's dictionary does not reach the Grid.
    locations["suspect_1"] = ("hall",)
    assert "suspect_1" not in grid.locations

    # 2. The Grid's own Rows cannot be replaced.
    with pytest.raises(TypeError):
        grid.locations[VICTIM_ID] = ()

    # 3. The Rows cannot be swapped for a new dictionary.
    with pytest.raises(FrozenInstanceError):
        grid.locations = {}

# Defining a Test Function to check that 'room_of' reads the Room of every Person at every Time Slot.
# Basically, a check for the correct implementation of 'room_of()' function.
@pytest.mark.parametrize("num_suspects", SUSPECT_COUNTS)
def test_room_of_reads_every_time_slot(num_suspects: int):
    for layout in LAYOUTS[count_rooms(num_suspects)]:
        for seed in range(GRIDS_PER_LAYOUT):
            grid = random_grid(layout, num_suspects, seed)

            for person_id, rooms in grid.locations.items():
                for time_slot in range(len(TIME_SLOTS)):
                    assert grid.room_of(person_id, time_slot) == rooms[time_slot]

# Defining a Test Function to check that 'room_of' rejects a Person who is not in the Grid.
def test_room_of_rejects_an_unknown_person():
    grid = TimelineGrid(locations = {VICTIM_ID: ("hall",) * len(TIME_SLOTS)})

    with pytest.raises(ValueError):
        grid.room_of("suspect_1", 0)

# Defining a Test Function to check that 'room_of' rejects a Time Slot outside the Night, instead of reading from the end of the Row.
@pytest.mark.parametrize("time_slot", [-1, len(TIME_SLOTS)])
def test_room_of_rejects_a_nonexistent_time_slot(time_slot: int):
    grid = TimelineGrid(locations = {VICTIM_ID: ("hall",) * len(TIME_SLOTS)})

    with pytest.raises(ValueError):
        grid.room_of(VICTIM_ID, time_slot)

# Defining a Test Function to check that a Room Roster lists every Person in its Room AND nobody from other Rooms (KN-3).
# Basically, a check for the correct implementation of 'roster()' function.
@pytest.mark.parametrize("num_suspects", SUSPECT_COUNTS)
def test_kn3_roster_lists_only_the_persons_in_the_room(num_suspects: int):
    for layout in LAYOUTS[count_rooms(num_suspects)]:
        for seed in range(GRIDS_PER_LAYOUT):
            grid = random_grid(layout, num_suspects, seed)

            for time_slot in range(len(TIME_SLOTS)):
                placed_ids = []

                # Gather the Rosters of every Room of the House at this Time Slot.
                for room in layout.rooms:
                    placed_ids.extend(grid.roster(room.id, time_slot))

                # Each Person shows up in ONLY one Roster, and that Roster is the one of their own Room.
                assert sorted(placed_ids) == sorted(grid.locations)

                # Check that the same Person shows up in the Roster of their Room at this Time Slot.
                # Basically, a check for the correct coupling of 'room_of()' function and 'roster()' function.
                for person_id in grid.locations:
                    assert person_id in grid.roster(grid.room_of(person_id, time_slot), time_slot)

# Defining a Test Function to check that 'roster' rejects a Time Slot outside the Night, like 'room_of' does.
@pytest.mark.parametrize("time_slot", [-1, len(TIME_SLOTS)])
def test_roster_rejects_a_nonexistent_time_slot(time_slot: int):
    grid = TimelineGrid(locations = {VICTIM_ID: ("hall",) * len(TIME_SLOTS)})

    with pytest.raises(ValueError):
        grid.roster("hall", time_slot)


# Helper function to list every allowed Time-of-death Window for each Crime Slot, for any Number of Time Slots.
# It slides a Window of WINDOW_LENGTH Time Slots along the Night and notes every Crime Slot inside it (CG-13).
# Time Slot 0 is never a Crime Slot, because an Innocent Suspect must see the Victim alive before the Crime (CG-16).
def allowed_windows() -> dict[int, list[tuple[int, ...]]]:
    windows_of_slot = {}

    for first_slot in range(len(TIME_SLOTS) - (WINDOW_LENGTH - 1)):
        window = tuple(range(first_slot, first_slot + WINDOW_LENGTH))

        for crime_slot in window:
            if crime_slot >= 1:
                windows_of_slot.setdefault(crime_slot, []).append(window)

    return windows_of_slot

# Every allowed Time-of-death Window for each Crime Slot, for the Time Slots of the Night.
# Crime Slot 0 has None, because an Innocent Suspect must see the Victim alive before the Crime (CG-16).
# For 6 Time Slots and WINDOW_LENGTH = 3, it looks like:
# ALLOWED_WINDOWS = {
#     1: [(0, 1, 2), (1, 2, 3)],
#     2: [(0, 1, 2), (1, 2, 3), (2, 3, 4)],
#     3: [(1, 2, 3), (2, 3, 4), (3, 4, 5)],
#     4: [(2, 3, 4), (3, 4, 5)],
#     5: [(3, 4, 5)],
# }
ALLOWED_WINDOWS = allowed_windows()

# Defining a Test Function to check every pair of a Crime Slot and a Window of consecutive Time Slots (CG-13, CG-16).
# The Crime Slots and the Window starts run one step past both ends of the Night, so every edge is tried.
@pytest.mark.parametrize("crime_slot", range(-1, len(TIME_SLOTS) + 1))
@pytest.mark.parametrize("first_slot", range(-1, len(TIME_SLOTS)))
def test_cg13_cg16_crime_slot_lies_in_its_window(first_slot: int, crime_slot: int):
    window = tuple(range(first_slot, first_slot + WINDOW_LENGTH))

    if window in ALLOWED_WINDOWS.get(crime_slot, []):
        crime = Crime(slot = crime_slot, room_id = "hall", window = window)

        assert crime.window == window

        # A frozen Crime never changes during the Game.
        with pytest.raises(FrozenInstanceError):
            crime.slot = 0

    else:
        with pytest.raises(ValueError):
            Crime(slot = crime_slot, room_id = "hall", window = window)

# A valid Window that holds the Crime Slot 1. It starts at Time Slot 1, or at Time Slot 0 when the Window is as long as the Night.
# Every bad Window below except the Empty one is built from it, and still holds the Crime Slot 1.
GOOD_WINDOW_START = 1 if WINDOW_LENGTH < len(TIME_SLOTS) else 0
GOOD_WINDOW = tuple(range(GOOD_WINDOW_START, GOOD_WINDOW_START + WINDOW_LENGTH))

# Every way a Window can break its shape (CG-13).
# For 6 Time Slots and WINDOW_LENGTH = 3, these break down to [(), (1, 2), (1, 2, 3, 4), (1, 2, 4), (1, 1, 2), (3, 2, 1)].
BAD_WINDOWS = [
    pytest.param((),                                        id = "Empty"),
    pytest.param(GOOD_WINDOW[:-1],                          id = "One Time Slot short"),
    pytest.param(GOOD_WINDOW + (GOOD_WINDOW[-1] + 1,),      id = "One Time Slot too many"),
    pytest.param(GOOD_WINDOW[:-1] + (GOOD_WINDOW[-1] + 1,), id = "A gap before the last Time Slot"),
    pytest.param((GOOD_WINDOW[0],) + GOOD_WINDOW[:-1],      id = "A repeated Time Slot"),
    pytest.param(tuple(reversed(GOOD_WINDOW)),              id = "Reversed"),
]

# Defining a Test Function to check that a Window which is not WINDOW_LENGTH consecutive Time Slots is rejected.
@pytest.mark.parametrize("window", BAD_WINDOWS)
def test_cg13_window_is_consecutive_slots(window: tuple):
    with pytest.raises(ValueError):
        Crime(slot = 1, room_id = "hall", window = window)

# Defining a Test Function to check that the Window must be a tuple, like the Rows of the Timeline Grid.
def test_crime_rejects_a_window_that_is_not_a_tuple():
    with pytest.raises(TypeError):
        Crime(slot = 1, room_id = "hall", window = list(GOOD_WINDOW))
