from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping


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


# Defining the Timeline Grid of a Case: The Room of every Person, the Suspects and the Victim, at every Time Slot.
# Each Person has exactly one Room ID for each Time Slot, so nobody is in two Rooms at once (CG-3).
# The Grid is the Ground Truth, so it keeps a read-only copy of its Rows and can never change after it is made.
@dataclass(frozen = True)
class TimelineGrid:
    locations: Mapping[str, tuple[str, ...]]

    # Check the Rows, then keep a read-only copy of them.
    # '__post_init__' is run just after '__init__' by Python automatically.
    def __post_init__(self):
        # 1. Every Case has a Victim, so the Grid always has a Row for them.
        if VICTIM_ID not in self.locations:
            raise ValueError("The Timeline Grid has no Row for the Victim.")

        # 2. Every Row is a tuple, which cannot change, with one Room ID for each Time Slot.
        for person_id, rooms in self.locations.items():
            if not isinstance(rooms, tuple):
                raise TypeError(f"The Row of '{person_id}' must be a tuple of Room IDs.")

            if len(rooms) != len(TIME_SLOTS):
                raise ValueError(f"'{person_id}' needs exactly {len(TIME_SLOTS)} Room IDs, one for each Time Slot, but has {len(rooms)} instead.")

        # 3. Keep a read-only copy, so a later change to the caller's dictionary never reaches the Grid.
        # A frozen dataclass blocks a normal assignment even inside '__post_init__', so 'object.__setattr__' is used to set the field (A valid Bypass).
        object.__setattr__(self, "locations", MappingProxyType(dict(self.locations)))

    # Returns the ID of the Room where the given Person is at the given Time Slot.
    def room_of(self, person_id: str, time_slot: int) -> str:
        # A Person outside the Grid has no Row to read.
        if person_id not in self.locations:
            raise ValueError(f"'{person_id}' is not in the Timeline Grid.")

        # A negative index would silently read from the end of the Row, so ONLY Time Slots from 0 to the last one are allowed.
        if time_slot < 0 or time_slot >= len(TIME_SLOTS):
            raise ValueError(f"Time Slot {time_slot} does not exist. Time Slots go from 0 to {len(TIME_SLOTS) - 1}.")

        return self.locations[person_id][time_slot]

    # Returns the IDs of every Person in the given Room at the given Time Slot: The Room Roster (KN-3).
    def roster(self, room_id: str, time_slot: int) -> set[str]:
        result = set()

        for person_id in self.locations:
            if self.room_of(person_id, time_slot) == room_id:
                result.add(person_id)

        return result


# Number of Time Slots in the Time-of-death Window that the Detectives get (CG-13).
WINDOW_LENGTH = 3

# Defining the Crime of a Case: The Crime Slot, the Crime Room, and the Time-of-death Window that the Detectives get (CG-13).
@dataclass(frozen = True)
class Crime:
    slot: int
    room_id: str
    window: tuple[int, ...]

    # Reject a Crime that the Rules do not allow.
    def __post_init__(self):
        # 1. An Innocent Suspect saw the Victim alive before the Crime (CG-16), so the Crime Slot is from the second to the last Time Slot.
        if self.slot < 1 or self.slot >= len(TIME_SLOTS):
            raise ValueError(f"The Crime Slot must be from 1 to {len(TIME_SLOTS) - 1}, not {self.slot}.")

        # 2. The Window is a tuple of exactly WINDOW_LENGTH Time Slots (CG-13).
        if not isinstance(self.window, tuple):
            raise TypeError("The Time-of-death Window must be a tuple of Time Slots.")

        if len(self.window) != WINDOW_LENGTH:
            raise ValueError(f"The Time-of-death Window needs exactly {WINDOW_LENGTH} Time Slots, not {len(self.window)}.")

        # 3. The Time Slots of the Window follow each other, and all of them exist.
        first_slot = self.window[0]

        if self.window != tuple(range(first_slot, first_slot + WINDOW_LENGTH)):
            raise ValueError(f"The Time-of-death Window must be {WINDOW_LENGTH} consecutive Time Slots, not {self.window}.")

        if first_slot < 0 or first_slot + WINDOW_LENGTH > len(TIME_SLOTS):
            raise ValueError(f"The Time-of-death Window must lie inside Time Slots 0 to {len(TIME_SLOTS) - 1}, not {self.window}.")

        # 4. The Crime Slot is one of the Time Slots of the Window (CG-13).
        if self.slot not in self.window:
            raise ValueError(f"The Crime Slot {self.slot} is not in the Time-of-death Window {self.window}.")


# Defining a Sighting: An Innocent Suspect, the Witness, sees the Victim alive in a Room at a Time Slot before the Crime Slot (CG-16).
@dataclass(frozen = True)
class Sighting:
    witness_id: str
    time_slot: int
    room_id: str
