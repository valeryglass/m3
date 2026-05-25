import json

import pytest

from app.derived_normalizer import (
    EpisodeBatchSummary,
    _format_summary,
    empty_derived,
    normalize_episode,
    normalize_episode_derived,
    normalize_episode_dir,
    scan_episode_dir,
)


def _episode(derived):
    return {
        "id": "episode-20260430-1",
        "date": "2026-04-30",
        "source": "telegram-chat:123",
        "observed": {
            "situation": {"value": "s", "source_quote": "s"},
            "automatic_thought": {"value": "at", "source_quote": "at"},
            "emotion": {"value": "e", "source_quote": "e"},
            "physical": {"value": "physical", "source_quote": "physical"},
            "behavior": {"value": "b", "source_quote": "b"},
            "short_term_consequence": {"value": "st", "source_quote": "st"},
            "long_term_consequence": {"value": "lt", "source_quote": "lt"},
        },
        "derived": derived,
    }


def _write_episode(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_normalize_episode_derived_replaces_legacy_shell():
    episode = _episode({"atomic_thoughts": [], "cognitive_distortions": []})

    normalized, changed = normalize_episode_derived(episode)

    assert changed is True
    assert normalized["derived"] == empty_derived()
    assert episode["derived"] == {"atomic_thoughts": [], "cognitive_distortions": []}


def test_normalize_episode_maps_old_emotion_label_and_high_intensity():
    episode = _episode({"atomic_thoughts": [], "cognitive_distortions": []})
    episode["observed"]["emotion"] = {
        "value": "нейтральное/смешанное: high",
        "source_quote": "нейтральное/смешанное: high",
        "items": [
            {
                "label": "нейтральное/смешанное",
                "intensity": "high",
                "source_quote": "нейтральное/смешанное: high",
            }
        ],
    }

    normalized, changed = normalize_episode(episode)

    assert changed is True
    assert normalized["observed"]["emotion"] == {
        "value": "нейтраль/мешанные: 1.0",
        "source_quote": "нейтраль/мешанные: 1.0",
        "items": [
            {
                "label": "нейтраль/мешанные",
                "intensity": 1.0,
                "source_quote": "нейтраль/мешанные: 1.0",
            }
        ],
    }


@pytest.mark.parametrize(
    ("old_intensity", "new_intensity", "rendered"),
    (
        ("low", 0.33, "0.33"),
        ("medium", 0.66, "0.66"),
        ("high", 1.0, "1.0"),
    ),
)
def test_normalize_episode_maps_old_emotion_intensities(
    old_intensity, new_intensity, rendered
):
    episode = _episode(empty_derived())
    episode["observed"]["emotion"] = {
        "value": f"страх: {old_intensity}",
        "source_quote": f"страх: {old_intensity}",
        "items": [
            {
                "label": "страх",
                "intensity": old_intensity,
                "source_quote": f"страх: {old_intensity}",
            }
        ],
    }

    normalized, changed = normalize_episode(episode)

    assert changed is True
    assert normalized["observed"]["emotion"]["items"][0]["intensity"] == new_intensity
    assert normalized["observed"]["emotion"]["value"] == f"страх: {rendered}"


def test_normalize_episode_leaves_unknown_old_emotion_label_invalid():
    episode = _episode(empty_derived())
    episode["observed"]["emotion"] = {
        "value": "паника: high",
        "source_quote": "паника: high",
        "items": [
            {
                "label": "паника",
                "intensity": "high",
                "source_quote": "паника: high",
            }
        ],
    }

    normalized, changed = normalize_episode(episode)

    assert changed is True
    assert normalized["observed"]["emotion"]["items"][0]["label"] == "паника"


def test_normalize_episode_leaves_unknown_old_emotion_intensity_invalid():
    episode = _episode(empty_derived())
    episode["observed"]["emotion"] = {
        "value": "страх: extreme",
        "source_quote": "страх: extreme",
        "items": [
            {
                "label": "страх",
                "intensity": "extreme",
                "source_quote": "страх: extreme",
            }
        ],
    }

    normalized, changed = normalize_episode(episode)

    assert changed is False
    assert normalized["observed"]["emotion"]["items"][0]["intensity"] == "extreme"


def test_scan_episode_dir_does_not_write_files(tmp_path):
    path = tmp_path / "episode-20260430-1.json"
    _write_episode(path, _episode({"atomic_thoughts": [], "cognitive_distortions": []}))
    before = path.read_text(encoding="utf-8")

    summary = scan_episode_dir(tmp_path)

    assert summary.total == 1
    assert summary.legacy_derived == 1
    assert summary.current_derived == 0
    assert summary.skipped == 0
    assert summary.failed == 0
    assert path.read_text(encoding="utf-8") == before


def test_normalize_episode_dir_rewrites_only_derived(tmp_path):
    path = tmp_path / "episode-20260430-1.json"
    original = _episode({"atomic_thoughts": [], "cognitive_distortions": []})
    _write_episode(path, original)

    summary = normalize_episode_dir(tmp_path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert summary.updated == 1
    assert data["observed"] == original["observed"]
    assert data["derived"] == empty_derived()


def test_normalize_episode_dir_rewrites_legacy_emotion_and_derived(tmp_path):
    path = tmp_path / "episode-20260430-1.json"
    original = _episode({"atomic_thoughts": [], "cognitive_distortions": []})
    original["observed"]["emotion"] = {
        "value": "нейтральное/смешанное: high, страх: medium, стыд: low",
        "source_quote": "нейтральное/смешанное: high, страх: medium, стыд: low",
        "items": [
            {
                "label": "нейтральное/смешанное",
                "intensity": "high",
                "source_quote": "нейтральное/смешанное: high",
            },
            {
                "label": "страх",
                "intensity": "medium",
                "source_quote": "страх: medium",
            },
            {
                "label": "стыд",
                "intensity": "low",
                "source_quote": "стыд: low",
            },
        ],
    }
    _write_episode(path, original)

    summary = normalize_episode_dir(tmp_path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert summary.updated == 1
    assert data["observed"]["situation"] == original["observed"]["situation"]
    assert data["observed"]["emotion"]["value"] == (
        "нейтраль/мешанные: 1.0, страх: 0.66, стыд: 0.33"
    )
    assert data["derived"] == empty_derived()


def test_normalize_episode_dir_fails_before_writing_invalid_files(tmp_path):
    valid_path = tmp_path / "episode-20260430-1.json"
    invalid_path = tmp_path / "episode-20260430-2.json"
    _write_episode(valid_path, _episode({"atomic_thoughts": [], "cognitive_distortions": []}))
    invalid_path.write_text("{broken", encoding="utf-8")
    before = valid_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError):
        normalize_episode_dir(tmp_path)

    assert valid_path.read_text(encoding="utf-8") == before


def test_normalize_episode_dir_preserves_current_derived(tmp_path):
    path = tmp_path / "episode-20260430-1.json"
    _write_episode(path, _episode(empty_derived()))

    summary = normalize_episode_dir(tmp_path)

    assert summary.current_derived == 1
    assert summary.updated == 0
    assert summary.skipped == 1


def test_normalize_episode_adds_missing_relations_shell():
    derived = empty_derived()
    derived.pop("relations")
    episode = _episode(derived)

    normalized, changed = normalize_episode(episode)

    assert changed is True
    assert normalized["derived"]["relations"] == []


def test_normalize_episode_preserves_existing_relations():
    relation = {
        "id": "relation-1",
        "type": "belongs_to",
        "from_ref": "node-1",
        "to_ref": "episode",
        "source_field": "observed.behavior",
        "source_quote": "b",
        "confidence": 1.0,
    }
    episode = _episode({**empty_derived(), "relations": [relation]})

    normalized, changed = normalize_episode(episode)

    assert changed is False
    assert normalized["derived"]["relations"] == [relation]


def test_normalize_episode_adds_missing_node_origin():
    episode = _episode(
        {
            **empty_derived(),
            "nodes": [
                {
                    "id": "node-1",
                    "kind": "emotion",
                    "text": "страх",
                    "source_field": "observed.emotion",
                    "source_quote": "страх",
                    "confidence": 0.9,
                }
            ],
        }
    )

    normalized, changed = normalize_episode(episode)

    assert changed is True
    assert normalized["derived"]["nodes"][0]["node_origin"] == "observed"


def test_normalize_episode_preserves_support_node_origin():
    episode = _episode(
        {
            **empty_derived(),
            "nodes": [
                {
                    "id": "node-1",
                    "node_origin": "support",
                    "kind": "cognition",
                    "text": "fear of social evaluation",
                    "source_field": "observed.automatic_thought",
                    "source_quote": "at",
                    "confidence": 0.7,
                }
            ],
        }
    )

    normalized, changed = normalize_episode(episode)

    assert changed is False
    assert normalized["derived"]["nodes"][0]["node_origin"] == "support"


def test_batch_summary_formats_updated_skipped_failed_counts():
    path_text = _format_summary(EpisodeBatchSummary(updated=2, skipped=3, failed=1))

    assert "updated: 2" in path_text
    assert "skipped: 3" in path_text
    assert "failed: 1" in path_text
