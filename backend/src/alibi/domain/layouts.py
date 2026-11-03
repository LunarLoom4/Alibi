from dataclasses import dataclass

from .types import Room


# Defining a House Layout -- its Rooms and the Doors between them.
# Each Door is a pair of Room IDs, and a Suspect can walk through it both ways (CG-15).
# Every Door is a solid Door kept closed, and every Curtain is drawn at night.
# Thus, a Suspect sees ONLY the people inside their own Room (KN-3).
@dataclass(frozen = True)
class Layout:
    id: str
    rooms: tuple[Room, ...]
    doors: tuple[tuple[str, str], ...]

    # Returns the IDs of the Rooms that have a Door to the given Room.
    def neighbors(self, room_id: str) -> set[str]:
        result = set()

        for room_a, room_b in self.doors:
            if room_a == room_id:
                result.add(room_b)

            elif room_b == room_id:
                result.add(room_a)

        return result


# Layout with 6 Rooms, variant A:
# a. Two rows of three Rooms, with the Living Room and the Hall at the center.
# b. The Kitchen has two Doors: one into the Dining Room for serving, and one into the Living Room.
# X grows to the right and Y grows downwards in this drawing. All values are in meters.
#
#   +--------------+-------------------+--------------+
#   |    Study     |    Living Room    |   Kitchen    |
#   |              |                   |              |
#   +--------------+-------------------+--------------+
#   |   Bedroom    |       Hall        | Dining Room  |
#   |              |                   |              |
#   +--------------+-------------------+--------------+
LAYOUT_6A = Layout(
    id = "6A",
    rooms = (
        Room(id = "study", name = "Study", x_min = -10, x_max = -4, y_min = -5.5, y_max = 0),
        Room(id = "living_room", name = "Living Room", x_min = -4, x_max = 4, y_min = -5.5, y_max = 0),
        Room(id = "kitchen", name = "Kitchen", x_min = 4, x_max = 10, y_min = -5.5, y_max = 0),
        Room(id = "bedroom", name = "Bedroom", x_min = -10, x_max = -4, y_min = 0, y_max = 5.5),
        Room(id = "hall", name = "Hall", x_min = -4, x_max = 4, y_min = 0, y_max = 5.5),
        Room(id = "dining_room", name = "Dining Room", x_min = 4, x_max = 10, y_min = 0, y_max = 5.5),
    ),
    doors = (
        ("study", "living_room"),
        ("living_room", "hall"),
        ("bedroom", "hall"),
        ("hall", "dining_room"),
        ("living_room", "kitchen"),
        ("kitchen", "dining_room"),
    )
)

# Layout with 6 Rooms, variant B:
# a. A Center Hall from the Front Door to the back, with two Rooms on each side and a Kitchen Wing on the East side.
# b. The Living Room and the Study share a connecting Door, and the Kitchen opens ONLY into the Dining Room.
# X grows to the right and Y grows downwards in this drawing. All values are in meters.
#
#   +-----------------+----------+-----------------+------------+
#   |   Living Room   |          |   Dining Room   |  Kitchen   |
#   |                 |          |                 |            |
#   +-----------------+   Hall   +-----------------+------------+
#   |      Study      |          |     Library     |
#   |                 |          |                 |
#   +-----------------+----------+-----------------+
LAYOUT_6B = Layout(
    id = "6B",
    rooms = (
        Room(id = "living_room", name = "Living Room", x_min = -9, x_max = -2, y_min = -6, y_max = 0),
        Room(id = "hall", name = "Hall", x_min = -2, x_max = 2, y_min = -6, y_max = 6),
        Room(id = "dining_room", name = "Dining Room", x_min = 2, x_max = 9, y_min = -6, y_max = 0),
        Room(id = "kitchen", name = "Kitchen", x_min = 9, x_max = 14, y_min = -6, y_max = 0),
        Room(id = "study", name = "Study", x_min = -9, x_max = -2, y_min = 0, y_max = 6),
        Room(id = "library", name = "Library", x_min = 2, x_max = 9, y_min = 0, y_max = 6),
    ),
    doors = (
        ("living_room", "hall"),
        ("study", "hall"),
        ("hall", "dining_room"),
        ("hall", "library"),
        ("living_room", "study"),
        ("dining_room", "kitchen"),
    )
)

