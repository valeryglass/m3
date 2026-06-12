from __future__ import annotations

"""Diagnostic HTML/SVG preview renderer for hex-world artifacts.

This module consumes the renderer-neutral JSON shape produced by
``app.hex_world.hex_world_to_dict``. It is intentionally diagnostic: it helps
inspect cells, ownership, paths, anchors, fields, and optional boundaries
without changing semantic compilation or the existing map payload renderer.
"""

import argparse
import hashlib
import json
import math
from html import escape
from pathlib import Path
from typing import Any


DEFAULT_CELL_SIZE = 28.0
SVG_PADDING = 72.0


def render_html(world: dict[str, Any], show_boundaries: bool = False) -> str:
    cells = _list_section(world, "cells")
    regions = _list_section(world, "regions")
    paths = _list_section(world, "paths")
    fields = _list_section(world, "fields")
    anchors = _list_section(world, "anchors")
    boundaries = _list_section(world, "boundaries")

    grid = world.get("grid", {}) or {}
    cell_size = _safe_float(grid.get("cell_size"), DEFAULT_CELL_SIZE)
    cell_by_id = {str(cell.get("id") or ""): cell for cell in cells}
    region_by_id = {str(region.get("id") or ""): region for region in regions}
    bounds = _svg_bounds(cells, cell_size)
    owned_count = sum(1 for cell in cells if cell.get("owner_id"))

    summary_items = {
        "source": str(world.get("source") or "unknown"),
        "cells": len(cells),
        "owned cells": owned_count,
        "regions": len(regions),
        "paths": len(paths),
        "fields": len(fields),
        "anchors": len(anchors),
        "boundaries": len(boundaries),
    }

    svg = _render_svg(
        cells=cells,
        regions=regions,
        paths=paths,
        fields=fields,
        anchors=anchors,
        boundaries=boundaries,
        cell_by_id=cell_by_id,
        region_by_id=region_by_id,
        cell_size=cell_size,
        bounds=bounds,
        show_boundaries=show_boundaries,
    )
    summary = "\n".join(
        f"<li><span>{escape(label)}</span><strong>{escape(str(value))}</strong></li>"
        for label, value in summary_items.items()
    )

    title = f"Hex World Preview - {summary_items['source']}"
    boundary_state = "shown" if show_boundaries else "hidden"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    body {{
      margin: 0;
      background: #f6f5f1;
      color: #202938;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      padding: 18px 24px 12px;
      border-bottom: 1px solid #d9d4ca;
      background: #fffdf8;
    }}
    h1 {{
      margin: 0;
      font-size: 22px;
      letter-spacing: 0;
    }}
    .meta {{
      margin-top: 6px;
      color: #5f6b7a;
      font-size: 13px;
    }}
    main {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 320px;
      min-height: calc(100vh - 70px);
    }}
    .stage {{
      overflow: auto;
      padding: 18px;
    }}
    aside {{
      border-left: 1px solid #d9d4ca;
      background: #fffdf8;
      padding: 18px;
      overflow: auto;
    }}
    svg {{
      width: 100%;
      min-width: 960px;
      height: auto;
      border: 1px solid #d9d4ca;
      background: #fbfaf6;
    }}
    .substrate-cell {{
      fill: #fbfaf7;
      stroke: rgba(108, 117, 125, 0.24);
      stroke-width: 1;
    }}
    .owned-cell {{
      stroke: rgba(38, 50, 56, 0.18);
      stroke-width: 0.8;
    }}
    .field-cell {{
      stroke: none;
      mix-blend-mode: multiply;
    }}
    .hex-path {{
      fill: none;
      stroke: rgba(64, 70, 82, 0.62);
      stroke-width: 5;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}
    .anchor-marker {{
      fill: #111827;
      stroke: #ffffff;
      stroke-width: 2.2;
    }}
    .boundary-line {{
      stroke: rgba(185, 28, 28, 0.55);
      stroke-width: 2;
      stroke-dasharray: 4 4;
      stroke-linecap: round;
    }}
    .region-label {{
      fill: #1f2937;
      font-size: 13px;
      font-weight: 720;
      paint-order: stroke;
      stroke: rgba(255, 255, 255, 0.86);
      stroke-width: 4px;
      stroke-linejoin: round;
    }}
    .anchor-label {{
      fill: #374151;
      font-size: 11px;
      paint-order: stroke;
      stroke: rgba(255, 255, 255, 0.88);
      stroke-width: 3px;
      stroke-linejoin: round;
    }}
    h2 {{
      margin: 0 0 10px;
      font-size: 14px;
    }}
    ul {{
      list-style: none;
      padding: 0;
      margin: 0;
      font-size: 13px;
    }}
    li {{
      display: flex;
      justify-content: space-between;
      gap: 14px;
      padding: 6px 0;
      border-bottom: 1px solid rgba(217, 212, 202, 0.7);
    }}
    li span {{
      color: #667085;
    }}
    li strong {{
      text-align: right;
      font-weight: 680;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Hex World Diagnostic Preview</h1>
    <div class="meta">source: {escape(summary_items["source"])} | kind: {escape(str(world.get("kind") or ""))} | boundaries: {boundary_state}</div>
  </header>
  <main>
    <section class="stage">
      {svg}
    </section>
    <aside>
      <h2>Summary</h2>
      <ul>{summary}</ul>
    </aside>
  </main>
</body>
</html>
"""


def write_html(
    input_path: Path,
    output_path: Path,
    show_boundaries: bool = False,
) -> Path:
    world = json.loads(input_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_html(world, show_boundaries=show_boundaries), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render hex-world JSON to diagnostic standalone HTML.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--show-boundaries", action="store_true")
    args = parser.parse_args()
    path = write_html(Path(args.input), Path(args.output), show_boundaries=args.show_boundaries)
    print(path.as_posix())


def _render_svg(
    *,
    cells: list[dict[str, Any]],
    regions: list[dict[str, Any]],
    paths: list[dict[str, Any]],
    fields: list[dict[str, Any]],
    anchors: list[dict[str, Any]],
    boundaries: list[dict[str, Any]],
    cell_by_id: dict[str, dict[str, Any]],
    region_by_id: dict[str, dict[str, Any]],
    cell_size: float,
    bounds: tuple[float, float, float, float],
    show_boundaries: bool,
) -> str:
    min_x, min_y, width, height = bounds
    parts = [
        f'<svg viewBox="{_fmt(min_x)} {_fmt(min_y)} {_fmt(width)} {_fmt(height)}" role="img" aria-label="Hex world diagnostic preview">',
        '<g data-layer="substrate">',
        *_render_cells(cells, cell_size, owned=False),
        "</g>",
        '<g data-layer="regions">',
        *_render_cells(cells, cell_size, owned=True),
        "</g>",
        '<g data-layer="paths">',
        *_render_paths(paths, cell_by_id),
        "</g>",
        '<g data-layer="fields">',
        *_render_fields(fields, cell_by_id, cell_size),
        "</g>",
        '<g data-layer="anchors">',
        *_render_anchors(anchors, cell_by_id),
        "</g>",
        '<g data-layer="labels">',
        *_render_region_labels(regions, cell_by_id),
        *_render_anchor_labels(anchors, cell_by_id),
        "</g>",
    ]
    if show_boundaries:
        parts.extend(
            [
                '<g data-layer="boundaries">',
                *_render_boundaries(boundaries, cell_by_id),
                "</g>",
            ]
        )
    parts.append("</svg>")
    return "".join(parts)


def _render_cells(cells: list[dict[str, Any]], cell_size: float, *, owned: bool) -> list[str]:
    parts: list[str] = []
    for cell in cells:
        owner_id = str(cell.get("owner_id") or "")
        if owned != bool(owner_id):
            continue
        cell_id = str(cell.get("id") or "")
        x, y = _cell_center(cell)
        points = _hex_points(x, y, cell_size)
        if owned:
            fill = _color(owner_id, saturation=58, lightness=72)
            parts.append(
                f'<polygon class="owned-cell" data-cell-id="{escape(cell_id)}" data-owner-id="{escape(owner_id)}" points="{points}" fill="{fill}" />'
            )
        else:
            parts.append(
                f'<polygon class="substrate-cell" data-cell-id="{escape(cell_id)}" points="{points}" />'
            )
    return parts


def _render_paths(paths: list[dict[str, Any]], cell_by_id: dict[str, dict[str, Any]]) -> list[str]:
    parts: list[str] = []
    for path in paths:
        points = _polyline_points(path.get("cell_ids", []) or [], cell_by_id)
        if not points:
            continue
        path_id = str(path.get("id") or "")
        from_region = str(path.get("from_region_id") or "")
        to_region = str(path.get("to_region_id") or "")
        parts.append(
            f'<polyline class="hex-path" data-path-id="{escape(path_id)}" data-from-region-id="{escape(from_region)}" data-to-region-id="{escape(to_region)}" points="{points}" />'
        )
    return parts


def _render_fields(
    fields: list[dict[str, Any]],
    cell_by_id: dict[str, dict[str, Any]],
    cell_size: float,
) -> list[str]:
    parts: list[str] = []
    for field in fields:
        field_id = str(field.get("id") or "")
        fill = _color(field_id, saturation=66, lightness=58)
        for field_cell in field.get("cells", []) or []:
            cell_id = str(field_cell.get("cell_id") or "")
            cell = cell_by_id.get(cell_id)
            if cell is None:
                continue
            weight = _safe_float(field_cell.get("weight"), 0.0)
            opacity = min(0.46, max(0.08, 0.08 + 0.34 * weight))
            x, y = _cell_center(cell)
            parts.append(
                f'<polygon class="field-cell" data-field-id="{escape(field_id)}" data-cell-id="{escape(cell_id)}" points="{_hex_points(x, y, cell_size * 0.82)}" fill="{fill}" opacity="{_fmt(opacity)}" />'
            )
    return parts


def _render_anchors(anchors: list[dict[str, Any]], cell_by_id: dict[str, dict[str, Any]]) -> list[str]:
    parts: list[str] = []
    for anchor in anchors:
        cell = cell_by_id.get(str(anchor.get("cell_id") or ""))
        if cell is None:
            continue
        x, y = _cell_center(cell)
        anchor_id = str(anchor.get("id") or "")
        kind = str(anchor.get("kind") or "")
        parts.append(
            f'<circle class="anchor-marker" data-anchor-id="{escape(anchor_id)}" data-anchor-kind="{escape(kind)}" cx="{_fmt(x)}" cy="{_fmt(y)}" r="6" />'
        )
    return parts


def _render_region_labels(
    regions: list[dict[str, Any]],
    cell_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    parts: list[str] = []
    for region in regions:
        cell = cell_by_id.get(str(region.get("anchor_cell_id") or ""))
        if cell is None:
            continue
        x, y = _cell_center(cell)
        region_id = str(region.get("id") or "")
        label = str(region.get("label") or region_id)
        parts.append(
            f'<text class="region-label" data-region-id="{escape(region_id)}" x="{_fmt(x + 8)}" y="{_fmt(y - 10)}">{escape(_truncate(label, 34))}</text>'
        )
    return parts


def _render_anchor_labels(
    anchors: list[dict[str, Any]],
    cell_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    parts: list[str] = []
    for anchor in anchors:
        cell = cell_by_id.get(str(anchor.get("cell_id") or ""))
        if cell is None:
            continue
        x, y = _cell_center(cell)
        anchor_id = str(anchor.get("id") or "")
        label = str(anchor.get("label") or anchor_id)
        parts.append(
            f'<text class="anchor-label" data-anchor-id="{escape(anchor_id)}" x="{_fmt(x + 8)}" y="{_fmt(y + 18)}">{escape(_truncate(label, 28))}</text>'
        )
    return parts


def _render_boundaries(
    boundaries: list[dict[str, Any]],
    cell_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    parts: list[str] = []
    for boundary in boundaries:
        cell_ids = list(boundary.get("between_cell_ids", []) or [])
        if len(cell_ids) != 2:
            continue
        first = cell_by_id.get(str(cell_ids[0]))
        second = cell_by_id.get(str(cell_ids[1]))
        if first is None or second is None:
            continue
        x1, y1 = _cell_center(first)
        x2, y2 = _cell_center(second)
        boundary_id = str(boundary.get("id") or "")
        parts.append(
            f'<line class="boundary-line" data-boundary-id="{escape(boundary_id)}" x1="{_fmt(x1)}" y1="{_fmt(y1)}" x2="{_fmt(x2)}" y2="{_fmt(y2)}" />'
        )
    return parts


def _svg_bounds(cells: list[dict[str, Any]], cell_size: float) -> tuple[float, float, float, float]:
    if not cells:
        return (-SVG_PADDING, -SVG_PADDING, SVG_PADDING * 2, SVG_PADDING * 2)
    xs = [_cell_center(cell)[0] for cell in cells]
    ys = [_cell_center(cell)[1] for cell in cells]
    padding = SVG_PADDING + cell_size
    min_x = min(xs) - padding
    min_y = min(ys) - padding
    max_x = max(xs) + padding
    max_y = max(ys) + padding
    return (min_x, min_y, max_x - min_x, max_y - min_y)


def _hex_points(x: float, y: float, cell_size: float) -> str:
    points: list[str] = []
    for index in range(6):
        angle = math.radians(-90 + 60 * index)
        points.append(f"{_fmt(x + cell_size * math.cos(angle))},{_fmt(y + cell_size * math.sin(angle))}")
    return " ".join(points)


def _polyline_points(cell_ids: list[Any], cell_by_id: dict[str, dict[str, Any]]) -> str:
    points: list[str] = []
    for cell_id in cell_ids:
        cell = cell_by_id.get(str(cell_id))
        if cell is None:
            continue
        x, y = _cell_center(cell)
        points.append(f"{_fmt(x)},{_fmt(y)}")
    return " ".join(points)


def _cell_center(cell: dict[str, Any]) -> tuple[float, float]:
    return (_safe_float(cell.get("x"), 0.0), _safe_float(cell.get("y"), 0.0))


def _color(value: str, *, saturation: int, lightness: int) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    hue = int(digest[:8], 16) % 360
    return f"hsl({hue} {saturation}% {lightness}%)"


def _list_section(world: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = world.get(key, []) or []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _safe_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _fmt(value: float) -> str:
    text = f"{value:.3f}"
    return text.rstrip("0").rstrip(".")


if __name__ == "__main__":
    main()
