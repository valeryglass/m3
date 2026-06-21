from __future__ import annotations

import asyncio
from pathlib import Path
from threading import Thread
from time import monotonic
from app.capture_artifacts import build_capture_artifact, save_capture_artifact
from app.capture_extraction import (
    UnavailableCaptureExtractionProvider,
    link_capture_extraction_to_episode,
    project_classic_10q,
    run_capture_extraction,
)
from app.draft_review_sessions import (
    DraftReviewSessionStore,
    review_session_from_extraction,
)
from app.openai_capture_extractor import OpenAICaptureExtractionProvider
from app.config import (
    Settings,
    admin_chat_ids_for_settings,
    load_settings,
    owner_chat_id_for_settings,
)
from app.capture_flow_store import CaptureFlowStore
from app.analytics_loader import annotation_coverage_for_episode_ids
from app.annotation_producer import produce_annotation_run
from app.graph_report import build_report, load_episodes
from app.telegram_media import (
    TelegramMediaDownloadFailed,
    TelegramMediaRejected,
    TelegramMediaRequest,
    temporary_telegram_media,
    validate_telegram_media_request,
)
from app.transcription import (
    MissingTranscriptionProvider,
    TranscriptionFailed,
    TranscriptionUnavailable,
    transcribe_and_attach,
)
from app.whisper_provider import WhisperCliTranscriptionProvider
from app.report_runner import (
    build_graph_report_summary,
    build_ux_report_text,
)
from app.user_report import render_details, render_summary
from app.input_funnels import (
    artifact_text,
    audio_document_input_artifact,
    audio_input_artifact,
    voice_input_artifact,
)
from app.intake_transcripts import (
    build_intake_transcript,
    link_intake_transcript_to_episode,
    load_intake_transcript,
    save_intake_transcript,
)
from app.loop_extractor import (
    active_target,
    apply_user_reply,
    completed_draft_field_count,
    completed_observed_count,
    new_session,
    prompt_for_current_target,
    status_text,
    target_fields,
)
from app.session_store import LoopSessionStore
from app.storage import JsonStorage
from app.tone_engine import load_tone_engine
from app.user_flow_router import (
    FlowKind,
    InputKind,
    RouteDecision,
    route_user_input,
)
from app.userlist import JsonUserList
from app.ux_events import (
    UxEventLog,
    base_event,
    format_utc,
    new_session_id,
    parse_utc,
    telegram_event,
    utc_now,
)


