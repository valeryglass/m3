from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_manifest() -> dict[str, Any]:
    return yaml.safe_load((ROOT / "project.manifest.yaml").read_text(encoding="utf-8"))


def hyphenated(name: str) -> str:
    return name.replace("_", "-")


def is_private_data_path(path: str) -> bool:
    return path.startswith("data/") and not path.endswith("/")


def test_manifest_owned_paths_exist_or_have_runtime_parent_dirs():
    manifest = load_manifest()

    for module in manifest["modules"].values():
        for raw_path in module.get("owned_paths", []):
            path = ROOT / raw_path.rstrip("/")
            if "*" in raw_path:
                assert path.parent.exists(), raw_path
            elif raw_path.endswith("/"):
                assert path.is_dir(), raw_path
            elif is_private_data_path(raw_path):
                assert path.parent.exists(), raw_path
            else:
                assert path.exists(), raw_path


def test_manifest_interface_contract_docs_exist():
    manifest = load_manifest()

    for interface in manifest["interfaces"].values():
        contract_doc = ROOT / interface["contract_doc"]
        assert contract_doc.is_file(), interface["contract_doc"]


def test_manifest_modules_have_module_passports():
    manifest = load_manifest()

    for module_name in manifest["modules"]:
        module_doc = ROOT / "docs" / "modules" / f"{hyphenated(module_name)}.md"
        assert module_doc.is_file(), module_name


def test_active_docs_do_not_reference_stale_architecture_paths():
    active_paths = [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "project.manifest.yaml",
        ROOT / "docs" / "architecture.md",
        ROOT / "docs" / "lifecycle.md",
        *sorted((ROOT / "docs" / "interfaces").glob("*.md")),
        *sorted((ROOT / "docs" / "modules").glob("*.md")),
        *sorted((ROOT / "roles").glob("*.md")),
    ]
    text_by_path = {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in active_paths
    }

    for name, text in text_by_path.items():
        assert "schema.md" not in text, name
        assert "roles/auditor.md" not in text, name
        assert "annotation_workflow" not in text, name
        assert "docs/modules/annotation-workflow.md" not in text, name
        assert "private runtime JSON artifacts" not in text, name
        assert "private runtime outputs" not in text, name
        assert "workflow tooling" not in text, name
        assert "data/reports/` stores private generated report artifacts" not in text, name
        assert "report files are durable" not in text.lower(), name
        assert "report storage" not in text.lower(), name
        assert "data/reports/" + "map-payload" not in text, name
        assert "data/" + "state" not in text, name
        assert "state" + "_dir" not in text, name
        assert "M3_" + "STATE_DIR" not in text, name
        assert re.search(r"(?<!docs/)(?<!external-)methodology/", text) is None, name


def test_map_payload_exports_do_not_use_report_directory():
    active_paths = [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "project.manifest.yaml",
        ROOT / "docs" / "interfaces" / "report-to-payload.md",
        ROOT / "docs" / "modules" / "pattern-payloads.md",
    ]

    for path in active_paths:
        text = path.read_text(encoding="utf-8")
        assert "data/exports/map-payload" in text, path.relative_to(ROOT).as_posix()
        assert "data/reports/" + "map-payload" not in text, path.relative_to(ROOT).as_posix()


def test_beta_capture_smoke_doc_uses_current_provider_policy():
    text = (ROOT / "docs" / "workflows" / "audio-input-smoke.md").read_text(
        encoding="utf-8"
    )

    for required in (
        "M3_APP_MODE=production",
        "M3_CAPTURE_EXTRACTION_PROVIDER=deepseek",
        "DEEPSEEK_API_KEY",
        "M3_CAPTURE_EXTRACTION_MODEL",
        "M3_CAPTURE_EXTRACTION_PROVIDER=openai",
        "count-only",
        "UX events",
        "/status",
    ):
        assert required in text

    assert "epic/input-funnel-alpha" not in text
    assert "OPENAI_API_KEY" not in text
    assert "alpha users" not in text
    assert "Audio alpha is releasable" not in text


def test_env_example_matches_current_runtime_config_keys():
    config_text = (ROOT / "app" / "config.py").read_text(encoding="utf-8")
    example_text = (ROOT / ".env.example").read_text(encoding="utf-8")
    example_keys = {
        line.split("=", 1)[0]
        for line in example_text.splitlines()
        if line and not line.startswith("#") and "=" in line
    }

    config_m3_keys = set(re.findall(r'"(M3_[A-Z0-9_]+)"', config_text))
    for key in sorted(config_m3_keys):
        assert key in example_keys

    for key in ("DEEPSEEK_API_KEY", "M3_DEEPSEEK_BASE_URL"):
        assert key in example_keys

    assert "M3_STATE_DIR" not in example_text
    assert "local alpha smoke" not in example_text
    assert "Required for /1t, /3b, and transcript-to-draft extraction" not in example_text
    assert "M3_CAPTURE_EXTRACTION_PROVIDER=deepseek" in example_text
    assert "Use only with M3_CAPTURE_EXTRACTION_PROVIDER=openai" in example_text


def test_capture_debug_directory_is_private_with_gitkeep():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    manifest = load_manifest()
    owned = set(manifest["modules"]["capture_extraction"]["owned_paths"])

    assert "data/capture-debug/**" in gitignore
    assert "!data/capture-debug/.gitkeep" in gitignore
    assert (ROOT / "data" / "capture-debug" / ".gitkeep").is_file()
    assert "data/capture-debug/" in owned
    assert "app/capture_debug.py" in owned


def test_external_methodology_first_drafts_are_listed():
    readme = (ROOT / "docs" / "external-methodology" / "README.md").read_text(
        encoding="utf-8"
    )

    for filename in ("00-architecture.md", "00-data-governance.md"):
        assert (ROOT / "docs" / "external-methodology" / filename).is_file()
        assert filename in readme
