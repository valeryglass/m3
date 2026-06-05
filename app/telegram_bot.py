from __future__ import annotations

from app.config import (
    Settings,
    admin_chat_ids_for_settings,
    load_settings,
    owner_chat_id_for_settings,
)
from app.graph_report import build_report, load_episodes
from app.report_runner import (
    regenerate_graph_reports,
    regenerate_ux_report,
)
from app.user_report import render_details, render_summary
from app.loop_extractor import (
    active_target,
    apply_user_reply,
    completed_observed_count,
    new_session,
    prompt_for_current_target,
    status_text,
    target_fields,
)
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
    storage = JsonStorage(settings.episode_dir, settings.state_dir)
    userlist = JsonUserList(settings.userlist_path)
    ux_events = UxEventLog(settings.ux_event_log)
    tone = load_tone_engine(settings.tone_config)

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
        await _handle_start_after_authorized(update, storage, ux_events, tone)

    async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        chat_id = update.effective_chat.id
        now = utc_now()
        session = storage.load_session(chat_id)
        if _expire_initial_session_if_stale(
            storage, ux_events, session, chat_id, now, settings.initial_session_ttl_sec
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
        await _handle_cancel_after_authorized(update, storage, ux_events, settings, tone)

    async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_message_after_authorized(update, storage, ux_events, settings, tone)

    async def episode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _authorize(
            update, settings, tone, ux_events, userlist, context.bot
        ):
            return
        await _handle_episode_callback_after_authorized(
            update, storage, ux_events, tone
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
    application.add_handler(CommandHandler("approve", approve))
    application.add_handler(CommandHandler("pause", pause))
    application.add_handler(CommandHandler("report_graph", report_graph))
    application.add_handler(CommandHandler("report_ux", report_ux))
    application.add_handler(CallbackQueryHandler(episode_callback, pattern="^episode:"))
    application.add_handler(CallbackQueryHandler(profile_callback, pattern="^profile:"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))
    application.run_polling(bootstrap_retries=-1)


REGISTERED_COMMANDS = (
    "start",
    "status",
    "cancel",
    "help",
    "profile",
    "approve",
    "pause",
    "report_graph",
    "report_ux",
)
VISIBLE_COMMANDS = ("start", "cancel", "help")
REPORT_REPLY_LIMIT = 3800


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
    episodes = [
        episode
        for episode in load_episodes(settings.episode_dir)
        if episode.source == source
    ]
    if not episodes:
        return None
    report = build_report(episodes)
    if not report.graph_ready or not any(item.report_ready for item in report.readiness):
        return None
    return report


async def _handle_report_graph_after_admin(update, settings: Settings, tone) -> None:
    try:
        summary = regenerate_graph_reports(settings)
    except Exception as exc:  # pragma: no cover - exact failures depend on data files
        await _reply_text(update, tone.report_failed(exc))
        return

    await _reply_text(
        update,
        tone.graph_reports_ready(
            episodes=summary["episodes"],
            invalid=summary["invalid"],
            empty_derived=summary["empty_derived"],
            annotation_ready=summary["annotation_ready"],
            graph_ready=summary["graph_ready"],
            report_ready=summary["report_ready"],
            payload_eligible=summary["payload_eligible"],
            graph_path=summary["graph_path"],
        ),
    )


async def _handle_report_ux_after_admin(update, settings: Settings, tone) -> None:
    try:
        markdown_path, _ = regenerate_ux_report(settings)
        text = markdown_path.read_text(encoding="utf-8")
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
    storage: JsonStorage,
    ux_events: UxEventLog,
    tone,
) -> None:
    chat_id = update.effective_chat.id
    now = utc_now()
    session = storage.load_session(chat_id)
    if session is not None and session.session_id is not None:
        ux_events.append(
            _session_cancelled_event(
                session,
                str(chat_id),
                now=now,
                cancel_reason="restart",
            )
        )
    session = _start_new_session(storage, ux_events, chat_id, now)
    await _reply_text(
        update,
        tone.start_session(
            prompt_for_current_target(session, tone),
            total_count=len(target_fields(session)),
        ),
    )


async def _handle_cancel_after_authorized(
    update,
    storage: JsonStorage,
    ux_events: UxEventLog,
    settings: Settings,
    tone,
) -> None:
    chat_id = update.effective_chat.id
    now = utc_now()
    session = storage.load_session(chat_id)
    if _expire_initial_session_if_stale(
        storage, ux_events, session, chat_id, now, settings.initial_session_ttl_sec
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
    storage.delete_session(chat_id)
    await _reply_text(update, tone.cancel())


async def _handle_message_after_authorized(
    update,
    storage: JsonStorage,
    ux_events: UxEventLog,
    settings: Settings,
    tone,
) -> None:
    chat_id = update.effective_chat.id
    session = storage.load_session(chat_id)
    now = utc_now()
    if _expire_initial_session_if_stale(
        storage, ux_events, session, chat_id, now, settings.initial_session_ttl_sec
    ):
        await _reply_text(update, _expired_initial_session_text(tone))
        return
    if session is None:
        await _reply_text(update, tone.no_active_loop_start())
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
        storage.save_session(session)
        await _reply_text(
            update,
            tone.review_screen(session.observed, target_fields(session)),
            reply_markup=_review_reply_markup(),
        )
        return
    _log_step_prompted(ux_events, session, str(chat_id), now=now)
    storage.save_session(session)
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
    ux_events: UxEventLog,
    tone,
) -> None:
    query = getattr(update, "callback_query", None)
    if query is not None:
        await query.answer()
    chat_id = update.effective_chat.id
    session = storage.load_session(chat_id)
    if session is None or not session.awaiting_save_confirmation:
        if query is not None:
            await _reply_to_callback(query, tone.no_active_loop())
        return

    now = utc_now()
    data = getattr(query, "data", "") if query is not None else ""
    if data == "episode:save":
        storage.save_episode(session)
        episode_count = storage.episode_count_for_chat(chat_id)
        ux_events.append(
            base_event(
                "session_completed",
                session.session_id,
                str(chat_id),
                created_at=now,
            )
        )
        storage.delete_session(chat_id)
        await _reply_to_callback(query, tone.saved_episode(tone.complete(), episode_count))
        return
    if data == "episode:cancel":
        ux_events.append(
            _session_cancelled_event(
                session,
                str(chat_id),
                now=now,
                cancel_reason="review_cancel",
            )
        )
        storage.delete_session(chat_id)
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


def _telegram_update_metadata(update) -> dict:
    chat = update.effective_chat
    user = update.effective_user
    message = update.message
    text = (getattr(message, "text", None) or "").strip() if message else ""
    command = text.split(maxsplit=1)[0] if text.startswith("/") else None
    message_kind = "command" if command else "text" if text else None

    metadata = {
        "chat_id": chat.id if chat is not None else None,
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
    )


def _start_new_session(
    storage: JsonStorage,
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
    storage.save_session(session)
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