def main() -> None:
    settings = load_settings()
    storage = JsonStorage(settings.episode_dir)
    session_store = LoopSessionStore(settings.runtime_session_dir)
    review_store = DraftReviewSessionStore(
        settings.runtime_session_dir,
        loop_session_store=session_store,
    )
    capture_flow_store = CaptureFlowStore(settings.runtime_flow_dir)
    userlist = JsonUserList(settings.userlist_path)
    ux_events = UxEventLog(settings.ux_event_log)
    tone = load_tone_engine(settings.tone_config)
    transcription_provider = _transcription_provider_for_settings(settings)
    extraction_provider = _capture_extraction_provider_for_settings(settings)

    try:
        from telegram import BotCommand, Update
        from telegram.ext import (
            Application,
            CallbackQueryHandler,
            CommandHandler,
            ContextTypes,
            MessageHandler,
            filters,
        )
    except ImportError as exc:  # pragma: no cover - runtime dependency guard
        raise RuntimeError(
            "Install project dependencies before running the Telegram bot."
        ) from exc
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_start_after_authorized(
            update,
            session_store,
            ux_events,
            tone,
            audio_flow_store=capture_flow_store,
            review_store=review_store,
        )

    async def ten_question(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_start_after_authorized(
            update,
            session_store,
            ux_events,
            tone,
            audio_flow_store=capture_flow_store,
            review_store=review_store,
        )

    async def one_take_text(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_capture_mode_command_after_authorized(
            update,
            session_store,
            capture_flow_store,
            settings,
            mode=FlowKind.ONE_TAKE_TEXT,
            review_store=review_store,
        )

    async def three_block(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_capture_mode_command_after_authorized(
            update,
            session_store,
            capture_flow_store,
            settings,
            mode=FlowKind.THREE_BLOCK,
            review_store=review_store,
        )

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_status_after_authorized(
            update,
            session_store,
            review_store,
            ux_events,
            settings,
            tone,
        )

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _send_help(update, tone)

    async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_profile_after_authorized(update, settings, tone)

    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_cancel_after_authorized(
            update,
            session_store,
            ux_events,
            settings,
            tone,
            audio_flow_store=capture_flow_store,
            review_store=review_store,
        )

    async def capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_capture_after_authorized(
            update,
            session_store,
            ux_events,
            settings,
            tone,
            capture_flow_store=capture_flow_store,
            review_store=review_store,
            extraction_provider=extraction_provider,
        )

    async def capture3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_capture3_after_authorized(
            update,
            session_store,
            ux_events,
            settings,
            tone,
            capture_flow_store=capture_flow_store,
            review_store=review_store,
            extraction_provider=extraction_provider,
        )

    async def voice_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_voice_command_after_authorized(
            update,
            session_store,
            capture_flow_store,
            settings,
            review_store=review_store,
        )

    async def voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_voice_after_authorized(
            update,
            session_store,
            ux_events,
            tone,
            bot=context.bot,
            settings=settings,
            transcription_provider=transcription_provider,
            audio_flow_store=capture_flow_store,
            review_store=review_store,
        )

    async def audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_audio_after_authorized(
            update,
            session_store,
            ux_events,
            tone,
            bot=context.bot,
            settings=settings,
            transcription_provider=transcription_provider,
            audio_flow_store=capture_flow_store,
            review_store=review_store,
        )

    async def document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_document_after_authorized(
            update,
            session_store,
            ux_events,
            tone,
            bot=context.bot,
            settings=settings,
            transcription_provider=transcription_provider,
            audio_flow_store=capture_flow_store,
            review_store=review_store,
        )

    async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_message_after_authorized(
            update,
            session_store,
            ux_events,
            settings,
            tone,
            audio_flow_store=capture_flow_store,
            review_store=review_store,
            extraction_provider=extraction_provider,
        )

    async def episode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_episode_callback_after_authorized(
            update, storage, session_store, ux_events, tone,
            review_store=review_store,
        )

    async def transcript_callback(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_transcript_callback_after_authorized(
            update,
            session_store,
            capture_flow_store,
            ux_events,
            tone,
            settings=settings,
            review_store=review_store,
            extraction_provider=extraction_provider,
        )

    async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_profile_callback_after_authorized(update, settings, tone)

    async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await _handle_admin_decision(
            update, context.args, settings, tone, ux_events, userlist, "approve", context.bot
        )

    async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await _handle_admin_decision(
            update, context.args, settings, tone, ux_events, userlist, "pause", context.bot
        )

    async def report_graph(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize_admin(update, settings, tone, ux_events):
            return
        await _handle_report_graph_after_admin(update, settings, tone)

    async def report_ux(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize_admin(update, settings, tone, ux_events):
            return
        await _handle_report_ux_after_admin(update, settings, tone)

    async def admin_annotate_gaps(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await _authorize_admin(update, settings, tone, ux_events):
            return
        await _handle_admin_annotate_gaps_after_admin(update, settings, tone)

    async def post_init(application) -> None:
        profile = _bot_profile(tone)
        await application.bot.set_my_commands(
            [
                BotCommand(command=command["command"], description=command["description"])
                for command in _visible_command_menu(tone)
            ]
        )
        await application.bot.set_my_short_description(
            short_description=profile["short_description"]
        )
        await application.bot.set_my_description(description=profile["description"])

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .post_init(post_init)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("10q", ten_question))
    application.add_handler(CommandHandler("3b", three_block))
    application.add_handler(CommandHandler("1t", one_take_text))
    application.add_handler(CommandHandler("1a", voice_command))
    application.add_handler(CommandHandler("1v", voice_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("capture", capture))
    application.add_handler(CommandHandler("capture3", capture3))
    application.add_handler(CommandHandler("voice", voice_command))
    application.add_handler(CommandHandler("approve", approve))
    application.add_handler(CommandHandler("pause", pause))
    application.add_handler(CommandHandler("report_graph", report_graph))
    application.add_handler(CommandHandler("report_ux", report_ux))
    application.add_handler(
        CommandHandler("admin_annotate_gaps", admin_annotate_gaps)
    )
    application.add_handler(CallbackQueryHandler(episode_callback, pattern="^episode:"))
    application.add_handler(
        CallbackQueryHandler(transcript_callback, pattern="^transcript:")
    )
    application.add_handler(CallbackQueryHandler(profile_callback, pattern="^profile:"))
    application.add_handler(MessageHandler(filters.VOICE, voice))
    application.add_handler(MessageHandler(filters.AUDIO, audio))
    application.add_handler(MessageHandler(filters.Document.ALL, document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))
    application.run_polling(bootstrap_retries=-1)


REGISTERED_COMMANDS = (
    "start",
    "10q",
    "3b",
    "1t",
    "1a",
    "1v",
    "status",
    "cancel",
    "help",
    "profile",
    "capture",
    "capture3",
    "voice",
    "approve",
    "pause",
    "report_graph",
    "report_ux",
    "admin_annotate_gaps",
)
VISIBLE_COMMANDS = ("start", "10q", "3b", "1t", "1a", "cancel", "help")
REPORT_REPLY_LIMIT = 3800
TELEGRAM_TEXT_LIMIT = 3800


def _transcription_provider_for_settings(settings):
    if getattr(settings, "transcription_provider", "missing") == "whisper":
        return WhisperCliTranscriptionProvider(
            command=getattr(settings, "whisper_command", "whisper"),
            model=getattr(settings, "whisper_model", None),
            language=getattr(settings, "whisper_language", None),
        )
    return MissingTranscriptionProvider()


def _capture_extraction_provider_for_settings(settings):
    api_key = getattr(settings, "openai_api_key", "")
    model = getattr(settings, "capture_extraction_model", "")
    if not api_key or not model:
        return UnavailableCaptureExtractionProvider(model)
    return OpenAICaptureExtractionProvider(api_key=api_key, model=model)


def target_fields_for_review() -> tuple[str, ...]:
    return (
        "situation",
        "trigger",
        "actor",
        "quote",
        "automatic_thought",
        "emotion",
        "behavior",
        "physical",
        "short_term_consequence",
        "long_term_consequence",
    )


def _visible_command_menu(tone) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "command": command,
            "description": tone.command_description(command),
        }
        for command in VISIBLE_COMMANDS
    )


def _bot_profile(tone) -> dict[str, str]:
    return {
        "short_description": tone.bot_short_description(),
        "description": tone.bot_description(),
    }


async def _send_help(update, tone) -> None:
    if update.message is not None:
        await _reply_text(update, tone.help())


async def _handle_profile_after_authorized(update, settings: Settings, tone) -> None:
    report = _build_chat_profile_report(settings, update.effective_chat.id)
    if report is None:
        await _reply_text(update, tone.profile_missing())
        return
    await _reply_text(
        update,
        render_summary(report),
        reply_markup=_profile_details_reply_markup(),
        parse_mode=None,
    )


async def _handle_profile_callback_after_authorized(update, settings: Settings, tone) -> None:
    query = getattr(update, "callback_query", None)
    if query is not None:
        await query.answer()
    data = getattr(query, "data", "") if query is not None else ""
    if data != "profile:details":
        return

    report = _build_chat_profile_report(settings, update.effective_chat.id)
    if report is None:
        await _reply_to_callback(query, tone.profile_missing(), parse_mode=None)
        return
    await _reply_to_callback(
        query,
        _trim_report_text(render_details(report)),
        parse_mode=None,
    )


def _build_chat_profile_report(settings: Settings, chat_id: int):
    if settings.episode_dir is None or not settings.episode_dir.exists():
        return None
    source = f"telegram-chat:{chat_id}"
    loaded_episodes = load_episodes(
        settings.episode_dir,
        annotation_run_dir=getattr(settings, "annotation_run_dir", None),
        annotation_run_root=getattr(settings, "annotation_run_root", None),
    )
    episodes = [
        episode
        for episode in loaded_episodes
        if episode.source == source
    ]
    if not episodes:
        return None
    report = build_report(
        episodes,
        coverage=annotation_coverage_for_episode_ids(
            {episode.id for episode in episodes},
            annotation_run_dir=getattr(settings, "annotation_run_dir", None),
            annotation_run_root=getattr(settings, "annotation_run_root", None),
            known_episode_ids={episode.id for episode in loaded_episodes},
        ),
    )
    if not report.graph_ready or not any(item.report_ready for item in report.readiness):
        return None
    return report


async def _handle_report_graph_after_admin(update, settings: Settings, tone) -> None:
    try:
        summary = build_graph_report_summary(settings)
    except Exception as exc:  # pragma: no cover - exact failures depend on data files
        await _reply_text(update, tone.report_failed(exc))
        return

    await _reply_text(
        update,
        tone.graph_reports_ready(
            episodes=summary["episodes"],
            observed_count=summary["observed_count"],
            annotated_count=summary["annotated_count"],
            pending_count=summary["pending_count"],
            coverage=summary["coverage"],
            invalid=summary["invalid"],
            empty_derived=summary["empty_derived"],
            annotation_ready=summary["annotation_ready"],
            graph_ready=summary["graph_ready"],
            report_ready=summary["report_ready"],
            payload_eligible=summary["payload_eligible"],
        ),
    )


async def _handle_admin_annotate_gaps_after_admin(
    update, settings: Settings, tone
) -> None:
    try:
        summary = produce_annotation_run(
            settings.episode_dir,
            settings.annotation_run_root,
            only_missing=True,
            annotation_run_dir=getattr(settings, "annotation_run_dir", None),
            annotation_run_root=getattr(settings, "annotation_run_root", None),
            write=False,
        )
        if summary.row_count:
            summary = produce_annotation_run(
                settings.episode_dir,
                settings.annotation_run_root,
                run_id=summary.run_id,
                only_missing=True,
                annotation_run_dir=getattr(settings, "annotation_run_dir", None),
                annotation_run_root=getattr(settings, "annotation_run_root", None),
                write=True,
            )
    except Exception as exc:  # pragma: no cover - exact failures depend on data files
        await _reply_text(update, tone.report_failed(exc))
        return

    await _reply_text(update, _admin_annotate_gaps_summary(summary), parse_mode=None)


def _admin_annotate_gaps_summary(summary) -> str:
    return (
        "Аннотации обновлены\n"
        f"episodes: {summary.episode_count}\n"
        f"new_annotations: {summary.row_count}\n"
        f"carried_forward: {summary.carried_forward_count}\n"
        f"final_snapshot: {summary.final_snapshot_count}\n"
        f"snapshot_written: {str(summary.snapshot_written).lower()}\n"
        f"coverage: {summary.annotated_before}/{summary.episode_count} -> "
        f"{summary.annotated_after}/{summary.episode_count} "
        f"({summary.coverage_after})\n"
        f"pending: {summary.pending_after}\n"
        f"run: {summary.run_id}"
    )


async def _handle_report_ux_after_admin(update, settings: Settings, tone) -> None:
    try:
        text = build_ux_report_text(settings)
    except Exception as exc:  # pragma: no cover - exact failures depend on data files
        await _reply_text(update, tone.report_failed(exc))
        return

    await _reply_text(update, _trim_report_text(text), parse_mode=None)


def _trim_report_text(text: str, limit: int = REPORT_REPLY_LIMIT) -> str:
    if len(text) <= limit:
        return text
    suffix = "\n\n[report trimmed]"
    return text[: limit - len(suffix)].rstrip() + suffix


async def _handle_start_after_authorized(
    update,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    tone,
    *,
    audio_flow_store: CaptureFlowStore | None = None,
    review_store: DraftReviewSessionStore | None = None,
) -> None:
    chat_id = update.effective_chat.id
    now = utc_now()
    if review_store is not None and review_store.load_session(chat_id, now=now):
        await _reply_text(update, _cancel_active_flow_first())
        return
    session = session_store.load_session(chat_id)
    audio_flow = (
        audio_flow_store.load_flow(chat_id, now=now)
        if audio_flow_store is not None
        else None
    )
    decision = route_user_input(
        has_classic_session=session is not None,
        active_flow=_flow_kind_for_capture_flow(audio_flow),
        input_kind=InputKind.START,
    )
    if decision is RouteDecision.REQUIRE_CANCEL:
        await _reply_text(update, _cancel_active_flow_first())
        return
    if decision is not RouteDecision.START_CLASSIC_10Q:
        raise RuntimeError(f"Unsupported start route decision: {decision}")
    session = _start_new_session(session_store, ux_events, chat_id, now)
    await _reply_text(
        update,
        tone.start_session(
            prompt_for_current_target(session, tone),
            total_count=len(target_fields(session)),
        ),
    )


async def _handle_status_after_authorized(
    update,
    session_store: LoopSessionStore,
    review_store: DraftReviewSessionStore,
    ux_events: UxEventLog,
    settings: Settings,
    tone,
) -> None:
    chat_id = update.effective_chat.id
    now = utc_now()
    review = review_store.load_session(chat_id, now=now)
    if review is not None:
        await _reply_text(
            update,
            tone.review_screen(review.observed, target_fields_for_review()),
            reply_markup=_review_reply_markup(),
        )
        return
    session = session_store.load_session(chat_id)
    if _expire_initial_session_if_stale(
        session_store,
        ux_events,
        session,
        chat_id,
        now,
        settings.initial_session_ttl_sec,
    ):
        await _reply_text(update, _expired_initial_session_text(tone))
        return
    if session is None:
        await _reply_text(update, tone.no_active_loop())
        return
    await _reply_text(update, status_text(session, tone))


async def _handle_cancel_after_authorized(
    update,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    settings: Settings,
    tone,
    *,
    audio_flow_store: CaptureFlowStore | None = None,
    review_store: DraftReviewSessionStore | None = None,
) -> None:
    chat_id = update.effective_chat.id
    now = utc_now()
    session = session_store.load_session(chat_id)
    audio_flow = (
        audio_flow_store.load_flow(chat_id, now=now)
        if audio_flow_store is not None
        else None
    )
    review = (
        review_store.load_session(chat_id, now=now)
        if review_store is not None
        else None
    )
    session_expired = _expire_initial_session_if_stale(
        session_store, ux_events, session, chat_id, now, settings.initial_session_ttl_sec
    )
    if session_expired:
        session = None
    if session_expired and audio_flow is None and review is None:
        await _reply_text(update, _expired_initial_session_text(tone))
        return
    if session is None and audio_flow is None and review is None:
        await _reply_text(update, tone.no_active_loop())
        return
    if session is not None and session.session_id is not None:
        ux_events.append(
            _session_cancelled_event(
                session,
                str(chat_id),
                now=now,
            )
        )
    if session is not None:
        session_store.delete_session(chat_id)
    if audio_flow_store is not None:
        audio_flow_store.delete_flow(chat_id)
    if review_store is not None:
        review_store.delete_session(chat_id)
    await _reply_text(update, tone.cancel())


async def _handle_voice_command_after_authorized(
    update,
    session_store: LoopSessionStore,
    audio_flow_store: CaptureFlowStore,
    settings: Settings,
    *,
    review_store: DraftReviewSessionStore | None = None,
) -> None:
    chat_id = update.effective_chat.id
    now = utc_now()
    if review_store is not None and review_store.load_session(chat_id, now=now):
        await _reply_text(update, _cancel_active_flow_first())
        return
    session = session_store.load_session(chat_id)
    audio_flow = audio_flow_store.load_flow(chat_id, now=now)
    decision = route_user_input(
        has_classic_session=session is not None,
        active_flow=_flow_kind_for_capture_flow(audio_flow),
        audio_status=audio_flow.status if audio_flow is not None else None,
        input_kind=InputKind.ONE_TAKE_AUDIO_COMMAND,
    )
    if decision is RouteDecision.REQUIRE_CANCEL:
        await _reply_text(update, _cancel_active_flow_first())
        return
    if decision is RouteDecision.AUDIO_ONE_TAKE_EXPECTS_MEDIA:
        await _reply_text(update, _audio_media_guidance())
        return
    if decision is RouteDecision.TRANSCRIPT_CONFIRMATION_REQUIRED:
        await _reply_text(
            update,
            "Подтверди расшифровку кнопкой «Продолжить» или «Отклонить».",
            reply_markup=_transcript_confirmation_reply_markup(),
        )
        return
    if decision is not RouteDecision.ARM_AUDIO_ONE_TAKE:
        raise RuntimeError(f"Unsupported voice route decision: {decision}")

    audio_flow_store.arm_flow(
        chat_id,
        mode="one_take_audio",
        now=now,
        ttl_sec=settings.initial_session_ttl_sec,
    )
    await _reply_text(update, _audio_media_guidance())


async def _handle_capture_mode_command_after_authorized(
    update,
    session_store: LoopSessionStore,
    capture_flow_store: CaptureFlowStore,
    settings: Settings,
    *,
    mode: FlowKind,
    review_store: DraftReviewSessionStore | None = None,
) -> None:
    chat_id = update.effective_chat.id
    now = utc_now()
    if review_store is not None and review_store.load_session(chat_id, now=now):
        await _reply_text(update, _cancel_active_flow_first())
        return
    session = session_store.load_session(chat_id)
    capture_flow = capture_flow_store.load_flow(chat_id, now=now)
    input_kind = {
        FlowKind.ONE_TAKE_TEXT: InputKind.ONE_TAKE_TEXT_COMMAND,
        FlowKind.THREE_BLOCK: InputKind.THREE_BLOCK_COMMAND,
    }[mode]
    decision = route_user_input(
        has_classic_session=session is not None,
        active_flow=_flow_kind_for_capture_flow(capture_flow),
        input_kind=input_kind,
    )
    expected = {
        FlowKind.ONE_TAKE_TEXT: RouteDecision.ARM_ONE_TAKE_TEXT,
        FlowKind.THREE_BLOCK: RouteDecision.ARM_THREE_BLOCK,
    }[mode]
    if decision is RouteDecision.REQUIRE_CANCEL:
        await _reply_text(update, _cancel_active_flow_first())
        return
    if decision is not expected:
        raise RuntimeError(f"Unsupported capture command decision: {decision}")

    capture_flow_store.arm_flow(
        chat_id,
        mode=mode.value,
        now=now,
        ttl_sec=settings.initial_session_ttl_sec,
    )
    if mode is FlowKind.ONE_TAKE_TEXT:
        await _reply_text(update, _one_take_text_guidance())
        return
    await _reply_text(update, _three_block_prompt(0))


async def _extract_capture_to_review(
    update,
    review_store: DraftReviewSessionStore,
    ux_events: UxEventLog,
    tone,
    *,
    chat_id: int,
    settings,
    extraction_provider,
    mode: str,
    pieces,
    now,
    media_kind: str,
    intake_transcript_path: str | None = None,
    message_id: int | None = None,
) -> None:
    artifact = build_capture_artifact(
        chat_id=chat_id,
        mode=mode,
        media_kind=media_kind,
        pieces=pieces,
        created_at=now,
        message_id=message_id,
        source_metadata={
            key: value
            for key, value in _telegram_update_metadata(update).items()
            if key in {"message_id", "message_kind", "command"}
        },
        intake_transcript_path=intake_transcript_path,
    )
    artifact_path = save_capture_artifact(
        getattr(
            settings,
            "capture_artifact_dir",
            review_store.review_dir.parent / "capture-artifacts",
        ),
        artifact,
    )
    ux_events.append(
        base_event(
            "input_received",
            artifact.capture_id,
            str(chat_id),
            created_at=now,
            funnel=mode,
            media_kind=media_kind,
            answer_chars=sum(len(piece.text) for piece in artifact.pieces),
        )
    )
    outcome = await _run_capture_extraction_in_worker(
        artifact,
        extraction_provider,
        getattr(
            settings,
            "capture_extraction_dir",
            review_store.review_dir.parent / "capture-extractions",
        ),
    )
    if outcome.draft is None:
        ux_events.append(
            base_event(
                "capture_extraction_failed",
                artifact.capture_id,
                str(chat_id),
                created_at=utc_now(),
                funnel=mode,
                media_kind=media_kind,
                    failure_code=outcome.extraction.failure_code,
            )
        )
        await _reply_text(update, _capture_extraction_failed_text(), parse_mode=None)
        return
    review = review_session_from_extraction(
        chat_id=chat_id,
        mode=mode,
        observed=outcome.draft.observed,
        episode_date=_episode_date_for_now(now),
        now=now,
        capture_id=artifact.capture_id,
        capture_artifact_path=artifact_path,
        extraction_id=outcome.extraction.extraction_id,
        extraction_path=outcome.path,
        intake_transcript_path=intake_transcript_path,
        media_kind=media_kind,
    )
    review_store.save_session(review)
    ux_events.append(
        base_event(
            "draft_created",
            review.review_id,
            str(chat_id),
            created_at=utc_now(),
            funnel=mode,
            media_kind=media_kind,
            draft_fields=len(review.observed),
        )
    )
    await _reply_text(
        update,
        tone.review_screen(review.observed, target_fields_for_review()),
        reply_markup=_review_reply_markup(),
    )


async def _run_capture_extraction_in_worker(artifact, provider, output_root):
    if getattr(provider, "_m3_run_inline_for_tests", False):
        return run_capture_extraction(artifact, provider, output_root)
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def worker() -> None:
        try:
            result = run_capture_extraction(artifact, provider, output_root)
        except BaseException as exc:  # pragma: no cover - surfaced by handler
            loop.call_soon_threadsafe(future.set_exception, exc)
        else:
            loop.call_soon_threadsafe(future.set_result, result)

    Thread(target=worker, daemon=True).start()
    return await future


def _capture_extraction_failed_text() -> str:
    return (
        "Не удалось надежно разобрать этот эпизод. Исходный материал сохранен "
        "приватно; начни заново той же командой."
    )


async def _handle_capture_after_authorized(
    update,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    settings: Settings,
    tone,
    *,
    capture_flow_store: CaptureFlowStore | None = None,
    review_store: DraftReviewSessionStore | None = None,
    extraction_provider=None,
) -> None:
    chat_id = update.effective_chat.id
    now = utc_now()
    if review_store is not None and review_store.load_session(chat_id, now=now):
        await _reply_text(update, _cancel_active_flow_first())
        return
    existing_session = session_store.load_session(chat_id)
    if _expire_initial_session_if_stale(
        session_store,
        ux_events,
        existing_session,
        chat_id,
        now,
        settings.initial_session_ttl_sec,
    ):
        await _reply_text(update, _expired_initial_session_text(tone))
        return
    existing_flow = (
        capture_flow_store.load_flow(chat_id, now=now)
        if capture_flow_store is not None
        else None
    )
    decision = route_user_input(
        has_classic_session=existing_session is not None,
        active_flow=_flow_kind_for_capture_flow(existing_flow),
        input_kind=InputKind.ONE_TAKE_TEXT_COMMAND,
    )
    if decision is RouteDecision.REQUIRE_CANCEL:
        await _reply_text(update, _cancel_active_flow_first())
        return
    if decision is not RouteDecision.ARM_ONE_TAKE_TEXT:
        raise RuntimeError(f"Unsupported capture route decision: {decision}")

    text = _command_argument_text(getattr(update.message, "text", "") or "")
    if not text:
        await _reply_text(update, "Используй /capture текст эпизода")
        return

    review_store = review_store or DraftReviewSessionStore(
        getattr(settings, "runtime_session_dir", session_store.session_dir),
        loop_session_store=session_store,
    )
    extraction_provider = extraction_provider or _capture_extraction_provider_for_settings(
        settings
    )
    await _extract_capture_to_review(
        update,
        review_store,
        ux_events,
        tone,
        chat_id=chat_id,
        settings=settings,
        extraction_provider=extraction_provider,
        mode="one_take_text",
        pieces=(("one_take_text", text),),
        now=now,
        media_kind="text",
        message_id=getattr(update.message, "message_id", None),
    )


async def _handle_capture3_after_authorized(
    update,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    settings: Settings,
    tone,
    *,
    capture_flow_store: CaptureFlowStore | None = None,
    review_store: DraftReviewSessionStore | None = None,
    extraction_provider=None,
) -> None:
    chat_id = update.effective_chat.id
    now = utc_now()
    if review_store is not None and review_store.load_session(chat_id, now=now):
        await _reply_text(update, _cancel_active_flow_first())
        return
    existing_session = session_store.load_session(chat_id)
    if _expire_initial_session_if_stale(
        session_store,
        ux_events,
        existing_session,
        chat_id,
        now,
        settings.initial_session_ttl_sec,
    ):
        await _reply_text(update, _expired_initial_session_text(tone))
        return
    existing_flow = (
        capture_flow_store.load_flow(chat_id, now=now)
        if capture_flow_store is not None
        else None
    )
    decision = route_user_input(
        has_classic_session=existing_session is not None,
        active_flow=_flow_kind_for_capture_flow(existing_flow),
        input_kind=InputKind.THREE_BLOCK_COMMAND,
    )
    if decision is RouteDecision.REQUIRE_CANCEL:
        await _reply_text(update, _cancel_active_flow_first())
        return
    if decision is not RouteDecision.ARM_THREE_BLOCK:
        raise RuntimeError(f"Unsupported capture3 route decision: {decision}")

    blocks = _capture3_blocks(getattr(update.message, "text", "") or "")
    if blocks is None:
        await _reply_text(
            update,
            "Используй /capture3 что случилось | что внутри | что сделал",
        )
        return

    review_store = review_store or DraftReviewSessionStore(
        getattr(settings, "runtime_session_dir", session_store.session_dir),
        loop_session_store=session_store,
    )
    extraction_provider = extraction_provider or _capture_extraction_provider_for_settings(
        settings
    )
    await _extract_capture_to_review(
        update,
        review_store,
        ux_events,
        tone,
        chat_id=chat_id,
        settings=settings,
        extraction_provider=extraction_provider,
        mode="three_block",
        pieces=tuple(
            zip(
                ("outside_context", "inner_context", "response_outcome"),
                blocks,
            )
        ),
        now=now,
        media_kind="three_block",
        message_id=getattr(update.message, "message_id", None),
    )


async def _handle_voice_after_authorized(
    update,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    tone,
    *,
    bot=None,
    settings=None,
    transcription_provider=None,
    audio_flow_store: CaptureFlowStore | None = None,
    review_store: DraftReviewSessionStore | None = None,
) -> None:
    if await _reject_unrouted_media_input(
        update,
        session_store,
        ux_events,
        tone,
        audio_flow_store=audio_flow_store,
        review_store=review_store,
        funnel="one_take_audio",
        media_kind="voice",
    ):
        return

    artifact = _voice_input_artifact_from_update(update)
    if artifact is None:
        _log_media_funnel_event(
            ux_events,
            update,
            "input_rejected",
            funnel="one_take_audio",
            media_kind="voice",
            reject_reason="missing_file_id",
        )
        await _reply_text(update, "Не смог прочитать голосовое сообщение")
        return

    _log_media_funnel_event(
        ux_events,
        update,
        "input_received",
        funnel="one_take_audio",
        media_kind=artifact.media_kind,
    )
    if bot is None or settings is None or transcription_provider is None:
        _log_media_funnel_event(
            ux_events,
            update,
            "transcription_pending",
            funnel="one_take_audio",
            media_kind=artifact.media_kind,
        )
        await _reply_text(
            update,
            "Голос получил, но расшифровка еще не подключена. "
            f"{_audio_retry_guidance()}",
        )
        return

    await _transcribe_media_artifact_or_reply(
        update,
        ux_events,
        tone,
        bot=bot,
        settings=settings,
        transcription_provider=transcription_provider,
        artifact=artifact,
        funnel="one_take_audio",
        audio_flow_store=audio_flow_store,
    )


async def _handle_audio_after_authorized(
    update,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    tone,
    *,
    bot=None,
    settings=None,
    transcription_provider=None,
    audio_flow_store: CaptureFlowStore | None = None,
    review_store: DraftReviewSessionStore | None = None,
) -> None:
    if await _reject_unrouted_media_input(
        update,
        session_store,
        ux_events,
        tone,
        audio_flow_store=audio_flow_store,
        review_store=review_store,
        funnel="one_take_audio",
        media_kind="audio",
    ):
        return

    artifact = _audio_input_artifact_from_update(update)
    if artifact is None:
        _log_media_funnel_event(
            ux_events,
            update,
            "input_rejected",
            funnel="one_take_audio",
            media_kind="audio",
            reject_reason="missing_file_id",
        )
        await _reply_text(update, "Не смог прочитать аудиофайл")
        return

    _log_media_funnel_event(
        ux_events,
        update,
        "input_received",
        funnel="one_take_audio",
        media_kind=artifact.media_kind,
    )
    if bot is None or settings is None or transcription_provider is None:
        _log_media_funnel_event(
            ux_events,
            update,
            "transcription_pending",
            funnel="one_take_audio",
            media_kind=artifact.media_kind,
        )
        await _reply_text(update, _audio_transcription_pending_text())
        return

    await _transcribe_media_artifact_or_reply(
        update,
        ux_events,
        tone,
        bot=bot,
        settings=settings,
        transcription_provider=transcription_provider,
        artifact=artifact,
        funnel="one_take_audio",
        audio_flow_store=audio_flow_store,
    )


async def _handle_document_after_authorized(
    update,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    tone,
    *,
    bot=None,
    settings=None,
    transcription_provider=None,
    audio_flow_store: CaptureFlowStore | None = None,
    review_store: DraftReviewSessionStore | None = None,
) -> None:
    if await _reject_unrouted_media_input(
        update,
        session_store,
        ux_events,
        tone,
        audio_flow_store=audio_flow_store,
        review_store=review_store,
        funnel="one_take_audio",
        media_kind="document",
    ):
        return

    artifact = _audio_document_input_artifact_from_update(update)
    if artifact is None:
        _log_media_funnel_event(
            ux_events,
            update,
            "input_rejected",
            funnel="one_take_audio",
            media_kind="document",
            reject_reason="unsupported_document",
        )
        await _reply_text(update, _audio_media_guidance())
        return

    _log_media_funnel_event(
        ux_events,
        update,
        "input_received",
        funnel="one_take_audio",
        media_kind=artifact.media_kind,
    )
    if bot is None or settings is None or transcription_provider is None:
        _log_media_funnel_event(
            ux_events,
            update,
            "transcription_pending",
            funnel="one_take_audio",
            media_kind=artifact.media_kind,
        )
        await _reply_text(update, _audio_transcription_pending_text())
        return

    await _transcribe_media_artifact_or_reply(
        update,
        ux_events,
        tone,
        bot=bot,
        settings=settings,
        transcription_provider=transcription_provider,
        artifact=artifact,
        funnel="one_take_audio",
        audio_flow_store=audio_flow_store,
    )


async def _handle_message_after_authorized(
    update,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    settings: Settings,
    tone,
    *,
    audio_flow_store: CaptureFlowStore | None = None,
    review_store: DraftReviewSessionStore | None = None,
    extraction_provider=None,
) -> None:
    chat_id = update.effective_chat.id
    now = utc_now()
    review_store = review_store or DraftReviewSessionStore(
        getattr(settings, "runtime_session_dir", session_store.session_dir),
        loop_session_store=session_store,
    )
    review = review_store.load_session(chat_id, now=now)
    if review is not None:
        await _reply_text(
            update,
            tone.review_screen(review.observed, target_fields_for_review()),
            reply_markup=_review_reply_markup(),
        )
        return
    session = session_store.load_session(chat_id)
    if _expire_initial_session_if_stale(
        session_store, ux_events, session, chat_id, now, settings.initial_session_ttl_sec
    ):
        await _reply_text(update, _expired_initial_session_text(tone))
        return
    audio_flow = (
        audio_flow_store.load_flow(chat_id, now=now)
        if audio_flow_store is not None
        else None
    )
    decision = route_user_input(
        has_classic_session=session is not None,
        active_flow=_flow_kind_for_capture_flow(audio_flow),
        audio_status=audio_flow.status if audio_flow is not None else None,
        input_kind=InputKind.TEXT,
    )
    if decision is RouteDecision.HANDLE_ONE_TAKE_TEXT:
        text = getattr(update.message, "text", "") or ""
        if not text.strip():
            await _reply_text(update, _one_take_text_guidance())
            return
        audio_flow_store.delete_flow(chat_id)
        await _extract_capture_to_review(
            update,
            review_store,
            ux_events,
            tone,
            chat_id=chat_id,
            settings=settings,
            extraction_provider=(
                extraction_provider
                or _capture_extraction_provider_for_settings(settings)
            ),
            mode="one_take_text",
            pieces=(("one_take_text", text),),
            now=now,
            media_kind="text",
            message_id=getattr(update.message, "message_id", None),
        )
        return
    if decision is RouteDecision.HANDLE_THREE_BLOCK_TEXT:
        text = (getattr(update.message, "text", "") or "").strip()
        if not text:
            await _reply_text(update, _three_block_prompt(len(audio_flow.blocks)))
            return
        if len(audio_flow.blocks) < 2:
            audio_flow = audio_flow_store.append_three_block(
                chat_id, text, now=now
            )
            await _reply_text(update, _three_block_prompt(len(audio_flow.blocks)))
            return
        blocks = (*audio_flow.blocks, text)
        audio_flow_store.delete_flow(chat_id)
        await _extract_capture_to_review(
            update,
            review_store,
            ux_events,
            tone,
            chat_id=chat_id,
            settings=settings,
            extraction_provider=(
                extraction_provider
                or _capture_extraction_provider_for_settings(settings)
            ),
            mode="three_block",
            pieces=tuple(
                zip(
                    ("outside_context", "inner_context", "response_outcome"),
                    blocks,
                )
            ),
            now=now,
            media_kind="text",
            message_id=getattr(update.message, "message_id", None),
        )
        return
    if decision is RouteDecision.TRANSCRIPT_CONFIRMATION_REQUIRED:
        await _reply_text(
            update,
            "Подтверди расшифровку кнопкой «Продолжить» или «Отклонить».",
            reply_markup=_transcript_confirmation_reply_markup(),
        )
        return
    if decision is RouteDecision.AUDIO_ONE_TAKE_EXPECTS_MEDIA:
        ux_events.append(
            telegram_event(
                "input_rejected",
                _telegram_update_user_id(update),
                created_at=now,
                chat_id=chat_id,
                message_kind="text",
                funnel="audio_one_take",
                media_kind="text",
                reject_reason="audio_flow_expects_media",
            )
        )
        await _reply_text(update, _audio_media_guidance())
        return
    if decision is RouteDecision.REQUIRE_CANCEL:
        ux_events.append(
            telegram_event(
                "input_rejected",
                _telegram_update_user_id(update),
                created_at=now,
                chat_id=chat_id,
                message_kind="text",
                funnel="flow_router",
                media_kind="text",
                reject_reason="active_flow_requires_cancel",
            )
        )
        await _reply_text(update, _cancel_active_flow_first())
        return
    if decision is RouteDecision.SHOW_START_GUIDANCE:
        ux_events.append(
            telegram_event(
                "input_rejected",
                _telegram_update_user_id(update),
                created_at=now,
                chat_id=chat_id,
                message_kind="text",
                funnel="one_take_text",
                media_kind="text",
                reject_reason="idle_requires_start",
            )
        )
        await _reply_text(update, tone.no_active_loop_start())
        return
    if decision is not RouteDecision.HANDLE_CLASSIC_10Q_TEXT:
        raise RuntimeError(f"Unsupported text route decision: {decision}")
    _ensure_episode_date(session, now)
    if session.session_id is None:
        session.session_id = new_session_id(str(chat_id), now)
        ux_events.append(
            base_event(
                "session_started",
                session.session_id,
                str(chat_id),
                created_at=now,
            )
        )
        _log_step_prompted(ux_events, session, str(chat_id), now=now)

    target_before = active_target(session)
    target_index_before = session.target_index
    result = apply_user_reply(session, update.message.text or "", tone)
    now = utc_now()
    target_after = active_target(session)
    advanced = result.should_save or target_after != target_before
    ux_events.append(
        base_event(
            "step_answered",
            session.session_id,
            str(chat_id),
            created_at=now,
            target=target_before,
            target_index=target_index_before,
            duration_sec=_duration_since_last_prompt(session, now),
            advanced=advanced,
            answer_chars=len(update.message.text or ""),
        )
    )
    if result.should_save:
        artifact = build_capture_artifact(
            chat_id=chat_id,
            mode="classic_10q",
            media_kind="text",
            pieces=tuple(
                (field, session.observed[field]["value"])
                for field in target_fields(session)
                if session.observed.get(field) is not None
            ),
            created_at=now,
            message_id=getattr(update.message, "message_id", None),
            source_metadata={"message_kind": "text"},
        )
        artifact_path = save_capture_artifact(
            getattr(
                settings,
                "capture_artifact_dir",
                review_store.review_dir.parent / "capture-artifacts",
            ),
            artifact,
        )
        outcome = project_classic_10q(
            artifact,
            getattr(
                settings,
                "capture_extraction_dir",
                review_store.review_dir.parent / "capture-extractions",
            ),
            created_at=now,
        )
        review = review_session_from_extraction(
            chat_id=chat_id,
            mode="classic_10q",
            observed=outcome.draft.observed,
            episode_date=session.episode_date,
            now=now,
            capture_id=artifact.capture_id,
            capture_artifact_path=artifact_path,
            extraction_id=outcome.extraction.extraction_id,
            extraction_path=outcome.path,
            media_kind="text",
        )
        review_store.save_session(review)
        session_store.delete_session(chat_id)
        await _reply_text(
            update,
            tone.review_screen(review.observed, target_fields_for_review()),
            reply_markup=_review_reply_markup(),
        )
        return
    _log_step_prompted(ux_events, session, str(chat_id), now=now)
    session_store.save_session(session)
    reply = result.reply
    if advanced:
        reply = tone.next_prompt_bridge(
            completed_observed_count(session),
            len(target_fields(session)),
            result.reply,
        )
    await _reply_text(update, reply)


async def _handle_episode_callback_after_authorized(
    update,
    storage: JsonStorage,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    tone,
    *,
    review_store: DraftReviewSessionStore | None = None,
) -> None:
    query = getattr(update, "callback_query", None)
    if query is not None:
        await query.answer()
    chat_id = update.effective_chat.id
    review_store = review_store or DraftReviewSessionStore(
        session_store.session_dir,
        loop_session_store=session_store,
    )
    now = utc_now()
    review = review_store.load_session(chat_id, now=now)
    if review is None:
        if query is not None:
            await _reply_to_callback(query, tone.no_active_loop())
        return

    data = getattr(query, "data", "") if query is not None else ""
    event_kwargs = {
        "funnel": review.mode,
        "media_kind": review.media_kind or "text",
    }
    draft_fields = sum(
        1 for value in review.observed.values() if value is not None
    )
    if data == "episode:save":
        ux_events.append(
            base_event(
                "draft_confirmed",
                review.review_id,
                str(chat_id),
                created_at=now,
                draft_fields=draft_fields,
                **event_kwargs,
            )
        )
        episode_path = storage.save_observed_episode(
            chat_id=chat_id,
            episode_date=review.episode_date,
            observed=review.observed,
        )
        if review.extraction_path:
            link_capture_extraction_to_episode(
                Path(review.extraction_path),
                episode_path.stem,
            )
        if review.intake_transcript_path:
            link_intake_transcript_to_episode(
                Path(review.intake_transcript_path),
                episode_path.stem,
            )
        episode_count = storage.episode_count_for_chat(chat_id)
        ux_events.append(
            base_event(
                "episode_saved",
                review.review_id,
                str(chat_id),
                created_at=now,
                draft_fields=draft_fields,
                **event_kwargs,
            )
        )
        ux_events.append(
            base_event(
                "session_completed",
                review.review_id,
                str(chat_id),
                created_at=now,
            )
        )
        review_store.delete_session(chat_id)
        await _reply_to_callback(query, tone.saved_episode(tone.complete(), episode_count))
        return
    if data == "episode:cancel":
        ux_events.append(
            base_event(
                "draft_discarded",
                review.review_id,
                str(chat_id),
                created_at=now,
                cancel_reason="review_cancel",
                draft_fields=draft_fields,
                **event_kwargs,
            )
        )
        ux_events.append(
            base_event(
                "session_cancelled",
                review.review_id,
                str(chat_id),
                created_at=now,
                cancel_reason="review_cancel",
            )
        )
        review_store.delete_session(chat_id)
        await _reply_to_callback(query, tone.cancel())
        return
    if query is not None:
        await _reply_to_callback(
            query, tone.review_screen(review.observed, target_fields_for_review())
        )


async def _handle_transcript_callback_after_authorized(
    update,
    session_store: LoopSessionStore,
    capture_flow_store: CaptureFlowStore,
    ux_events: UxEventLog,
    tone,
    *,
    settings=None,
    review_store: DraftReviewSessionStore | None = None,
    extraction_provider=None,
) -> None:
    query = getattr(update, "callback_query", None)
    if query is not None:
        await query.answer()
    chat_id = update.effective_chat.id
    now = utc_now()
    flow = capture_flow_store.load_flow(chat_id, now=now)
    if (
        flow is None
        or flow.mode != "one_take_audio"
        or flow.status != "awaiting_transcript_confirmation"
        or not flow.transcript_path
    ):
        await _reply_to_callback(query, tone.no_active_loop(), parse_mode=None)
        return

    data = getattr(query, "data", "") if query is not None else ""
    if data == "transcript:reject":
        capture_flow_store.delete_flow(chat_id)
        ux_events.append(
            telegram_event(
                "transcript_rejected",
                _telegram_update_user_id(update),
                created_at=now,
                chat_id=chat_id,
                message_kind="callback",
                funnel="one_take_audio",
                media_kind="audio",
                reject_reason="transcript_rejected",
            )
        )
        await _reply_to_callback(
            query,
            "Расшифровка сохранена как исходный материал. Эпизод не создан.",
            parse_mode=None,
        )
        return
    if data != "transcript:continue":
        await _reply_to_callback(
            query,
            "Выбери «Продолжить» или «Отклонить».",
            reply_markup=_transcript_confirmation_reply_markup(),
            parse_mode=None,
        )
        return

    transcript_path = Path(flow.transcript_path)
    transcript = load_intake_transcript(transcript_path)
    if transcript.chat_id != chat_id:
        raise ValueError("transcript chat id does not match active flow")
    capture_flow_store.delete_flow(chat_id)
    review_store = review_store or DraftReviewSessionStore(
        getattr(settings, "runtime_session_dir", session_store.session_dir),
        loop_session_store=session_store,
    )
    await _extract_capture_to_review(
        update,
        review_store,
        ux_events,
        tone,
        chat_id=chat_id,
        settings=settings,
        extraction_provider=(
            extraction_provider
            or _capture_extraction_provider_for_settings(settings)
        ),
        mode="one_take_audio",
        pieces=(("transcript", transcript.text),),
        now=now,
        media_kind=transcript.media_kind,
        intake_transcript_path=str(transcript_path),
        message_id=transcript.message_id,
    )


async def _reply_to_callback(
    query, text: str, *, reply_markup=None, parse_mode="HTML"
) -> None:
    message = getattr(query, "message", None) if query is not None else None
    if message is not None:
        kwargs = {}
        if parse_mode is not None:
            kwargs["parse_mode"] = parse_mode
        if reply_markup is not None:
            kwargs["reply_markup"] = reply_markup
        await message.reply_text(text, **kwargs)


def _review_reply_markup():
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:  # pragma: no cover - runtime dependency guard
        return None
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Сохранить", callback_data="episode:save"),
                InlineKeyboardButton("Отменить", callback_data="episode:cancel"),
            ]
        ]
    )


def _transcript_confirmation_reply_markup():
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:  # pragma: no cover - runtime dependency guard
        return None
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Продолжить",
                    callback_data="transcript:continue",
                ),
                InlineKeyboardButton(
                    "Отклонить",
                    callback_data="transcript:reject",
                ),
            ]
        ]
    )


