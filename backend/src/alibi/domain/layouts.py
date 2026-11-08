from dataclasses import dataclass, field

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

    # Tables worked out in '__post_init__'. They are not given when a Layout is made, and they are left out of its comparison and printing.
    neighbors_of_room: dict[str, set[str]] = field(init = False, repr = False, compare = False)
    distances_of_room: dict[str, dict[str, int]] = field(init = False, repr = False, compare = False)

    # Works out the Neighbors of every Room and the fewest Doors between every two Rooms.
    # The Case Generator asks for both very often, so it reads them from these tables instead of walking the Doors again and again.
    def __post_init__(self):
        # 1. The Neighbors of every Room.
        neighbors_of_room = {}

        for room in self.rooms:
            neighbors_of_room[room.id] = set()

        # A Door must join two Rooms of this House.
        for room_a, room_b in self.doors:
            if room_a not in neighbors_of_room or room_b not in neighbors_of_room:
                raise ValueError(f"The Door '{room_a}' - '{room_b}' joins a Room that is not in Layout '{self.id}'.")

            neighbors_of_room[room_a].add(room_b)
            neighbors_of_room[room_b].add(room_a)

        # The Layout is frozen, so the tables are set through 'object.__setattr__', as in 'TimelineGrid'.
        object.__setattr__(self, "neighbors_of_room", neighbors_of_room)

        # 2. The fewest Doors from every Room to every Room.
        distances_of_room = {}

        for room in self.rooms:
            distances_of_room[room.id] = self.walk_out_ring_by_ring(room.id)

        object.__setattr__(self, "distances_of_room", distances_of_room)

    # Returns the IDs of the Rooms that have a Door to the given Room, as a new set that the caller may change freely.
    def neighbors(self, room_id: str) -> set[str]:
        return set(self.neighbors_of_room.get(room_id, set()))

    # Returns the IDs of the Rooms that a Person in the given Room can walk to without entering the avoided Room, the given Room included.
    # After the Crime Slot, an Innocent Suspect who walked through the Crime Room would find the Body.
    # So the Case Generator avoids the Crime Room for them (CG-18).
    def reachable_rooms(self, room_id: str, avoided_room_id: str) -> set[str]:
        # 1. Both Rooms belong to the House, and the walk never starts inside the avoided Room.
        room_ids = [room.id for room in self.rooms]

        if room_id not in room_ids:
            raise ValueError(f"'{room_id}' is not a Room of Layout '{self.id}'.")

        if avoided_room_id not in room_ids:
            raise ValueError(f"The avoided Room '{avoided_room_id}' is not a Room of Layout '{self.id}'.")

        if room_id == avoided_room_id:
            raise ValueError(f"The walk cannot start in the avoided Room '{avoided_room_id}'.")

        # 2. Walk through the Doors until no new Room is found, and never step into the avoided Room.
        result = {room_id}
        rooms_to_visit = [room_id]

        while rooms_to_visit:
            current_room_id = rooms_to_visit.pop()

            for neighbor_id in self.neighbors(current_room_id):
                if neighbor_id != avoided_room_id and neighbor_id not in result:
                    result.add(neighbor_id)
                    rooms_to_visit.append(neighbor_id)

        return result

    # Returns the fewest Doors a Person must walk through to get from the given Room to each Room of the House.
    # Before the Crime Slot, a Person goes through at most one Door per Time Slot (CG-15), so this is the fewest Time Slots too.
    def distances_from(self, room_id: str) -> dict[str, int]:
        # The walk starts in a Room of the House.
        if room_id not in self.distances_of_room:
            raise ValueError(f"'{room_id}' is not a Room of Layout '{self.id}'.")

        # A new dict, so the caller may change it freely.
        return dict(self.distances_of_room[room_id])

    # Walks out from a Room ring by ring: Every Room behind a Door of the last ring, and not found before, is one Door further away.
    # The Neighbors are sorted, so the Rooms come back in the same order in every Python process (CG-1).
    # Only '__post_init__' calls it, always with a Room of the House.
    def walk_out_ring_by_ring(self, room_id: str) -> dict[str, int]:
        distances = {room_id: 0}
        last_ring = [room_id]

        while last_ring:
            next_ring = []

            for ring_room_id in last_ring:
                for neighbor_id in sorted(self.neighbors(ring_room_id)):
                    if neighbor_id not in distances:
                        distances[neighbor_id] = distances[ring_room_id] + 1
                        next_ring.append(neighbor_id)

            last_ring = next_ring

        return distances


# Layout with 6 Rooms, variant A:
# a. Two rows of three Rooms, with the Living Room and the Hall at the center.
# b. The Kitchen has two Doors: One into the Dining Room for serving, and one into the Living Room.
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

