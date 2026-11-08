import os
import subprocess
import sys
import math
import random
import pytest
import itertools

import alibi
from alibi.domain import generator
from alibi.domain.generator import pick_layout, pick_roles, pick_crime
from alibi.domain.generator import place_at_crime_slot, place_before_crime_slot, place_after_crime_slot
from alibi.domain.generator import build_timeline, find_witnesses, pick_sighting
from alibi.domain.generator import generate_case, MAX_SEEDS_PER_CASE

from alibi.domain.layouts import Layout, LAYOUTS
from alibi.domain.parameters import MIN_SUSPECTS, MAX_SUSPECTS, count_rooms, max_murderers, max_red_herrings
from alibi.domain.types import Crime, Sighting, Suspect, TimelineGrid, TIME_SLOTS, VICTIM_ID, WINDOW_LENGTH


# Every allowed Number of Suspects. The tests below run once for each of them.
SUSPECT_COUNTS = range(MIN_SUSPECTS, MAX_SUSPECTS + 1)

# The Seeds for the tests that check a Rule on every Seed. Each Seed is a full check of its own.
# This number ONLY trades run time for confidence. More Suspects and More Layouts mostly add test cases through 'parametrize', not Seeds.
SEEDS = range(200)

# Highest chance that a coverage test is allowed to miss an outcome that the code can really produce.
MISS_CHANCE = 1e-9


# Helper function to count the Seeds that a coverage test needs, so that missing any outcome has a chance below MISS_CHANCE.
# An outcome with the chance 'p' is missed by N Seeds with the chance (1 - p) ** N, which is at most e ** (-p * N).
# For all the outcomes together, that stays below MISS_CHANCE when N >= ln(num_outcomes / MISS_CHANCE) / p.
# Thus, N grows by itself with more Layouts, Rooms or Suspects, and stays small when there are few outcomes.
def seeds_for_coverage(num_outcomes: int, smallest_chance: float) -> range:
    return range(math.ceil(math.log(num_outcomes / MISS_CHANCE) / smallest_chance))

# Defining a Test Function to check that 'seeds_for_coverage' keeps the chance of a miss below MISS_CHANCE.
# It also checks that more outcomes and rarer outcomes get more Seeds.
@pytest.mark.parametrize("num_outcomes", [1, 2, 3, 5, 8, 10, 26])
def test_seeds_for_coverage_scales_with_the_outcomes(num_outcomes: int):
    for smallest_chance in [0.5, 1 / num_outcomes, 0.1, 0.01]:
        num_seeds = len(seeds_for_coverage(num_outcomes, smallest_chance))

        # Asserts that the chance of missing any outcome is below MISS_CHANCE.
        assert num_outcomes * (1 - smallest_chance) ** num_seeds <= MISS_CHANCE

        # Asserts that more outcomes get more Seeds.
        assert len(seeds_for_coverage(num_outcomes + 1, smallest_chance)) >= num_seeds

        # Asserts that rarer outcomes (who have smaller chances) get more Seeds than frequent outcomes.
        assert len(seeds_for_coverage(num_outcomes, smallest_chance / 2)) > num_seeds


# Defining a Test Function to check that the picked House has the Number of Rooms that CG-2 gives, and comes from LAYOUTS.
@pytest.mark.parametrize("num_suspects", SUSPECT_COUNTS)
def test_cg2_layout_has_the_rooms_for_the_suspects(num_suspects: int):
    num_rooms = count_rooms(num_suspects)

    # Any value of 'seed' should choose a Layout only from the pre-constructed set of Layouts.
    for seed in SEEDS:
        layout = pick_layout(num_suspects, random.Random(seed))

        assert len(layout.rooms) == num_rooms
        assert layout in LAYOUTS[num_rooms]

# Defining a Test Function to check that every Layout with the Number of Rooms for this Number of Suspects gets picked over the Seeds (CG-2).
@pytest.mark.parametrize("num_suspects", SUSPECT_COUNTS)
def test_cg2_every_layout_can_be_picked(num_suspects: int):
    layout_ids = {layout.id for layout in LAYOUTS[count_rooms(num_suspects)]}
    picked_ids = set()

    # Each Layout has the chance 1 / L, where L is the Number of Layouts for this Number of Rooms.
    for seed in seeds_for_coverage(len(layout_ids), 1 / len(layout_ids)):
        picked_ids.add(pick_layout(num_suspects, random.Random(seed)).id)

    assert picked_ids == layout_ids

# Defining a Test Function to check that a Number of Suspects outside 5 to 10 is rejected.
@pytest.mark.parametrize("num_suspects", [MIN_SUSPECTS - 1, MAX_SUSPECTS + 1])
def test_pick_layout_rejects_a_disallowed_number_of_suspects(num_suspects: int):
    with pytest.raises(ValueError):
        pick_layout(num_suspects, random.Random(0))


# Every allowed pair of (Number of Suspects, Number of Murderers), from the limits in 'parameters.py'.
ROLE_COUNTS = [
    (num_suspects, num_murderers)
    for num_suspects in SUSPECT_COUNTS
    for num_murderers in range(1, max_murderers(num_suspects) + 1)
]

