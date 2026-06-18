import pytest

from app.user_flow_router import InputKind, RouteDecision, route_user_input


@pytest.mark.parametrize(
    ("classic", "audio", "input_kind", "expected"),
    [
        (False, False, InputKind.START, RouteDecision.START_CLASSIC_10Q),
        (False, False, InputKind.VOICE_COMMAND, RouteDecision.ARM_AUDIO_ONE_TAKE),
        (False, False, InputKind.TEXT, RouteDecision.SHOW_START_GUIDANCE),
        (False, False, InputKind.MEDIA, RouteDecision.SHOW_START_GUIDANCE),
        (True, False, InputKind.TEXT, RouteDecision.HANDLE_CLASSIC_10Q_TEXT),
        (True, False, InputKind.MEDIA, RouteDecision.SHOW_TEXT_REQUIRED),
        (True, False, InputKind.START, RouteDecision.START_CLASSIC_10Q),
        (True, False, InputKind.VOICE_COMMAND, RouteDecision.REQUIRE_CANCEL),
        (
            False,
            True,
            InputKind.MEDIA,
            RouteDecision.HANDLE_AUDIO_ONE_TAKE_MEDIA,
        ),
        (
            False,
            True,
            InputKind.TEXT,
            RouteDecision.AUDIO_ONE_TAKE_EXPECTS_MEDIA,
        ),
        (
            False,
            True,
            InputKind.VOICE_COMMAND,
            RouteDecision.AUDIO_ONE_TAKE_EXPECTS_MEDIA,
        ),
        (False, True, InputKind.START, RouteDecision.REQUIRE_CANCEL),
        (True, True, InputKind.TEXT, RouteDecision.REQUIRE_CANCEL),
        (True, True, InputKind.MEDIA, RouteDecision.REQUIRE_CANCEL),
        (False, False, InputKind.CANCEL, RouteDecision.CANCEL_ACTIVE_FLOW),
        (True, True, InputKind.CANCEL, RouteDecision.CANCEL_ACTIVE_FLOW),
        (False, False, InputKind.OTHER_COMMAND, RouteDecision.COMMAND_ONLY),
    ],
)
def test_route_user_input_covers_mvp_matrix(
    classic, audio, input_kind, expected
):
    assert (
        route_user_input(
            has_classic_session=classic,
            has_audio_flow=audio,
            input_kind=input_kind,
        )
        is expected
    )