# Layout with 8 Rooms, variant B:
# a. An H-shaped House: A Great Hall between two Wings, with a Chapel in the North Court.
# b. The Living Room leads to the Library and the Music Room, and the Dining Room leads to the Kitchen and the Billiard Room.
# X grows to the right and Y grows downwards in this drawing. All values are in meters.
#
#   +--------------+    +-------------------+    +--------------+
#   |   Library    |    |      Chapel       |    |   Kitchen    |
#   |              |    |                   |    |              |
#   +--------------+----+-------------------+----+--------------+
#   | Living Room  |            Hall             | Dining Room  |
#   |              |                             |              |
#   +--------------+-----------------------------+--------------+
#   |  Music Room  |                             |   Billiard   |
#   |              |                             |     Room     |
#   +--------------+                             +--------------+
LAYOUT_8B = Layout(
    id = "8B",
    rooms = (
        Room(id = "library", name = "Library", x_min = -12, x_max = -6, y_min = -8, y_max = -3),
        Room(id = "chapel", name = "Chapel", x_min = -4, x_max = 4, y_min = -8, y_max = -3),
        Room(id = "kitchen", name = "Kitchen", x_min = 6, x_max = 12, y_min = -8, y_max = -3),
        Room(id = "living_room", name = "Living Room", x_min = -12, x_max = -6, y_min = -3, y_max = 3),
        Room(id = "hall", name = "Hall", x_min = -6, x_max = 6, y_min = -3, y_max = 3),
        Room(id = "dining_room", name = "Dining Room", x_min = 6, x_max = 12, y_min = -3, y_max = 3),
        Room(id = "music_room", name = "Music Room", x_min = -12, x_max = -6, y_min = 3, y_max = 8),
        Room(id = "billiard_room", name = "Billiard Room", x_min = 6, x_max = 12, y_min = 3, y_max = 8),
    ),
    doors = (
        ("hall", "chapel"),
        ("hall", "living_room"),
        ("hall", "dining_room"),
        ("living_room", "library"),
        ("living_room", "music_room"),
        ("dining_room", "kitchen"),
        ("dining_room", "billiard_room"),
    )
)

# Layout with 8 Rooms, variant C:
# a. A Courtyard House like an Indian Haveli, with seven Rooms around an open Courtyard and the Hall along the North side.
# b. The Hall, the Bedroom, the Living Room and the Kitchen open onto the Courtyard, and the Study opens ONLY into the Hall.
# X grows to the right and Y grows downwards in this drawing. All values are in meters.
#
#   +--------------+-----------------------------+
#   |    Study     |            Hall             |
#   |              |                             |
#   +--------------+--------------+--------------+
#   |   Bedroom    |  Courtyard   |   Kitchen    |
#   |              |              |              |
#   +--------------+--------------+--------------+
#   |  Music Room  | Living Room  | Dining Room  |
#   |              |              |              |
#   +--------------+--------------+--------------+
LAYOUT_8C = Layout(
    id = "8C",
    rooms = (
        Room(id = "study", name = "Study", x_min = -9, x_max = -3, y_min = -9, y_max = -3),
        Room(id = "hall", name = "Hall", x_min = -3, x_max = 9, y_min = -9, y_max = -3),
        Room(id = "bedroom", name = "Bedroom", x_min = -9, x_max = -3, y_min = -3, y_max = 3),
        Room(id = "courtyard", name = "Courtyard", x_min = -3, x_max = 3, y_min = -3, y_max = 3),
        Room(id = "kitchen", name = "Kitchen", x_min = 3, x_max = 9, y_min = -3, y_max = 3),
        Room(id = "music_room", name = "Music Room", x_min = -9, x_max = -3, y_min = 3, y_max = 9),
        Room(id = "living_room", name = "Living Room", x_min = -3, x_max = 3, y_min = 3, y_max = 9),
        Room(id = "dining_room", name = "Dining Room", x_min = 3, x_max = 9, y_min = 3, y_max = 9),
    ),
    doors = (
        ("hall", "study"),
        ("hall", "courtyard"),
        ("courtyard", "bedroom"),
        ("courtyard", "living_room"),
        ("courtyard", "kitchen"),
        ("kitchen", "dining_room"),
        ("living_room", "dining_room"),
        ("living_room", "music_room"),
    )
)


# Every Layout, grouped by its Number of Rooms (CG-2).
# A Case with S Suspects picks one of the Layouts listed under count_rooms(S).
LAYOUTS = {
    6: (LAYOUT_6A, LAYOUT_6B, LAYOUT_6C),
    7: (LAYOUT_7A, LAYOUT_7B, LAYOUT_7C),
    8: (LAYOUT_8A, LAYOUT_8B, LAYOUT_8C),
}