def _profile_details_reply_markup():
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:  # pragma: no cover - runtime dependency guard
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Подробнее", callback_data="profile:details")]]
    )


async def _authorize(
    update,
    settings: Settings,
    tone,
    ux_events: UxEventLog,
    userlist: JsonUserList,
    bot=None,
) -> bool:
    chat = update.effective_chat
    if chat is None:
        return False
    now = utc_now()
    user_id = _telegram_update_user_id(update)
    metadata = _telegram_update_metadata(update)
    ux_events.append(
        telegram_event(
            "update_received",
            user_id,
            created_at=now,
            **metadata,
        )
    )
    if userlist.is_approved(chat.id):
        return True

    ux_events.append(
        telegram_event(
            "unauthorized_attempt",
            user_id,
            created_at=now,
            **metadata,
        )
    )
    result = userlist.upsert_waitlisted(
        chat.id,
        user_id,
        now=now,
        profile=_telegram_user_profile(update),
    )
    if result.created:
        await _notify_admin_waitlist(bot, settings, tone, result.record)
    if update.message is not None:
        await _reply_text(update, tone.waitlisted())
    return False


async def _authorize_admin(
    update,
    settings: Settings,
    tone,
    ux_events: UxEventLog,
) -> bool:
    chat = update.effective_chat
    if chat is None:
        return False
    now = utc_now()
    user_id = _telegram_update_user_id(update)
    metadata = _telegram_update_metadata(update)
    ux_events.append(
        telegram_event(
            "update_received",
            user_id,
            created_at=now,
            **metadata,
        )
    )
    if chat.id not in admin_chat_ids_for_settings(settings):
        ux_events.append(
            telegram_event(
                "unauthorized_attempt",
                user_id,
                created_at=now,
                **metadata,
            )
        )
        if update.message is not None:
            await _reply_text(update, tone.unauthorized())
        return False
    return True


