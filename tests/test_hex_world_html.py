import json
import subprocess
import sys

from app.hex_world_html import render_html, write_html


def test_render_html_returns_standalone_inline_svg():
    html = render_html(_world())

    assert html.startswith("<!doctype html>")
    assert "<html" in html
    assert "<svg" in html
    assert "Hex World Diagnostic Preview" in html
    assert "source: test-source" in html


def test_render_html_draws_cells_regions_paths_fields_anchors_and_summary():
    html = render_html(_world())

    assert "substrate-cell" in html
    assert "owned-cell" in html
    assert "hex-path" in html
    assert "field-cell" in html
    assert "anchor-marker" in html
    assert "region:one" in html
    assert "one region" in html
    assert "<span>cells</span><strong>3</strong>" in html
    assert "<span>owned cells</span><strong>2</strong>" in html
    assert "<span>paths</span><strong>1</strong>" in html


def test_render_html_includes_layer_controls_for_all_layers():
    html = render_html(_world())

    assert "Layers" in html
    for layer in ("substrate", "regions", "paths", "fields", "anchors", "labels", "boundaries"):
        assert f'data-layer-toggle value="{layer}"' in html


def test_render_html_emits_all_svg_layer_groups():
    html = render_html(_world())

    for layer in ("substrate", "regions", "paths", "fields", "anchors", "labels", "boundaries"):
        assert f'data-layer="{layer}"' in html


def test_boundaries_are_hidden_by_default_but_present():
    html = render_html(_world())

    assert 'data-layer="boundaries" data-hidden="true"' in html
    assert 'data-boundary-id="boundary:one:two"' in html
    assert "boundaries: hidden" in html


def test_boundaries_are_visible_initially_when_enabled():
    html = render_html(_world(), show_boundaries=True)

    assert 'data-layer="boundaries" data-hidden="false"' in html
    assert 'class="boundary-line"' in html
    assert 'data-boundary-id="boundary:one:two"' in html
    assert "boundaries: shown" in html
    assert 'data-layer-toggle value="boundaries" checked' in html


def test_style_controls_and_inline_js_are_present():
    html = render_html(_world())

    for variable in ("--region-opacity", "--field-opacity", "--path-opacity"):
        assert variable in html

    assert "data-style-var" in html
    assert "data-label-mode-select" in html
    assert "data-layer-toggle" in html
    assert "layer.dataset.hidden" in html
    assert "style.setProperty(control.dataset.styleVar" in html
    assert "previewSvg.dataset.labelMode" in html


def test_label_mode_selector_contains_all_modes():
    html = render_html(_world())

    for mode in ("none", "id", "short", "full"):
        assert f'<option value="{mode}"' in html


def test_missing_optional_sections_do_not_crash():
    world = _world()
    for key in ("fields", "anchors", "boundaries", "paths", "regions"):
        world.pop(key, None)

    html = render_html(world)

    assert "<svg" in html
    for layer in ("substrate", "regions", "paths", "fields", "anchors", "labels", "boundaries"):
        assert f'data-layer="{layer}"' in html
    assert "<span>fields</span><strong>0</strong>" in html
    assert "<span>anchors</span><strong>0</strong>" in html
    assert "<span>boundaries</span><strong>0</strong>" in html


def test_render_html_escapes_labels_and_ids():
    world = _world()
    world["source"] = "<source>"
    world["regions"][0]["label"] = "<b>region</b>"
    world["anchors"][0]["label"] = "<script>alert(1)</script>"

    html = render_html(world)

    assert "<b>region</b>" not in html
    assert "<script>alert" not in html
    assert "&lt;source&gt;" in html
    assert "&lt;b&gt;region&lt;/b&gt;" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert 'data-label-mode="id"' in html
    assert 'data-label-mode="short"' in html
    assert 'data-label-mode="full"' in html


def test_write_html_writes_requested_output(tmp_path):
    source = tmp_path / "hex-world.json"
    output = tmp_path / "preview.html"
    source.write_text(json.dumps(_world(), ensure_ascii=False), encoding="utf-8")

    path = write_html(source, output)

    assert path == output
    assert output.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_cli_writes_requested_output_file(tmp_path):
    source = tmp_path / "hex-world.json"
    output = tmp_path / "preview.html"
    source.write_text(json.dumps(_world(), ensure_ascii=False), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.hex_world_html",
            "--input",
            str(source),
            "--output",
            str(output),
            "--show-boundaries",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == str(output)
    html = output.read_text(encoding="utf-8")
    assert 'data-layer="boundaries"' in html


def _world():
    return {
        "kind": "hex_world",
        "version": "0.1",
        "source": "test-source",
        "grid": {
            "width": 200,
            "height": 160,
            "cell_size": 20,
            "orientation": "pointy",
            "coordinate_system": "axial",
        },
        "cells": [
            {
                "id": "h:0:0",
                "q": 0,
                "r": 0,
                "s": 0,
                "x": 0.0,
                "y": 0.0,
                "owner_id": "region:one",
                "tags": ["owner:region:one"],
            },
            {
                "id": "h:1:0",
                "q": 1,
                "r": 0,
                "s": -1,
                "x": 34.641,
                "y": 0.0,
                "owner_id": "region:two",
                "tags": ["owner:region:two"],
            },
            {
                "id": "h:0:1",
                "q": 0,
                "r": 1,
                "s": -1,
                "x": 17.321,
                "y": 30.0,
                "owner_id": None,
                "tags": [],
            },
        ],
        "regions": [
            {
                "id": "region:one",
                "source_entity_id": "district-1",
                "source_entity_type": "district",
                "label": "one region",
                "anchor_cell_id": "h:0:0",
                "cell_ids": ["h:0:0"],
                "border_cell_ids": ["h:0:0"],
            },
            {
                "id": "region:two",
                "source_entity_id": "district-2",
                "source_entity_type": "district",
                "label": "two region",
                "anchor_cell_id": "h:1:0",
                "cell_ids": ["h:1:0"],
                "border_cell_ids": ["h:1:0"],
            },
        ],
        "paths": [
            {
                "id": "path:one",
                "kind": "straight_hex_relation",
                "from_region_id": "region:one",
                "to_region_id": "region:two",
                "cell_ids": ["h:0:0", "h:1:0"],
                "source_id": "neighbor-1",
            }
        ],
        "fields": [
            {
                "id": "field:climate-1",
                "source_entity_id": "climate-1",
                "source_entity_type": "climate",
                "layer": "climate",
                "cells": [{"cell_id": "h:0:0", "weight": 0.7}],
            }
        ],
        "anchors": [
            {
                "id": "anchor:gate-1",
                "source_entity_id": "gate-1",
                "source_entity_type": "gate",
                "kind": "gate",
                "cell_id": "h:0:0",
                "label": "entry gate",
            }
        ],
        "boundaries": [
            {
                "id": "boundary:one:two",
                "between_cell_ids": ["h:0:0", "h:1:0"],
                "between_region_ids": ["region:one", "region:two"],
                "tags": ["border"],
            }
        ],
    }
