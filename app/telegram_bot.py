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
        if not await _authorize(update, settings):
            return
        chat_id = update.effective_chat.id
        now = utc_now()
        session = storage.load_session(chat_id)
        if session is None:
            session = new_session(chat_id, session_id=new_session_id(str(chat_id), now))
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
        await update.message.reply_text(prompt_for_current_target(session))

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(update, settings):
            return
        chat_id = update.effective_chat.id
        session = storage.load_session(chat_id)
        if session is None:
            await update.message.reply_text("No active episode loop.")
            return
        await update.message.reply_text(status_text(session))

    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(update, settings):
            return
        chat_id = update.effective_chat.id
        now = utc_now()
        session = storage.load_session(chat_id)
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
        await update.message.reply_text("Episode loop canceled.")

    async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(update, settings):
            return
        chat_id = update.effective_chat.id
        session = storage.load_session(chat_id)
        if session is None:
            now = utc_now()
            session = new_session(chat_id, session_id=new_session_id(str(chat_id), now))
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
            now = utc_now()
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
        result = apply_user_reply(session, update.message.text or "")
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
            await update.message.reply_text(f"{result.reply}\nSaved: {path}")
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


async def _authorize(update, settings: Settings) -> bool:
    chat = update.effective_chat
    if chat is None:
        return False
    if (
        settings.telegram_allowed_chat_ids
        and chat.id not in settings.telegram_allowed_chat_ids
    ):
        if update.message is not None:
            await update.message.reply_text("Unauthorized chat.")
        return False
    return True


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


if __name__ == "__main__":
    main()