async def _authorize_admin_user(
    update,
    settings: Settings,
    tone,
    ux_events: UxEventLog,
    userlist: JsonUserList,
    bot=None,
) -> bool:
    if not await _authorize_admin(update, settings, tone, ux_events):
        return False
    chat = update.effective_chat
    if chat is None:
        return False
    if userlist.is_approved(chat.id):
        return True

    now = utc_now()
    user_id = _telegram_update_user_id(update)
    metadata = _telegram_update_metadata(update)
    ux_events.append(
        telegram_event(
            "unauthorized_attempt",
            user_id,
            created_at=now,
            **metadata,
        )
    )
    result = userlist.upsert_waitlisted(
        chat.id,
        user_id,
        now=now,
        profile=_telegram_user_profile(update),
    )
    if result.created:
        await _notify_admin_waitlist(bot, settings, tone, result.record)
    if update.message is not None:
        await _reply_text(update, tone.waitlisted())
    return False


async def _handle_admin_decision(
    update,
    args,
    settings: Settings,
    tone,
    ux_events: UxEventLog,
    userlist: JsonUserList,
    decision: str,
    bot=None,
) -> None:
    if not await _authorize_admin(update, settings, tone, ux_events):
        return
    command = f"/{decision}"
    if len(args) != 1:
        await _reply_text(update, tone.admin_bad_command(command))
        return
    try:
        target_chat_id = int(args[0])
    except ValueError:
        await _reply_text(update, tone.admin_bad_command(command))
        return

    decided_by = _telegram_update_user_id(update)
    now = utc_now()
    if decision == "approve":
        userlist.approve(target_chat_id, decided_by=decided_by, now=now)
        await _reply_text(update, tone.admin_approved(target_chat_id))
        await _notify_approved_user(bot, target_chat_id, tone)
        return
    if decision == "pause":
        userlist.pause(target_chat_id, decided_by=decided_by, now=now)
        await _reply_text(update, tone.admin_paused(target_chat_id))
        return
    raise ValueError(f"Unknown admin decision: {decision}")


