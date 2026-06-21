import pytest

from app.user_flow_router import FlowKind, InputKind, RouteDecision, route_user_input


@pytest.mark.parametrize(
    ("classic", "audio", "input_kind", "expected"),
    [
        (False, False, InputKind.START, RouteDecision.START_CLASSIC_10Q),
        (False, False, InputKind.VOICE_COMMAND, RouteDecision.ARM_AUDIO_ONE_TAKE),
        (False, False, InputKind.TEXT, RouteDecision.SHOW_START_GUIDANCE),
        (False, False, InputKind.MEDIA, RouteDecision.SHOW_START_GUIDANCE),
        (True, False, InputKind.TEXT, RouteDecision.HANDLE_CLASSIC_10Q_TEXT),
        (True, False, InputKind.MEDIA, RouteDecision.SHOW_TEXT_REQUIRED),
        (True, False, InputKind.START, RouteDecision.REQUIRE_CANCEL),
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


@pytest.mark.parametrize(
    ("flow", "input_kind", "expected"),
    [
        (FlowKind.IDLE, InputKind.THREE_BLOCK_COMMAND, RouteDecision.ARM_THREE_BLOCK),
        (
            FlowKind.IDLE,
            InputKind.ONE_TAKE_TEXT_COMMAND,
            RouteDecision.ARM_ONE_TAKE_TEXT,
        ),
        (
            FlowKind.IDLE,
            InputKind.ONE_TAKE_AUDIO_COMMAND,
            RouteDecision.ARM_AUDIO_ONE_TAKE,
        ),
        (
            FlowKind.THREE_BLOCK,
            InputKind.TEXT,
            RouteDecision.HANDLE_THREE_BLOCK_TEXT,
        ),
        (
            FlowKind.ONE_TAKE_TEXT,
            InputKind.TEXT,
            RouteDecision.HANDLE_ONE_TAKE_TEXT,
        ),
        (
            FlowKind.ONE_TAKE_AUDIO,
            InputKind.MEDIA,
            RouteDecision.HANDLE_AUDIO_ONE_TAKE_MEDIA,
        ),
        (
            FlowKind.ONE_TAKE_AUDIO,
            InputKind.TEXT,
            RouteDecision.TRANSCRIPT_CONFIRMATION_REQUIRED,
        ),
        (
            FlowKind.ONE_TAKE_AUDIO,
            InputKind.ONE_TAKE_AUDIO_COMMAND,
            RouteDecision.TRANSCRIPT_CONFIRMATION_REQUIRED,
        ),
        (
            FlowKind.THREE_BLOCK,
            InputKind.ONE_TAKE_TEXT_COMMAND,
            RouteDecision.REQUIRE_CANCEL,
        ),
    ],
)
def test_route_user_input_covers_first_class_capture_modes(
    flow, input_kind, expected
):
    kwargs = {}
    if expected is RouteDecision.TRANSCRIPT_CONFIRMATION_REQUIRED:
        kwargs["audio_status"] = "awaiting_transcript_confirmation"
    assert (
        route_user_input(
            active_flow=flow,
            input_kind=input_kind,
            **kwargs,
        )
        is expected
    )
