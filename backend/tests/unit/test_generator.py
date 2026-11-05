import random
import pytest

from alibi.domain.generator import pick_layout, pick_roles
from alibi.domain.layouts import LAYOUTS
from alibi.domain.parameters import MIN_SUSPECTS, MAX_SUSPECTS, count_rooms, max_murderers, max_red_herrings


# Every allowed Number of Suspects. The tests below run once for each of them.
SUSPECT_COUNTS = range(MIN_SUSPECTS, MAX_SUSPECTS + 1)

# The Seeds that each test tries. A fixed set, so a failure can always be run again.
SEEDS = range(200)


# Defining a Test Function to check that the picked House has the Number of Rooms that CG-2 gives, and comes from LAYOUTS.
@pytest.mark.parametrize("num_suspects", SUSPECT_COUNTS)
def test_cg2_layout_has_the_rooms_for_the_suspects(num_suspects: int):
    num_rooms = count_rooms(num_suspects)

    for seed in SEEDS:
        layout = pick_layout(num_suspects, random.Random(seed))

        assert len(layout.rooms) == num_rooms
        assert layout in LAYOUTS[num_rooms]

# Defining a Test Function to check that every Layout with the Number of Rooms for this Number of Suspects gets picked over the Seeds (CG-2).
@pytest.mark.parametrize("num_suspects", SUSPECT_COUNTS)
def test_cg2_every_layout_can_be_picked(num_suspects: int):
    picked_ids = set()

    for seed in SEEDS:
        picked_ids.add(pick_layout(num_suspects, random.Random(seed)).id)

    assert picked_ids == {layout.id for layout in LAYOUTS[count_rooms(num_suspects)]}

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
    murderer_ids = set()
    red_herring_ids = set()
    red_herring_counts = set()

    for seed in SEEDS:
        suspects = pick_roles(num_suspects, num_murderers, random.Random(seed))

        murderer_ids.update(suspect.id for suspect in suspects if suspect.is_murderer)
        red_herring_ids.update(suspect.id for suspect in suspects if suspect.is_red_herring)
        red_herring_counts.add(len([suspect for suspect in suspects if suspect.is_red_herring]))

    assert murderer_ids == all_ids
    assert red_herring_ids == all_ids
    assert red_herring_counts == set(range(1, max_red_herrings(num_suspects, num_murderers) + 1))

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