async def _notify_admin_waitlist(bot, settings: Settings, tone, record: dict) -> None:
    owner_chat_id = owner_chat_id_for_settings(settings)
    if bot is None or owner_chat_id is None:
        return
    await bot.send_message(
        chat_id=owner_chat_id,
        text=tone.admin_waitlist_notice(
            record["chat_id"], str(record["user_id"]), record
        ),
        parse_mode="HTML",
    )


async def _notify_approved_user(bot, chat_id: int, tone) -> None:
    if bot is None:
        return
    await bot.send_message(
        chat_id=chat_id,
        text=tone.approval_granted(),
        parse_mode="HTML",
    )


async def _reply_text(update, text: str, *, reply_markup=None, parse_mode="HTML"):
    message = update.message
    if message is None:
        query = getattr(update, "callback_query", None)
        message = getattr(query, "message", None) if query is not None else None
    if message is not None:
        kwargs = {}
        if parse_mode is not None:
            kwargs["parse_mode"] = parse_mode
        if reply_markup is not None:
            kwargs["reply_markup"] = reply_markup
        return await message.reply_text(
            text,
            **kwargs,
        )
    return None


def _telegram_update_user_id(update) -> str:
    user = update.effective_user
    if user is not None:
        return str(user.id)
    return str(update.effective_chat.id)


