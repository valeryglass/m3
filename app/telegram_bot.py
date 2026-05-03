from __future__ import annotations

from app.config import Settings, load_settings
from app.loop_extractor import (
    active_target,
    apply_user_reply,
    new_session,
    prompt_for_current_target,
    status_text,
)
from app.storage import JsonStorage
from app.tone_engine import load_tone_engine
from app.ux_events import (
    UxEventLog,
    base_event,
    format_utc,
    new_session_id,
    parse_utc,
    utc_now,
)


def main() -> None:
    settings = load_settings()
    storage = JsonStorage(settings.episode_dir, settings.state_dir)
    ux_events = UxEventLog(settings.ux_event_log)
    tone = load_tone_engine(settings.tone_config)

    try:
        from telegram import Update
        from telegram.ext import (
            Application,
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
        if not await _authorize(update, settings, tone):
            return
        chat_id = update.effective_chat.id
        now = utc_now()
        session = storage.load_session(chat_id)
        if _expire_initial_session_if_stale(
            storage, ux_events, session, chat_id, now, settings.initial_session_ttl_sec
        ):
            await update.message.reply_text(_expired_initial_session_text(tone))
            return
        if session is None:
            session = _new_session_for_now(chat_id, now)
            ux_events.append(
                base_event(
                    "session_started",
                    session.session_id,
                    str(chat_id),
                    created_at=now,
                )
            )
        elif session.session_id is None:
            session.session_id = new_session_id(str(chat_id), now)
            _ensure_episode_date(session, now)
            ux_events.append(
                base_event(
                    "session_started",
                    session.session_id,
                    str(chat_id),
                    created_at=now,
                )
            )
        _log_step_prompted(ux_events, session, str(chat_id), now=now)
        storage.save_session(session)
        await update.message.reply_text(prompt_for_current_target(session, tone))

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(update, settings, tone):
            return
        chat_id = update.effective_chat.id
        now = utc_now()
        session = storage.load_session(chat_id)
        if _expire_initial_session_if_stale(
            storage, ux_events, session, chat_id, now, settings.initial_session_ttl_sec
        ):
            await update.message.reply_text(_expired_initial_session_text(tone))
            return
        if session is None:
            await update.message.reply_text(tone.no_active_loop())
            return
        await update.message.reply_text(status_text(session, tone))

    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(update, settings, tone):
            return
        chat_id = update.effective_chat.id
        now = utc_now()
        session = storage.load_session(chat_id)
        if _expire_initial_session_if_stale(
            storage, ux_events, session, chat_id, now, settings.initial_session_ttl_sec
        ):
            await update.message.reply_text(_expired_initial_session_text(tone))
            return
        if session is not None and session.session_id is not None:
            ux_events.append(
                base_event(
                    "session_cancelled",
                    session.session_id,
                    str(chat_id),
                    created_at=now,
                    target=active_target(session),
                    target_index=session.target_index,
                )
            )
        storage.delete_session(chat_id)
        await update.message.reply_text(tone.cancel())

    async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(update, settings, tone):
            return
        chat_id = update.effective_chat.id
        session = storage.load_session(chat_id)
        now = utc_now()
        if _expire_initial_session_if_stale(
            storage, ux_events, session, chat_id, now, settings.initial_session_ttl_sec
        ):
            await update.message.reply_text(_expired_initial_session_text(tone))
            return
        if session is None:
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
        elif session.session_id is None:
            session.session_id = new_session_id(str(chat_id), now)
            _ensure_episode_date(session, now)
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
            path = storage.save_episode(session)
            ux_events.append(
                base_event(
                    "session_completed",
                    session.session_id,
                    str(chat_id),
                    created_at=now,
                )
            )
            storage.delete_session(chat_id)
            await update.message.reply_text(tone.saved_episode(result.reply, path))
            return
        _log_step_prompted(ux_events, session, str(chat_id), now=now)
        storage.save_session(session)
        await update.message.reply_text(result.reply)

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))
    application.run_polling()


async def _authorize(update, settings: Settings, tone) -> bool:
    chat = update.effective_chat
    if chat is None:
        return False
    if (
        settings.telegram_allowed_chat_ids
        and chat.id not in settings.telegram_allowed_chat_ids
    ):
        if update.message is not None:
            await update.message.reply_text(tone.unauthorized())
        return False
    return True


def _new_session_for_now(chat_id: int, now):
    return new_session(
        chat_id,
        session_id=new_session_id(str(chat_id), now),
        episode_date=_episode_date_for_now(now),
    )


def _ensure_episode_date(session, now) -> None:
    if session.episode_date is None:
        session.episode_date = _episode_date_for_now(now)


def _episode_date_for_now(now) -> str:
    return now.astimezone().date().isoformat()


def _log_step_prompted(
    ux_events: UxEventLog, session, user_id: str, *, now
) -> None:
    session.last_prompted_at = format_utc(now)
    ux_events.append(
        base_event(
            "step_prompted",
            session.session_id,
            user_id,
            created_at=now,
            target=active_target(session),
            target_index=session.target_index,
        )
    )


def _duration_since_last_prompt(session, now) -> int:
    if session.last_prompted_at is None:
        return 0
    return max(0, int((now - parse_utc(session.last_prompted_at)).total_seconds()))


def _expired_initial_session_text(tone) -> str:
    return tone.expired_initial_session()


def _expire_initial_session_if_stale(
    storage: JsonStorage,
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
    storage.delete_session(chat_id)
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
