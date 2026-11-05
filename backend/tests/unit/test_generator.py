import math
import random
import pytest

from alibi.domain.generator import pick_layout, pick_roles, pick_crime
from alibi.domain.layouts import Layout, LAYOUTS
from alibi.domain.parameters import MIN_SUSPECTS, MAX_SUSPECTS, count_rooms, max_murderers, max_red_herrings
from alibi.domain.types import TIME_SLOTS


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

        # Asserts that the chance of missing any outcome is below MISS_CHANCE
        assert num_outcomes * (1 - smallest_chance) ** num_seeds <= MISS_CHANCE

        # Asserts that more outcomes get more Seeds
        assert len(seeds_for_coverage(num_outcomes + 1, smallest_chance)) >= num_seeds

        # Asserts that rarer outcomes (who have smaller chances) get more Seeds than frequent outcomes
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

# Every allowed Time-of-death Window for each Crime Slot, written by hand as in 'test_types.py' (CG-13, CG-16).
ALLOWED_WINDOWS = {
    1: [(0, 1, 2), (1, 2, 3)],
    2: [(0, 1, 2), (1, 2, 3), (2, 3, 4)],
    3: [(1, 2, 3), (2, 3, 4), (3, 4, 5)],
    4: [(2, 3, 4), (3, 4, 5)],
    5: [(3, 4, 5)],
}

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
    room_ids = {room.id for room in layout.rooms}
    all_windows = set()
    picked_room_ids = set()
    picked_windows = set()

    for crime_slot, windows in ALLOWED_WINDOWS.items():
        for window in windows:
            all_windows.add((crime_slot, window))

    # Each Room has the chance 1 / R. The rarest (Crime Slot, Window) pair has the chance 1 / 5 * 1 / 3.
    room_seeds = seeds_for_coverage(len(room_ids), 1 / len(room_ids))
    window_seeds = seeds_for_coverage(len(all_windows), 1 / (len(TIME_SLOTS) - 1) / 3)

    for seed in range(max(len(room_seeds), len(window_seeds))):
        crime = pick_crime(layout, random.Random(seed))

        picked_room_ids.add(crime.room_id)
        picked_windows.add((crime.slot, crime.window))

    assert picked_room_ids == room_ids
    assert picked_windows == all_windows

# Defining a Test Function to check that the same Seed always picks the same Crime (CG-1).
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = ALL_LAYOUT_IDS)
def test_cg1_same_seed_picks_the_same_crime(layout: Layout):
    for seed in SEEDS:
        assert pick_crime(layout, random.Random(seed)) == pick_crime(layout, random.Random(seed))