def _telegram_user_profile(update) -> dict:
    user = update.effective_user
    if user is None:
        return {}
    fields = {
        "username": getattr(user, "username", None),
        "first_name": getattr(user, "first_name", None),
        "last_name": getattr(user, "last_name", None),
        "language_code": getattr(user, "language_code", None),
        "is_bot": getattr(user, "is_bot", None),
    }
    return {
        key: value
        for key, value in fields.items()
        if value is not None and value != ""
    }


def _log_audio_lifecycle(
    marker: str,
    *,
    update,
    funnel: str,
    media_kind: str,
    duration_seconds: int | None = None,
    file_size: int | None = None,
    elapsed_ms: int | None = None,
    failure_reason: str | None = None,
) -> None:
    fields = {
        "marker": marker,
        "chat_id": update.effective_chat.id,
        "funnel": funnel,
        "media_kind": media_kind,
        "duration_seconds": duration_seconds,
        "file_size": file_size,
        "elapsed_ms": elapsed_ms,
        "failure_reason": failure_reason,
    }
    safe = " ".join(
        f"{key}={value}" for key, value in fields.items() if value is not None
    )
    print(f"audio_lifecycle {safe}", flush=True)

def _is_initial_capture_step(session) -> bool:
    return (
        session is not None
        and not session.awaiting_save_confirmation
        and session.target_index == 0
        and completed_draft_field_count(session) == 0
    )