# Layout with 6 Rooms, variant C:
# a. Three rows that step back, with three Rooms at the Front, two in the Middle, and the Kitchen at the Back.
# b. The Bedroom opens ONLY into the Hall, and the Kitchen opens ONLY into the Dining Room.
# X grows to the right and Y grows downwards in this drawing. All values are in meters.
#
#   +-----------------+-------------------+------------+
#   |   Living Room   |       Hall        |   Study    |
#   |                 |                   |            |
#   +-----------------+-------------------+------------+
#   |   Dining Room   |      Bedroom      |
#   |                 |                   |
#   +-----------------+-------------------+
#   |     Kitchen     |
#   |                 |
#   +-----------------+
LAYOUT_6C = Layout(
    id = "6C",
    rooms = (
        Room(id = "living_room", name = "Living Room", x_min = -10, x_max = -3, y_min = -5, y_max = 0),
        Room(id = "hall", name = "Hall", x_min = -3, x_max = 5, y_min = -5, y_max = 0),
        Room(id = "study", name = "Study", x_min = 5, x_max = 10, y_min = -5, y_max = 0),
        Room(id = "dining_room", name = "Dining Room", x_min = -10, x_max = -3, y_min = 0, y_max = 5),
        Room(id = "bedroom", name = "Bedroom", x_min = -3, x_max = 5, y_min = 0, y_max = 5),
        Room(id = "kitchen", name = "Kitchen", x_min = -10, x_max = -3, y_min = 5, y_max = 10),
    ),
    doors = (
        ("living_room", "hall"),
        ("hall", "study"),
        ("hall", "bedroom"),
        ("living_room", "dining_room"),
        ("dining_room", "kitchen"),
    )
)


# Layout with 7 Rooms, variant A:
# a. Two rows of Rooms with a Garden Terrace on the East side.
# b. The Kitchen opens into the Hall and the Dining Room, and the Garden Terrace opens ONLY into the Dining Room.
# X grows to the right and Y grows downwards in this drawing. All values are in meters.
#
#   +--------------+--------------+--------------+
#   |    Study     |   Library    |   Kitchen    |
#   |              |              |              +--------------+
#   +--------------+--------------+----+---------+              |
#   |   Bedroom    |       Hall        | Dining  |    Garden    |
#   |              |                   |  Room   |   Terrace    |
#   +--------------+-------------------+---------+--------------+
LAYOUT_7A = Layout(
    id = "7A",
    rooms = (
        Room(id = "study", name = "Study", x_min = -9, x_max = -3, y_min = -5.5, y_max = 0),
        Room(id = "library", name = "Library", x_min = -3, x_max = 3, y_min = -5.5, y_max = 0),
        Room(id = "kitchen", name = "Kitchen", x_min = 3, x_max = 9, y_min = -5.5, y_max = 0),
        Room(id = "bedroom", name = "Bedroom", x_min = -9, x_max = -3, y_min = 0, y_max = 5.5),
        Room(id = "hall", name = "Hall", x_min = -3, x_max = 5, y_min = 0, y_max = 5.5),
        Room(id = "dining_room", name = "Dining Room", x_min = 5, x_max = 9, y_min = 0, y_max = 5.5),
        Room(id = "garden_terrace", name = "Garden Terrace", x_min = 9, x_max = 15, y_min = -2, y_max = 5.5),
    ),
    doors = (
        ("study", "library"),
        ("library", "hall"),
        ("bedroom", "hall"),
        ("hall", "kitchen"),
        ("hall", "dining_room"),
        ("kitchen", "dining_room"),
        ("dining_room", "garden_terrace"),
    )
)

# Layout with 7 Rooms, variant B:
# a. A long Hall from West to East, with three Rooms on each side of it.
# b. Every Room opens into the Hall, and the Kitchen also has a serving Door into the Dining Room.
# X grows to the right and Y grows downwards in this drawing. All values are in meters.
#
#   +--------------+--------------+-------------------+
#   |   Kitchen    | Dining Room  |      Library      |
#   |              |              |                   |
#   +--------------+--------------+-------------------+
#   |                      Hall                       |
#   +-------------------+--------------+--------------+
#   |    Living Room    |    Study     |   Bedroom    |
#   |                   |              |              |
#   +-------------------+--------------+--------------+
LAYOUT_7B = Layout(
    id = "7B",
    rooms = (
        Room(id = "kitchen", name = "Kitchen", x_min = -10, x_max = -4, y_min = -6.5, y_max = -1.5),
        Room(id = "dining_room", name = "Dining Room", x_min = -4, x_max = 2, y_min = -6.5, y_max = -1.5),
        Room(id = "library", name = "Library", x_min = 2, x_max = 10, y_min = -6.5, y_max = -1.5),
        Room(id = "hall", name = "Hall", x_min = -10, x_max = 10, y_min = -1.5, y_max = 1.5),
        Room(id = "living_room", name = "Living Room", x_min = -10, x_max = -2, y_min = 1.5, y_max = 6.5),
        Room(id = "study", name = "Study", x_min = -2, x_max = 4, y_min = 1.5, y_max = 6.5),
        Room(id = "bedroom", name = "Bedroom", x_min = 4, x_max = 10, y_min = 1.5, y_max = 6.5),
    ),
    doors = (
        ("hall", "kitchen"),
        ("hall", "dining_room"),
        ("hall", "library"),
        ("hall", "living_room"),
        ("hall", "study"),
        ("hall", "bedroom"),
        ("kitchen", "dining_room"),
    )
)

