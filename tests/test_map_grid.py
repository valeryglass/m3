from dataclasses import dataclass

from app.map_grid import (
    HexCoord,
    axial_to_pixel,
    build_hex_grid,
    hex_distance,
    hex_line,
    hex_neighbors,
    parse_hex_id,
    pixel_to_axial,
)


@dataclass(frozen=True)
class Entity:
    id: str
    x: float
    y: float
    radius_hint: float


@dataclass(frozen=True)
class Topology:
    width: int
    height: int
    entities: tuple[Entity, ...]


def test_hex_coord_id_round_trips():
    coord = HexCoord(2, -1)

    assert coord.s == -1
    assert coord.id == "h:2:-1"
    assert parse_hex_id(coord.id) == coord


def test_hex_neighbors_and_distance_are_cube_compatible():
    origin = HexCoord(0, 0)

    assert hex_neighbors(origin) == (
        HexCoord(1, 0),
        HexCoord(1, -1),
        HexCoord(0, -1),
        HexCoord(-1, 0),
        HexCoord(-1, 1),
        HexCoord(0, 1),
    )
    assert hex_distance(origin, HexCoord(2, -1)) == 2


def test_hex_line_returns_straight_inclusive_path():
    assert hex_line(HexCoord(0, 0), HexCoord(3, 0)) == (
        HexCoord(0, 0),
        HexCoord(1, 0),
        HexCoord(2, 0),
        HexCoord(3, 0),
    )


def test_pixel_axial_conversion_round_trips_hex_centers():
    x, y = axial_to_pixel(2, -1, cell_size=28.0)

    assert pixel_to_axial(x, y, cell_size=28.0) == HexCoord(2, -1)


def test_build_hex_grid_is_deterministic_and_assigns_nearest_owner():
    topology = Topology(
        width=240,
        height=180,
        entities=(Entity(id="region:a", x=60, y=60, radius_hint=80),),
    )

    first = build_hex_grid(topology, cell_size=24)
    second = build_hex_grid(topology, cell_size=24)

    assert first == second
    assert first.kind == "hex"
    assert first.orientation == "pointy"
    assert any(cell.owner_id == "region:a" for cell in first.cells)