def _current_question_requires_text() -> str:
    return "Ответь, пожалуйста, текстом на текущий вопрос."


def _cancel_active_flow_first() -> str:
    return "Сначала отправь /cancel, чтобы завершить активный сценарий."


def _audio_media_guidance() -> str:
    return "Пришли голосовое сообщение или аудиофайл. Чтобы выйти, отправь /cancel."


def _one_take_text_guidance() -> str:
    return "Опиши один конкретный эпизод одним сообщением. Чтобы выйти, отправь /cancel."


def _three_block_prompt(completed: int) -> str:
    prompts = (
        "1/3 Что произошло?",
        "2/3 Что происходило внутри — какая мысль или смысл мелькнули?",
        "3/3 Что ты сделал?",
    )
    if completed < 0 or completed >= len(prompts):
        raise ValueError("invalid three-block progress")
    return prompts[completed]


def _flow_kind_for_capture_flow(flow) -> FlowKind:
    if flow is None:
        return FlowKind.IDLE
    return FlowKind(flow.mode)


def _audio_retry_guidance() -> str:
    return "Попробуй другое голосовое или аудио либо отправь /cancel."


async def _reject_unrouted_media_input(
    update,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    tone,
    *,
    audio_flow_store: CaptureFlowStore | None,
    review_store: DraftReviewSessionStore | None = None,
    funnel: str,
    media_kind: str,
) -> bool:
    chat_id = update.effective_chat.id
    if (
        review_store is not None
        and review_store.load_session(chat_id, now=utc_now()) is not None
    ):
        await _reply_text(update, _cancel_active_flow_first())
        return True
    audio_flow = (
        audio_flow_store.load_flow(chat_id, now=utc_now())
        if audio_flow_store is not None
        else None
    )
    decision = route_user_input(
        has_classic_session=session_store.load_session(chat_id) is not None,
        active_flow=_flow_kind_for_capture_flow(audio_flow),
        audio_status=audio_flow.status if audio_flow is not None else None,
        input_kind=InputKind.MEDIA,
    )
    if decision is RouteDecision.SHOW_START_GUIDANCE:
        reject_reason = "idle_requires_start"
        reply = tone.no_active_loop_start()
    elif decision is RouteDecision.SHOW_TEXT_REQUIRED:
        reject_reason = "active_session"
        reply = _current_question_requires_text()
    elif decision is RouteDecision.REQUIRE_CANCEL:
        reject_reason = "active_flow_requires_cancel"
        reply = _cancel_active_flow_first()
    elif decision is RouteDecision.TRANSCRIPT_CONFIRMATION_REQUIRED:
        reject_reason = "transcript_confirmation_required"
        reply = "Сначала подтверди или отклони готовую расшифровку."
    elif decision is RouteDecision.HANDLE_AUDIO_ONE_TAKE_MEDIA:
        return False
    else:
        raise RuntimeError(f"Unsupported media route decision: {decision}")

    _log_media_funnel_event(
        ux_events,
        update,
        "input_rejected",
        funnel=funnel,
        media_kind=media_kind,
        reject_reason=reject_reason,
    )
    await _reply_text(update, reply)
    return True


async def _transcribe_and_attach_in_worker(transcription_provider, artifact, media):
    if getattr(transcription_provider, "_m3_run_inline_for_tests", False):
        return transcribe_and_attach(transcription_provider, artifact, media)

    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def worker() -> None:
        try:
            result = transcribe_and_attach(transcription_provider, artifact, media)
        except BaseException as exc:  # pragma: no cover - surfaced through handler tests
            loop.call_soon_threadsafe(future.set_exception, exc)
        else:
            loop.call_soon_threadsafe(future.set_result, result)

    Thread(target=worker, name="m3-audio-transcription", daemon=True).start()
    return await future


async def _transcribe_media_artifact_or_reply(
    update,
    ux_events: UxEventLog,
    tone,
    *,
    bot,
    settings,
    transcription_provider,
    artifact,
    funnel: str,
    audio_flow_store: CaptureFlowStore | None,
) -> None:
    _log_audio_lifecycle(
        "media_received",
        update=update,
        funnel=funnel,
        media_kind=artifact.media_kind,
        duration_seconds=artifact.duration_seconds,
        file_size=artifact.file_size,
    )
    request = _telegram_media_request_from_artifact(artifact)
    max_duration_sec = getattr(settings, "audio_max_duration_sec", 300)
    max_file_size_bytes = getattr(settings, "audio_max_file_size_bytes", 20 * 1024 * 1024)
    try:
        validate_telegram_media_request(
            request,
            max_duration_sec=max_duration_sec,
            max_file_size_bytes=max_file_size_bytes,
        )
    except TelegramMediaRejected as exc:
        _log_audio_lifecycle(
            "media_rejected",
            update=update,
            funnel=funnel,
            media_kind=artifact.media_kind,
            duration_seconds=artifact.duration_seconds,
            file_size=artifact.file_size,
            failure_reason=exc.reason,
        )
        _log_media_funnel_event(
            ux_events,
            update,
            "input_rejected",
            funnel=funnel,
            media_kind=artifact.media_kind,
            reject_reason=exc.reason,
        )
        await _reply_text(
            update,
            f"{_media_rejected_text(exc.reason)} {_audio_retry_guidance()}",
        )
        return

    await _reply_text(update, _media_processing_ack_text(artifact.media_kind))

    try:
        download_started = monotonic()
        _log_audio_lifecycle(
            "media_download_started",
            update=update,
            funnel=funnel,
            media_kind=artifact.media_kind,
            duration_seconds=artifact.duration_seconds,
            file_size=artifact.file_size,
        )
        async with temporary_telegram_media(
            bot,
            request,
            temp_dir=getattr(settings, "audio_temp_dir"),
            max_duration_sec=max_duration_sec,
            max_file_size_bytes=max_file_size_bytes,
        ) as media:
            _log_audio_lifecycle(
                "media_download_done",
                update=update,
                funnel=funnel,
                media_kind=artifact.media_kind,
                duration_seconds=artifact.duration_seconds,
                file_size=artifact.file_size,
                elapsed_ms=int((monotonic() - download_started) * 1000),
            )
            transcription_started = monotonic()
            _log_audio_lifecycle(
                "transcription_started",
                update=update,
                funnel=funnel,
                media_kind=artifact.media_kind,
                duration_seconds=artifact.duration_seconds,
                file_size=artifact.file_size,
            )
            transcribed = await _transcribe_and_attach_in_worker(
                transcription_provider, artifact, media
            )
            _log_audio_lifecycle(
                "transcription_done",
                update=update,
                funnel=funnel,
                media_kind=artifact.media_kind,
                duration_seconds=artifact.duration_seconds,
                file_size=artifact.file_size,
                elapsed_ms=int((monotonic() - transcription_started) * 1000),
            )
    except TelegramMediaRejected as exc:
        _log_media_funnel_event(
            ux_events,
            update,
            "input_rejected",
            funnel=funnel,
            media_kind=artifact.media_kind,
            reject_reason=exc.reason,
        )
        await _reply_text(
            update,
            f"{_media_rejected_text(exc.reason)} {_audio_retry_guidance()}",
        )
        return
    except TelegramMediaDownloadFailed:
        _log_audio_lifecycle(
            "media_download_failed",
            update=update,
            funnel=funnel,
            media_kind=artifact.media_kind,
            duration_seconds=artifact.duration_seconds,
            file_size=artifact.file_size,
            failure_reason="download_failed",
        )
        _log_media_funnel_event(
            ux_events,
            update,
            "media_download_failed",
            funnel=funnel,
            media_kind=artifact.media_kind,
        )
        await _reply_text(
            update,
            f"Не смог скачать аудио. {_audio_retry_guidance()}",
        )
        return
    except (TranscriptionFailed, TranscriptionUnavailable, ValueError):
        _log_audio_lifecycle(
            "transcription_failed",
            update=update,
            funnel=funnel,
            media_kind=artifact.media_kind,
            duration_seconds=artifact.duration_seconds,
            file_size=artifact.file_size,
            failure_reason="transcription_failed",
        )
        _log_media_funnel_event(
            ux_events,
            update,
            "transcription_failed",
            funnel=funnel,
            media_kind=artifact.media_kind,
        )
        await _reply_text(
            update,
            f"Не смог расшифровать аудио. {_audio_retry_guidance()}",
        )
        return

    _log_media_funnel_event(
        ux_events,
        update,
        "transcript_created",
        funnel=funnel,
        media_kind=artifact.media_kind,
    )
    try:
        transcript_artifact = build_intake_transcript(transcribed)
        transcript_path = save_intake_transcript(
            getattr(settings, "intake_transcript_dir", Path("data/intake-transcripts")),
            transcript_artifact,
        )
    except (OSError, ValueError):
        _log_audio_lifecycle(
            "transcript_store_failed",
            update=update,
            funnel=funnel,
            media_kind=artifact.media_kind,
            duration_seconds=artifact.duration_seconds,
            file_size=artifact.file_size,
            failure_reason="transcript_store_failed",
        )
        await _reply_text(
            update,
            f"Не смог сохранить расшифровку. {_audio_retry_guidance()}",
        )
        return

    _log_audio_lifecycle(
        "audio_intake_completed",
        update=update,
        funnel=funnel,
        media_kind=artifact.media_kind,
        duration_seconds=artifact.duration_seconds,
        file_size=artifact.file_size,
    )
    if audio_flow_store is None:
        raise RuntimeError("audio capture flow store is required")
    audio_flow_store.await_transcript_confirmation(
        update.effective_chat.id,
        transcript_path,
        now=utc_now(),
        ttl_sec=settings.initial_session_ttl_sec,
    )
    await _send_transcript_confirmation(
        update,
        artifact_text(transcribed),
    )


