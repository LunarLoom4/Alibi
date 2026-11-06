import os
import subprocess
import sys
import math
import random
import pytest
import itertools

import alibi
from alibi.domain.generator import pick_layout, pick_roles, pick_crime, place_at_crime_slot, place_before_crime_slot
from alibi.domain.layouts import Layout, LAYOUTS
from alibi.domain.parameters import MIN_SUSPECTS, MAX_SUSPECTS, count_rooms, max_murderers, max_red_herrings
from alibi.domain.types import Crime, Suspect, TIME_SLOTS, VICTIM_ID, WINDOW_LENGTH


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

# Defining a Test Function to check that the same Seed always picks the same House (CG-1).
@pytest.mark.parametrize("num_suspects", SUSPECT_COUNTS)
def test_cg1_same_seed_picks_the_same_layout(num_suspects: int):
    for seed in SEEDS:
        assert pick_layout(num_suspects, random.Random(seed)) == pick_layout(num_suspects, random.Random(seed))

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

# Defining a Test Function to check that the same Seed always gives the same Roles (CG-1).
@pytest.mark.parametrize("num_suspects, num_murderers", ROLE_COUNTS)
def test_cg1_same_seed_gives_the_same_roles(num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        first_roles = pick_roles(num_suspects, num_murderers, random.Random(seed))
        second_roles = pick_roles(num_suspects, num_murderers, random.Random(seed))

        assert first_roles == second_roles

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

# Defining a Test Function to check that the same Seed always picks the same Crime (CG-1).
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = ALL_LAYOUT_IDS)
def test_cg1_same_seed_picks_the_same_crime(layout: Layout):
    for seed in SEEDS:
        assert pick_crime(layout, random.Random(seed)) == pick_crime(layout, random.Random(seed))


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

# Defining a Test Function to check that the same Seed always places every Person in the same Room (CG-1).
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_cg1_same_seed_gives_the_same_places(layout: Layout, num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        first_case = case_at_crime_slot(layout, num_suspects, num_murderers, seed)
        second_case = case_at_crime_slot(layout, num_suspects, num_murderers, seed)

        assert first_case == second_case

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

        assert set(earlier_rooms) == set(places)

        for rooms in earlier_rooms.values():
            assert isinstance(rooms, tuple)
            assert len(rooms) == crime.slot
            assert set(rooms) <= room_ids

# Defining a Test Function to check that, up to the Crime Slot, every Person stays in their Room or goes through a Door (CG-15).
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

    # The step back from a Room with D Doors picks one of (D + 1) choices, so the rarest move has the chance 1 / (largest D + 1).
    largest_doors = max(len(layout.neighbors(room.id)) for room in layout.rooms)

    for seed in seeds_for_coverage(len(all_moves), 1 / (largest_doors + 1)):
        earlier_rooms = place_before_crime_slot(layout, places, crime, random.Random(seed))

        for person_id, rooms in earlier_rooms.items():
            picked_moves.add((rooms[0], places[person_id]))

    assert picked_moves == all_moves

# Defining a Test Function to check that the same Seed always gives every Person the same Rooms before the Crime Slot (CG-1).
@pytest.mark.parametrize("layout, num_suspects, num_murderers", PLACEMENT_CASES)
def test_cg1_same_seed_gives_the_same_rooms_before_the_crime_slot(layout: Layout, num_suspects: int, num_murderers: int):
    for seed in SEEDS:
        first_case = case_before_crime_slot(layout, num_suspects, num_murderers, seed)
        second_case = case_before_crime_slot(layout, num_suspects, num_murderers, seed)

        assert first_case == second_case

# Defining a Test Function to check that a Place outside the House is rejected.
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = ALL_LAYOUT_IDS)
def test_place_before_crime_slot_rejects_a_place_outside_the_house(layout: Layout):
    places = {VICTIM_ID: layout.rooms[0].id, "suspect_1": "attic"}
    crime = Crime(slot = 1, room_id = layout.rooms[0].id, window = tuple(range(WINDOW_LENGTH)))

    with pytest.raises(ValueError):
        place_before_crime_slot(layout, places, crime, random.Random(0))


# Python code that a new Python process runs: It prints the Places and the Rooms before the Crime Slot.
# It does so for every allowed (Layout, Suspects, Murderers).
# A few Seeds are enough, because a choice that follows the order of a set changes the Case within the first few of them.
CASE_SCRIPT = """
import random

from alibi.domain.generator import pick_crime, pick_roles, place_at_crime_slot, place_before_crime_slot
from alibi.domain.layouts import LAYOUTS
from alibi.domain.parameters import MIN_SUSPECTS, MAX_SUSPECTS, count_rooms, max_murderers

for num_suspects in range(MIN_SUSPECTS, MAX_SUSPECTS + 1):
    for num_murderers in range(1, max_murderers(num_suspects) + 1):
        for layout in LAYOUTS[count_rooms(num_suspects)]:
            for seed in range(10):
                rng = random.Random(seed)
                suspects = pick_roles(num_suspects, num_murderers, rng)
                crime = pick_crime(layout, rng)
                places = place_at_crime_slot(layout, suspects, crime, rng)
                earlier_rooms = place_before_crime_slot(layout, places, crime, rng)

                print(sorted(places.items()), sorted(earlier_rooms.items()))
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
