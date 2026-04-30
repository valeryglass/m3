from __future__ import annotations

from app.config import Settings, load_settings
from app.loop_extractor import (
    apply_user_reply,
    new_session,
    prompt_for_current_target,
    status_text,
)
from app.storage import JsonStorage


def main() -> None:
    settings = load_settings()
    storage = JsonStorage(settings.episode_dir, settings.state_dir)

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
        session = storage.load_session(chat_id) or new_session(chat_id)
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
        storage.delete_session(update.effective_chat.id)
        await update.message.reply_text("Episode loop canceled.")

    async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(update, settings):
            return
        chat_id = update.effective_chat.id
        session = storage.load_session(chat_id)
        if session is None:
            session = new_session(chat_id)
        result = apply_user_reply(session, update.message.text or "")
        if result.should_save:
            path = storage.save_episode(session)
            storage.delete_session(chat_id)
            await update.message.reply_text(f"{result.reply}\nSaved: {path}")
            return
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


if __name__ == "__main__":
    main()
