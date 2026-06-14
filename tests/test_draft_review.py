from app.draft_review import draft_review_lines, render_draft_review_overview


def test_draft_review_lines_use_target_labels_and_values():
    lines = draft_review_lines(
        {
            "situation": {"value": "коллега написал"},
            "emotion": {"value": "злость"},
        },
        targets=("situation", "emotion"),
    )

    assert [line.field_name for line in lines] == ["situation", "emotion"]
    assert [line.label for line in lines] == ["ситуация", "эмоция"]
    assert [line.value for line in lines] == ["коллега написал", "злость"]


def test_render_draft_review_overview_escapes_user_values():
    text = render_draft_review_overview(
        {"quote": {"value": "<b>нет</b>"}},
        targets=("quote",),
    )

    assert text == "цитата: &lt;b&gt;нет&lt;/b&gt;"


def test_render_draft_review_overview_keeps_missing_values_empty():
    text = render_draft_review_overview({}, targets=("situation",))

    assert text == "ситуация: "


def test_render_draft_review_overview_falls_back_to_source_quote():
    text = render_draft_review_overview(
        {"situation": {"source_quote": "source text"}},
        targets=("situation",),
    )

    assert text == "ситуация: source text"
