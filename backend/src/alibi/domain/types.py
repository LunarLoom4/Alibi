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
