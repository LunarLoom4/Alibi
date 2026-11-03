import pytest
from alibi.domain.parameters import count_rooms, count_rounds, max_murderers, max_red_herrings


# Values from the table 'Values for each number of suspects' in Section 3 of the Spec.
# Each dictionary maps the Number of Suspects to the expected value.
SPEC_ROOMS = {5: 6, 6: 6, 7: 7, 8: 7, 9: 8, 10: 8}
SPEC_ROUNDS = {5: 3, 6: 3, 7: 4, 8: 4, 9: 5, 10: 5}
SPEC_MAX_MURDERERS = {5: 2, 6: 2, 7: 3, 8: 3, 9: 3, 10: 3}


# Defining a Test Function to check the Number of Rooms against the Spec table (CG-2).
@pytest.mark.parametrize("num_suspects, rooms", SPEC_ROOMS.items())
def test_cg2_room_count_matches_spec(num_suspects, rooms):
    assert count_rooms(num_suspects) == rooms

# Defining a Test Function to check the Number of Rounds against the Spec table (RD-1).
@pytest.mark.parametrize("num_suspects, rounds", SPEC_ROUNDS.items())
def test_rd1_round_count_matches_spec(num_suspects, rounds):
    assert count_rounds(num_suspects) == rounds

# Defining a Test Function to check the largest Number of Murderers against the Spec table.
@pytest.mark.parametrize("num_suspects, murderers", SPEC_MAX_MURDERERS.items())
def test_max_murderers_matches_spec(num_suspects, murderers):
    assert max_murderers(num_suspects) == murderers

# Defining a Test Function to check that the Red Herrings stay fewer than the Innocent Suspects.
@pytest.mark.parametrize("num_suspects, num_murderers, red_herrings", [(5, 2, 2), (6, 2, 3), (10, 1, 3)])
def test_max_red_herrings_stays_below_innocents(num_suspects, num_murderers, red_herrings):
    assert max_red_herrings(num_suspects, num_murderers) == red_herrings


# Defining a Test Function to check that a Number of Suspects outside 5 to 10 is rejected.
@pytest.mark.parametrize("num_suspects", [4, 11])
def test_num_suspects_outside_range_is_rejected(num_suspects):
    with pytest.raises(ValueError):
        count_rooms(num_suspects)

# Defining a Test Function to check that a Number of Murderers the Case does not allow is rejected.
@pytest.mark.parametrize("num_suspects, num_murderers", [(5, 0), (5, 3)])
def test_disallowed_murderer_count_is_rejected(num_suspects, num_murderers):
    with pytest.raises(ValueError):
        max_red_herrings(num_suspects, num_murderers)
