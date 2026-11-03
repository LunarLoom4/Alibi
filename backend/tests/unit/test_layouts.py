import pytest
from itertools import combinations

from alibi.domain import layouts as layouts_module
from alibi.domain.layouts import Layout, LAYOUTS
from alibi.domain.parameters import MIN_SUSPECTS, MAX_SUSPECTS, count_rooms
from alibi.domain.types import Room


# Every Layout in the LAYOUTS dictionary, from all the Room counts.
ALL_LAYOUTS = [layout for layouts in LAYOUTS.values() for layout in layouts]

# Name each test run after its Layout ID, so a failure reads 'test_...[7A]' instead of the default 'test_...[layout0]'.
LAYOUT_IDS = [layout.id for layout in ALL_LAYOUTS]

# Shortest shared Wall that can hold a Door: A 0.9 m wide Door plus its Frame on both sides.
MIN_DOOR_WALL_LENGTH = 1.0


# Helper function to measure the Wall segment that two Rooms share, in meters.
# Rooms that do not touch, or touch ONLY at a corner, share 0 m.
def shared_wall_length(room_a: Room, room_b: Room) -> float:
    # Rooms side by side: They touch on a vertical Wall and overlap along Y.
    if room_a.x_max == room_b.x_min or room_b.x_max == room_a.x_min:

        # Minimum of maximum y's should be greater than the maximum of minimum y's. A negative value is a gap, so it counts as 0.
        return max(0, min(room_a.y_max, room_b.y_max) - max(room_a.y_min, room_b.y_min))

    # Rooms one above the other: They touch on a horizontal Wall and overlap along X.
    if room_a.y_max == room_b.y_min or room_b.y_max == room_a.y_min:

        # Minimum of maximum x's minus the maximum of minimum x's. A negative value is a gap, so it counts as 0.
        return max(0, min(room_a.x_max, room_b.x_max) - max(room_a.x_min, room_b.x_min))

    return 0

# Helper function to check that two Rooms cover a common area larger than zero.
def rooms_overlap(room_a: Room, room_b: Room) -> bool:
    # The Rectangles must overlap along X AND along Y. Touching along a Wall or at a corner overlaps by zero.
    overlap_along_x = min(room_a.x_max, room_b.x_max) > max(room_a.x_min, room_b.x_min)
    overlap_along_y = min(room_a.y_max, room_b.y_max) > max(room_a.y_min, room_b.y_min)

    return overlap_along_x and overlap_along_y


# Defining a Test Function to check that every Room of a Layout has a unique ID.
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = LAYOUT_IDS)
def test_room_ids_are_unique(layout: Layout):
    room_ids = [room.id for room in layout.rooms]

    assert len(room_ids) == len(set(room_ids)), f"Layout '{layout.id}' repeats a Room ID."

# Defining a Test Function to check that every Room has a width and a depth larger than zero.
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = LAYOUT_IDS)
def test_rooms_have_positive_size(layout: Layout):
    for room in layout.rooms:
        assert room.x_min < room.x_max, f"'{room.id}' has no width."
        assert room.y_min < room.y_max, f"'{room.id}' has no depth."

# Defining a Test Function to check that no two Rooms of a Layout cover the same Floor area.
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = LAYOUT_IDS)
def test_rooms_never_overlap(layout: Layout):
    for room_a, room_b in combinations(layout.rooms, 2):
        assert not rooms_overlap(room_a, room_b), f"'{room_a.id}' overlaps '{room_b.id}'."

# Defining a Test Function to check that every Door joins two Rooms of the same Layout.
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = LAYOUT_IDS)
def test_doors_join_rooms_of_the_layout(layout: Layout):
    room_ids = {room.id for room in layout.rooms}

    for room_a, room_b in layout.doors:
        assert room_a in room_ids
        assert room_b in room_ids

# Defining a Test Function to check that every Door sits in a Wall that its two Rooms share, long enough to hold the Door.
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = LAYOUT_IDS)
def test_doors_sit_in_shared_walls(layout: Layout):
    rooms = {room.id: room for room in layout.rooms}

    for room_a, room_b in layout.doors:
        wall_length = shared_wall_length(rooms[room_a], rooms[room_b])
        assert wall_length >= MIN_DOOR_WALL_LENGTH, f"The Door '{room_a}' - '{room_b}' sits in a shared Wall of {wall_length} m."

