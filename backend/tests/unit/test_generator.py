import random
import pytest

from alibi.domain.generator import pick_layout
from alibi.domain.layouts import LAYOUTS
from alibi.domain.parameters import MIN_SUSPECTS, MAX_SUSPECTS, count_rooms


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
