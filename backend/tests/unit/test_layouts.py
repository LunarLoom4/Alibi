import pytest
from alibi.domain.layouts import Layout, LAYOUT_7A
from alibi.domain.types import Room


# Every Layout written so far. The tests below run once for each of them.
ALL_LAYOUTS = [LAYOUT_7A]


# Helper function to check that two Rooms share a Wall segment longer than zero.
def rooms_share_wall(room_a: Room, room_b: Room) -> bool:
    # Rooms side by side: They touch on a vertical Wall and overlap along Y.
    if room_a.x_max == room_b.x_min or room_b.x_max == room_a.x_min:

        # Minimum of maximum y's should be greater than the maximum of minimum y's.
        return min(room_a.y_max, room_b.y_max) > max(room_a.y_min, room_b.y_min)

    # Rooms one above the other: They touch on a horizontal Wall and overlap along X.
    if room_a.y_max == room_b.y_min or room_b.y_max == room_a.y_min:

        # Minimum of maximum x's should be greater than the maximum of minimum x's.
        return min(room_a.x_max, room_b.x_max) > max(room_a.x_min, room_b.x_min)

    return False


# Defining a Test Function to check that every Door joins two Rooms of the same Layout.
@pytest.mark.parametrize("layout", ALL_LAYOUTS)
def test_doors_join_rooms_of_the_layout(layout: Layout):
    room_ids = {room.id for room in layout.rooms}

    for room_a, room_b in layout.doors:
        assert room_a in room_ids
        assert room_b in room_ids

# Defining a Test Function to check that every Door sits in a Wall that its two Rooms share.
@pytest.mark.parametrize("layout", ALL_LAYOUTS)
def test_doors_sit_in_shared_walls(layout: Layout):
    rooms = {room.id: room for room in layout.rooms}

    for room_a, room_b in layout.doors:
        assert rooms_share_wall(rooms[room_a], rooms[room_b])

# Defining a Test Function to check that a Suspect can walk from any Room to every other Room (CG-15).
@pytest.mark.parametrize("layout", ALL_LAYOUTS)
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

# Defining a Test Function to check that a Door works in both directions.
def test_neighbors_work_both_ways():
    assert "library" in LAYOUT_7A.neighbors("study")
    assert "study" in LAYOUT_7A.neighbors("library")
    assert LAYOUT_7A.neighbors("garden_terrace") == {"dining_room"}

# Defining a Test Function to check that two Rooms meeting ONLY at a corner share no Wall.
def test_rooms_touching_at_a_corner_share_no_wall():
    rooms = {room.id: room for room in LAYOUT_7A.rooms}

    # The Study and the Hall meet ONLY at the point (-3, 0).
    assert not rooms_share_wall(rooms["study"], rooms["hall"])
    assert not rooms_share_wall(rooms["hall"], rooms["study"])

    # The Study and the Library share the full Wall at x = -3.
    assert rooms_share_wall(rooms["study"], rooms["library"])