# Defining a Test Function to check that a Suspect can walk from any Room to every other Room (CG-15).
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = LAYOUT_IDS)
def test_cg15_every_room_is_reachable(layout: Layout):
    start = layout.rooms[0].id
    visited = {start}
    to_visit = [start]

    # Walk through the Doors until no new Room is found.
    while to_visit:
        current = to_visit.pop()

        for neighbor in layout.neighbors(current):
            if neighbor not in visited:
                visited.add(neighbor)
                to_visit.append(neighbor)

    assert visited == {room.id for room in layout.rooms}

# Defining a Test Function to check that no Door joins a Room to itself and no Door is listed twice.
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = LAYOUT_IDS)
def test_doors_join_two_different_rooms_once(layout: Layout):
    seen_doors = set()

    for room_a, room_b in layout.doors:
        assert room_a != room_b

        # A Door is the same Door in both directions, so compare it as an unordered pair.
        door = frozenset((room_a, room_b))
        assert door not in seen_doors
        seen_doors.add(door)

# Defining a Test Function to check that 'neighbors' returns exactly the Rooms behind the Doors of a Room.
@pytest.mark.parametrize("layout", ALL_LAYOUTS, ids = LAYOUT_IDS)
def test_neighbors_match_the_doors(layout: Layout):
    # 1. Each Door makes its two Rooms Neighbors of each other, in both directions.
    for room_a, room_b in layout.doors:
        assert room_b in layout.neighbors(room_a)
        assert room_a in layout.neighbors(room_b)

    # 2. A Room has exactly as many Neighbors as it has Doors, and is never its own Neighbor.
    for room in layout.rooms:
        doors_of_room = [door for door in layout.doors if room.id in door]

        assert len(layout.neighbors(room.id)) == len(doors_of_room)
        assert room.id not in layout.neighbors(room.id)

# Defining a Test Function to check that no two Layouts share an ID.
def test_layout_ids_are_unique():
    assert len(LAYOUT_IDS) == len(set(LAYOUT_IDS)), "Two Layouts share an ID."

# Defining a Test Function to check that every Layout in 'layouts.py' is named after its ID and listed in LAYOUTS exactly once.
def test_every_layout_is_registered():
    written_ids = []

    # Every Layout object in the module, found by its type, so a new Layout cannot be forgotten.
    for name, value in vars(layouts_module).items():
        if isinstance(value, Layout):

            # The variable is named after the Layout ID, like LAYOUT_6B for '6B'.
            assert name == f"LAYOUT_{value.id}", f"'{name}' holds Layout '{value.id}'."
            written_ids.append(value.id)

    assert sorted(LAYOUT_IDS) == sorted(written_ids)

# Defining a Test Function to check that each Layout is listed under its own Number of Rooms, and that CG-2 asks for that Number.
def test_cg2_layouts_are_grouped_by_room_count():
    # The Room counts that CG-2 gives over every allowed Number of Suspects.
    room_counts = {count_rooms(num_suspects) for num_suspects in range(MIN_SUSPECTS, MAX_SUSPECTS + 1)}

    for num_rooms, layouts in LAYOUTS.items():
        assert num_rooms in room_counts, f"CG-2 never asks for {num_rooms} Rooms."

        for layout in layouts:
            assert len(layout.rooms) == num_rooms, f"Layout '{layout.id}' has {len(layout.rooms)} Rooms, not {num_rooms}."

            # A Layout ID is its Number of Rooms followed by the variant letter A, B or C, like '6B'.
            assert layout.id in (f"{num_rooms}A", f"{num_rooms}B", f"{num_rooms}C"), f"Layout '{layout.id}' is listed under {num_rooms} Rooms."


