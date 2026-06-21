from __future__ import annotations

from enum import Enum


class FlowKind(str, Enum):
    IDLE = "idle"
    CLASSIC_10Q = "classic_10q"
    THREE_BLOCK = "three_block"
    ONE_TAKE_TEXT = "one_take_text"
    ONE_TAKE_AUDIO = "one_take_audio"
    AUDIO_ONE_TAKE = "one_take_audio"


class InputKind(str, Enum):
    START = "start"
    TEN_QUESTION_COMMAND = "ten_question_command"
    THREE_BLOCK_COMMAND = "three_block_command"
    ONE_TAKE_TEXT_COMMAND = "one_take_text_command"
    ONE_TAKE_AUDIO_COMMAND = "one_take_audio_command"
    VOICE_COMMAND = "voice_command"
    CANCEL = "cancel"
    TEXT = "text"
    MEDIA = "media"
    OTHER_COMMAND = "other_command"


class RouteDecision(str, Enum):
    START_CLASSIC_10Q = "start_classic_10q"
    ARM_THREE_BLOCK = "arm_three_block"
    ARM_ONE_TAKE_TEXT = "arm_one_take_text"
    ARM_AUDIO_ONE_TAKE = "arm_audio_one_take"
    HANDLE_THREE_BLOCK_TEXT = "handle_three_block_text"
    HANDLE_ONE_TAKE_TEXT = "handle_one_take_text"
    HANDLE_CLASSIC_10Q_TEXT = "handle_classic_10q_text"
    HANDLE_AUDIO_ONE_TAKE_MEDIA = "handle_audio_one_take_media"
    TRANSCRIPT_CONFIRMATION_REQUIRED = "transcript_confirmation_required"
    AUDIO_ONE_TAKE_EXPECTS_MEDIA = "audio_one_take_expects_media"
    SHOW_START_GUIDANCE = "show_start_guidance"
    SHOW_TEXT_REQUIRED = "show_text_required"
    REQUIRE_CANCEL = "require_cancel"
    CANCEL_ACTIVE_FLOW = "cancel_active_flow"
    COMMAND_ONLY = "command_only"


def route_user_input(
    *,
    has_classic_session: bool = False,
    has_audio_flow: bool = False,
    active_flow: FlowKind | str | None = None,
    audio_status: str | None = None,
    input_kind: InputKind,
) -> RouteDecision:
    if input_kind is InputKind.CANCEL:
        return RouteDecision.CANCEL_ACTIVE_FLOW
    if input_kind is InputKind.OTHER_COMMAND:
        return RouteDecision.COMMAND_ONLY
    if has_classic_session and (has_audio_flow or active_flow not in (None, FlowKind.IDLE)):
        return RouteDecision.REQUIRE_CANCEL

    if has_classic_session:
        flow = FlowKind.CLASSIC_10Q
    elif active_flow is not None:
        flow = FlowKind(active_flow)
    else:
        flow = _flow_kind(
            has_classic_session=has_classic_session,
            has_audio_flow=has_audio_flow,
        )
    if input_kind in (InputKind.START, InputKind.TEN_QUESTION_COMMAND):
        if flow is not FlowKind.IDLE:
            return RouteDecision.REQUIRE_CANCEL
        return RouteDecision.START_CLASSIC_10Q
    if input_kind is InputKind.THREE_BLOCK_COMMAND:
        if flow is not FlowKind.IDLE:
            return RouteDecision.REQUIRE_CANCEL
        return RouteDecision.ARM_THREE_BLOCK
    if input_kind is InputKind.ONE_TAKE_TEXT_COMMAND:
        if flow is not FlowKind.IDLE:
            return RouteDecision.REQUIRE_CANCEL
        return RouteDecision.ARM_ONE_TAKE_TEXT
    if input_kind in (InputKind.ONE_TAKE_AUDIO_COMMAND, InputKind.VOICE_COMMAND):
        if flow is FlowKind.CLASSIC_10Q:
            return RouteDecision.REQUIRE_CANCEL
        if flow is FlowKind.ONE_TAKE_AUDIO:
            if audio_status == "awaiting_transcript_confirmation":
                return RouteDecision.TRANSCRIPT_CONFIRMATION_REQUIRED
            return RouteDecision.AUDIO_ONE_TAKE_EXPECTS_MEDIA
        if flow is not FlowKind.IDLE:
            return RouteDecision.REQUIRE_CANCEL
        return RouteDecision.ARM_AUDIO_ONE_TAKE
    if input_kind is InputKind.TEXT:
        if flow is FlowKind.CLASSIC_10Q:
            return RouteDecision.HANDLE_CLASSIC_10Q_TEXT
        if flow is FlowKind.THREE_BLOCK:
            return RouteDecision.HANDLE_THREE_BLOCK_TEXT
        if flow is FlowKind.ONE_TAKE_TEXT:
            return RouteDecision.HANDLE_ONE_TAKE_TEXT
        if flow is FlowKind.ONE_TAKE_AUDIO:
            if audio_status == "awaiting_transcript_confirmation":
                return RouteDecision.TRANSCRIPT_CONFIRMATION_REQUIRED
            return RouteDecision.AUDIO_ONE_TAKE_EXPECTS_MEDIA
        return RouteDecision.SHOW_START_GUIDANCE
    if input_kind is InputKind.MEDIA:
        if flow is FlowKind.CLASSIC_10Q:
            return RouteDecision.SHOW_TEXT_REQUIRED
        if flow is FlowKind.ONE_TAKE_AUDIO:
            if audio_status == "awaiting_transcript_confirmation":
                return RouteDecision.TRANSCRIPT_CONFIRMATION_REQUIRED
            return RouteDecision.HANDLE_AUDIO_ONE_TAKE_MEDIA
        if flow in (FlowKind.THREE_BLOCK, FlowKind.ONE_TAKE_TEXT):
            return RouteDecision.SHOW_TEXT_REQUIRED
        return RouteDecision.SHOW_START_GUIDANCE
    raise ValueError(f"Unsupported input kind: {input_kind}")


def _flow_kind(*, has_classic_session: bool, has_audio_flow: bool) -> FlowKind:
    if has_classic_session:
        return FlowKind.CLASSIC_10Q
    if has_audio_flow:
        return FlowKind.ONE_TAKE_AUDIO
    return FlowKind.IDLE