# Defining a Test Function to check that the Roles come as a tuple of 'suspect_1' to 'suspect_S', in that order.
# It also checks the given Number of Murderers and an allowed Number of Red Herrings.
@pytest.mark.parametrize("num_suspects, num_murderers", ROLE_COUNTS)
def test_roles_have_the_right_counts(num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        suspects = pick_roles(num_suspects, num_murderers, random.Random(seed))
        num_red_herrings = len([suspect for suspect in suspects if suspect.is_red_herring])

        assert isinstance(suspects, tuple)
        assert [suspect.id for suspect in suspects] == [f"suspect_{number}" for number in range(1, num_suspects + 1)]
        assert len([suspect for suspect in suspects if suspect.is_murderer]) == num_murderers
        assert 1 <= num_red_herrings <= max_red_herrings(num_suspects, num_murderers)

# Defining a Test Function to check that a Red Herring is always an Innocent Suspect (RH-1).
@pytest.mark.parametrize("num_suspects, num_murderers", ROLE_COUNTS)
def test_rh1_red_herrings_are_innocent(num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        for suspect in pick_roles(num_suspects, num_murderers, random.Random(seed)):
            assert not (suspect.is_murderer and suspect.is_red_herring)

# Defining a Test Function to check that, over the Seeds, every Suspect can be a Murderer and every Suspect can be a Red Herring.
# It also checks that every allowed Number of Red Herrings shows up.
@pytest.mark.parametrize("num_suspects, num_murderers", ROLE_COUNTS)
def test_roles_cover_every_choice(num_suspects: int, num_murderers: int):
    all_ids = {f"suspect_{number}" for number in range(1, num_suspects + 1)}
    maximum_red_herrings = max_red_herrings(num_suspects, num_murderers)

    murderer_ids = set()
    red_herring_ids = set()
    red_herring_counts = set()

    # The rarest outcomes:
    # a. A given Suspect is a Murderer with the chance M / S.
    # b. A given Suspect is a Red Herring with the chance (average Number of Red Herrings) / S.
    # c. Each Number of Red Herrings shows up with the chance 1 / (largest Number).
    murderer_seeds = seeds_for_coverage(num_suspects, num_murderers / num_suspects)
    red_herring_seeds = seeds_for_coverage(num_suspects, (1 + maximum_red_herrings) / 2 / num_suspects)
    count_seeds = seeds_for_coverage(maximum_red_herrings, 1 / maximum_red_herrings)

    for seed in range(max(len(murderer_seeds), len(red_herring_seeds), len(count_seeds))):
        suspects = pick_roles(num_suspects, num_murderers, random.Random(seed))

        murderer_ids.update(suspect.id for suspect in suspects if suspect.is_murderer)
        red_herring_ids.update(suspect.id for suspect in suspects if suspect.is_red_herring)
        red_herring_counts.add(len([suspect for suspect in suspects if suspect.is_red_herring]))

    assert murderer_ids == all_ids
    assert red_herring_ids == all_ids
    assert red_herring_counts == set(range(1, maximum_red_herrings + 1))

# Defining a Test Function to check that, for every Number of Suspects, 0 Murderers and one more than the largest Number are rejected.
@pytest.mark.parametrize("num_suspects", SUSPECT_COUNTS)
def test_pick_roles_rejects_a_disallowed_number_of_murderers(num_suspects: int):
    for num_murderers in [0, max_murderers(num_suspects) + 1]:
        with pytest.raises(ValueError):
            pick_roles(num_suspects, num_murderers, random.Random(0))

# Defining a Test Function to check that a Number of Suspects outside 5 to 10 is rejected.
@pytest.mark.parametrize("num_suspects", [MIN_SUSPECTS - 1, MAX_SUSPECTS + 1])
def test_pick_roles_rejects_a_disallowed_number_of_suspects(num_suspects: int):
    with pytest.raises(ValueError):
        pick_roles(num_suspects, 1, random.Random(0))


# Every Layout in the LAYOUTS dictionary, and their IDs. The Crime tests below run once for each of them.
ALL_LAYOUTS = [layout for layouts in LAYOUTS.values() for layout in layouts]
ALL_LAYOUT_IDS = [layout.id for layout in ALL_LAYOUTS]

# Helper function to list every allowed Time-of-death Window for each Crime Slot, built the same way as in 'test_types.py'.
# It slides a Window of WINDOW_LENGTH Time Slots along the Night and notes every Crime Slot inside it (CG-13, CG-16).
def allowed_windows() -> dict[int, list[tuple[int, ...]]]:
    windows_of_slot = {}

    for first_slot in range(len(TIME_SLOTS) - (WINDOW_LENGTH - 1)):
        window = tuple(range(first_slot, first_slot + WINDOW_LENGTH))

        for crime_slot in window:
            if crime_slot >= 1:
                windows_of_slot.setdefault(crime_slot, []).append(window)

    return windows_of_slot

# Every allowed Time-of-death Window for each Crime Slot, for the Time Slots of the Night.
# Crime Slot 0 has None, because an innocent Suspect must see the Victim alive before the Crime (CG-16). 
# For 6 Time Slots and WINDOW_LENGTH = 3, it looks like:
# ALLOWED_WINDOWS = {
#     1: [(0, 1, 2), (1, 2, 3)],
#     2: [(0, 1, 2), (1, 2, 3), (2, 3, 4)],
#     3: [(1, 2, 3), (2, 3, 4), (3, 4, 5)],
#     4: [(2, 3, 4), (3, 4, 5)],
#     5: [(3, 4, 5)],
# }
ALLOWED_WINDOWS = allowed_windows()

# Defining a Test Function to check that the Crime Room is a Room of the House (CG-13).
# The Crime itself already rejects a Crime Slot or a Window that the Rules do not allow.
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = ALL_LAYOUT_IDS)
def test_cg13_crime_room_is_in_the_house(layout: Layout):
    room_ids = {room.id for room in layout.rooms}

    for seed in SEEDS:
        assert pick_crime(layout, random.Random(seed)).room_id in room_ids

# Defining a Test Function to check that, over the Seeds, every Room can be the Crime Room and every Window of every Crime Slot shows up.
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = ALL_LAYOUT_IDS)
def test_cg13_crime_covers_every_choice(layout: Layout):
    all_room_ids = {room.id for room in layout.rooms}
    all_windows = set()
    for crime_slot, windows in ALLOWED_WINDOWS.items():
        for window in windows:
            all_windows.add((crime_slot, window))

    picked_room_ids = set()
    picked_windows = set()

    # Each Room has the chance 1 / R.
    # The rarest (Crime Slot, Window) pair has the chance 1 / num_crime_slots * 1 / max_num_of_windows_in_a_crime_slot.
    # Time Slot 0 is never a Crime Slot, so num_crime_slots = len(TIME_SLOTS) - 1.
    # A Crime Slot can occur in at most WINDOW_LENGTH Windows, so max_num_of_windows_in_a_crime_slot <= WINDOW_LENGTH.
    # => 1 / (len(TIME_SLOTS) - 1) * 1 / WINDOW_LENGTH
    # => For 6 Time Slots and WINDOW_LENGTH = 3:
    # => 1 / 5 * 1 / 3
    # => 1 / 15
    room_seeds = seeds_for_coverage(len(all_room_ids), 1 / len(all_room_ids))
    window_seeds = seeds_for_coverage(len(all_windows), 1 / (len(TIME_SLOTS) - 1) / WINDOW_LENGTH)

    for seed in range(max(len(room_seeds), len(window_seeds))):
        crime = pick_crime(layout, random.Random(seed))

        picked_room_ids.add(crime.room_id)
        picked_windows.add((crime.slot, crime.window))

    assert picked_room_ids == all_room_ids
    assert picked_windows == all_windows


# Helper function to build the Case up to the Crime Slot from one Seed: The Roles, then the Crime, then the Places.
def case_at_crime_slot(
    layout: Layout,
    num_suspects: int,
    num_murderers: int,
    seed: int
) -> tuple[tuple[Suspect, ...], Crime, dict[str, str]]:
    rng = random.Random(seed)
    suspects = pick_roles(num_suspects, num_murderers, rng)
    crime = pick_crime(layout, rng)
    places = place_at_crime_slot(layout, suspects, crime, rng)

    return suspects, crime, places

# Every allowed (Layout, Number of Suspects, Number of Murderers): Each Number of Suspects with every Layout of its Number of Rooms.
PLACEMENT_CASES = [
    pytest.param(layout, num_suspects, num_murderers, id = f"{layout.id}-S{num_suspects}-M{num_murderers}")
    for num_suspects, num_murderers in ROLE_COUNTS
    for layout in LAYOUTS[count_rooms(num_suspects)]
]

# Defining a Test Function to check that every Person is placed once, in a Room of the House.
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_every_person_is_placed_once(layout: Layout, num_suspects: int, num_murderers: int):
    room_ids = {room.id for room in layout.rooms}

    for seed in SEEDS:
        suspects, crime, places = case_at_crime_slot(layout, num_suspects, num_murderers, seed)

        assert set(places) == {VICTIM_ID} | {suspect.id for suspect in suspects}
        assert set(places.values()) <= room_ids

