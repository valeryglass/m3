from __future__ import annotations

import asyncio
from pathlib import Path
from threading import Thread
from time import monotonic
from app.config import (
    Settings,
    admin_chat_ids_for_settings,
    load_settings,
    owner_chat_id_for_settings,
)
from app.analytics_loader import annotation_coverage_for_episode_ids
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
from app.episode_drafts import draft_from_input_artifact, draft_from_three_blocks
from app.input_funnels import (
    artifact_text,
    audio_document_input_artifact,
    audio_input_artifact,
    text_input_artifact,
    voice_input_artifact,
)
from app.intake_transcripts import (
    build_intake_transcript,
    save_intake_transcript,
)
from app.loop_extractor import (
    active_target,
    apply_user_reply,
    completed_draft_field_count,
    completed_observed_count,
    new_session,
    new_session_from_draft,
    prompt_for_current_target,
    status_text,
    target_fields,
)
from app.session_store import LoopSessionStore
from app.storage import JsonStorage
from app.tone_engine import load_tone_engine
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
    userlist = JsonUserList(settings.userlist_path)
    ux_events = UxEventLog(settings.ux_event_log)
    tone = load_tone_engine(settings.tone_config)
    transcription_provider = _transcription_provider_for_settings(settings)

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
        await _handle_start_after_authorized(update, session_store, ux_events, tone)

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        chat_id = update.effective_chat.id
        now = utc_now()
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
            update, session_store, ux_events, settings, tone
        )

    async def capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_capture_after_authorized(
            update, session_store, ux_events, settings, tone
        )

    async def capture3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_capture3_after_authorized(
            update, session_store, ux_events, settings, tone
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
        )

    async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_message_after_authorized(
            update, session_store, ux_events, settings, tone
        )

    async def episode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_episode_callback_after_authorized(
            update, storage, session_store, ux_events, tone
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
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("capture", capture))
    application.add_handler(CommandHandler("capture3", capture3))
    application.add_handler(CommandHandler("approve", approve))
    application.add_handler(CommandHandler("pause", pause))
    application.add_handler(CommandHandler("report_graph", report_graph))
    application.add_handler(CommandHandler("report_ux", report_ux))
    application.add_handler(CallbackQueryHandler(episode_callback, pattern="^episode:"))
    application.add_handler(CallbackQueryHandler(profile_callback, pattern="^profile:"))
    application.add_handler(MessageHandler(filters.VOICE, voice))
    application.add_handler(MessageHandler(filters.AUDIO, audio))
    application.add_handler(MessageHandler(filters.Document.ALL, document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))
    application.run_polling(bootstrap_retries=-1)


REGISTERED_COMMANDS = (
    "start",
    "status",
    "cancel",
    "help",
    "profile",
    "capture",
    "capture3",
    "approve",
    "pause",
    "report_graph",
    "report_ux",
)
VISIBLE_COMMANDS = ("start", "cancel", "help")
REPORT_REPLY_LIMIT = 3800


def _transcription_provider_for_settings(settings):
    if getattr(settings, "transcription_provider", "missing") == "whisper":
        return WhisperCliTranscriptionProvider(
            command=getattr(settings, "whisper_command", "whisper"),
            model=getattr(settings, "whisper_model", None),
            language=getattr(settings, "whisper_language", None),
        )
    return MissingTranscriptionProvider()


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
) -> None:
    chat_id = update.effective_chat.id
    now = utc_now()
    session = session_store.load_session(chat_id)
    if session is not None and session.session_id is not None:
        ux_events.append(
            _session_cancelled_event(
                session,
                str(chat_id),
                now=now,
                cancel_reason="restart",
            )
        )
    session = _start_new_session(session_store, ux_events, chat_id, now)
    await _reply_text(
        update,
        tone.start_session(
            prompt_for_current_target(session, tone),
            total_count=len(target_fields(session)),
        ),
    )


async def _handle_cancel_after_authorized(
    update,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    settings: Settings,
    tone,
) -> None:
    chat_id = update.effective_chat.id
    now = utc_now()
    session = session_store.load_session(chat_id)
    if _expire_initial_session_if_stale(
        session_store, ux_events, session, chat_id, now, settings.initial_session_ttl_sec
    ):
        await _reply_text(update, _expired_initial_session_text(tone))
        return
    if session is None:
        await _reply_text(update, tone.no_active_loop())
        return
    if session.session_id is not None:
        ux_events.append(
            _session_cancelled_event(
                session,
                str(chat_id),
                now=now,
            )
        )
    session_store.delete_session(chat_id)
    await _reply_text(update, tone.cancel())


