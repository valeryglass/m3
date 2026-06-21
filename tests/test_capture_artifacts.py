from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.capture_artifacts import (
    build_capture_artifact,
    capture_text_sha256,
    load_capture_artifact,
    save_capture_artifact,
)


NOW = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)


def test_capture_artifact_preserves_exact_text_and_hash(tmp_path):
    text = "  exact evidence\n"
    artifact = build_capture_artifact(
        chat_id=42,
        mode="one_take_text",
        media_kind="text",
        pieces=(("one_take_text", text),),
        created_at=NOW,
        message_id=7,
    )

    assert artifact.pieces[0].text == text
    assert artifact.pieces[0].text_sha256 == capture_text_sha256(text)
    assert load_capture_artifact(save_capture_artifact(tmp_path, artifact)) == artifact


@pytest.mark.parametrize(
    ("mode", "pieces"),
    [
        ("three_block", (("outside_context", "a"), ("inner_context", "b"))),
        ("one_take_text", (("transcript", "a"),)),
        ("one_take_audio", (("one_take_text", "a"),)),
        ("classic_10q", (("situation", "a"),)),
    ],
)
def test_capture_artifact_rejects_wrong_role_cardinality(mode, pieces):
    with pytest.raises(ValidationError):
        build_capture_artifact(
            chat_id=42,
            mode=mode,
            media_kind="text",
            pieces=pieces,
            created_at=NOW,
        )


def test_capture_artifact_rejects_private_telegram_media_identifiers():
    with pytest.raises(ValidationError, match="prohibited"):
        build_capture_artifact(
            chat_id=42,
            mode="one_take_audio",
            media_kind="voice",
            pieces=(("transcript", "words"),),
            created_at=NOW,
            source_metadata={"file_id": "private"},
        )
