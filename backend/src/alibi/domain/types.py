from dataclasses import dataclass


# The 6 Time Slots of the Night, every 30 minutes from 20:00 to 22:30.
# A Time Slot is referred to by its index in this tuple: 0 is 20:00, 5 is 22:30.
TIME_SLOTS = ("20:00", "20:30", "21:00", "21:30", "22:00", "22:30")


# Defining a Room of the House: Its ID, its display Name, and its Rectangle on the Floor Plan in meters.
@dataclass(frozen = True)
class Room:
    id: str
    name: str
    x_min: float
    x_max: float
    y_min: float
    y_max: float


# The ID of the Victim in the Timeline Grid. No 'Suspect' can have this ID.
VICTIM_ID = "victim"

# Defining a Suspect of the Case: Their ID and the Role that the Case Generator gives them.
# The LLM writes the Name later (CG-8), so the Rules need ONLY the ID and the Role.
@dataclass(frozen = True)
class Suspect:
    id: str
    is_murderer: bool
    is_red_herring: bool

    # Reject a Suspect that the Rules do not allow.
    def __post_init__(self):
        # 1. The Victim's ID keeps the Victim apart from every Suspect in the Timeline Grid.
        if self.id == VICTIM_ID:
            raise ValueError(f"A Suspect cannot have the ID '{VICTIM_ID}', which belongs to the Victim.")

        # 2. A Red Herring is an Innocent Suspect who ONLY looks guilty, so they are never a Murderer.
        if self.is_murderer and self.is_red_herring:
            raise ValueError(f"Suspect '{self.id}' cannot be a Murderer AND a Red Herring.")