# Layout with 7 Rooms, variant C:
# a. A U-shaped House around a Courtyard that is open to the sky and closed by a Garden Wall on the South side.
# b. The Courtyard opens into the Hall and the Kitchen, and the Study opens ONLY into the Library.
# X grows to the right and Y grows downwards in this drawing. All values are in meters.
#
#   +--------------+-------------------+--------------+
#   | Living Room  |       Hall        | Dining Room  |
#   |              |                   |              |
#   +--------------+-------------------+--------------+
#   |   Library    |     Courtyard     |   Kitchen    |
#   |              |                   |              |
#   +--------------+-------------------+--------------+
#   |    Study     |
#   |              |
#   +--------------+
LAYOUT_7C = Layout(
    id = "7C",
    rooms = (
        Room(id = "living_room", name = "Living Room", x_min = -10, x_max = -4, y_min = -5, y_max = 0),
        Room(id = "hall", name = "Hall", x_min = -4, x_max = 4, y_min = -5, y_max = 0),
        Room(id = "dining_room", name = "Dining Room", x_min = 4, x_max = 10, y_min = -5, y_max = 0),
        Room(id = "library", name = "Library", x_min = -10, x_max = -4, y_min = 0, y_max = 5),
        Room(id = "courtyard", name = "Courtyard", x_min = -4, x_max = 4, y_min = 0, y_max = 5),
        Room(id = "kitchen", name = "Kitchen", x_min = 4, x_max = 10, y_min = 0, y_max = 5),
        Room(id = "study", name = "Study", x_min = -10, x_max = -4, y_min = 5, y_max = 10),
    ),
    doors = (
        ("living_room", "hall"),
        ("hall", "dining_room"),
        ("dining_room", "kitchen"),
        ("hall", "courtyard"),
        ("courtyard", "kitchen"),
        ("living_room", "library"),
        ("library", "study"),
    )
)


# Layout with 8 Rooms, variant A:
# a. Two rows of four Rooms, with the Library and the Hall in the wider second column.
# b. The Billiard Room opens ONLY into the Library, and the Music Room connects the Library and the Living Room.
# X grows to the right and Y grows downwards in this drawing. All values are in meters.
#
#   +--------------+-------------------+--------------+--------------+
#   |   Billiard   |      Library      |  Music Room  |   Kitchen    |
#   |     Room     |                   |              |              |
#   +--------------+-------------------+--------------+--------------+
#   |    Study     |       Hall        | Living Room  | Dining Room  |
#   |              |                   |              |              |
#   +--------------+-------------------+--------------+--------------+
LAYOUT_8A = Layout(
    id = "8A",
    rooms = (
        Room(id = "billiard_room", name = "Billiard Room", x_min = -13, x_max = -7, y_min = -5.5, y_max = 0),
        Room(id = "library", name = "Library", x_min = -7, x_max = 1, y_min = -5.5, y_max = 0),
        Room(id = "music_room", name = "Music Room", x_min = 1, x_max = 7, y_min = -5.5, y_max = 0),
        Room(id = "kitchen", name = "Kitchen", x_min = 7, x_max = 13, y_min = -5.5, y_max = 0),
        Room(id = "study", name = "Study", x_min = -13, x_max = -7, y_min = 0, y_max = 5.5),
        Room(id = "hall", name = "Hall", x_min = -7, x_max = 1, y_min = 0, y_max = 5.5),
        Room(id = "living_room", name = "Living Room", x_min = 1, x_max = 7, y_min = 0, y_max = 5.5),
        Room(id = "dining_room", name = "Dining Room", x_min = 7, x_max = 13, y_min = 0, y_max = 5.5),
    ),
    doors = (
        ("study", "hall"),
        ("hall", "library"),
        ("hall", "living_room"),
        ("library", "billiard_room"),
        ("library", "music_room"),
        ("music_room", "living_room"),
        ("living_room", "dining_room"),
        ("dining_room", "kitchen"),
    )
)




# Every Layout, grouped by its Number of Rooms (CG-2).
# A Case with S Suspects picks one of the Layouts listed under count_rooms(S).
LAYOUTS = {
    6: (LAYOUT_6A, LAYOUT_6B, LAYOUT_6C),
    7: (LAYOUT_7A, LAYOUT_7B, LAYOUT_7C),
    8: (LAYOUT_8A,),
}