async def _start_text_capture_session(
    update,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    tone,
    *,
    chat_id: int,
    text: str,
    now,
    existing_session=None,
    cancel_reason: str | None = None,
    funnel: str = "one_take_text",
) -> None:
    artifact = text_input_artifact(
        text,
        source_ref=_telegram_update_metadata(update),
    )
    await _start_input_artifact_capture_session(
        update,
        session_store,
        ux_events,
        tone,
        chat_id=chat_id,
        artifact=artifact,
        now=now,
        existing_session=existing_session,
        cancel_reason=cancel_reason,
        funnel=funnel,
    )


async def _start_input_artifact_capture_session(
    update,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    tone,
    *,
    chat_id: int,
    artifact,
    now,
    existing_session=None,
    cancel_reason: str | None = None,
    funnel: str = "input_artifact",
) -> None:
    capture_text = artifact_text(artifact)
    await _start_episode_draft_capture_session(
        update,
        session_store,
        ux_events,
        tone,
        chat_id=chat_id,
        draft=draft_from_input_artifact(artifact),
        answer_chars=len(capture_text),
        now=now,
        existing_session=existing_session,
        cancel_reason=cancel_reason,
        funnel=funnel,
        media_kind=artifact.media_kind,
    )


async def _start_episode_draft_capture_session(
    update,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    tone,
    *,
    chat_id: int,
    draft,
    answer_chars: int,
    now,
    existing_session=None,
    cancel_reason: str | None = None,
    funnel: str = "unknown",
    media_kind: str | None = None,
) -> None:
    if (
        cancel_reason is not None
        and existing_session is not None
        and existing_session.session_id is not None
    ):
        ux_events.append(
            _session_cancelled_event(
                existing_session,
                str(chat_id),
                now=now,
                cancel_reason=cancel_reason,
            )
        )

    session = new_session_from_draft(
        chat_id,
        draft,
        session_id=new_session_id(str(chat_id), now),
        episode_date=_episode_date_for_now(now),
        capture_funnel=funnel,
        media_kind=media_kind,
    )
    ux_events.append(
        base_event(
            "input_received",
            session.session_id,
            str(chat_id),
            created_at=now,
            funnel=funnel,
            media_kind=media_kind,
            answer_chars=answer_chars,
        )
    )
    ux_events.append(
        base_event(
            "draft_created",
            session.session_id,
            str(chat_id),
            created_at=now,
            funnel=funnel,
            media_kind=media_kind,
            draft_fields=len(draft.observed),
        )
    )
    ux_events.append(
        base_event(
            "session_started",
            session.session_id,
            str(chat_id),
            created_at=now,
        )
    )
    ux_events.append(
        base_event(
            "step_answered",
            session.session_id,
            str(chat_id),
            created_at=now,
            target="situation",
            target_index=0,
            duration_sec=0,
            advanced=True,
            answer_chars=answer_chars,
        )
    )
    _log_step_prompted(ux_events, session, str(chat_id), now=now)
    session_store.save_session(session)
    await _reply_text(
        update,
        tone.next_prompt_bridge(
            completed_observed_count(session),
            len(target_fields(session)),
            prompt_for_current_target(session, tone),
        ),
    )


async def _handle_capture_after_authorized(
    update,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    settings: Settings,
    tone,
) -> None:
    chat_id = update.effective_chat.id
    now = utc_now()
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

    text = _command_argument_text(getattr(update.message, "text", "") or "")
    if not text:
        await _reply_text(update, "Используй /capture текст эпизода")
        return

    await _start_text_capture_session(
        update,
        session_store,
        ux_events,
        tone,
        chat_id=chat_id,
        text=text,
        now=now,
        existing_session=existing_session,
        cancel_reason="capture_restart",
        funnel="capture_command",
    )