def _telegram_media_request_from_artifact(artifact) -> TelegramMediaRequest:
    return TelegramMediaRequest(
        file_id=artifact.file_id or "",
        media_kind=artifact.media_kind,
        duration_seconds=artifact.duration_seconds,
        file_size=artifact.file_size,
        mime_type=artifact.mime_type,
        file_name=artifact.file_name,
    )


async def _send_transcript_confirmation(update, transcript: str) -> None:
    chunks = _split_telegram_text(transcript)
    await _reply_text(update, "Готово, расшифровал. Проверь текст:", parse_mode=None)
    for chunk in chunks:
        await _reply_text(update, chunk, parse_mode=None)
    await _reply_text(
        update,
        "Продолжить с этой расшифровкой?",
        reply_markup=_transcript_confirmation_reply_markup(),
        parse_mode=None,
    )


def _audio_intake_preview(text: str, *, limit: int = 180) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _split_telegram_text(
    text: str,
    *,
    limit: int = TELEGRAM_TEXT_LIMIT,
) -> tuple[str, ...]:
    if limit <= 0:
        raise ValueError("Telegram text limit must be positive")
    if not text:
        return ()
    return tuple(text[index:index + limit] for index in range(0, len(text), limit))


def _media_processing_ack_text(media_kind: str) -> str:
    if media_kind == "voice":
        return "Голос получил. Беру в расшифровку — когда будет готово, продолжим."
    return "Аудио получил. Беру в расшифровку — когда будет готово, продолжим."

def _media_rejected_text(reason: str) -> str:
    if reason == "over_duration":
        return "Слишком длинное аудио."
    if reason == "over_size":
        return "Аудиофайл слишком большой."
    return "Не могу обработать этот аудиофайл."

def _log_media_funnel_event(
    ux_events: UxEventLog,
    update,
    event_type: str,
    *,
    funnel: str,
    media_kind: str,
    reject_reason: str | None = None,
) -> None:
    ux_events.append(
        telegram_event(
            event_type,
            _telegram_update_user_id(update),
            created_at=utc_now(),
            chat_id=update.effective_chat.id,
            message_kind=media_kind,
            funnel=funnel,
            media_kind=media_kind,
            reject_reason=reject_reason,
        )
    )


def _audio_transcription_pending_text() -> str:
    return (
        "Аудио получил, но расшифровка еще не подключена. "
        f"{_audio_retry_guidance()}"
    )


def _audio_input_artifact_from_update(update):
    audio = getattr(update.message, "audio", None)
    if audio is None:
        return None
    file_id = getattr(audio, "file_id", "") or ""
    if not file_id:
        return None
    return audio_input_artifact(
        file_id,
        source_ref=_telegram_update_metadata(update),
        duration_seconds=getattr(audio, "duration", None),
        mime_type=getattr(audio, "mime_type", None),
        file_size=getattr(audio, "file_size", None),
        file_name=getattr(audio, "file_name", None),
    )


def _audio_document_input_artifact_from_update(update):
    document = getattr(update.message, "document", None)
    if document is None:
        return None
    try:
        return audio_document_input_artifact(
            getattr(document, "file_id", "") or "",
            source_ref=_telegram_update_metadata(update),
            mime_type=getattr(document, "mime_type", None),
            file_size=getattr(document, "file_size", None),
            file_name=getattr(document, "file_name", None),
        )
    except ValueError:
        return None


def _voice_input_artifact_from_update(update):
    voice = getattr(update.message, "voice", None)
    if voice is None:
        return None
    file_id = getattr(voice, "file_id", "") or ""
    if not file_id:
        return None
    return voice_input_artifact(
        file_id,
        source_ref=_telegram_update_metadata(update),
        duration_seconds=getattr(voice, "duration", None),
        mime_type=getattr(voice, "mime_type", None),
        file_size=getattr(voice, "file_size", None),
    )


def _capture3_blocks(text: str) -> tuple[str, str, str] | None:
    payload = _command_argument_text(text)
    parts = tuple(part.strip() for part in payload.split("|"))
    if len(parts) != 3 or any(not part for part in parts):
        return None
    return parts


def _command_argument_text(text: str) -> str:
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


def _telegram_update_metadata(update) -> dict:
    chat = update.effective_chat
    user = update.effective_user
    message = update.message
    text = (getattr(message, "text", None) or "").strip() if message else ""
    voice = getattr(message, "voice", None) if message else None
    audio = getattr(message, "audio", None) if message else None
    document = getattr(message, "document", None) if message else None
    command = text.split(maxsplit=1)[0] if text.startswith("/") else None
    if command:
        message_kind = "command"
    elif text:
        message_kind = "text"
    elif voice:
        message_kind = "voice"
    elif audio:
        message_kind = "audio"
    elif document:
        message_kind = "document"
    else:
        message_kind = None

    metadata = {
        "chat_id": chat.id if chat is not None else None,
        "message_id": getattr(message, "message_id", None) if message else None,
        "message_kind": message_kind,
        "command": command,
    }
    if message_kind == "text":
        metadata["answer_chars"] = len(text)
    return {key: value for key, value in metadata.items() if value is not None}


def _new_session_for_now(chat_id: int, now):
    return new_session(
        chat_id,
        session_id=new_session_id(str(chat_id), now),
        episode_date=_episode_date_for_now(now),
        flow_mode="classic_10q",
        capture_funnel="classic_10q",
        media_kind="text",
    )


def _start_new_session(
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    chat_id: int,
    now,
):
    session = _new_session_for_now(chat_id, now)
    ux_events.append(
        base_event(
            "session_started",
            session.session_id,
            str(chat_id),
            created_at=now,
        )
    )
    _log_step_prompted(ux_events, session, str(chat_id), now=now)
    session_store.save_session(session)
    return session


def _ensure_episode_date(session, now) -> None:
    if session.episode_date is None:
        session.episode_date = _episode_date_for_now(now)


def _episode_date_for_now(now) -> str:
    return now.astimezone().date().isoformat()


def _session_cancelled_event(
    session,
    user_id: str,
    *,
    now,
    cancel_reason: str | None = None,
) -> dict:
    return base_event(
        "session_cancelled",
        session.session_id,
        user_id,
        created_at=now,
        target=active_target(session),
        target_index=session.target_index,
        cancel_reason=cancel_reason,
    )


def _log_step_prompted(
    ux_events: UxEventLog, session, user_id: str, *, now
) -> None:
    session.last_prompted_at = format_utc(now)
    target = active_target(session)
    target_index = session.target_index
    ux_events.append(
        base_event(
            "step_prompted",
            session.session_id,
            user_id,
            created_at=now,
            target=target,
            target_index=target_index,
        )
    )
    if target != "complete":
        ux_events.append(
            base_event(
                "gap_question_asked",
                session.session_id,
                user_id,
                created_at=now,
                target=target,
                target_index=target_index,
                draft_fields=completed_draft_field_count(session),
                **_session_funnel_event_kwargs(session),
            )
        )


def _session_funnel_event_kwargs(session: LoopSession) -> dict[str, str]:
    return {
        "funnel": session.capture_funnel or "classic_10q",
        "media_kind": session.media_kind or "text",
    }


def _duration_since_last_prompt(session, now) -> int:
    if session.last_prompted_at is None:
        return 0
    return max(0, int((now - parse_utc(session.last_prompted_at)).total_seconds()))


def _expired_initial_session_text(tone) -> str:
    return tone.expired_initial_session()


def _expire_initial_session_if_stale(
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    session,
    chat_id: int,
    now,
    initial_session_ttl_sec: int,
) -> bool:
    if session is None or not _is_initial_session_stale(
        session, now, initial_session_ttl_sec
    ):
        return False

    if session.session_id is None:
        session.session_id = new_session_id(str(chat_id), now)
    ux_events.append(
        base_event(
            "session_cancelled",
            session.session_id,
            str(chat_id),
            created_at=now,
            target=active_target(session),
            target_index=session.target_index,
            cancel_reason="initial_session_expired",
        )
    )
    session_store.delete_session(chat_id)
    return True


def _is_initial_session_stale(session, now, initial_session_ttl_sec: int) -> bool:
    if session.target_index != 0 or session.observed:
        return False
    if session.last_prompted_at is None:
        return False
    age_sec = int((now - parse_utc(session.last_prompted_at)).total_seconds())
    return age_sec >= initial_session_ttl_sec


if __name__ == "__main__":
    main()
