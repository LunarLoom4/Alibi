import random
import pytest
from dataclasses import FrozenInstanceError

from alibi.domain.layouts import Layout, LAYOUTS
from alibi.domain.parameters import MIN_SUSPECTS, MAX_SUSPECTS, count_rooms
from alibi.domain.types import Suspect, TimelineGrid, TIME_SLOTS, VICTIM_ID


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

# Defining a Test Function to check that 'room_of' rejects a Time Slot outside 0 to 5, instead of reading from the end of the Row.
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

# Defining a Test Function to check that 'roster' rejects a Time Slot outside 0 to 5, like 'room_of' does.
@pytest.mark.parametrize("time_slot", [-1, len(TIME_SLOTS)])
def test_roster_rejects_a_nonexistent_time_slot(time_slot: int):
    grid = TimelineGrid(locations = {VICTIM_ID: ("hall",) * len(TIME_SLOTS)})

    with pytest.raises(ValueError):
        grid.roster("hall", time_slot)
