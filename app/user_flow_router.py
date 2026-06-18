from __future__ import annotations

from enum import Enum


class FlowKind(str, Enum):
    IDLE = "idle"
    CLASSIC_10Q = "classic_10q"
    AUDIO_ONE_TAKE = "audio_one_take"


class InputKind(str, Enum):
    START = "start"
    VOICE_COMMAND = "voice_command"
    CANCEL = "cancel"
    TEXT = "text"
    MEDIA = "media"
    OTHER_COMMAND = "other_command"


class RouteDecision(str, Enum):
    START_CLASSIC_10Q = "start_classic_10q"
    ARM_AUDIO_ONE_TAKE = "arm_audio_one_take"
    HANDLE_CLASSIC_10Q_TEXT = "handle_classic_10q_text"
    HANDLE_AUDIO_ONE_TAKE_MEDIA = "handle_audio_one_take_media"
    AUDIO_ONE_TAKE_EXPECTS_MEDIA = "audio_one_take_expects_media"
    SHOW_START_GUIDANCE = "show_start_guidance"
    SHOW_TEXT_REQUIRED = "show_text_required"
    REQUIRE_CANCEL = "require_cancel"
    CANCEL_ACTIVE_FLOW = "cancel_active_flow"
    COMMAND_ONLY = "command_only"


def route_user_input(
    *,
    has_classic_session: bool,
    has_audio_flow: bool,
    input_kind: InputKind,
) -> RouteDecision:
    if input_kind is InputKind.CANCEL:
        return RouteDecision.CANCEL_ACTIVE_FLOW
    if input_kind is InputKind.OTHER_COMMAND:
        return RouteDecision.COMMAND_ONLY
    if has_classic_session and has_audio_flow:
        return RouteDecision.REQUIRE_CANCEL

    flow = _flow_kind(
        has_classic_session=has_classic_session,
        has_audio_flow=has_audio_flow,
    )
    if input_kind is InputKind.START:
        if flow is FlowKind.AUDIO_ONE_TAKE:
            return RouteDecision.REQUIRE_CANCEL
        return RouteDecision.START_CLASSIC_10Q
    if input_kind is InputKind.VOICE_COMMAND:
        if flow is FlowKind.CLASSIC_10Q:
            return RouteDecision.REQUIRE_CANCEL
        if flow is FlowKind.AUDIO_ONE_TAKE:
            return RouteDecision.AUDIO_ONE_TAKE_EXPECTS_MEDIA
        return RouteDecision.ARM_AUDIO_ONE_TAKE
    if input_kind is InputKind.TEXT:
        if flow is FlowKind.CLASSIC_10Q:
            return RouteDecision.HANDLE_CLASSIC_10Q_TEXT
        if flow is FlowKind.AUDIO_ONE_TAKE:
            return RouteDecision.AUDIO_ONE_TAKE_EXPECTS_MEDIA
        return RouteDecision.SHOW_START_GUIDANCE
    if input_kind is InputKind.MEDIA:
        if flow is FlowKind.CLASSIC_10Q:
            return RouteDecision.SHOW_TEXT_REQUIRED
        if flow is FlowKind.AUDIO_ONE_TAKE:
            return RouteDecision.HANDLE_AUDIO_ONE_TAKE_MEDIA
        return RouteDecision.SHOW_START_GUIDANCE
    raise ValueError(f"Unsupported input kind: {input_kind}")


def _flow_kind(*, has_classic_session: bool, has_audio_flow: bool) -> FlowKind:
    if has_classic_session:
        return FlowKind.CLASSIC_10Q
    if has_audio_flow:
        return FlowKind.AUDIO_ONE_TAKE
    return FlowKind.IDLE
