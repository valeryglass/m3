from __future__ import annotations

import argparse
import json
import math
from html import escape
from pathlib import Path
from typing import Any


WIDTH = 1480
HEIGHT = 900
CENTER_X = 680
CENTER_Y = 440
DISTRICT_RADIUS_X = 370
DISTRICT_RADIUS_Y = 235
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
LAYER_CONTROLS = (
    ("climate", "Climate"),
    ("clusters", "Clusters"),
    ("neighbors", "Neighbor links"),
    ("roads", "Roads"),
    ("destinations", "Destinations"),
    ("gates", "Gates"),
    ("districts", "Districts"),
    ("architecture", "Architecture"),
    ("crossroads", "Crossroads"),
    ("landmarks", "Landmarks"),
)


def render_html(payload: dict[str, Any]) -> str:
    svg_markup = _render_map_svg(payload)
    groups = _group_entities(payload.get("entities", []))
    top_districts = _list_items(groups["district"][:8])
    top_crossroads = _list_items(groups["crossroads"][:8])
    top_roads = _list_items(groups["road"][:8])
    layer_controls = "\n".join(
        (
            f'<label class="layer-control"><input type="checkbox" '
            f'data-layer-toggle value="{layer}" checked> {escape(label)}</label>'
        )
        for layer, label in LAYER_CONTROLS
    )

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
    svg [data-layer][data-hidden="true"] {{ display: none; }}
    .bg {{ fill: #fbfaf7; }}
    .map-title {{
      font-size: 17px;
      font-weight: 760;
      fill: #1f2937;
    }}
    .layer-controls {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px 10px;
      margin: 8px 0 18px;
    }}
    .layer-control {{
      font-size: 12px;
      color: #475467;
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
    .gate-entry-path {{
      fill: none;
      stroke: rgba(37, 99, 235, 0.22);
      stroke-width: 2;
      stroke-dasharray: 5 6;
    }}
    .gate-marker {{
      stroke: rgba(37, 99, 235, 0.55);
      stroke-width: 2;
      fill: rgba(37, 99, 235, 0.86);
    }}
    .road-path {{
      fill: none;
      stroke: rgba(75, 85, 99, 0.48);
      stroke-linecap: round;
    }}
    .destination-marker {{
      fill: rgba(107, 114, 128, 0.22);
      stroke: rgba(75, 85, 99, 0.5);
      stroke-width: 1.5;
    }}
    .destination-short-term {{ fill: rgba(245, 158, 11, 0.72); }}
    .destination-long-term {{ fill: rgba(99, 102, 241, 0.72); }}
    .destination-unknown {{ fill: rgba(100, 116, 139, 0.62); }}
    .crossroads-marker {{
      fill: rgba(217, 119, 6, 0.86);
      stroke: rgba(120, 53, 15, 0.38);
      stroke-width: 2;
    }}
    .climate-band {{
      stroke-width: 1;
      mix-blend-mode: multiply;
    }}
    .architecture-block {{
      stroke: rgba(76, 29, 149, 0.34);
      stroke-width: 1.2;
    }}
    .architecture-segment {{
      opacity: 0.86;
    }}
    .architecture-wedge {{
      pointer-events: none;
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
      text-anchor: middle;
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
      <h2>Layers</h2>
      <div class="layer-controls">{layer_controls}</div>
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
  <script>
    document.querySelectorAll('[data-layer-toggle]').forEach((control) => {{
      control.addEventListener('change', () => {{
        document.querySelectorAll(`[data-layer="${{control.value}}"]`).forEach((layer) => {{
          layer.dataset.hidden = control.checked ? 'false' : 'true';
        }});
      }});
    }});
  </script>
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
    entities = payload.get("entities", [])
    links = payload.get("links", [])
    groups = _group_entities(entities)
    district_positions = _district_positions(
        groups["district"],
        payload.get("neighbors", []),
        CENTER_X,
        CENTER_Y,
        DISTRICT_RADIUS_X,
        DISTRICT_RADIUS_Y,
    )
    districts_by_id = {str(item["id"]): item for item in groups["district"]}
    road_sources = _sources_by_target_with_support(links, "district_to_road")
    destinations_by_id = {str(item["id"]): item for item in groups["destination"]}
    destination_positions = _destination_positions(
        groups["destination"],
        links,
        road_sources,
        district_positions,
        WIDTH,
        HEIGHT,
    )
    road_parts, destination_parts = _render_roads_and_destinations(
        groups["road"],
        groups["destination"],
        links,
        road_sources,
        destination_positions,
        district_positions,
        districts_by_id,
    )
    district_parts, architecture_parts = _render_districts_and_architecture(
        groups["district"],
        groups["architecture"],
        links,
        district_positions,
    )

    svg = [
        f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="Map payload">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" class="bg" />',
        '<text class="map-title" x="32" y="42">semantic map payload</text>',
        _layer("climate", _render_climates(groups["climate"], links, district_positions)),
        _layer("clusters", _render_clusters(payload.get("clusters", []), district_positions)),
        _layer("neighbors", _render_neighbors(payload.get("neighbors", []), district_positions)),
        _layer("roads", road_parts),
        _layer("destinations", destination_parts),
        _layer("gates", _render_gates(groups["gate"], links, district_positions)),
        _layer("districts", district_parts),
        _layer("architecture", architecture_parts),
        _layer("crossroads", _render_crossroads(groups["crossroads"], district_positions)),
        _layer("landmarks", _render_landmarks(groups["landmark"], district_positions)),
        "</svg>",
    ]
    return "".join(svg)


def _layer(layer_id: str, parts: list[str]) -> str:
    return f'<g data-layer="{layer_id}" data-hidden="false">{"".join(parts)}</g>'


def _render_climates(
    items: list[dict[str, Any]],
    links: list[dict[str, Any]],
    district_positions: dict[str, tuple[float, float]],
) -> list[str]:
    parts: list[str] = []
    linked_districts = _targets_by_source(links, "climate_to_district")
    for index, item in enumerate(items[:8]):
        item_id = str(item.get("id", ""))
        positions = [
            district_positions[district_id]
            for district_id in linked_districts.get(item_id, [])
            if district_id in district_positions
        ]
        if positions:
            x = sum(point[0] for point in positions) / len(positions)
            y = sum(point[1] for point in positions) / len(positions)
            spread = max(
                [math.hypot(point[0] - x, point[1] - y) for point in positions] + [80]
            )
            rx = min(390, 150 + spread + _weight(item) * 95)
            ry = min(250, 95 + spread * 0.48 + _weight(item) * 55)
        else:
            angle = -math.pi / 2 + index * math.pi / max(1, len(items[:8]))
            x = CENTER_X + math.cos(angle) * 120
            y = CENTER_Y + math.sin(angle) * 80
            rx = 260 - index * 10
            ry = 160 - index * 6
        fill, stroke = _climate_palette(str(item.get("label", "")))
        opacity = min(0.34, 0.18 + _weight(item) * 0.16)
        parts.append(
            f'<ellipse class="climate-band climate-field" cx="{x:.1f}" cy="{y:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="{fill}" stroke="{stroke}" opacity="{opacity:.2f}" />'
        )
        parts.append(
            f'<text class="small-label" x="{x:.1f}" y="{y - ry - 8:.1f}">{escape(_short(str(item.get("label", "")), 18))}</text>'
        )
    return parts


def _render_clusters(
    clusters: list[dict[str, Any]],
    positions: dict[str, tuple[float, float]],
) -> list[str]:
    parts: list[str] = []
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
    parts: list[str] = []
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


def _render_gates(
    items: list[dict[str, Any]],
    links: list[dict[str, Any]],
    district_positions: dict[str, tuple[float, float]],
) -> list[str]:
    parts: list[str] = []
    linked_districts = _targets_by_source(links, "gate_to_district")
    for index, item in enumerate(items[:10]):
        item_id = str(item.get("id", ""))
        district_ids = linked_districts.get(item_id, [])
        district_points = [
            district_positions[district_id]
            for district_id in district_ids
            if district_id in district_positions
        ]
        if district_points:
            anchor_x = sum(point[0] for point in district_points) / len(district_points)
            anchor_y = sum(point[1] for point in district_points) / len(district_points)
            x, y = _territory_border_point(anchor_x, anchor_y)
        else:
            angle = -math.pi + (index + 0.5) * (2 * math.pi / max(1, len(items[:10])))
            x = CENTER_X + math.cos(angle) * (DISTRICT_RADIUS_X + 115)
            y = CENTER_Y + math.sin(angle) * (DISTRICT_RADIUS_Y + 90)
            x = _clamp(x, 48, WIDTH - 48)
            y = _clamp(y, 72, HEIGHT - 48)
            district_points = [min(district_positions.values(), key=lambda p: _distance((x, y), p))] if district_positions else []
        count = int(item.get("metrics", {}).get("count", 0))
        radius = min(30, 10 + count)
        for district_x, district_y in district_points[:3]:
            parts.append(
                f'<path class="gate-entry-path" d="M {x:.1f} {y:.1f} L {district_x:.1f} {district_y:.1f}" />'
            )
        parts.extend(
            [
                f'<circle class="gate-marker" cx="{x:.1f}" cy="{y:.1f}" r="{radius}" />',
                f'<text class="node-count" x="{x:.1f}" y="{y + 1:.1f}">{count}</text>',
                f'<text class="node-label" x="{x:.1f}" y="{y + radius + 18:.1f}">{escape(_short(str(item.get("label", "")), 16))}</text>',
            ]
        )
    return parts


def _render_roads_and_destinations(
    roads: list[dict[str, Any]],
    destinations: list[dict[str, Any]],
    links: list[dict[str, Any]],
    road_sources: dict[str, list[tuple[str, float]]],
    destination_positions: dict[str, tuple[float, float]],
    district_positions: dict[str, tuple[float, float]],
    districts_by_id: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str]]:
    road_parts: list[str] = []
    destination_parts: list[str] = []
    road_by_id = {str(item.get("id", "")): item for item in roads}
    destination_by_id = {str(item.get("id", "")): item for item in destinations}

    for link in sorted(
        (link for link in links if link.get("type") == "road_to_destination"),
        key=lambda item: (
            str(item.get("from", "")),
            str(item.get("to", "")),
            str(item.get("id", "")),
        ),
    ):
        road_id = str(link.get("from", ""))
        destination_id = str(link.get("to", ""))
        if destination_id not in destination_positions:
            continue
        destination_x, destination_y = destination_positions[destination_id]
        sources = _road_start_sources(road_id, road_sources, district_positions, destination_x, destination_y)
        for district_id, _support in sources:
            if district_id not in district_positions:
                continue
            district_x, district_y = district_positions[district_id]
            radius = _district_radius(districts_by_id.get(district_id, {}))
            start_x, start_y = _district_boundary_point(
                district_x,
                district_y,
                radius,
                destination_x,
                destination_y,
            )
            control_x = (start_x + destination_x) / 2
            control_y = min(start_y, destination_y) - 62
            stroke_width = 1.5 + _weight(road_by_id.get(road_id, {})) * 7
            road_parts.append(
                f'<path class="road-path" d="M {start_x:.1f} {start_y:.1f} Q {control_x:.1f} {control_y:.1f} {destination_x:.1f} {destination_y:.1f}" stroke-width="{stroke_width:.1f}" />'
            )

    for item in sorted(destinations, key=_entity_sort_key)[:12]:
        item_id = str(item.get("id", ""))
        if item_id not in destination_positions:
            continue
        x, y = destination_positions[item_id]
        horizon = _destination_horizon(item)
        css = {
            "short_term": "destination-short-term",
            "long_term": "destination-long-term",
        }.get(horizon, "destination-unknown")
        radius = 12 + min(8, _count(item))
        destination_parts.append(
            f'<polygon class="destination-marker destination-poi {css}" points="{_triangle_points(x, y, radius)}" data-horizon="{escape(horizon)}" />'
        )
        destination_parts.append(
            f'<text class="outcome-label" x="{x:.1f}" y="{y + radius + 16:.1f}">{escape(_short(str(item.get("label", "")), 24))}</text>'
        )
    return road_parts, destination_parts


def _render_districts_and_architecture(
    districts: list[dict[str, Any]],
    architectures: list[dict[str, Any]],
    links: list[dict[str, Any]],
    positions: dict[str, tuple[float, float]],
) -> tuple[list[str], list[str]]:
    district_parts: list[str] = []
    architecture_parts: list[str] = []
    architectures_by_id = {str(item.get("id", "")): item for item in architectures}
    by_district = _architectures_by_district(links, architectures_by_id)
    for item in districts:
        x, y = positions[item["id"]]
        radius = _district_radius(item)
        district_parts.extend(
            [
                f'<circle class="district-area" cx="{x:.1f}" cy="{y:.1f}" r="{radius}" />',
                f'<text class="node-count" x="{x:.1f}" y="{y - 3:.1f}">{_count(item)}</text>',
                f'<text class="node-label" x="{x:.1f}" y="{y + radius + 16:.1f}">{escape(_short(str(item.get("label", "")), 24))}</text>',
            ]
        )
        architecture_parts.extend(
            _render_architecture_segments(x, y, radius, by_district.get(str(item["id"]), []))
        )
    return district_parts, architecture_parts


def _render_architecture_segments(
    x: float,
    y: float,
    district_radius: float,
    items: list[tuple[dict[str, Any], float]],
) -> list[str]:
    if not items:
        return []
    total = sum(support for _item, support in items) or 1.0
    parts: list[str] = []
    start = -math.pi / 2
    radius = district_radius * 0.56
    for item, support in items[:6]:
        proportion = support / total
        end = start + proportion * math.tau
        fill = _architecture_fill(proportion)
        parts.append(
            f'<path class="architecture-block architecture-segment architecture-wedge" d="{_sector_path(x, y, radius, start, end)}" data-proportion="{proportion:.2f}" fill="{fill}" />'
        )
        start = end
    return parts


def _render_crossroads(
    items: list[dict[str, Any]],
    positions: dict[str, tuple[float, float]],
) -> list[str]:
    parts: list[str] = []
    district_points = list(positions.values()) or [(CENTER_X, CENTER_Y)]
    for index, item in enumerate(items[:12]):
        base_x, base_y = district_points[index % len(district_points)]
        x = (base_x + CENTER_X) / 2
        y = (base_y + CENTER_Y) / 2
        radius = min(28, 8 + _count(item) * 2)
        parts.extend(
            [
                f'<polygon class="crossroads-marker" points="{_diamond_points(x, y, radius)}" />',
                f'<text class="node-count" x="{x:.1f}" y="{y + 1:.1f}">{_count(item)}</text>',
            ]
        )
    return parts


def _render_landmarks(
    items: list[dict[str, Any]],
    positions: dict[str, tuple[float, float]],
) -> list[str]:
    parts: list[str] = []
    district_points = list(positions.values()) or [(CENTER_X, CENTER_Y)]
    for index, item in enumerate(items[:12]):
        base_x, base_y = district_points[index % len(district_points)]
        x = base_x + 34
        y = base_y - 34
        parts.extend(
            [
                f'<polygon class="landmark-marker" points="{_star_points(x, y, 13, 6)}" />',
                f'<text class="small-label" x="{x:.1f}" y="{y - 17:.1f}">{escape(_short(str(item.get("label", "")), 18))}</text>',
            ]
        )
    return parts


def _destination_positions(
    destinations: list[dict[str, Any]],
    links: list[dict[str, Any]],
    road_sources: dict[str, list[tuple[str, float]]],
    district_positions: dict[str, tuple[float, float]],
    width: int,
    height: int,
) -> dict[str, tuple[float, float]]:
    road_to_destinations = _sources_by_target_with_support(links, "road_to_destination")
    positions: dict[str, tuple[float, float]] = {}
    placed: list[tuple[float, float]] = []
    for item in sorted(destinations, key=_entity_sort_key)[:12]:
        item_id = str(item.get("id", ""))
        source_points: list[tuple[float, float, float]] = []
        for road_id, road_support in road_to_destinations.get(item_id, []):
            for district_id, district_support in road_sources.get(road_id, []):
                if district_id in district_positions:
                    weight = max(road_support, 0.1) * max(district_support, 0.1)
                    x, y = district_positions[district_id]
                    source_points.append((x, y, weight))
        if source_points:
            total = sum(point[2] for point in source_points)
            anchor_x = sum(point[0] * point[2] for point in source_points) / total
            anchor_y = sum(point[1] * point[2] for point in source_points) / total
        elif district_positions:
            anchor_x = sum(point[0] for point in district_positions.values()) / len(district_positions)
            anchor_y = sum(point[1] for point in district_positions.values()) / len(district_positions)
        else:
            anchor_x, anchor_y = CENTER_X, CENTER_Y

        identity_x, identity_y = _identity_vector(item)
        outward_x, outward_y = _unit(anchor_x - CENTER_X, anchor_y - CENTER_Y)
        if outward_x == 0 and outward_y == 0:
            outward_x, outward_y = identity_x, identity_y
        vector_x, vector_y = _unit(outward_x * 0.72 + identity_x * 0.42, outward_y * 0.72 + identity_y * 0.42)
        distance = _destination_distance(_destination_horizon(item))
        x = anchor_x + vector_x * distance
        y = anchor_y + vector_y * distance
        for attempt in range(6):
            if all(_distance((x, y), existing) >= 42 for existing in placed):
                break
            nudge_x, nudge_y = _identity_vector(item, salt=f"nudge-{attempt}")
            x += nudge_x * (18 + attempt * 8)
            y += nudge_y * (18 + attempt * 8)
        x = _clamp(x, 44, width - 44)
        y = _clamp(y, 64, height - 44)
        positions[item_id] = (x, y)
        placed.append((x, y))
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


def _group_entities(entities: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = {entity_type: [] for entity_type in ENTITY_ORDER}
    for entity in entities:
        groups.setdefault(str(entity.get("type", "")), []).append(entity)
    for items in groups.values():
        items.sort(key=_entity_sort_key)
    return groups


def _architectures_by_district(
    links: list[dict[str, Any]],
    architectures_by_id: dict[str, dict[str, Any]],
) -> dict[str, list[tuple[dict[str, Any], float]]]:
    by_district: dict[str, list[tuple[dict[str, Any], float]]] = {}
    for link in links:
        if link.get("type") != "architecture_to_district":
            continue
        architecture_id = str(link.get("from", ""))
        district_id = str(link.get("to", ""))
        if architecture_id not in architectures_by_id:
            continue
        by_district.setdefault(district_id, []).append(
            (architectures_by_id[architecture_id], _link_support(link))
        )
    for items in by_district.values():
        items.sort(key=lambda item: (-item[1], str(item[0].get("label", "")), str(item[0].get("id", ""))))
    return by_district


def _targets_by_source(
    links: list[dict[str, Any]],
    link_type: str,
) -> dict[str, list[str]]:
    targets: dict[str, list[str]] = {}
    for link in links:
        if link.get("type") == link_type:
            targets.setdefault(str(link.get("from", "")), []).append(str(link.get("to", "")))
    for values in targets.values():
        values.sort()
    return targets


def _sources_by_target_with_support(
    links: list[dict[str, Any]],
    link_type: str,
) -> dict[str, list[tuple[str, float]]]:
    sources: dict[str, list[tuple[str, float]]] = {}
    for link in links:
        if link.get("type") == link_type:
            sources.setdefault(str(link.get("to", "")), []).append(
                (str(link.get("from", "")), _link_support(link))
            )
    for values in sources.values():
        values.sort(key=lambda item: (-item[1], item[0]))
    return sources


def _road_start_sources(
    road_id: str,
    road_sources: dict[str, list[tuple[str, float]]],
    district_positions: dict[str, tuple[float, float]],
    destination_x: float,
    destination_y: float,
) -> list[tuple[str, float]]:
    sources = [
        item
        for item in road_sources.get(road_id, [])
        if item[0] in district_positions
    ][:3]
    if sources:
        return sources
    if not district_positions:
        return []
    nearest = min(
        district_positions,
        key=lambda district_id: _distance(
            district_positions[district_id],
            (destination_x, destination_y),
        ),
    )
    return [(nearest, 1.0)]


def _district_boundary_point(
    district_x: float,
    district_y: float,
    radius: float,
    destination_x: float,
    destination_y: float,
) -> tuple[float, float]:
    dx, dy = _unit(destination_x - district_x, destination_y - district_y)
    if dx == 0 and dy == 0:
        dx, dy = 1.0, 0.0
    return district_x + dx * radius, district_y + dy * radius


def _territory_border_point(anchor_x: float, anchor_y: float) -> tuple[float, float]:
    dx, dy = _unit(anchor_x - CENTER_X, anchor_y - CENTER_Y)
    if dx == 0 and dy == 0:
        dx, dy = -1.0, 0.0
    x = CENTER_X + dx * (DISTRICT_RADIUS_X + 118)
    y = CENTER_Y + dy * (DISTRICT_RADIUS_Y + 100)
    return _clamp(x, 42, WIDTH - 42), _clamp(y, 64, HEIGHT - 42)


def _district_radius(item: dict[str, Any]) -> float:
    count = _count(item)
    recurrence = int(item.get("metrics", {}).get("recurrence_weeks", 0))
    return float(min(62, 22 + count * 6 + recurrence * 3))


def _destination_horizon(item: dict[str, Any]) -> str:
    signature = item.get("signature", {})
    if isinstance(signature, dict):
        horizon = signature.get("horizon")
        if isinstance(horizon, str) and horizon:
            return horizon
    label = str(item.get("label", ""))
    if label.startswith("short_term"):
        return "short_term"
    if label.startswith("long_term"):
        return "long_term"
    return "unknown"


def _destination_distance(horizon: str) -> float:
    if horizon == "short_term":
        return 74.0
    if horizon == "long_term":
        return 168.0
    return 116.0


def _identity_vector(item: dict[str, Any], *, salt: str = "") -> tuple[float, float]:
    signature = item.get("signature", {})
    parts: list[str] = []
    if isinstance(signature, dict):
        parts.extend(
            str(signature.get(key, ""))
            for key in ("horizon", "outcome")
            if signature.get(key)
        )
    parts.extend([str(item.get("label", "")), str(item.get("id", "")), salt])
    value = "|".join(parts)
    angle = (_stable_hash(value) % 3600) / 3600 * math.tau
    return math.cos(angle), math.sin(angle)


def _climate_palette(label: str) -> tuple[str, str]:
    normalized = label.lower()
    palettes = [
        (("fear", "страх", "тревог"), "rgba(37, 99, 235, 0.86)", "rgba(30, 64, 175, 0.42)"),
        (("shame", "стыд", "смущ"), "rgba(219, 39, 119, 0.86)", "rgba(157, 23, 77, 0.42)"),
        (("anger", "злость", "гнев", "rage"), "rgba(220, 38, 38, 0.88)", "rgba(153, 27, 27, 0.44)"),
        (("joy", "радость", "happy"), "rgba(245, 158, 11, 0.88)", "rgba(180, 83, 9, 0.42)"),
        (("sad", "грусть", "печаль"), "rgba(79, 70, 229, 0.84)", "rgba(55, 48, 163, 0.42)"),
        (("love", "любов", "тепло", "warm"), "rgba(244, 63, 94, 0.84)", "rgba(190, 18, 60, 0.42)"),
        (("disgust", "отвращ", "брезг"), "rgba(22, 163, 74, 0.84)", "rgba(21, 128, 61, 0.42)"),
        (("neutral", "нейтраль", "mixed", "смеш"), "rgba(20, 184, 166, 0.78)", "rgba(15, 118, 110, 0.38)"),
    ]
    for needles, fill, stroke in palettes:
        if any(needle in normalized for needle in needles):
            return fill, stroke
    hue = _stable_hash(label) % 360
    return f"hsla({hue}, 72%, 53%, 0.78)", f"hsla({hue}, 68%, 34%, 0.38)"


def _architecture_fill(proportion: float) -> str:
    value = _clamp(proportion, 0.0, 1.0)
    red = round(196 - value * 78)
    green = round(181 - value * 95)
    blue = round(253 - value * 46)
    return f"rgb({red}, {green}, {blue})"


def _sector_path(
    x: float,
    y: float,
    radius: float,
    start: float,
    end: float,
) -> str:
    if end - start >= math.tau:
        end = start + math.tau - 0.001
    start_x = x + math.cos(start) * radius
    start_y = y + math.sin(start) * radius
    end_x = x + math.cos(end) * radius
    end_y = y + math.sin(end) * radius
    large = 1 if end - start > math.pi else 0
    return (
        f"M {x:.1f} {y:.1f} L {start_x:.1f} {start_y:.1f} "
        f"A {radius:.1f} {radius:.1f} 0 {large} 1 {end_x:.1f} {end_y:.1f} Z"
    )


def _triangle_points(x: float, y: float, radius: float) -> str:
    return " ".join(
        f"{x + math.cos(angle) * radius:.1f},{y + math.sin(angle) * radius:.1f}"
        for angle in (-math.pi / 2, math.pi / 6, 5 * math.pi / 6)
    )


def _diamond_points(x: float, y: float, radius: float) -> str:
    return f"{x:.1f},{y-radius:.1f} {x+radius:.1f},{y:.1f} {x:.1f},{y+radius:.1f} {x-radius:.1f},{y:.1f}"


def _star_points(x: float, y: float, outer: float, inner: float) -> str:
    points = []
    for index in range(10):
        angle = -math.pi / 2 + index * math.pi / 5
        radius = outer if index % 2 == 0 else inner
        points.append(f"{x + math.cos(angle) * radius:.1f},{y + math.sin(angle) * radius:.1f}")
    return " ".join(points)


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


def _link_support(link: dict[str, Any]) -> float:
    provenance = link.get("provenance", {})
    if isinstance(provenance, dict):
        episode_ids = provenance.get("episode_ids")
        if isinstance(episode_ids, list) and episode_ids:
            return float(len(episode_ids))
    try:
        return float(link.get("weight", 0))
    except (TypeError, ValueError):
        return 0.0


def _count(item: dict[str, Any]) -> int:
    try:
        return int(item.get("metrics", {}).get("count", 0))
    except (TypeError, ValueError):
        return 0


def _weight(item: dict[str, Any]) -> float:
    try:
        return float(item.get("metrics", {}).get("weight", 0))
    except (TypeError, ValueError):
        return 0.0


def _entity_sort_key(item: dict[str, Any]) -> tuple[int, str, str]:
    return (-_count(item), str(item.get("label", "")), str(item.get("id", "")))


def _unit(x: float, y: float) -> tuple[float, float]:
    length = math.hypot(x, y)
    if length == 0:
        return 0.0, 0.0
    return x / length, y / length


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _stable_hash(value: str) -> int:
    total = 0
    for char in value:
        total = (total * 131 + ord(char)) % 1_000_003
    return total


def _list_items(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<li>none</li>"
    return "\n".join(
        f"<li>{escape(str(item.get('label', item.get('id', ''))))}: {_count(item)}</li>"
        for item in items
    )


def _short(value: str, limit: int = 26) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "..."


if __name__ == "__main__":
    main()
