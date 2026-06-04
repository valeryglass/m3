from __future__ import annotations

import argparse
import json
import math
from html import escape
from pathlib import Path
from typing import Any


ENTITY_ORDER = (
    "gate",
    "climate",
    "architecture",
    "district",
    "crossroads",
    "landmark",
    "road",
    "destination",
)


def render_html(payload: dict[str, Any]) -> str:
    svg_markup = _render_map_svg(payload)
    groups = _group_entities(payload.get("entities", []))
    top_districts = _list_items(groups["district"][:8])
    top_crossroads = _list_items(groups["crossroads"][:8])
    top_roads = _list_items(groups["road"][:8])

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Map Payload - {escape(str(payload.get("source", "unknown")))}</title>
  <style>
    body {{
      margin: 0;
      background: #f7f5ef;
      color: #1f2937;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      padding: 18px 24px 12px;
      border-bottom: 1px solid #d8d2c4;
      background: #fffdfa;
    }}
    h1 {{
      margin: 0;
      font-size: 22px;
      letter-spacing: 0;
    }}
    .meta {{
      margin-top: 6px;
      color: #667085;
      font-size: 13px;
    }}
    main {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      min-height: calc(100vh - 70px);
    }}
    .stage {{
      overflow: auto;
      padding: 18px;
    }}
    aside {{
      border-left: 1px solid #d8d2c4;
      background: #fffdfa;
      padding: 18px;
      overflow: auto;
    }}
    svg {{
      width: 100%;
      min-width: 980px;
      height: auto;
      border: 1px solid #d8d2c4;
      background: #f8f5ec;
    }}
    .bg {{ fill: #fbfaf7; }}
    .map-title {{
      font-size: 17px;
      font-weight: 760;
      fill: #1f2937;
    }}
    .zone-label {{
      font-size: 13px;
      font-weight: 700;
      fill: #374151;
    }}
    .district-area {{
      stroke: rgba(4, 120, 87, 0.42);
      stroke-width: 2;
      fill: rgba(4, 120, 87, 0.18);
    }}
    .cluster-halo {{
      fill: rgba(4, 120, 87, 0.08);
      stroke: rgba(4, 120, 87, 0.18);
      stroke-width: 2;
      stroke-dasharray: 8 6;
    }}
    .neighbor-link {{
      fill: none;
      stroke: rgba(8, 145, 178, 0.24);
      stroke-width: 2;
      stroke-linecap: round;
    }}
    .gate-marker {{
      stroke: rgba(37, 99, 235, 0.48);
      stroke-width: 2;
      fill: rgba(37, 99, 235, 0.82);
    }}
    .road-path {{
      fill: none;
      stroke: rgba(75, 85, 99, 0.48);
      stroke-linecap: round;
    }}
    .destination-marker {{
      fill: rgba(107, 114, 128, 0.18);
      stroke: rgba(75, 85, 99, 0.42);
      stroke-width: 1.5;
    }}
    .crossroads-marker {{
      fill: rgba(217, 119, 6, 0.86);
      stroke: rgba(120, 53, 15, 0.38);
      stroke-width: 2;
    }}
    .climate-band {{
      fill: rgba(220, 38, 38, 0.08);
      stroke: rgba(220, 38, 38, 0.18);
      stroke-width: 1;
    }}
    .architecture-block {{
      fill: rgba(124, 58, 237, 0.78);
      stroke: rgba(76, 29, 149, 0.34);
      stroke-width: 1.5;
    }}
    .landmark-marker {{
      fill: rgba(8, 145, 178, 0.9);
      stroke: rgba(22, 78, 99, 0.42);
      stroke-width: 1.5;
    }}
    .node-count {{
      font-size: 12px;
      font-weight: 740;
      fill: #ffffff;
      text-anchor: middle;
      dominant-baseline: middle;
    }}
    .node-label {{
      font-size: 11px;
      fill: #374151;
      text-anchor: middle;
    }}
    .small-label {{
      font-size: 10px;
      fill: #4b5563;
      text-anchor: middle;
    }}
    .outcome-label {{
      font-size: 11px;
      fill: #374151;
    }}
    h2 {{
      margin: 18px 0 8px;
      font-size: 14px;
    }}
    ul {{
      margin: 0;
      padding-left: 18px;
      color: #4b5563;
      font-size: 13px;
      line-height: 1.45;
    }}
    li + li {{ margin-top: 5px; }}
  </style>
</head>
<body>
  <header>
    <h1>Map Payload</h1>
    <div class="meta">source: {escape(str(payload.get("source", "unknown")))} | episodes: {payload.get("episodes", 0)} | quant: {escape(str(payload.get("timespan_quant", "")))}</div>
  </header>
  <main>
    <section class="stage">
      {svg_markup}
    </section>
    <aside>
      <h2>Compiler Contract</h2>
      <ul>
        <li>kind: {escape(str(payload.get("kind", "")))}</li>
        <li>entities: {len(payload.get("entities", []))}</li>
        <li>links: {len(payload.get("links", []))}</li>
      </ul>
      <h2>Top Districts</h2>
      <ul>{top_districts}</ul>
      <h2>Top Crossroads</h2>
      <ul>{top_crossroads}</ul>
      <h2>Top Roads</h2>
      <ul>{top_roads}</ul>
    </aside>
  </main>
</body>
</html>
"""


def write_html(input_path: Path, output_path: Path) -> Path:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_html(payload), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render map payload JSON to standalone HTML.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    path = write_html(Path(args.input), Path(args.output))
    print(path.as_posix())


def _render_map_svg(payload: dict[str, Any]) -> str:
    width = 1480
    height = 900
    center_x = 680
    center_y = 440
    groups = _group_entities(payload.get("entities", []))
    district_positions = _district_positions(
        groups["district"],
        payload.get("neighbors", []),
        center_x,
        center_y,
        370,
        235,
    )
    svg = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Map payload">',
        f'<rect width="{width}" height="{height}" class="bg" />',
        '<text class="map-title" x="32" y="42">semantic map payload</text>',
        '<text class="zone-label" x="44" y="128">gates</text>',
        '<text class="zone-label" x="1180" y="128">architecture</text>',
        '<text class="zone-label" x="1160" y="548">destinations</text>',
        '<text class="zone-label" x="58" y="814">climate</text>',
    ]
    svg.extend(_render_climates(groups["climate"], width, height))
    svg.extend(_render_clusters(payload.get("clusters", []), district_positions))
    svg.extend(_render_neighbors(payload.get("neighbors", []), district_positions))
    svg.extend(_render_roads(groups["road"], groups["destination"], district_positions, center_x, center_y))
    svg.extend(_render_gates(groups["gate"]))
    svg.extend(_render_architectures(groups["architecture"]))
    svg.extend(_render_districts(groups["district"], district_positions))
    svg.extend(_render_crossroads(groups["crossroads"], district_positions, center_x, center_y))
    svg.extend(_render_landmarks(groups["landmark"], district_positions, center_x, center_y))
    svg.append("</svg>")
    return "".join(svg)


def _render_climates(items: list[dict[str, Any]], width: int, height: int) -> list[str]:
    parts = []
    for index, item in enumerate(items[:5]):
        y = height - 145 + index * 22
        opacity = min(0.2, 0.06 + _weight(item) * 0.14)
        parts.append(
            f'<ellipse class="climate-band" cx="{width / 2:.0f}" cy="{y}" rx="{520 - index * 38}" ry="{68 - index * 7}" opacity="{opacity:.2f}" />'
        )
        parts.append(
            f'<text class="small-label" x="{170 + index * 145}" y="{y + 6}">{escape(_short(str(item.get("label", "")), 18))}</text>'
        )
    return parts


def _render_clusters(
    clusters: list[dict[str, Any]],
    positions: dict[str, tuple[float, float]],
) -> list[str]:
    parts = []
    for cluster in clusters:
        points = [
            positions[member_id]
            for member_id in cluster.get("member_entity_ids", [])
            if member_id in positions
        ]
        if not points:
            continue
        center_x = sum(point[0] for point in points) / len(points)
        center_y = sum(point[1] for point in points) / len(points)
        radius_x = max(abs(point[0] - center_x) for point in points) + 92
        radius_y = max(abs(point[1] - center_y) for point in points) + 74
        parts.append(
            f'<ellipse class="cluster-halo" cx="{center_x:.1f}" cy="{center_y:.1f}" rx="{radius_x:.1f}" ry="{radius_y:.1f}" />'
        )
        parts.append(
            f'<text class="small-label" x="{center_x:.1f}" y="{center_y - radius_y - 10:.1f}">{escape(_short(str(cluster.get("label", "")), 24))}</text>'
        )
    return parts


def _render_neighbors(
    neighbors: list[dict[str, Any]],
    positions: dict[str, tuple[float, float]],
) -> list[str]:
    parts = []
    for neighbor in neighbors:
        if neighbor.get("from") not in positions or neighbor.get("to") not in positions:
            continue
        start_x, start_y = positions[neighbor["from"]]
        end_x, end_y = positions[neighbor["to"]]
        stroke_width = 1 + float(neighbor.get("score", 0)) * 4
        parts.append(
            f'<path class="neighbor-link" d="M {start_x:.1f} {start_y:.1f} L {end_x:.1f} {end_y:.1f}" stroke-width="{stroke_width:.1f}" />'
        )
    return parts


def _render_gates(items: list[dict[str, Any]]) -> list[str]:
    parts = []
    for index, item in enumerate(items[:8]):
        x = 95 + (index % 2) * 95
        y = 180 + index * 68
        count = int(item["metrics"].get("count", 0))
        radius = min(30, 10 + count)
        parts.extend(
            [
                f'<circle class="gate-marker" cx="{x}" cy="{y}" r="{radius}" />',
                f'<text class="node-count" x="{x}" y="{y + 1}">{count}</text>',
                f'<text class="node-label" x="{x}" y="{y + radius + 18}">{escape(_short(str(item.get("label", "")), 16))}</text>',
            ]
        )
    return parts


def _render_architectures(items: list[dict[str, Any]]) -> list[str]:
    parts = []
    for index, item in enumerate(items[:8]):
        x = 1130 + (index % 2) * 118
        y = 175 + (index // 2) * 86
        count = int(item["metrics"].get("count", 0))
        block_height = min(58, 18 + count * 4)
        parts.extend(
            [
                f'<rect class="architecture-block" x="{x}" y="{y - block_height}" width="74" height="{block_height}" rx="4" />',
                f'<text class="node-count" x="{x + 37}" y="{y - block_height / 2 + 4:.1f}">{count}</text>',
                f'<text class="node-label" x="{x + 37}" y="{y + 18}">{escape(_short(str(item.get("label", "")), 16))}</text>',
            ]
        )
    return parts


def _render_districts(items: list[dict[str, Any]], positions: dict[str, tuple[float, float]]) -> list[str]:
    parts = []
    for item in items:
        x, y = positions[item["id"]]
        count = int(item["metrics"].get("count", 0))
        recurrence = int(item["metrics"].get("recurrence_weeks", 0))
        radius = min(62, 22 + count * 6 + recurrence * 3)
        parts.extend(
            [
                f'<circle class="district-area" cx="{x:.1f}" cy="{y:.1f}" r="{radius}" />',
                f'<text class="node-count" x="{x:.1f}" y="{y - 3:.1f}">{count}</text>',
                f'<text class="node-label" x="{x:.1f}" y="{y + radius + 16:.1f}">{escape(_short(str(item.get("label", "")), 24))}</text>',
            ]
        )
    return parts


def _render_roads(
    roads: list[dict[str, Any]],
    destinations: list[dict[str, Any]],
    positions: dict[str, tuple[float, float]],
    center_x: int,
    center_y: int,
) -> list[str]:
    parts = []
    district_points = list(positions.values()) or [(center_x, center_y)]
    destination_y = {item["id"]: 475 + index * 48 for index, item in enumerate(destinations[:10])}
    for item in destinations[:10]:
        y = destination_y[item["id"]]
        parts.append(f'<rect class="destination-marker" x="1146" y="{y - 18}" width="180" height="30" rx="8" />')
        parts.append(
            f'<text class="outcome-label" x="1160" y="{y + 4}">{escape(_short(str(item.get("label", "")), 26))}</text>'
        )
    for index, road in enumerate(roads[:12]):
        target_y = 475 + (index % max(1, min(10, len(destinations)))) * 48
        target_x = 1146
        start_x, start_y = district_points[index % len(district_points)]
        control_x = (start_x + target_x) / 2 + 45
        control_y = min(start_y, target_y) - 70
        stroke_width = 1.5 + _weight(road) * 9
        parts.append(
            f'<path class="road-path" d="M {start_x:.1f} {start_y:.1f} Q {control_x:.1f} {control_y:.1f} {target_x} {target_y}" stroke-width="{stroke_width:.1f}" />'
        )
    return parts


def _render_crossroads(
    items: list[dict[str, Any]],
    positions: dict[str, tuple[float, float]],
    center_x: int,
    center_y: int,
) -> list[str]:
    parts = []
    district_points = list(positions.values()) or [(center_x, center_y)]
    for index, item in enumerate(items[:12]):
        base_x, base_y = district_points[index % len(district_points)]
        x = (base_x + center_x) / 2
        y = (base_y + center_y) / 2
        count = int(item["metrics"].get("count", 0))
        radius = min(28, 8 + count * 2)
        parts.extend(
            [
                f'<polygon class="crossroads-marker" points="{_diamond_points(x, y, radius)}" />',
                f'<text class="node-count" x="{x:.1f}" y="{y + 1:.1f}">{count}</text>',
            ]
        )
    return parts


def _render_landmarks(
    items: list[dict[str, Any]],
    positions: dict[str, tuple[float, float]],
    center_x: int,
    center_y: int,
) -> list[str]:
    parts = []
    district_points = list(positions.values()) or [(center_x, center_y)]
    for index, item in enumerate(items[:12]):
        base_x, base_y = district_points[index % len(district_points)]
        x = base_x + 34
        y = base_y - 34
        parts.extend(
            [
                f'<polygon class="landmark-marker" points="{_star_points(x, y, 13, 6)}" />',
                f'<text class="small-label" x="{x}" y="{y - 17}">{escape(_short(str(item.get("label", "")), 18))}</text>',
            ]
        )
    return parts


def _group_entities(entities: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = {entity_type: [] for entity_type in ENTITY_ORDER}
    for entity in entities:
        groups.setdefault(str(entity.get("type", "")), []).append(entity)
    for items in groups.values():
        items.sort(key=lambda item: (-item["metrics"].get("count", 0), str(item.get("label", "")), str(item.get("id", ""))))
    return groups


def _ellipse_positions(
    items: list[dict[str, Any]],
    center_x: int,
    center_y: int,
    radius_x: int,
    radius_y: int,
) -> dict[str, tuple[float, float]]:
    positions = {}
    count = max(1, len(items))
    for index, item in enumerate(items):
        angle = -math.pi / 2 + (2 * math.pi * index / count)
        positions[item["id"]] = (
            center_x + math.cos(angle) * radius_x,
            center_y + math.sin(angle) * radius_y,
        )
    return positions


def _district_positions(
    districts: list[dict[str, Any]],
    neighbors: list[dict[str, Any]],
    center_x: int,
    center_y: int,
    radius_x: int,
    radius_y: int,
) -> dict[str, tuple[float, float]]:
    if not districts:
        return {}
    if len(districts) == 1:
        return {districts[0]["id"]: (center_x, center_y)}

    district_ids = {district["id"] for district in districts}
    usable_neighbors = sorted(
        (
            neighbor
            for neighbor in neighbors
            if neighbor.get("from") in district_ids and neighbor.get("to") in district_ids
        ),
        key=lambda neighbor: str(neighbor.get("id", "")),
    )
    if not usable_neighbors:
        return _ellipse_positions(districts, center_x, center_y, radius_x, radius_y)

    iterations = 80
    repulsion = 1200.0
    spring = 0.015
    damping = 0.82
    min_dist = 1e-6
    positions = _ellipse_positions(districts, center_x, center_y, radius_x, radius_y)
    velocities = {district["id"]: (0.0, 0.0) for district in districts}
    ordered_ids = [district["id"] for district in districts]

    for _ in range(iterations):
        forces = {district_id: (0.0, 0.0) for district_id in ordered_ids}
        for left_index, left_id in enumerate(ordered_ids):
            for right_id in ordered_ids[left_index + 1 :]:
                left_x, left_y = positions[left_id]
                right_x, right_y = positions[right_id]
                dx = left_x - right_x
                dy = left_y - right_y
                distance = max(math.hypot(dx, dy), min_dist)
                force = repulsion / (distance * distance)
                fx = (dx / distance) * force
                fy = (dy / distance) * force
                forces[left_id] = (forces[left_id][0] + fx, forces[left_id][1] + fy)
                forces[right_id] = (forces[right_id][0] - fx, forces[right_id][1] - fy)

        for neighbor in usable_neighbors:
            left_id = str(neighbor["from"])
            right_id = str(neighbor["to"])
            left_x, left_y = positions[left_id]
            right_x, right_y = positions[right_id]
            dx = right_x - left_x
            dy = right_y - left_y
            distance = max(math.hypot(dx, dy), min_dist)
            score = float(neighbor.get("score", 0))
            target = 260 - score * 140
            force = (distance - target) * spring
            fx = (dx / distance) * force
            fy = (dy / distance) * force
            forces[left_id] = (forces[left_id][0] + fx, forces[left_id][1] + fy)
            forces[right_id] = (forces[right_id][0] - fx, forces[right_id][1] - fy)

        for district_id in ordered_ids:
            vx, vy = velocities[district_id]
            fx, fy = forces[district_id]
            vx = (vx + fx) * damping
            vy = (vy + fy) * damping
            x, y = positions[district_id]
            positions[district_id] = _clamp_to_ellipse(
                x + vx,
                y + vy,
                center_x,
                center_y,
                radius_x,
                radius_y,
            )
            velocities[district_id] = (vx, vy)

    return positions


def _clamp_to_ellipse(
    x: float,
    y: float,
    center_x: int,
    center_y: int,
    radius_x: int,
    radius_y: int,
) -> tuple[float, float]:
    dx = x - center_x
    dy = y - center_y
    distance = (dx * dx) / (radius_x * radius_x) + (dy * dy) / (radius_y * radius_y)
    if distance <= 1:
        return x, y
    scale = 1 / math.sqrt(distance)
    return center_x + dx * scale, center_y + dy * scale


def _list_items(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<li>none</li>"
    return "\n".join(
        f"<li>{escape(str(item.get('label', item.get('id', ''))))}: {int(item['metrics'].get('count', 0))}</li>"
        for item in items
    )


def _weight(item: dict[str, Any]) -> float:
    return float(item.get("metrics", {}).get("weight", 0))


def _diamond_points(x: float, y: float, r: float) -> str:
    return f"{x:.1f},{y-r:.1f} {x+r:.1f},{y:.1f} {x:.1f},{y+r:.1f} {x-r:.1f},{y:.1f}"


def _star_points(x: float, y: float, outer: float, inner: float) -> str:
    points = []
    for index in range(10):
        angle = -math.pi / 2 + index * math.pi / 5
        radius = outer if index % 2 == 0 else inner
        points.append(f"{x + math.cos(angle) * radius:.1f},{y + math.sin(angle) * radius:.1f}")
    return " ".join(points)


def _short(value: str, limit: int = 26) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "..."


if __name__ == "__main__":
    main()
