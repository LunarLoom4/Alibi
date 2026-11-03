import math


# Smallest and largest Number of Suspects that a Case can have.
MIN_SUSPECTS = 5
MAX_SUSPECTS = 10

# Largest Number of Murderers and of Red Herrings in any Case.
MAX_MURDERERS = 3
MAX_RED_HERRINGS = 3


# Helper function to reject a Number of Suspects outside the allowed range.
def check_num_suspects(num_suspects: int) -> None:
    if num_suspects < MIN_SUSPECTS or num_suspects > MAX_SUSPECTS:
        raise ValueError(f"A Case needs {MIN_SUSPECTS} to {MAX_SUSPECTS} Suspects, not {num_suspects}.")

# Number of Rooms in the House: 3 + ceil(S / 2) (CG-2).
def count_rooms(num_suspects: int) -> int:
    check_num_suspects(num_suspects)

    return 3 + math.ceil(num_suspects / 2)

# Number of Rounds in a Game Session: 3 + floor((S - 5) / 2) (RD-1).
def count_rounds(num_suspects: int) -> int:
    check_num_suspects(num_suspects)

    return 3 + (num_suspects - MIN_SUSPECTS) // 2

# Largest Number of Murderers that keeps the Innocent Suspects in the majority.
def max_murderers(num_suspects: int) -> int:
    check_num_suspects(num_suspects)

    # Innocents (S - M) must be 3 or more, AND more than the Murderers, which means M < S / 2.
    return min(MAX_MURDERERS, num_suspects - 3, (num_suspects - 1) // 2)

# Largest Number of Red Herrings: 1 to 3, and fewer than the Innocent Suspects.
def max_red_herrings(num_suspects: int, num_murderers: int) -> int:
    allowed_murderers = max_murderers(num_suspects)

    # Reject a Number of Murderers that this Number of Suspects does not allow.
    if num_murderers < 1 or num_murderers > allowed_murderers:
        raise ValueError(
            f"A Case with {num_suspects} Suspects allows 1 to {allowed_murderers} Murderers, not {num_murderers}."
        )

    num_innocents = num_suspects - num_murderers

    return min(MAX_RED_HERRINGS, num_innocents - 1)