async def _handle_capture3_after_authorized(
    update,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    settings: Settings,
    tone,
) -> None:
    chat_id = update.effective_chat.id
    now = utc_now()
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

    blocks = _capture3_blocks(getattr(update.message, "text", "") or "")
    if blocks is None:
        await _reply_text(
            update,
            "Используй /capture3 что случилось | что внутри | что сделал",
        )
        return

    draft = draft_from_three_blocks(*blocks)
    await _start_episode_draft_capture_session(
        update,
        session_store,
        ux_events,
        tone,
        chat_id=chat_id,
        draft=draft,
        answer_chars=sum(len(block) for block in blocks),
        now=now,
        existing_session=existing_session,
        cancel_reason="capture3_restart",
        funnel="three_block",
        media_kind="three_block",
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
) -> None:
    artifact = _voice_input_artifact_from_update(update)
    if artifact is None:
        _log_media_funnel_event(
            ux_events,
            update,
            "input_rejected",
            funnel="voice",
            media_kind="voice",
            reject_reason="missing_file_id",
        )
        await _reply_text(update, "Не смог прочитать голосовое сообщение")
        return

    _log_media_funnel_event(
        ux_events, update, "input_received", funnel="voice", media_kind=artifact.media_kind
    )
    if bot is None or settings is None or transcription_provider is None:
        _log_media_funnel_event(
            ux_events,
            update,
            "transcription_pending",
            funnel="voice",
            media_kind=artifact.media_kind,
        )
        await _reply_text(
            update,
            "Голос получил, но расшифровка еще не подключена. "
            "Пока пришли этот эпизод текстом.",
        )
        return

    await _transcribe_media_artifact_or_reply(
        update,
        session_store,
        ux_events,
        tone,
        bot=bot,
        settings=settings,
        transcription_provider=transcription_provider,
        artifact=artifact,
        funnel="voice",
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
) -> None:
    artifact = _audio_input_artifact_from_update(update)
    if artifact is None:
        _log_media_funnel_event(
            ux_events,
            update,
            "input_rejected",
            funnel="audio",
            media_kind="audio",
            reject_reason="missing_file_id",
        )
        await _reply_text(update, "Не смог прочитать аудиофайл")
        return

    _log_media_funnel_event(
        ux_events, update, "input_received", funnel="audio", media_kind=artifact.media_kind
    )
    if bot is None or settings is None or transcription_provider is None:
        _log_media_funnel_event(
            ux_events,
            update,
            "transcription_pending",
            funnel="audio",
            media_kind=artifact.media_kind,
        )
        await _reply_text(update, _audio_transcription_pending_text())
        return

    await _transcribe_media_artifact_or_reply(
        update,
        session_store,
        ux_events,
        tone,
        bot=bot,
        settings=settings,
        transcription_provider=transcription_provider,
        artifact=artifact,
        funnel="audio",
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
) -> None:
    artifact = _audio_document_input_artifact_from_update(update)
    if artifact is None:
        _log_media_funnel_event(
            ux_events,
            update,
            "input_rejected",
            funnel="audio_document",
            media_kind="document",
            reject_reason="unsupported_document",
        )
        await _reply_text(update, "Поддерживаю только аудиофайлы")
        return

    _log_media_funnel_event(
        ux_events,
        update,
        "input_received",
        funnel="audio_document",
        media_kind=artifact.media_kind,
    )
    if bot is None or settings is None or transcription_provider is None:
        _log_media_funnel_event(
            ux_events,
            update,
            "transcription_pending",
            funnel="audio_document",
            media_kind=artifact.media_kind,
        )
        await _reply_text(update, _audio_transcription_pending_text())
        return

    await _transcribe_media_artifact_or_reply(
        update,
        session_store,
        ux_events,
        tone,
        bot=bot,
        settings=settings,
        transcription_provider=transcription_provider,
        artifact=artifact,
        funnel="audio_document",
    )


