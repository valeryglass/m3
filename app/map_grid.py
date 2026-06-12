from __future__ import annotations

"""Axial/cube-compatible hex grid primitives for map layout.

This module owns coordinate math only. It does not decide semantic meaning and
it does not render. The preferred storage coordinate is axial ``q, r`` with
computed cube coordinate ``s = -q - r``.
"""

from dataclasses import dataclass
import math
from typing import Iterable, Protocol


SQRT3 = math.sqrt(3.0)
AXIAL_DIRECTIONS: tuple[tuple[int, int], ...] = (
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, 0),
    (-1, 1),
    (0, 1),
)


class _TopologyLike(Protocol):
    width: int
    height: int
    entities: Iterable[object]


@dataclass(frozen=True, order=True)
class HexCoord:
    q: int
    r: int

    @property
    def s(self) -> int:
        return -self.q - self.r

    @property
    def id(self) -> str:
        return hex_id(self.q, self.r)


@dataclass(frozen=True)
class GridCell:
    q: int
    r: int
    s: int
    id: str
    x: float
    y: float
    owner_id: str | None = None
    tags: tuple[str, ...] = ()

    @property
    def coord(self) -> HexCoord:
        return HexCoord(self.q, self.r)


@dataclass(frozen=True)
class GridModel:
    kind: str
    width: int
    height: int
    cell_size: float
    orientation: str
    coordinate_system: str
    cells: tuple[GridCell, ...]


def hex_id(q: int, r: int) -> str:
    return f"h:{q}:{r}"


def parse_hex_id(cell_id: str) -> HexCoord:
    prefix, q, r = cell_id.split(":", 2)
    if prefix != "h":
        raise ValueError(f"unsupported hex cell id: {cell_id!r}")
    return HexCoord(int(q), int(r))


def cube_s(q: int, r: int) -> int:
    return -q - r


def axial_to_pixel(q: int | float, r: int | float, *, cell_size: float) -> tuple[float, float]:
    """Convert pointy-top axial hex coordinates to pixel center."""

    x = cell_size * SQRT3 * (q + r / 2.0)
    y = cell_size * 1.5 * r
    return (x, y)


def pixel_to_axial(x: float, y: float, *, cell_size: float) -> HexCoord:
    """Convert pixel coordinates to the nearest axial hex coordinate."""

    q = (SQRT3 / 3.0 * x - y / 3.0) / cell_size
    r = (2.0 / 3.0 * y) / cell_size
    return hex_round(q, r)


def hex_round(q: float, r: float) -> HexCoord:
    """Round fractional axial coordinates using cube-coordinate correction."""

    s = -q - r
    rounded_q = round(q)
    rounded_r = round(r)
    rounded_s = round(s)

    q_diff = abs(rounded_q - q)
    r_diff = abs(rounded_r - r)
    s_diff = abs(rounded_s - s)

    if q_diff > r_diff and q_diff > s_diff:
        rounded_q = -rounded_r - rounded_s
    elif r_diff > s_diff:
        rounded_r = -rounded_q - rounded_s

    return HexCoord(int(rounded_q), int(rounded_r))


def hex_neighbor(coord: HexCoord, direction: int) -> HexCoord:
    dq, dr = AXIAL_DIRECTIONS[direction % 6]
    return HexCoord(coord.q + dq, coord.r + dr)


def hex_neighbors(coord: HexCoord) -> tuple[HexCoord, ...]:
    return tuple(hex_neighbor(coord, direction) for direction in range(6))


def hex_distance(a: HexCoord, b: HexCoord) -> int:
    return int((abs(a.q - b.q) + abs(a.r - b.r) + abs(a.s - b.s)) / 2)


def hex_line(a: HexCoord, b: HexCoord) -> tuple[HexCoord, ...]:
    """Return a straight hex line between two cells, inclusive."""

    distance = hex_distance(a, b)
    if distance == 0:
        return (a,)

    cells: list[HexCoord] = []
    for step in range(distance + 1):
        t = step / distance
        q = _lerp(a.q, b.q, t)
        r = _lerp(a.r, b.r, t)
        cells.append(hex_round(q, r))
    return tuple(dict.fromkeys(cells))


def build_hex_grid(
    topology: _TopologyLike,
    *,
    cell_size: float = 28.0,
    margin_cells: int = 2,
) -> GridModel:
    """Build deterministic pointy-top hex cells covering topology bounds.

    If topology entities expose ``x``, ``y``, ``id`` and ``radius_hint`` fields,
    cells inside their radius hint are assigned to the nearest entity. This is a
    temporary ownership heuristic, not the final attractor model.
    """

    if cell_size <= 0:
        raise ValueError("cell_size must be positive")

    corners = [
        pixel_to_axial(0, 0, cell_size=cell_size),
        pixel_to_axial(topology.width, 0, cell_size=cell_size),
        pixel_to_axial(0, topology.height, cell_size=cell_size),
        pixel_to_axial(topology.width, topology.height, cell_size=cell_size),
    ]
    q_min = min(corner.q for corner in corners) - margin_cells
    q_max = max(corner.q for corner in corners) + margin_cells
    r_min = min(corner.r for corner in corners) - margin_cells
    r_max = max(corner.r for corner in corners) + margin_cells

    entities = list(topology.entities)
    cells: list[GridCell] = []
    for q in range(q_min, q_max + 1):
        for r in range(r_min, r_max + 1):
            x, y = axial_to_pixel(q, r, cell_size=cell_size)
            if not _within_bounds(x, y, width=topology.width, height=topology.height, margin=cell_size):
                continue

            owner_id = _nearest_owner_id(x, y, entities)
            tags = (f"owner:{owner_id}",) if owner_id else ()
            cells.append(
                GridCell(
                    q=q,
                    r=r,
                    s=cube_s(q, r),
                    id=hex_id(q, r),
                    x=x,
                    y=y,
                    owner_id=owner_id,
                    tags=tags,
                )
            )

    return GridModel(
        kind="hex",
        width=topology.width,
        height=topology.height,
        cell_size=cell_size,
        orientation="pointy",
        coordinate_system="axial",
        cells=tuple(sorted(cells, key=lambda cell: (cell.q, cell.r))),
    )


def _within_bounds(x: float, y: float, *, width: int, height: int, margin: float) -> bool:
    return -margin <= x <= width + margin and -margin <= y <= height + margin


def _nearest_owner_id(x: float, y: float, entities: Iterable[object]) -> str | None:
    best_id: str | None = None
    best_distance_sq: float | None = None

    for entity in entities:
        entity_id = getattr(entity, "id", None)
        entity_x = getattr(entity, "x", None)
        entity_y = getattr(entity, "y", None)
        radius_hint = getattr(entity, "radius_hint", None)
        if entity_id is None or entity_x is None or entity_y is None or radius_hint is None:
            continue

        dx = x - float(entity_x)
        dy = y - float(entity_y)
        distance_sq = dx * dx + dy * dy
        if distance_sq > float(radius_hint) * float(radius_hint):
            continue
        if best_distance_sq is None or distance_sq < best_distance_sq:
            best_id = str(entity_id)
            best_distance_sq = distance_sq

    return best_id


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