# Defining a Test Function to check that the Crime Room holds the Victim and every Murderer, and nobody else (CG-4).
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_cg4_crime_room_has_only_the_victim_and_the_murderers(layout: Layout, num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        suspects, crime, places = case_at_crime_slot(layout, num_suspects, num_murderers, seed)
        in_crime_room = {person_id for person_id, room_id in places.items() if room_id == crime.room_id}

        assert in_crime_room == {VICTIM_ID} | {suspect.id for suspect in suspects if suspect.is_murderer}

# Defining a Test Function to check that no Innocent Suspect is in a Room with a Murderer (CG-5).
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_cg5_no_innocent_is_with_a_murderer(layout: Layout, num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        suspects, crime, places = case_at_crime_slot(layout, num_suspects, num_murderers, seed)
        murderer_room_ids = {places[suspect.id] for suspect in suspects if suspect.is_murderer}

        for suspect in suspects:
            if not suspect.is_murderer:
                assert places[suspect.id] not in murderer_room_ids

# Defining a Test Function to check that every Innocent Suspect shares their Room with one or more other Innocent Suspects (CG-6).
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_cg6_every_innocent_has_an_innocent_witness(layout: Layout, num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        suspects, crime, places = case_at_crime_slot(layout, num_suspects, num_murderers, seed)
        innocent_ids = [suspect.id for suspect in suspects if not suspect.is_murderer]

        # The list counts the Innocent Suspect too, so 2 or more means one or more other Innocent Suspects.
        for innocent_id in innocent_ids:
            same_room_ids = [other_id for other_id in innocent_ids if places[other_id] == places[innocent_id]]

            assert len(same_room_ids) >= 2

# Defining a Test Function to check that, over the Seeds, every Room of the House can hold a group of Innocent Suspects.
# It also checks that every Number of groups from 1 to (Number of Innocent Suspects // 2) shows up.
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_placement_covers_every_choice(layout: Layout, num_suspects: int, num_murderers: int):
    room_ids = {room.id for room in layout.rooms}
    largest_groups = (num_suspects - num_murderers) // 2
    group_room_ids = set()
    group_counts = set()

    # A given Room holds a group with a chance of at least 1 / R. Each Number of groups has the chance 1 / (largest Number).
    room_seeds = seeds_for_coverage(len(room_ids), 1 / len(room_ids))
    count_seeds = seeds_for_coverage(largest_groups, 1 / largest_groups)

    for seed in range(max(len(room_seeds), len(count_seeds))):
        suspects, crime, places = case_at_crime_slot(layout, num_suspects, num_murderers, seed)
        innocent_room_ids = {places[suspect.id] for suspect in suspects if not suspect.is_murderer}

        group_room_ids.update(innocent_room_ids)
        group_counts.add(len(innocent_room_ids))

    assert group_room_ids == room_ids
    assert group_counts == set(range(1, largest_groups + 1))


# Every allowed (Layout, Number of Suspects, Number of Murderers) where the Innocent Suspects can form 2 or more groups.
GROUPING_CASES = [
    pytest.param(layout, num_suspects, num_murderers, id = f"{layout.id}-S{num_suspects}-M{num_murderers}")
    for num_suspects, num_murderers in ROLE_COUNTS
    if (num_suspects - num_murderers) // 2 >= 2
    for layout in LAYOUTS[count_rooms(num_suspects)]
]

# Defining a Test Function to check that, over the Seeds, every two Suspects can stand in two different groups of Innocent Suspects.
# It also checks that, with 6 or more Innocent Suspects, two groups can both have 3 or more Innocent Suspects.
@pytest.mark.parametrize("layout, num_suspects, num_murderers", GROUPING_CASES)
def test_placement_mixes_the_groups(layout: Layout, num_suspects: int, num_murderers: int):
    num_innocents = num_suspects - num_murderers
    largest_groups = num_innocents // 2

    all_possible_pairs_of_suspects = set(itertools.combinations([f"suspect_{number}" for number in range(1, num_suspects + 1)], 2))

    split_pairs = set()
    saw_two_big_groups = False

    # Two given Suspects are both Innocent together with the chance of: I (I - 1) / (S (S - 1)).
    both_innocent_chance = num_innocents * (num_innocents - 1) / (num_suspects * (num_suspects - 1))

    # They then stand in 2 different groups with a chance of at least 1 / (2 * largest Number of groups).
    pair_seeds = seeds_for_coverage(len(all_possible_pairs_of_suspects), both_innocent_chance / (2 * largest_groups))

    # With 6 or more Innocent Suspects, two groups of 3 or more show up with a chance of at least 1 / (2 * largest Number of groups).
    big_group_seeds = seeds_for_coverage(1, 1 / (2 * largest_groups))

    for seed in range(max(len(pair_seeds), len(big_group_seeds))):
        suspects, crime, places = case_at_crime_slot(layout, num_suspects, num_murderers, seed)
        innocent_ids = [suspect.id for suspect in suspects if not suspect.is_murderer]
        group_sizes = {}

        for first_id, second_id in itertools.combinations(innocent_ids, 2):
            if places[first_id] != places[second_id]:
                split_pairs.add((first_id, second_id))

        for innocent_id in innocent_ids:
            group_sizes[places[innocent_id]] = group_sizes.get(places[innocent_id], 0) + 1

        if len([size for size in group_sizes.values() if size >= 3]) >= 2:
            saw_two_big_groups = True

    assert split_pairs == all_possible_pairs_of_suspects

    if num_innocents >= 6:
        assert saw_two_big_groups

# Defining a Test Function to check that a Crime Room outside the House is rejected.
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = ALL_LAYOUT_IDS)
def test_place_at_crime_slot_rejects_a_crime_room_outside_the_house(layout: Layout):
    num_suspects = MIN_SUSPECTS
    suspects = pick_roles(num_suspects, 1, random.Random(0))
    crime = Crime(slot = 1, room_id = "attic", window = tuple(range(WINDOW_LENGTH)))

    with pytest.raises(ValueError):
        place_at_crime_slot(layout, suspects, crime, random.Random(0))


# Helper function to build the Case up to the Crime Slot from one Seed, and then the Rooms of every Person before it.
def case_before_crime_slot(
    layout: Layout,
    num_suspects: int,
    num_murderers: int,
    seed: int
) -> tuple[Crime, dict[str, str], dict[str, tuple[str, ...]]]:
    rng = random.Random(seed)
    suspects = pick_roles(num_suspects, num_murderers, rng)
    crime = pick_crime(layout, rng)
    places = place_at_crime_slot(layout, suspects, crime, rng)
    earlier_rooms = place_before_crime_slot(layout, places, crime, rng)

    return crime, places, earlier_rooms

# Defining a Test Function to check that every Person gets one Room of the House for each Time Slot before the Crime Slot.
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_every_person_has_a_room_before_the_crime_slot(layout: Layout, num_suspects: int, num_murderers: int):
    room_ids = {room.id for room in layout.rooms}

    for seed in SEEDS:
        crime, places, earlier_rooms = case_before_crime_slot(layout, num_suspects, num_murderers, seed)

        # Assert that the people in 'earlier_rooms' are also in the 'places' dictionary.
        assert set(earlier_rooms) == set(places)

        for rooms in earlier_rooms.values():
            assert isinstance(rooms, tuple)
            assert len(rooms) == crime.slot     # Asserts that there is one Room for each Time Slot before the Crime Slot.
            assert set(rooms) <= room_ids       # Asserts that every Room assigned to every Person across all Time Slots is a Room of the House.

# Defining a Test Function to check that, from one Time Slot to the next, every Person either stays in their Room or enters a Neighbor Room (CG-15).
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_cg15_moves_before_the_crime_slot_use_the_doors(layout: Layout, num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        crime, places, earlier_rooms = case_before_crime_slot(layout, num_suspects, num_murderers, seed)

        # The walk of each Person ends at their Place at the Crime Slot.
        for person_id, rooms in earlier_rooms.items():
            walk = rooms + (places[person_id],)

            for time_slot in range(crime.slot):
                from_room_id = walk[time_slot]
                to_room_id = walk[time_slot + 1]

                assert to_room_id == from_room_id or to_room_id in layout.neighbors(from_room_id), \
                    f"'{person_id}' moved from '{from_room_id}' to '{to_room_id}' without a Door, after Time Slot {time_slot}."

# Defining a Test Function to check that, over the Seeds, every Person can stay in a Room or come from each Room with a Door to it.
# Each Room of the House holds one Person at the Crime Slot 1, so each of them takes exactly one step back.
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = ALL_LAYOUT_IDS)
def test_moves_before_the_crime_slot_cover_every_door(layout: Layout):
    places = {f"person_in_{room.id}": room.id for room in layout.rooms}
    crime = Crime(slot = 1, room_id = layout.rooms[0].id, window = tuple(range(WINDOW_LENGTH)))

    all_moves = set()
    picked_moves = set()

    for room in layout.rooms:
        all_moves.add((room.id, room.id))

        for neighbor_id in layout.neighbors(room.id):
            all_moves.add((neighbor_id, room.id))

    # From a Room with D Doors, there are D + 1 choices in front of a Person.
    max_doors_from_a_room = max(len(layout.neighbors(room.id)) for room in layout.rooms)

    # Each seed allows 'len(places)' number of People to choose the first and the last Rooms.
    # Among all possible start-and-end room combinations, the smallest chance exists for the room with the most number of Doors attached to it.
    # That smallest chance is 1 / (max_doors_from_a_room + 1).
    # '+1' has been added because a person can choose to stay in the same room as well, so D + 1 choices per room with D Doors.
    for seed in seeds_for_coverage(len(all_moves), 1 / (max_doors_from_a_room + 1)):
        earlier_rooms = place_before_crime_slot(layout, places, crime, random.Random(seed))

        for person_id, rooms in earlier_rooms.items():
            picked_moves.add((rooms[0], places[person_id]))

    assert picked_moves == all_moves

# Defining a Test Function to check that a Place outside the House is rejected.
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = ALL_LAYOUT_IDS)
def test_place_before_crime_slot_rejects_a_place_outside_the_house(layout: Layout):
    places = {VICTIM_ID: layout.rooms[0].id, "suspect_1": "attic"}
    crime = Crime(slot = 1, room_id = layout.rooms[0].id, window = tuple(range(WINDOW_LENGTH)))

    with pytest.raises(ValueError):
        place_before_crime_slot(layout, places, crime, random.Random(0))


# Python code that a new Python process runs: It prints the picked Houses, and the Roles, the Crime and the Timeline Grid of a few Seeds.
# It does so for every allowed (Layout, Suspects, Murderers).
# It also prints the walks back from the Crime Slot without a Sighting, because 'build_timeline' always passes a Sighting.
# A few Seeds are enough, because a choice that follows the order of a set changes the Case within the first few of them.
CASE_SCRIPT = """
import random

from alibi.domain.generator import pick_layout, pick_crime, pick_roles, build_timeline
from alibi.domain.generator import place_at_crime_slot, place_before_crime_slot
from alibi.domain.layouts import LAYOUTS
from alibi.domain.parameters import MIN_SUSPECTS, MAX_SUSPECTS, count_rooms, max_murderers

for num_suspects in range(MIN_SUSPECTS, MAX_SUSPECTS + 1):
    for seed in range(20):
        print(pick_layout(num_suspects, random.Random(seed)).id)

    for num_murderers in range(1, max_murderers(num_suspects) + 1):
        for layout in LAYOUTS[count_rooms(num_suspects)]:
            for seed in range(20):
                rng = random.Random(seed)
                suspects = pick_roles(num_suspects, num_murderers, rng)
                crime = pick_crime(layout, rng)
                grid = build_timeline(layout, suspects, crime, rng)

                print(suspects, crime)

                places = place_at_crime_slot(layout, suspects, crime, random.Random(seed))
                print(sorted(place_before_crime_slot(layout, places, crime, random.Random(seed)).items()))

                if grid is None:
                    print("Rejected")
                else:
                    print(sorted(grid.locations.items()))
"""

# Defining a Test Function to check that the same Seed gives the same Case in every new Python process (CG-1).
# Each new process orders a set of strings in its own way, chosen by PYTHONHASHSEED.
# So a random choice that follows the order of a set gives another Case in another process, and this test catches it.
def test_cg1_same_seed_gives_the_same_case_in_every_process():
    # The new process imports 'alibi' from the same folder as this test run does.
    source_folder = os.path.dirname(os.path.dirname(alibi.__file__))
    outputs = []

    for hash_seed in ["0", "1", "2"]:
        environment = dict(os.environ, PYTHONHASHSEED = hash_seed, PYTHONPATH = source_folder)
        result = subprocess.run(
            [sys.executable, "-c", CASE_SCRIPT],
            env = environment,
            capture_output = True,
            text = True,
            check = True
        )
        outputs.append(result.stdout)

    assert outputs[0] != ""
    assert outputs[0] == outputs[1] == outputs[2]


# Helper function to build the Case up to the Crime Slot from one Seed, and then the Rooms of every Person after it.
def case_after_crime_slot(
    layout: Layout,
    num_suspects: int,
    num_murderers: int,
    seed: int
) -> tuple[tuple[Suspect, ...], Crime, dict[str, str], dict[str, tuple[str, ...]]]:
    rng = random.Random(seed)
    suspects = pick_roles(num_suspects, num_murderers, rng)
    crime = pick_crime(layout, rng)
    places = place_at_crime_slot(layout, suspects, crime, rng)
    later_rooms = place_after_crime_slot(layout, suspects, places, crime, rng)

    return suspects, crime, places, later_rooms

# Defining a Test Function to check that every Person gets one Room of the House for each Time Slot after the Crime Slot.
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_every_person_has_a_room_after_the_crime_slot(layout: Layout, num_suspects: int, num_murderers: int):
    room_ids = {room.id for room in layout.rooms}

    for seed in SEEDS:
        suspects, crime, places, later_rooms = case_after_crime_slot(layout, num_suspects, num_murderers, seed)

        # Assert that the people in 'later_rooms' are also in the 'suspects' tuple.
        assert set(later_rooms) == {VICTIM_ID} | {suspect.id for suspect in suspects}

        for rooms in later_rooms.values():
            assert isinstance(rooms, tuple)
            assert len(rooms) == len(TIME_SLOTS) - 1 - crime.slot       # Size of 'rooms' must be equal to the Time Slots remaining 'after' the Crime Slot.
            assert set(rooms) <= room_ids                               # Every Room assigned to every Person across all Time Slots is a Room of the House.

# Defining a Test Function to check that the Victim stays in the Crime Room after the Crime Slot (CG-3).
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_cg3_victim_stays_in_the_crime_room(layout: Layout, num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        suspects, crime, places, later_rooms = case_after_crime_slot(layout, num_suspects, num_murderers, seed)

        assert set(later_rooms[VICTIM_ID]) <= {crime.room_id}   # '<=' because the Crime Slot can be the last slot in 'TIME_SLOTS'.

# Defining a Test Function to check that, after the Crime Slot, no Innocent Suspect enters the Crime Room or passes through it (CG-18).
# Each of them stays among the Rooms they can walk to from their Place at the Crime Slot without the Crime Room.
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_cg18_no_innocent_enters_the_crime_room(layout: Layout, num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        suspects, crime, places, later_rooms = case_after_crime_slot(layout, num_suspects, num_murderers, seed)

        for suspect in suspects:
            if not suspect.is_murderer:
                reachable_room_ids = layout.reachable_rooms(places[suspect.id], crime.room_id)

                assert crime.room_id not in later_rooms[suspect.id]
                assert set(later_rooms[suspect.id]) <= reachable_room_ids

# Every (Layout, Crime Room) pair. The Crime Room decides which Rooms an Innocent Suspect can reach after the Crime Slot.
CRIME_ROOM_CASES = [
    pytest.param(layout, room.id, id = f"{layout.id}-{room.id}")
    for layout in ALL_LAYOUTS
    for room in layout.rooms
]

# Helper function to place one Murderer in the Crime Room and one Innocent Suspect in every other Room at the Crime Slot 1.
# With the Crime Slot 1, every Suspect has len(TIME_SLOTS) - 2 Time Slots left to move, which is one or more for 3 or more Time Slots.
def every_room_at_crime_slot_1(layout: Layout, crime_room_id: str) -> tuple[tuple[Suspect, ...], Crime, dict[str, str]]:
    murderer = Suspect(id = "murderer", is_murderer = True, is_red_herring = False)
    suspects = [murderer]
    places = {VICTIM_ID: crime_room_id, murderer.id: crime_room_id}

    for room in layout.rooms:
        if room.id != crime_room_id:
            innocent = Suspect(id = f"innocent_in_{room.id}", is_murderer = False, is_red_herring = False)
            suspects.append(innocent)
            places[innocent.id] = room.id

    crime = Crime(slot = 1, room_id = crime_room_id, window = tuple(range(WINDOW_LENGTH)))

    return tuple(suspects), crime, places

# Defining a Test Function to check that, over the Seeds, a Murderer can be in every Room at the Time Slot just after the Crime Slot.
# It also checks that each Innocent Suspect can be in every Room there that they can reach without passing through the Crime Room.
# That move is not limited to one Door (CG-15), and the Murderer may stay in the Crime Room.
@pytest.mark.skipif(len(TIME_SLOTS) < 3, reason = "The Night has no Time Slot after the Crime Slot 1.")
@pytest.mark.parametrize("layout, crime_room_id", CRIME_ROOM_CASES)
def test_moves_after_the_crime_slot_cover_every_room(layout: Layout, crime_room_id: str):
    suspects, crime, places = every_room_at_crime_slot_1(layout, crime_room_id)
    num_rooms = len(layout.rooms)

    all_rooms = set()
    picked_rooms = set()

    for suspect in suspects:
        if suspect.is_murderer:
            allowed_room_ids = {room.id for room in layout.rooms}
        else:
            allowed_room_ids = layout.reachable_rooms(places[suspect.id], crime_room_id)

        for room_id in allowed_room_ids:
            all_rooms.add((suspect.id, room_id))

    # A Suspect picks each of their allowed Rooms with the chance 1 / (Number of allowed Rooms), which is 1 / R or more.
    for seed in seeds_for_coverage(len(all_rooms), 1 / num_rooms):
        later_rooms = place_after_crime_slot(layout, suspects, places, crime, random.Random(seed))

        for suspect in suspects:
            picked_rooms.add((suspect.id, later_rooms[suspect.id][0]))

    assert picked_rooms == all_rooms

# Defining a Test Function to check that, over the Seeds, a Suspect can go between any two allowed Rooms after the Crime Slot.
# There are no Doors to follow after the Crime Slot (CG-15), so every pair of allowed Rooms is a possible move, and staying too.
# A move between two Time Slots after the Crime Slot 1 needs 2 or more of them, so the Night must have 4 or more Time Slots.
@pytest.mark.skipif(len(TIME_SLOTS) < 4, reason = "The Night is too short for two Time Slots after the Crime Slot 1.")
@pytest.mark.parametrize("layout, crime_room_id", CRIME_ROOM_CASES)
def test_moves_after_the_crime_slot_reach_any_allowed_room(layout: Layout, crime_room_id: str):
    suspects, crime, places = every_room_at_crime_slot_1(layout, crime_room_id)
    num_rooms = len(layout.rooms)

    all_moves = set()
    picked_moves = set()

    for suspect in suspects:
        if suspect.is_murderer:
            allowed_room_ids = {room.id for room in layout.rooms}
        else:
            allowed_room_ids = layout.reachable_rooms(places[suspect.id], crime_room_id)

        for from_room_id, to_room_id in itertools.product(allowed_room_ids, repeat = 2):
            all_moves.add((suspect.id, from_room_id, to_room_id))

    # A move is two draws in a row, so each one has the chance 1 / (Number of allowed Rooms) ** 2, which is 1 / R ** 2 or more.
    for seed in seeds_for_coverage(len(all_moves), 1 / num_rooms ** 2):
        later_rooms = place_after_crime_slot(layout, suspects, places, crime, random.Random(seed))

        for suspect in suspects:
            rooms = later_rooms[suspect.id]
            for time_slot in range(len(rooms) - 1):
                picked_moves.add((suspect.id, rooms[time_slot], rooms[time_slot + 1]))

    assert picked_moves == all_moves

# Defining a Test Function to check that, over the Seeds, two Murderers can stay together or split up after the Crime Slot (CG-19).
@pytest.mark.skipif(len(TIME_SLOTS) < 3, reason = "The Night has no Time Slot after the Crime Slot 1.")
@pytest.mark.parametrize("layout, crime_room_id", CRIME_ROOM_CASES)
def test_cg19_murderers_can_split_up_after_the_crime_slot(layout: Layout, crime_room_id: str):
    first_murderer = Suspect(id = "suspect_1", is_murderer = True, is_red_herring = False)
    second_murderer = Suspect(id = "suspect_2", is_murderer = True, is_red_herring = False)

    places = {VICTIM_ID: crime_room_id, first_murderer.id: crime_room_id, second_murderer.id: crime_room_id}
    crime = Crime(slot = 1, room_id = crime_room_id, window = tuple(range(WINDOW_LENGTH)))

    saw_together = False
    saw_apart = False

    # Just after the Crime Slot, the two Murderers share a Room with the chance 1 / R, and are apart with the chance (R - 1) / R.
    # So, we take the minimum of these chances to cover both scenarios.
    for seed in seeds_for_coverage(2, 1 / len(layout.rooms)):
        later_rooms = place_after_crime_slot(layout, (first_murderer, second_murderer), places, crime, random.Random(seed))

        if later_rooms[first_murderer.id][0] == later_rooms[second_murderer.id][0]:
            saw_together = True
        else:
            saw_apart = True

    assert saw_together
    assert saw_apart

# Defining a Test Function to check that a Crime Room outside the House is rejected, and so is a Suspect without a Place in the House.
# The Crime Room is checked with every Suspect and with the Murderer alone, so the error cannot come ONLY from an Innocent Suspect.
# Each Suspect is checked with a missing Place and with a Place outside the House, and the error must name that Suspect.
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = ALL_LAYOUT_IDS)
def test_place_after_crime_slot_rejects_a_place_outside_the_house(layout: Layout):
    suspects, crime, places = every_room_at_crime_slot_1(layout, layout.rooms[0].id)
    crime_outside = Crime(slot = 1, room_id = "attic", window = tuple(range(WINDOW_LENGTH)))

    with pytest.raises(ValueError):
        place_after_crime_slot(layout, suspects, places, crime_outside, random.Random(0))

    # The first Suspect of the helper is the Murderer.
    with pytest.raises(ValueError):
        place_after_crime_slot(layout, suspects[:1], places, crime_outside, random.Random(0))

    for suspect in suspects:
        places_without_suspect = dict(places)
        places_without_suspect.pop(suspect.id)

        places_outside = dict(places)
        places_outside[suspect.id] = "attic"

        with pytest.raises(ValueError, match = suspect.id):
            place_after_crime_slot(layout, suspects, places_without_suspect, crime, random.Random(0))

        with pytest.raises(ValueError, match = suspect.id):
            place_after_crime_slot(layout, suspects, places_outside, crime, random.Random(0))


# Helper function to build the Roles, the Crime and the Timeline Grid of a Case from one Seed.
def case_timeline(
    layout: Layout,
    num_suspects: int,
    num_murderers: int,
    seed: int
) -> tuple[tuple[Suspect, ...], Crime, TimelineGrid | None]:
    rng = random.Random(seed)
    suspects = pick_roles(num_suspects, num_murderers, rng)
    crime = pick_crime(layout, rng)
    grid = build_timeline(layout, suspects, crime, rng)

    return suspects, crime, grid

# Defining a Test Function to check that each Row of the Timeline Grid is the three parts of the Night, joined in order.
# It replays the Seed with the four steps one by one, in the same order and with the same Random Number Generator.
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_timeline_joins_the_three_parts_in_order(layout: Layout, num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        suspects, crime, grid = case_timeline(layout, num_suspects, num_murderers, seed)

        rng = random.Random(seed)
        pick_roles(num_suspects, num_murderers, rng)
        pick_crime(layout, rng)
        places = place_at_crime_slot(layout, suspects, crime, rng)
        sighting = pick_sighting(layout, suspects, places, crime, rng)

        # A Case where no Innocent Suspect can see the Victim alive is rejected (CG-16).
        if sighting is None:
            assert grid is None
            continue

        earlier_rooms = place_before_crime_slot(layout, places, crime, rng, sighting)
        later_rooms = place_after_crime_slot(layout, suspects, places, crime, rng)

        # The Rows come in the order of the IDs, the Victim first, so their order never gives away the Murderers.
        assert list(grid.locations) == [VICTIM_ID] + [suspect.id for suspect in suspects]

        for person_id, rooms in grid.locations.items():
            assert rooms == earlier_rooms[person_id] + (places[person_id],) + later_rooms[person_id]

# Defining a Test Function to check the Rules of where People can be on the whole Timeline Grid, Time Slot by Time Slot.
# a. Up to the Crime Slot, every Person stays in their Room or goes through a Door (CG-15).
# b. At the Crime Slot: ONLY the Victim and the Murderers are in the Crime Room (CG-4).
#    Innocent Suspects stand in groups of 2 or more, away from every Murderer (CG-5, CG-6).
# c. From the Crime Slot on, the Victim is in the Crime Room (CG-3), and no Innocent Suspect enters it or passes through it (CG-18).
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_timeline_keeps_the_rules_of_movement(layout: Layout, num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        suspects, crime, grid = case_timeline(layout, num_suspects, num_murderers, seed)

        # A rejected Case has no Timeline Grid to check.
        if grid is None:
            continue

        murderer_ids = {suspect.id for suspect in suspects if suspect.is_murderer}
        innocent_ids = {suspect.id for suspect in suspects if not suspect.is_murderer}

        # a. The moves up to the Crime Slot.
        for person_id in grid.locations:
            for time_slot in range(crime.slot):
                from_room_id = grid.room_of(person_id, time_slot)
                to_room_id = grid.room_of(person_id, time_slot + 1)

                assert to_room_id == from_room_id or to_room_id in layout.neighbors(from_room_id)

        # b. The Crime Slot.
        assert grid.roster(crime.room_id, crime.slot) == {VICTIM_ID} | murderer_ids

        for innocent_id in innocent_ids:
            roster = grid.roster(grid.room_of(innocent_id, crime.slot), crime.slot)

            assert not (roster & murderer_ids), "Roster contains a murderer!"
            assert len(roster & innocent_ids) >= 2, "Roster has fewer than 2 innocents."

        # c. The Time Slots from the Crime Slot to the end of the Night.
        for time_slot in range(crime.slot, len(TIME_SLOTS)):
            assert grid.room_of(VICTIM_ID, time_slot) == crime.room_id

        for innocent_id in innocent_ids:
            reachable_room_ids = layout.reachable_rooms(grid.room_of(innocent_id, crime.slot), crime.room_id)

            for time_slot in range(crime.slot + 1, len(TIME_SLOTS)):
                assert grid.room_of(innocent_id, time_slot) in reachable_room_ids


# Defining a Test Function to check 'find_witnesses' on every generated Case against the Room Rosters (CG-16, KN-3).
# Before the Crime Slot, every Innocent Suspect in the Roster of the Victim's Room saw the Victim alive at that Time Slot.
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_cg16_witnesses_match_the_rosters(layout: Layout, num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        suspects, crime, grid = case_timeline(layout, num_suspects, num_murderers, seed)

        # A rejected Case has no Timeline Grid to check.
        if grid is None:
            continue

        innocent_ids = {suspect.id for suspect in suspects if not suspect.is_murderer}
        expected_witnesses = {}

        for time_slot in range(crime.slot):
            for person_id in grid.roster(grid.room_of(VICTIM_ID, time_slot), time_slot):
                if person_id in innocent_ids:
                    expected_witnesses[person_id] = expected_witnesses.get(person_id, ()) + (time_slot,)

        assert find_witnesses(grid, suspects, crime) == expected_witnesses

# Every (Crime Slot, Time Slot of the sighting) pair of the Night. The sighting counts ONLY before the Crime Slot.
SIGHTING_CASES = [
    pytest.param(crime_slot, sighting_slot, id = f"Crime-{crime_slot}-Sighting-{sighting_slot}")
    for crime_slot in range(1, len(TIME_SLOTS))
    for sighting_slot in range(len(TIME_SLOTS))
]

# Defining a Test Function to check that a meeting with the Victim makes a Witness ONLY before the Crime Slot (CG-16).
# The Innocent Suspect meets the Victim at one Time Slot. The Murderer is with the Victim all Night, and is never a Witness.
@pytest.mark.parametrize("crime_slot, sighting_slot", SIGHTING_CASES)
def test_cg16_witnesses_saw_the_victim_before_the_crime_slot(crime_slot: int, sighting_slot: int):
    murderer = Suspect(id = "suspect_1", is_murderer = True, is_red_herring = False)
    innocent = Suspect(id = "suspect_2", is_murderer = False, is_red_herring = False)
    innocent_rooms = []

    for time_slot in range(len(TIME_SLOTS)):
        if time_slot == sighting_slot:
            innocent_rooms.append("hall")
        else:
            innocent_rooms.append("study")

    grid = TimelineGrid(locations = {
        VICTIM_ID: ("hall",) * len(TIME_SLOTS),
        murderer.id: ("hall",) * len(TIME_SLOTS),
        innocent.id: tuple(innocent_rooms),
    })
    crime = Crime(slot = crime_slot, room_id = "hall", window = ALLOWED_WINDOWS[crime_slot][0])

    if sighting_slot < crime_slot:
        assert find_witnesses(grid, (murderer, innocent), crime) == {innocent.id: (sighting_slot,)}
    else:
        assert find_witnesses(grid, (murderer, innocent), crime) == {}


# Helper function to build the Case up to the Crime Slot from one Seed, and then pick its Sighting.
def case_sighting(
    layout: Layout,
    num_suspects: int,
    num_murderers: int,
    seed: int
) -> tuple[tuple[Suspect, ...], Crime, dict[str, str], Sighting | None]:
    rng = random.Random(seed)
    suspects = pick_roles(num_suspects, num_murderers, rng)
    crime = pick_crime(layout, rng)
    places = place_at_crime_slot(layout, suspects, crime, rng)
    sighting = pick_sighting(layout, suspects, places, crime, rng)

    return suspects, crime, places, sighting

# Defining a Test Function to check that a picked Sighting can really happen (CG-15, CG-16).
# The Witness is an Innocent Suspect, the Sighting is before the Crime Slot, and both the Victim and the Witness reach their Places in time.
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_cg16_sighting_can_happen_in_time(layout: Layout, num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        suspects, crime, places, sighting = case_sighting(layout, num_suspects, num_murderers, seed)

        if sighting is not None:
            innocent_ids = {suspect.id for suspect in suspects if not suspect.is_murderer}
            slots_left = crime.slot - sighting.time_slot

            assert sighting.witness_id in innocent_ids
            assert 0 <= sighting.time_slot < crime.slot

            # Asserts that the distances from the Sighting Room to the Crime Room and the Suspect's Crime Slot Room is <= Remaining Time.
            assert layout.distances_from(sighting.room_id)[crime.room_id] <= slots_left
            assert layout.distances_from(sighting.room_id)[places[sighting.witness_id]] <= slots_left

# Defining a Test Function to check that a Sighting is missing ONLY when no Innocent Suspect can meet the Victim in time (CG-16).
# Two People can meet before the Crime Slot exactly when their Places are at most (2 x Crime Slot) Doors apart.
# Each of them walks back at most one Door per Time Slot, so they can close that gap from both sides.
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_cg16_sighting_is_missing_only_when_no_one_can_meet_the_victim(layout: Layout, num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        suspects, crime, places, sighting = case_sighting(layout, num_suspects, num_murderers, seed)
        distance_from_crime_room = layout.distances_from(crime.room_id)

        someone_can_meet = False
        for suspect in suspects:
            if not suspect.is_murderer and distance_from_crime_room[places[suspect.id]] <= 2 * crime.slot:
                someone_can_meet = True
                break

        assert (sighting is not None) == someone_can_meet

# Defining a Test Function to check that, over the Seeds, every possible Sighting can be picked.
# Every Room but the Crime Room holds one Innocent Suspect at the Crime Slot 1, so every Sighting is at Time Slot 0, with the same chance.
@pytest.mark.parametrize("layout, crime_room_id", CRIME_ROOM_CASES)
def test_cg16_sightings_cover_every_meeting(layout: Layout, crime_room_id: str):
    suspects, crime, places = every_room_at_crime_slot_1(layout, crime_room_id)

    all_sightings = set()
    picked_sightings = set()

    # A meeting at Time Slot 0 leaves one Time Slot, so the Room must be at most one Door from both Places.
    for suspect in suspects:
        if not suspect.is_murderer:
            for room in layout.rooms:
                near_crime_room = room.id == crime_room_id or room.id in layout.neighbors(crime_room_id)
                near_place = room.id == places[suspect.id] or room.id in layout.neighbors(places[suspect.id])

                if near_crime_room and near_place:
                    all_sightings.add(Sighting(witness_id = suspect.id, time_slot = 0, room_id = room.id))

    # One Sighting is picked from all of them, each with the chance 1 / (Number of possible Sightings).
    for seed in seeds_for_coverage(len(all_sightings), 1 / len(all_sightings)):
        picked_sightings.add(pick_sighting(layout, suspects, places, crime, random.Random(seed)))

    assert picked_sightings == all_sightings


# Helper function to build the Case up to the Crime Slot from one Seed, pick its Sighting, and then walk every Person back to it.
def case_before_sighting(
    layout: Layout,
    num_suspects: int,
    num_murderers: int,
    seed: int
) -> tuple[Crime, dict[str, str], Sighting | None, dict[str, tuple[str, ...]]]:
    rng = random.Random(seed)
    suspects = pick_roles(num_suspects, num_murderers, rng)
    crime = pick_crime(layout, rng)
    places = place_at_crime_slot(layout, suspects, crime, rng)
    sighting = pick_sighting(layout, suspects, places, crime, rng)
    earlier_rooms = place_before_crime_slot(layout, places, crime, rng, sighting)

    return crime, places, sighting, earlier_rooms

# Defining a Test Function to check that the Victim and the Witness are both in the Sighting Room at the Sighting Time Slot (CG-16).
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_cg16_victim_and_witness_meet_at_the_sighting(layout: Layout, num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        crime, places, sighting, earlier_rooms = case_before_sighting(layout, num_suspects, num_murderers, seed)

        if sighting is not None:
            assert earlier_rooms[VICTIM_ID][sighting.time_slot] == sighting.room_id
            assert earlier_rooms[sighting.witness_id][sighting.time_slot] == sighting.room_id

# Defining a Test Function to check that, with a Sighting, every Person still walks through the Doors up to the Crime Slot (CG-15).
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_cg15_walks_to_the_sighting_use_the_doors(layout: Layout, num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        crime, places, sighting, earlier_rooms = case_before_sighting(layout, num_suspects, num_murderers, seed)

        for person_id, rooms in earlier_rooms.items():
            walk = rooms + (places[person_id],)

            assert len(rooms) == crime.slot

            for time_slot in range(crime.slot):
                assert walk[time_slot + 1] == walk[time_slot] or walk[time_slot + 1] in layout.neighbors(walk[time_slot])

# Defining a Test Function to check that a Sighting that cannot happen in this Case is rejected.
# a. A Witness who is the Victim or has no Place, and a Sighting before the Night or at the Crime Slot.
# b. A Sighting Room too far for the Witness, or too far for the Victim, at the Crime Slot 1.
@pytest.mark.parametrize("layout, crime_room_id", CRIME_ROOM_CASES)
def test_place_before_crime_slot_rejects_an_impossible_sighting(layout: Layout, crime_room_id: str):
    suspects, crime, places = every_room_at_crime_slot_1(layout, crime_room_id)
    innocent_ids = [suspect.id for suspect in suspects if not suspect.is_murderer]

    unknown_witness = Sighting(witness_id = "suspect_99", time_slot = 0, room_id = crime_room_id)
    victim_as_witness = Sighting(witness_id = VICTIM_ID, time_slot = 0, room_id = crime_room_id)

    # The Murderer is in the Crime Room with the Victim, so ONLY the Time Slot of these two Sightings is wrong.
    before_the_night = Sighting(witness_id = "murderer", time_slot = -1, room_id = crime_room_id)
    at_the_crime_slot = Sighting(witness_id = "murderer", time_slot = crime.slot, room_id = crime_room_id)

    for impossible_sighting in [unknown_witness, victim_as_witness, before_the_night, at_the_crime_slot]:
        with pytest.raises(ValueError):
            place_before_crime_slot(layout, places, crime, random.Random(0), impossible_sighting)

    # The Victim waits in the Crime Room, so a Sighting in the Place of an Innocent Suspect far from it is too far for the Victim.
    distance_from_crime_room = layout.distances_from(crime_room_id)

    for innocent_id in innocent_ids:
        if distance_from_crime_room[places[innocent_id]] > 1:
            too_far_for_the_victim = Sighting(witness_id = innocent_id, time_slot = 0, room_id = places[innocent_id])

            with pytest.raises(ValueError):
                place_before_crime_slot(layout, places, crime, random.Random(0), too_far_for_the_victim)

    # The Witness waits in their Place, so a Room two or more Doors from it is too far for the Witness.
    for innocent_id in innocent_ids:
        distance_from_place = layout.distances_from(places[innocent_id])

        for room in layout.rooms:
            if distance_from_place[room.id] > 1:
                too_far_for_the_witness = Sighting(witness_id = innocent_id, time_slot = 0, room_id = room.id)

                with pytest.raises(ValueError):
                    place_before_crime_slot(layout, places, crime, random.Random(0), too_far_for_the_witness)


# Defining a Test Function to check that every Timeline Grid has one or more Witnesses who saw the Victim alive (CG-16).
# It also checks that at most a quarter of the Seeds are rejected for lack of a possible Witness.
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_cg16_every_timeline_has_a_witness(layout: Layout, num_suspects: int, num_murderers: int):
    num_rejected = 0

    for seed in SEEDS:
        suspects, crime, grid = case_timeline(layout, num_suspects, num_murderers, seed)

        if grid is None:
            num_rejected += 1
        else:
            assert find_witnesses(grid, suspects, crime) != {}

    assert num_rejected <= len(SEEDS) // 4, f"{num_rejected} of {len(SEEDS)} Seeds were rejected."


# Defining a Test Function to check that every Crime Room has late Crime Slots at which no Case is ever rejected (CG-16).
# The farthest Room is D Doors from the Crime Room. By the Crime Slot C, the Victim and a Witness can close 2 x C Doors between them.
# So from the Crime Slot ceil(D / 2) on, any Innocent Suspect can meet the Victim, and the last Crime Slot of the Night must be one of them.
@pytest.mark.parametrize("layout, crime_room_id", CRIME_ROOM_CASES)
def test_cg16_late_crime_slots_always_have_a_sighting(layout: Layout, crime_room_id: str):
    farthest_distance = max(layout.distances_from(crime_room_id).values())
    first_safe_slot = math.ceil(farthest_distance / 2)

    assert first_safe_slot <= len(TIME_SLOTS) - 1, \
        f"A Room of Layout '{layout.id}' is {farthest_distance} Doors from the Crime Room, too far for the Night."

    murderer = Suspect(id = "murderer", is_murderer = True, is_red_herring = False)
    innocent = Suspect(id = "innocent", is_murderer = False, is_red_herring = False)

    for crime_slot in range(first_safe_slot, len(TIME_SLOTS)):
        crime = Crime(slot = crime_slot, room_id = crime_room_id, window = ALLOWED_WINDOWS[crime_slot][0])

        # The Innocent Suspect stands in each Room but the Crime Room in turn, so the farthest Room is tried too.
        for room in layout.rooms:
            if room.id != crime_room_id:
                places = {VICTIM_ID: crime_room_id, murderer.id: crime_room_id, innocent.id: room.id}

                assert pick_sighting(layout, (murderer, innocent), places, crime, random.Random(0)) is not None

# Defining a Test Function to check that an early Crime has no Sighting when every Innocent Suspect stands too far away (CG-16).
# At the Crime Slot 1, a Witness more than 2 Doors from the Crime Room cannot meet the Victim in time, so the Case is rejected.
@pytest.mark.parametrize("layout, crime_room_id", CRIME_ROOM_CASES)
def test_cg16_an_early_crime_far_from_everyone_has_no_sighting(layout: Layout, crime_room_id: str):
    distance_from_crime_room = layout.distances_from(crime_room_id)
    murderer = Suspect(id = "murderer", is_murderer = True, is_red_herring = False)
    suspects = [murderer]
    places = {VICTIM_ID: crime_room_id, murderer.id: crime_room_id}
    crime = Crime(slot = 1, room_id = crime_room_id, window = ALLOWED_WINDOWS[1][0])

    # One Innocent Suspect in every Room more than 2 Doors from the Crime Room.
    for room in layout.rooms:
        if distance_from_crime_room[room.id] > 2:
            innocent = Suspect(id = f"innocent_in_{room.id}", is_murderer = False, is_red_herring = False)
            suspects.append(innocent)
            places[innocent.id] = room.id

    assert pick_sighting(layout, tuple(suspects), places, crime, random.Random(0)) is None


# Helper function to build the Case of one Seed step by step, the same way 'generate_case' does. The Grid is None for a rejected Seed.
def case_of_seed(
    num_suspects: int,
    num_murderers: int,
    seed: int
) -> tuple[Layout, tuple[Suspect, ...], Crime, TimelineGrid | None]:
    rng = random.Random(seed)
    layout = pick_layout(num_suspects, rng)
    suspects = pick_roles(num_suspects, num_murderers, rng)
    crime = pick_crime(layout, rng)
    grid = build_timeline(layout, suspects, crime, rng)

    return layout, suspects, crime, grid

# Defining a Test Function to check that 'generate_case' returns the Case of the first Seed that is not rejected (CG-12).
# Every Seed before it, from 'first_seed' on, must be rejected, and the Case must be exactly the Case of its own Seed.
# 'generate_case' and 'case_of_seed' build each Case on their own, so they agree ONLY if every step gives the same result for the same Seed (CG-1).
@pytest.mark.parametrize("num_suspects, num_murderers", ROLE_COUNTS)
def test_cg12_generate_case_takes_the_first_accepted_seed(num_suspects: int, num_murderers: int):
    for first_seed in SEEDS:
        case = generate_case(num_suspects, num_murderers, first_seed)

        assert case is not None
        assert case.grid is not None
        assert first_seed <= case.seed < first_seed + MAX_SEEDS_PER_CASE

        for seed in range(first_seed, case.seed):
            layout, suspects, crime, grid = case_of_seed(num_suspects, num_murderers, seed)

            assert grid is None

        assert case_of_seed(num_suspects, num_murderers, case.seed) == (case.layout, case.suspects, case.crime, case.grid)

# Defining a Test Function to check that 'generate_case' tries MAX_SEEDS_PER_CASE Seeds, and then gives up (CG-12).
# For this test ONLY, 'monkeypatch' swaps 'build_timeline' for a stand-in that rejects every Case and counts its calls.
@pytest.mark.parametrize("num_suspects, num_murderers", ROLE_COUNTS)
def test_cg12_generate_case_gives_up_after_the_last_seed(monkeypatch, num_suspects: int, num_murderers: int):
    rejected_crimes = []

    # A stand-in for 'build_timeline' that rejects every Case.
    def reject_every_case(layout: Layout, suspects: tuple[Suspect, ...], crime: Crime, rng: random.Random) -> None:
        rejected_crimes.append(crime)

        return None

    monkeypatch.setattr(generator, "build_timeline", reject_every_case)

    assert generate_case(num_suspects, num_murderers, 0) is None
    assert len(rejected_crimes) == MAX_SEEDS_PER_CASE

# Defining a Test Function to check that the Case Generator tries at most 200 Seeds for one Case, as CG-12 says.
def test_cg12_max_seeds_matches_the_spec():
    assert MAX_SEEDS_PER_CASE == 200

# Defining a Test Function to check that 'generate_case' rejects a negative first Seed.
@pytest.mark.parametrize("num_suspects, num_murderers", ROLE_COUNTS)
def test_generate_case_rejects_a_negative_seed(num_suspects: int, num_murderers: int):
    with pytest.raises(ValueError):
        generate_case(num_suspects, num_murderers, -1)