async def _handle_message_after_authorized(
    update,
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    settings: Settings,
    tone,
) -> None:
    chat_id = update.effective_chat.id
    session = session_store.load_session(chat_id)
    now = utc_now()
    if _expire_initial_session_if_stale(
        session_store, ux_events, session, chat_id, now, settings.initial_session_ttl_sec
    ):
        await _reply_text(update, _expired_initial_session_text(tone))
        return
    if session is None:
        text = (getattr(update.message, "text", "") or "").strip()
        if not text:
            await _reply_text(update, tone.no_active_loop_start())
            return
        await _start_text_capture_session(
            update,
            session_store,
            ux_events,
            tone,
            chat_id=chat_id,
            text=text,
            now=now,
        )
        return
    if session.awaiting_save_confirmation:
        await _reply_text(
            update,
            tone.review_screen(session.observed, target_fields(session)),
            reply_markup=_review_reply_markup(),
        )
        return
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
        session.awaiting_save_confirmation = True
        session_store.save_session(session)
        await _reply_text(
            update,
            tone.review_screen(session.observed, target_fields(session)),
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
) -> None:
    query = getattr(update, "callback_query", None)
    if query is not None:
        await query.answer()
    chat_id = update.effective_chat.id
    session = session_store.load_session(chat_id)
    if session is None or not session.awaiting_save_confirmation:
        if query is not None:
            await _reply_to_callback(query, tone.no_active_loop())
        return

    now = utc_now()
    data = getattr(query, "data", "") if query is not None else ""
    if data == "episode:save":
        event_kwargs = _session_funnel_event_kwargs(session)
        ux_events.append(
            base_event(
                "draft_confirmed",
                session.session_id,
                str(chat_id),
                created_at=now,
                draft_fields=completed_draft_field_count(session),
                **event_kwargs,
            )
        )
        storage.save_episode(session)
        episode_count = storage.episode_count_for_chat(chat_id)
        ux_events.append(
            base_event(
                "episode_saved",
                session.session_id,
                str(chat_id),
                created_at=now,
                draft_fields=completed_draft_field_count(session),
                **event_kwargs,
            )
        )
        ux_events.append(
            base_event(
                "session_completed",
                session.session_id,
                str(chat_id),
                created_at=now,
            )
        )
        session_store.delete_session(chat_id)
        await _reply_to_callback(query, tone.saved_episode(tone.complete(), episode_count))
        return
    if data == "episode:cancel":
        ux_events.append(
            base_event(
                "draft_discarded",
                session.session_id,
                str(chat_id),
                created_at=now,
                cancel_reason="review_cancel",
                draft_fields=completed_draft_field_count(session),
                **_session_funnel_event_kwargs(session),
            )
        )
        ux_events.append(
            _session_cancelled_event(
                session,
                str(chat_id),
                now=now,
                cancel_reason="review_cancel",
            )
        )
        session_store.delete_session(chat_id)
        await _reply_to_callback(query, tone.cancel())
        return
    if query is not None:
        await _reply_to_callback(
            query, tone.review_screen(session.observed, target_fields(session))
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
    if update.message is not None:
        kwargs = {}
        if parse_mode is not None:
            kwargs["parse_mode"] = parse_mode
        if reply_markup is not None:
            kwargs["reply_markup"] = reply_markup
        return await update.message.reply_text(
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


def _media_should_start_audio_draft(session) -> bool:
    return session is None or _is_initial_capture_step(session)


def _current_question_requires_text() -> str:
    return "Ответь, пожалуйста, текстом на текущий вопрос."


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
    session_store: LoopSessionStore,
    ux_events: UxEventLog,
    tone,
    *,
    bot,
    settings,
    transcription_provider,
    artifact,
    funnel: str,
) -> None:
    _log_audio_lifecycle(
        "media_received",
        update=update,
        funnel=funnel,
        media_kind=artifact.media_kind,
        duration_seconds=artifact.duration_seconds,
        file_size=artifact.file_size,
    )
    existing_session = session_store.load_session(update.effective_chat.id)
    if not _media_should_start_audio_draft(existing_session):
        _log_audio_lifecycle(
            "media_blocked_active_session",
            update=update,
            funnel=funnel,
            media_kind=artifact.media_kind,
            duration_seconds=artifact.duration_seconds,
            file_size=artifact.file_size,
            failure_reason="active_session",
        )
        _log_media_funnel_event(
            ux_events,
            update,
            "input_rejected",
            funnel=funnel,
            media_kind=artifact.media_kind,
            reject_reason="active_session",
        )
        await _reply_text(update, _current_question_requires_text())
        return

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
        await _reply_text(update, _media_rejected_text(exc.reason))
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
        await _reply_text(update, _media_rejected_text(exc.reason))
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
        await _reply_text(update, "Не смог скачать аудио. Пришли текстом или попробуй позже.")
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
        await _reply_text(update, "Не смог расшифровать аудио. Пришли этот эпизод текстом.")
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
        save_intake_transcript(
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
        await _reply_text(update, "Не смог сохранить расшифровку. Пришли этот эпизод текстом.")
        return

    _log_audio_lifecycle(
        "audio_intake_completed",
        update=update,
        funnel=funnel,
        media_kind=artifact.media_kind,
        duration_seconds=artifact.duration_seconds,
        file_size=artifact.file_size,
    )
    if existing_session is not None:
        session_store.delete_session(update.effective_chat.id)
    await _reply_text(update, _audio_intake_completed_text(artifact_text(transcribed)))


def _telegram_media_request_from_artifact(artifact) -> TelegramMediaRequest:
    return TelegramMediaRequest(
        file_id=artifact.file_id or "",
        media_kind=artifact.media_kind,
        duration_seconds=artifact.duration_seconds,
        file_size=artifact.file_size,
        mime_type=artifact.mime_type,
        file_name=artifact.file_name,
    )


def _audio_intake_completed_text(transcript: str) -> str:
    preview = _audio_intake_preview(transcript)
    return (
        "Готово, расшифровал.\n\n"
        f"Черновик:\n«{preview}»\n\n"
        "Аудио-черновик принят. Уточнения пока не включены."
    )


def _audio_intake_preview(text: str, *, limit: int = 180) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _media_processing_ack_text(media_kind: str) -> str:
    if media_kind == "voice":
        return "Голос получил. Беру в расшифровку — когда будет готово, продолжим."
    return "Аудио получил. Беру в расшифровку — когда будет готово, продолжим."

def _media_rejected_text(reason: str) -> str:
    if reason == "over_duration":
        return "Слишком длинное аудио. Пришли голос до 3–5 минут или текстом."
    if reason == "over_size":
        return "Аудиофайл слишком большой. Пришли короче или текстом."
    return "Не могу обработать этот аудиофайл. Пришли текстом или другим аудио."

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
        "Пока пришли этот эпизод текстом."
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
        capture_funnel="ten_question",
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
        "funnel": session.capture_funnel or "ten_question",
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