# Every way two Rooms can sit on a Floor Plan.
# The First Room is always the 4 m x 4 m square at the origin.
# The Second Room is a Rectangle (x_min, x_max, y_min, y_max) and is associated with an expected answer of 'rooms_share_wall'.
WALL_CASES = [
    pytest.param(( 4, 8,  0,   4), 4,   id = "Side by side, full Wall"),
    pytest.param(( 4, 8,  2,   6), 2,   id = "Side by side, part of a Wall"),
    pytest.param(( 4, 8,  3.5, 8), 0.5, id = "Side by side, a short piece of Wall"),
    pytest.param(( 0, 4,  4,   8), 4,   id = "One above the other, full Wall"),
    pytest.param((-2, 2,  4,   8), 2,   id = "One above the other, part of a Wall"),
    pytest.param(( 4, 8,  4,   8), 0,   id = "Meeting ONLY at a corner"),
    pytest.param(( 4, 8, -4,   0), 0,   id = "Meeting ONLY at the opposite corner"),
    pytest.param(( 5, 8,  0,   4), 0,   id = "Side by side with a gap"),
    pytest.param(( 0, 4,  6,   8), 0,   id = "One above the other with a gap"),
    pytest.param(( 4, 8,  6,   8), 0,   id = "Side by side along one line, with a gap"),
    pytest.param(( 6, 8,  4,   8), 0,   id = "One above the other along one line, with a gap"),
]

# Defining a Test Function to check 'shared_wall_length' on every arrangement, with the Rooms in both orders.
@pytest.mark.parametrize("dimensions, expected", WALL_CASES)
def test_shared_wall_length_on_every_arrangement(dimensions: tuple, expected: float):
    squareRoom = Room(id = "a", name = "A", x_min = 0, x_max = 4, y_min = 0, y_max = 4)

    x_min, x_max, y_min, y_max = dimensions
    otherRoom = Room(id = "b", name = "B", x_min = x_min, x_max = x_max, y_min = y_min, y_max = y_max)

    assert shared_wall_length(squareRoom, otherRoom) == expected
    assert shared_wall_length(otherRoom, squareRoom) == expected


# Every way two Rooms can sit on a Floor Plan.
# The First Room is always the 4 m x 4 m square at the origin.
# The Second Room is a Rectangle (x_min, x_max, y_min, y_max) with the expected answer of 'rooms_overlap'.
OVERLAP_CASES = [
    pytest.param(( 0, 4,  0, 4), True,  id = "The same Rectangle"),
    pytest.param(( 1, 3,  1, 3), True,  id = "One inside the other"),
    pytest.param((-1, 5,  1, 3), True,  id = "Crossing like a plus sign"),
    pytest.param(( 2, 6,  2, 6), True,  id = "Overlapping at one corner"),
    pytest.param(( 2, 6,  0, 4), True,  id = "Side by side, overlapping by half"),
    pytest.param(( 0, 4,  2, 6), True,  id = "One above the other, overlapping by half"),
    pytest.param(( 4, 8,  0, 4), False, id = "Side by side, sharing a full Wall"),
    pytest.param(( 0, 4,  4, 8), False, id = "One above the other, sharing a full Wall"),
    pytest.param(( 4, 8,  4, 8), False, id = "Meeting ONLY at a corner"),
    pytest.param(( 5, 8,  0, 4), False, id = "Side by side with a gap"),
    pytest.param(( 0, 4,  6, 8), False, id = "One above the other with a gap"),
    pytest.param(( 6, 8,  6, 8), False, id = "Apart along X AND along Y"),
]

# Defining a Test Function to check 'rooms_overlap' on every arrangement, with the Rooms in both orders.
@pytest.mark.parametrize("dimensions, expected", OVERLAP_CASES)
def test_rooms_overlap_on_every_arrangement(dimensions: tuple, expected: bool):
    squareRoom = Room(id = "a", name = "A", x_min = 0, x_max = 4, y_min = 0, y_max = 4)

    x_min, x_max, y_min, y_max = dimensions
    otherRoom = Room(id = "b", name = "B", x_min = x_min, x_max = x_max, y_min = y_min, y_max = y_max)

    assert rooms_overlap(squareRoom, otherRoom) == expected
    assert rooms_overlap(otherRoom, squareRoom) == expected
