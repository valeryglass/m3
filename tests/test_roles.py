from pathlib import Path


def test_loop_extractor_role_uses_current_derived_contract():
    text = Path("roles/loop-extractor.md").read_text(encoding="utf-8")

    assert "atomic_thoughts" not in text
    assert "cognitive_distortions" not in text
    assert "trigger_annotations" in text
    assert "roles/annotator.md" in text


def test_annotator_role_names_all_derived_annotation_lists():
    text = Path("roles/annotator.md").read_text(encoding="utf-8")

    for key in (
        "nodes",
        "trigger_annotations",
        "actor_annotations",
        "cognition_annotations",
        "emotion_annotations",
        "behavior_annotations",
        "relations",
    ):
        assert key in text
    assert "Before annotation" in text
    assert "node_origin" in text
    assert "`observed`: direct split" in text
    assert "`support`: inferred helper node" in text
    assert "Prefer fewer high-confidence relations" in text
    assert "Never change `id`, `date`, `source`, or `observed`" in text


def test_graph_model_explains_true_support_nodes():
    text = Path("model/graph.md").read_text(encoding="utf-8")

    assert "node_origin" in text
    assert "observed = true node" in text
    assert "support = helper node" in text
    assert "Taxonomy, Classification, Annotation" in text
    assert "LOD1 - Core CBT Loop" in text
    assert "LOD2 - Current Derived Nodes" in text
    assert "LOD3 - Future Projection" in text
    assert "not part of the current episode contract" in text


def test_auditor_role_defines_read_only_db_reports():
    text = Path("roles/auditor.md").read_text(encoding="utf-8")

    assert "Role name: `auditor`" in text
    assert "This role does not edit episode files" in text
    for section in (
        "schema_validation",
        "observed_quality",
        "derived_coverage",
        "relation_integrity",
        "junk_candidates",
    ):
        assert section in text
    assert "Stop annotation work if any file is schema-invalid" in text
