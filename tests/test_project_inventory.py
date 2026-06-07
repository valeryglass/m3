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
        assert re.search(r"(?<!docs/)(?<!external-)methodology/", text) is None, name


def test_external_methodology_first_drafts_are_listed():
    readme = (ROOT / "docs" / "external-methodology" / "README.md").read_text(
        encoding="utf-8"
    )

    for filename in ("00-architecture.md", "00-data-governance.md"):
        assert (ROOT / "docs" / "external-methodology" / filename).is_file()
        assert filename in readme
