import pytest
from dataclasses import FrozenInstanceError

from alibi.domain.types import Suspect, VICTIM_ID


# Every Role that a Suspect can be given, whether the Rules allow it or not.
ROLE_CASES = [
    pytest.param(False, False, True,  id = "Innocent"),
    pytest.param(False, True,  True,  id = "Innocent Red Herring"),
    pytest.param(True,  False, True,  id = "Murderer"),
    pytest.param(True,  True,  False, id = "Murderer AND Red Herring"),
]

# Defining a Test Function to check that a Suspect is created ONLY with a Role that the Rules allow.
@pytest.mark.parametrize("is_murderer, is_red_herring, allowed", ROLE_CASES)
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
