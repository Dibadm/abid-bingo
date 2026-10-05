# bot.py
# ============================================
# HABESHA BET - TELEGRAM CHAT BOT
#
# The chat bot is a lightweight interface only. All gameplay
# (rooms, card buying, number calling, win detection) happens
# inside the Mini App. The chat bot handles:
#   - User registration + phone collection
#   - Deposit instructions
#   - Withdraw / Transfer flows
#   - Balance, profile, transactions
#   - Daily bonus, referrals
#   - Admin dashboard
# ============================================

import asyncio
import html
import logging
import os
import sys
import time as _time
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
    MenuButtonWebApp,
    MenuButtonDefault,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram.error import BadRequest, Forbidden

import config
from monitoring import init_monitoring, capture_error
import database as db
import bingo
from game_state import ACTIVE_GAME_TASKS, ROOM_LOCKS, GAME_COUNTDOWN_START
from locales import get_text, get_user_text, STRINGS

_BOT_PID_PATH = os.path.join(os.path.dirname(__file__), "bot.pid")
_bot_app = None

def _ensure_single_instance():
    pid = os.getpid()
    if os.path.exists(_BOT_PID_PATH):
        try:
            with open(_BOT_PID_PATH, "r") as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)
            logger.error(f"Another bot instance is already running (PID {old_pid}). Exiting.")
            raise SystemExit(1)
        except (ProcessLookupError, ValueError):
            pass
    with open(_BOT_PID_PATH, "w") as f:
        f.write(str(pid))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
(
    PHONE_COLLECT,
    WITHDRAW_AMOUNT,
    WITHDRAW_PHONE,
    TRANSFER_USERNAME,
    TRANSFER_AMOUNT,
    DEPOSIT_CUSTOM_AMOUNT,
    ADMIN_BROADCAST_WAIT,
    ADMIN_ADD_ACCOUNT_PHONE,
    ADMIN_ADD_ACCOUNT_NAME,
    ADMIN_HOUSE_WITHDRAW_AMOUNT,
) = range(10)

# =====================================================================
# SMALL HELPERS
# =====================================================================

def lang_of(user_row) -> str:
    return user_row["language"] if user_row and "language" in user_row.keys() else config.DEFAULT_LANGUAGE


def display_name(user) -> str:
    return user.username or user.first_name or str(user.id)


def safe_amount(text: str):
    try:
        value = float(text.strip().replace(",", ""))
        if value <= 0:
            return None
        return round(value, 2)
    except (ValueError, AttributeError):
        return None


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


# =====================================================================
# BACKGROUND GAME ENGINE
# =====================================================================

def fmt(amount) -> str:
    if amount == int(amount):
        return str(int(amount))
    return f"{amount:.2f}"


async def safe_edit_by_id(bot, chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    if not chat_id or not message_id:
        return
    try:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=message_id, text=text,
            parse_mode=parse_mode, reply_markup=reply_markup
        )
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            logger.warning(f"safe_edit_by_id BadRequest ({chat_id}/{message_id}): {e}")
    except Forbidden:
        logger.info(f"User {chat_id} blocked the bot - skipping update")


GROUP_BROADCAST_MSG = {}
BROADCAST_FAILURE_COUNT = {}
BROADCAST_FAILED = {}


async def notify_game_players(bot, game_id, text):
    """DM every player who already has a card in this game — not a broadcast
    to your whole user base, just the people who already bought in. Safe to
    call even if some players have blocked the bot or never opened a DM
    with it; those failures are skipped, not raised."""
    players = db.get_game_players(game_id)
    seen = set()
    for p in players:
        uid = p["user_id"]
        if uid in seen:
            continue
        seen.add(uid)
        chat_id = db.get_user_chat_id(uid)
        if not chat_id:
            continue
        try:
            await bot.send_message(chat_id=chat_id, text=text)
        except (Forbidden, BadRequest):
            pass  # user blocked the bot or never started a DM — not an error
        except Exception as e:
            logger.warning(f"[notify] failed to DM user {uid} for game {game_id}: {e}")


def notify_game_players_async(bot, game_id, text):
    """Fire notify_game_players in the background instead of awaiting it.

    Sending one DM per player, one at a time, can easily take several
    seconds once a room has more than a handful of players — Telegram's
    own per-message latency and rate limiting add up fast in a sequential
    loop. That delay has nothing to do with the game itself, so it must
    never block the call sequence from starting. Call this instead of
    awaiting notify_game_players directly wherever it's used to announce
    something time-sensitive (like a game starting)."""
    async def _run():
        try:
            await notify_game_players(bot, game_id, text)
        except Exception:
            logger.exception(f"[notify] notify_game_players crashed for game {game_id}")
            capture_error(f"notify_game_players crashed for game {game_id}")
    asyncio.create_task(_run())


async def group_broadcast(bot, game_id, text, reply_markup=None):
    if not config.BROADCAST_ENABLED:
        return
    if BROADCAST_FAILED.get(game_id):
        return

    chat_id = config.GROUP_CHAT_ID
    msg_id = GROUP_BROADCAST_MSG.get(game_id)
    try:
        if msg_id:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, reply_markup=reply_markup)
            BROADCAST_FAILURE_COUNT.pop(game_id, None)
            return
    except Exception as e:
        logger.warning(f"[broadcast] edit failed game {game_id}: {e}")
    try:
        msg = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        GROUP_BROADCAST_MSG[game_id] = msg.message_id
        BROADCAST_FAILURE_COUNT.pop(game_id, None)
    except Exception as e:
        count = BROADCAST_FAILURE_COUNT.get(game_id, 0) + 1
        BROADCAST_FAILURE_COUNT[game_id] = count
        logger.error(f"[broadcast] send failed game {game_id}: {e}")
        if count >= 3:
            BROADCAST_FAILED[game_id] = True
            logger.critical(
                f"[broadcast] GAME {game_id} broadcast permanently disabled after "
                f"{count} consecutive failures. Fix GROUP_CHAT_ID in .env (numeric ID with "
                f"-100 prefix, e.g. -1001234567890) and ensure bot is admin in that chat."
            )


async def send_message_to_chat(chat_id, text):
    if _bot_app is None:
        logger.warning("[broadcast] bot not initialized")
        return False
    try:
        await _bot_app.bot.send_message(chat_id=chat_id, text=text)
        return True
    except Exception as e:
        logger.warning(f"[broadcast] failed to send to {chat_id}: {e}")
        return False


async def send_photo_to_chat(chat_id, photo, caption=None):
    if _bot_app is None:
        logger.warning("[broadcast] bot not initialized")
        return False
    try:
        await _bot_app.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
        return True
    except Exception as e:
        logger.warning(f"[broadcast] failed to send photo to {chat_id}: {e}")
        return False


def get_bot():
    if _bot_app is None:
        logger.warning("[broadcast] bot not initialized")
        return None
    return _bot_app.bot


async def send_admin_alert(text: str, parse_mode=None):
    try:
        bot_instance = get_bot()
        if bot_instance is None:
            return
        chat_ids = [x.strip() for x in config.ADMIN_NOTIFICATION_CHAT_IDS.split(",") if x.strip()] if config.ADMIN_NOTIFICATION_CHAT_IDS else [str(x) for x in config.ADMIN_IDS]
        for chat_id in chat_ids:
            try:
                await bot_instance.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
            except Exception as e:
                logger.error(f"[admin_alert] failed for {chat_id}: {e}")
    except Exception as e:
        logger.error(f"[admin_alert] unexpected error: {e}")


def _safe_card_index(c):
    if isinstance(c, dict) or hasattr(c, "keys"):
        return int(c["card_index"])
    return int(c)


def _find_user_active_game(user_id):
    for fee in config.ROOM_FEES:
        game = db.get_or_create_active_game(fee)
        logger.debug("[find_active] room=%s game_id=%s state=%s task_done=%s", fee, game["id"], game["state"], ACTIVE_GAME_TASKS.get(fee, {}).done() if fee in ACTIVE_GAME_TASKS else "none")
        gp = db.get_game_player(game["id"], user_id)
        if gp:
            return game["id"], fee
    return None, None


async def ensure_game_lifecycle_started(context, room_fee, game_id):
    lock = ROOM_LOCKS.setdefault(room_fee, asyncio.Lock())
    async with lock:
        if room_fee in ACTIVE_GAME_TASKS and ACTIVE_GAME_TASKS[room_fee].done():
            ACTIVE_GAME_TASKS.pop(room_fee, None)

        if room_fee in ACTIVE_GAME_TASKS:
            return

        loop = asyncio.get_running_loop()
        task = loop.create_task(run_game_lifecycle(context.application.bot, room_fee, game_id))
        ACTIVE_GAME_TASKS[room_fee] = task


async def _scan_and_start_games(application):
    active_triggers = set()
    for fee in config.ROOM_FEES:
        game = db.get_or_create_active_game(fee)
        task_done = ACTIVE_GAME_TASKS[fee].done() if fee in ACTIVE_GAME_TASKS else "not_running"
        logger.debug("[scanner] room=%s game_id=%s state=%s task_status=%s", fee, game["id"], game["state"], task_done)

        if game and game["state"] != "waiting" and game["id"] in active_triggers:
            active_triggers.remove(game["id"])

        if game and game["state"] == "waiting" and game["id"] not in active_triggers:
            cards_sold = db.count_cards_sold(game["id"])
            if cards_sold >= config.MIN_CARDS_TO_START:
                logger.info(f"Scanner: {cards_sold} cards in Room {fee}, starting countdown...")
                active_triggers.add(game["id"])
                mock_context = type("obj", (object,), {"application": application})()
                await ensure_game_lifecycle_started(mock_context, fee, game["id"])


async def auto_start_web_app_games(application):
    while True:
        try:
            await _scan_and_start_games(application)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("[scanner] unexpected error")
        await asyncio.sleep(1)








def push_call_and_check_wins(game_id, called_numbers):
    players = db.get_game_players(game_id)
    auto_player_ids = [p["user_id"] for p in players if p["auto_win"] == 1]
    cards_by_user = db.get_cards_for_players(game_id, auto_player_ids)
    winners = {}

    for user_id in auto_player_ids:
        card_indices = cards_by_user.get(user_id, [])
        safe_cards = [_safe_card_index(c) for c in card_indices]
        detected = bingo.evaluate_player_cards_detailed(safe_cards, called_numbers)
        if detected:
            winners[user_id] = detected

    return winners


async def resolve_round_winners(bot, game_id, room_fee, winners_found):
    """Resolve a winner the bot detected itself (auto-win, or a manual
    claim it noticed during its own polling). Goes through the same
    atomic guard and shared payout logic the API's instant manual-claim
    path uses (database.try_claim_game_resolution /
    database.resolve_game_winners), so if an instant API claim resolved
    this exact game in the same instant, only one of them actually pays
    out — this function just backs off quietly if it loses that race."""
    if not db.try_claim_game_resolution(game_id):
        logger.info(f"[lifecycle] game {game_id} already resolved elsewhere (likely an instant API claim) — not paying out again")
        pending = db.drain_broadcasts(game_id)
        for text in pending:
            await group_broadcast(bot, game_id, text)
        return

    result = db.resolve_game_winners(game_id, winners_found)

    winner_lines = []
    for w in result["winner_lines"]:
        username_masked = bingo.mask_username(w["username"] or str(w["user_id"]))
        card_num = _safe_card_index(w["card_index"]) + 1 if w["card_index"] is not None else "?"
        winner_lines.append(f"• @{username_masked} — {fmt(w['amount'])} ETB — Card #{card_num} ({w['win_type']})")

    text = f"🎉 Winners ({len(result['winner_ids'])})\n\n" + "\n".join(winner_lines)
    await group_broadcast(bot, game_id, text)

    # Also send anything the API queued for this game around the same
    # time (e.g. a different player's instant claim resolved it a moment
    # before this check ran, but we still won try_claim_game_resolution
    # for... actually if we won the claim, nothing else could have
    # queued a resolution broadcast for this same game — this just
    # covers any other queued message, defensively, so nothing is lost).
    pending = db.drain_broadcasts(game_id)
    for extra_text in pending:
        await group_broadcast(bot, game_id, extra_text)


async def resolve_round_no_winner(bot, game_id, room_fee, called_numbers):
    """No winner found after the maximum number of calls. Still goes
    through the atomic guard — an instant manual claim via the API could
    have resolved this game in the same moment the bot's loop was about
    to give up and refund everyone."""
    if not db.try_claim_game_resolution(game_id):
        logger.info(f"[lifecycle] game {game_id} resolved elsewhere right as it was about to be refunded — not refunding")
        pending = db.drain_broadcasts(game_id)
        for text in pending:
            await group_broadcast(bot, game_id, text)
        return

    refunded = db.refund_game(game_id)
    db.set_game_state(game_id, "finished")
    text = f"😔 No winner after {len(called_numbers)} calls. All {len(refunded)} players refunded."
    await group_broadcast(bot, game_id, text)


async def handle_insufficient_players_refund(bot, game_id):
    refunded = db.refund_game(game_id)
    db.set_game_state(game_id, "finished")
    text = f"⚠️ Game cancelled — only {len(refunded)} players. All refunded."
    await group_broadcast(bot, game_id, text)


def _check_manual_claims(game_id, called_numbers):
    """Re-validate any pending manual claims against the authoritative
    called-numbers list (and, transitively, the fixed CARD_POOL — both
    processes now agree on what each card contains). Returns a dict of
    {user_id: win_type} for any claims that check out."""
    found = {}
    manual_claims = db.get_manual_bingo_claims(game_id)
    for claim_uid, claimed_cards in manual_claims.items():
        safe_cards = [_safe_card_index(c) for c in claimed_cards]
        revalidated = bingo.evaluate_player_cards_detailed(safe_cards, called_numbers)
        if revalidated:
            found[claim_uid] = revalidated
    return found


async def _check_externally_resolved(bot, game_id) -> bool:
    """Check whether this game has already been resolved by someone else
    — specifically, an instant manual BINGO claim handled directly by the
    API process, which has no live Telegram connection of its own. If
    so, send whatever announcement it queued and report True so the
    calling loop stops immediately instead of continuing to call more
    numbers for a game that's already over."""
    game = db.get_game(game_id)
    if game is None or game["state"] in ("resolving", "finished"):
        pending = db.drain_broadcasts(game_id)
        for text in pending:
            await group_broadcast(bot, game_id, text)
        return True
    return False


async def run_game_lifecycle(bot, room_fee, game_id):
    from game_state import GAME_COUNTDOWN_START, ACTIVE_GAME_TASKS, GROUP_BROADCAST_MSG

    stuck, reason = db.is_game_stuck(game_id)
    if stuck:
        logger.warning("[lifecycle] game %s stuck (%s) — finishing and refunding", game_id, reason)
        try:
            db.refund_game(game_id)
            db.clear_manual_bingo_claims(game_id)
            db.set_game_state(game_id, "finished")
        except Exception:
            logger.exception("[lifecycle] failed to recover stuck game %s", game_id)
        return

    try:
        GAME_COUNTDOWN_START[game_id] = _time.monotonic()
        db.set_game_countdown_start(game_id)

        for remaining in range(config.COUNTDOWN_SECONDS, 0, -1):
            await asyncio.sleep(1)

            current_state = db.get_game(game_id)
            if current_state is None or current_state["state"] == "finished":
                logger.info(f"[lifecycle] game {game_id} already finished during countdown — exiting")
                return

            sold = db.count_cards_sold(game_id)
            logger.info(f"[lifecycle] game {game_id} countdown t={remaining} sold={sold}")
            if sold > 0 and remaining % 5 == 0:
                game = db.get_game(game_id)
                text = f"🎟 Room {room_fee} ETB\nPool: {fmt(game['pool'])} ETB\nCards sold: {sold}\nCountdown: {remaining}s"
                await group_broadcast(bot, game_id, text)

        GAME_COUNTDOWN_START.pop(game_id, None)
        db.clear_game_countdown_start(game_id)

        sold = db.count_cards_sold(game_id)
        if sold < config.MIN_CARDS_TO_START:
            logger.info(f"[lifecycle] game {game_id} refunding: only {sold} cards sold, need {config.MIN_CARDS_TO_START}")
            await handle_insufficient_players_refund(bot, game_id)
            return

        logger.info(f"[lifecycle] game {game_id} starting: {sold} cards sold")
        db.set_game_state(game_id, "running")

        bonus = db.try_trigger_jackpot(game_id)
        if bonus:
            await group_broadcast(
                bot, game_id,
                f"💰 JACKPOT HIT! +{fmt(bonus)} ETB added to this game's pool!"
            )

        await group_broadcast(bot, game_id, f"🚀 Game starting! Room {room_fee} ETB — {sold} cards sold.")
        notify_game_players_async(bot, game_id, f"🎱 Your Habesha Bet game ({room_fee} ETB room) is starting now — open the app to play!")

        call_sequence = bingo.generate_call_sequence()
        called_numbers = []
        winners_found = {}

        for call_index, number in enumerate(call_sequence[: config.MAX_NUMBERS_CALLED], start=1):
            if await _check_externally_resolved(bot, game_id):
                logger.info(f"[lifecycle] game {game_id} resolved externally before call {call_index} — exiting loop")
                return

            called_numbers.append(number)
            db.add_called_number(game_id, call_index, number)

            auto_winners = push_call_and_check_wins(game_id, called_numbers)

            winners_found.update(auto_winners)
            winners_found.update(_check_manual_claims(game_id, called_numbers))

            if winners_found:
                logger.info(f"[lifecycle] WIN DETECTED game {game_id} winners={list(winners_found.keys())} types={list(winners_found.values())}")
                break

            letter = bingo.number_to_letter(number)
            amharic = bingo.number_to_amharic(number)
            last_6 = called_numbers[-6:]
            history_str = ", ".join(map(str, last_6))
            player_count = len(db.get_game_players(game_id))
            pool = db.get_pool(game_id)
            text = f"🎱 {letter}-{number} / {amharic}\nCalls: {call_index}/{config.MAX_NUMBERS_CALLED}\nPool: {fmt(pool)} ETB\nPlayers: {player_count}\nLast 6: {history_str}"
            await group_broadcast(bot, game_id, text)

            # Check for manual claims frequently during the gap between
            # calls, rather than only once per CALL_DELAY_SECONDS cycle —
            # otherwise a claim made mid-gap could sit unresolved for up
            # to the full delay before the bot notices it.
            claim_poll_step = 0.5
            elapsed = 0.0
            resolved_externally = False
            while elapsed < config.CALL_DELAY_SECONDS:
                step = min(claim_poll_step, config.CALL_DELAY_SECONDS - elapsed)
                await asyncio.sleep(step)
                elapsed += step
                if await _check_externally_resolved(bot, game_id):
                    resolved_externally = True
                    break
                # This is a defensive fallback now — the normal path for a
                # manual claim is handle_claim_bingo resolving it
                # instantly via the API, which the check above will pick
                # up as soon as it happens. This only matters if that
                # somehow didn't complete (e.g. the API process died
                # mid-request after recording the claim).
                winners_found.update(_check_manual_claims(game_id, called_numbers))
                if winners_found:
                    break
            if resolved_externally:
                logger.info(f"[lifecycle] game {game_id} resolved externally during inter-call wait — exiting loop")
                return
            if winners_found:
                logger.info(f"[lifecycle] WIN DETECTED game {game_id} winners={list(winners_found.keys())} types={list(winners_found.values())}")
                break

        if not winners_found:
            post_loop_result = _check_manual_claims(game_id, called_numbers)
            logger.info(f"[lifecycle] post-loop manual claim check for game {game_id}: {post_loop_result}")
            winners_found.update(post_loop_result)

        if winners_found:
            await resolve_round_winners(bot, game_id, room_fee, winners_found)
        else:
            await resolve_round_no_winner(bot, game_id, room_fee, called_numbers)

    except asyncio.CancelledError:
        logger.info(f"[lifecycle] task for game {game_id} was cancelled")
        raise

    except Exception:
        logger.exception(f"[lifecycle] crashed for room {room_fee}, game {game_id}")
        capture_error(f"game lifecycle crashed for room {room_fee}, game {game_id}")
        refund_ok = True
        try:
            game_check = db.get_game(game_id)
            if game_check and game_check["state"] != "finished":
                db.refund_game(game_id)
                db.set_game_state(game_id, "finished")
        except Exception:
            refund_ok = False
            logger.exception("[lifecycle] refund-on-crash ALSO failed")
            capture_error(f"refund-on-crash ALSO failed for game {game_id} (room {room_fee})")

        alert = (
            f"⚠️ Game {game_id} (room {room_fee} ETB) crashed mid-run.\n"
            f"Players {'were refunded' if refund_ok else 'were NOT refunded — needs manual review'}."
        )
        await send_admin_alert(alert)

    finally:
        GAME_COUNTDOWN_START.pop(game_id, None)
        db.clear_manual_bingo_claims(game_id)
        ACTIVE_GAME_TASKS.pop(room_fee, None)
        GROUP_BROADCAST_MSG.pop(game_id, None)
        db.get_or_create_active_game(room_fee)


async def safe_edit(query, text, reply_markup=None, parse_mode="HTML"):
    try:
        await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            logger.warning(f"safe_edit BadRequest: {e}")




# =====================================================================
# KEYBOARDS
# =====================================================================

def main_menu_keyboard(lang) -> InlineKeyboardMarkup:
    if config.MINI_APP_URL:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text("btn_open_app", lang), web_app=WebAppInfo(url=config.MINI_APP_URL))],
            [InlineKeyboardButton(get_text("btn_join_group", lang), url=config.GROUP_LINK)],
        ])

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text("btn_play_games", lang), callback_data="noop")],
        [
            [InlineKeyboardButton(get_text("btn_deposit", lang), callback_data="menu_deposit"),
             InlineKeyboardButton(get_text("btn_withdraw", lang), callback_data="menu_withdraw")]
        ],
        [
            [InlineKeyboardButton(get_text("btn_transfer", lang), callback_data="menu_transfer"),
             InlineKeyboardButton(get_text("btn_profile", lang), callback_data="menu_profile")]
        ],
        [
            [InlineKeyboardButton(get_text("btn_transactions", lang), callback_data="menu_transactions"),
             InlineKeyboardButton(get_text("btn_balance", lang), callback_data="menu_balance")]
        ],
        [
            [InlineKeyboardButton(get_text("btn_join_group", lang), url=config.GROUP_LINK),
             InlineKeyboardButton(get_text("btn_contact", lang), url=f"https://t.me/{config.SUPPORT_USERNAME}")]
        ],
        [InlineKeyboardButton(get_text("btn_refer", lang), callback_data="menu_referral")],
        [
            [InlineKeyboardButton(get_text("btn_daily_bonus", lang), callback_data="menu_bonus"),
             InlineKeyboardButton(get_text("btn_language", lang), callback_data="menu_language")]
        ],
    ])


def back_keyboard(lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(get_text("btn_back", lang), callback_data="back_main")]])


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("English", callback_data="lang_en"),
            InlineKeyboardButton("Amharic", callback_data="lang_am"),
        ],
        [InlineKeyboardButton(get_text("btn_back", config.DEFAULT_LANGUAGE), callback_data="back_main")],
    ])


def deposit_amount_keyboard(lang) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for amt in config.DEPOSIT_QUICK_AMOUNTS:
        row.append(InlineKeyboardButton(f"{amt} ETB", callback_data=f"depamt_{amt}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(get_text("btn_custom_amount", lang), callback_data="depamt_custom")])
    rows.append([InlineKeyboardButton(get_text("btn_back", lang), callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def withdraw_approval_keyboard(withdrawal_id) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Approve", callback_data=f"wdapprove_{withdrawal_id}"),
        InlineKeyboardButton("Reject", callback_data=f"wdreject_{withdrawal_id}"),
    ]])


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Dashboard", callback_data="admin_dashboard")],
        [InlineKeyboardButton("Withdrawals", callback_data="admin_withdrawals")],
        [InlineKeyboardButton("Deposit Accounts", callback_data="admin_accounts")],
        [InlineKeyboardButton("Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("House Wallet", callback_data="admin_house")],
    ])

# =====================================================================
# /start  +  PHONE COLLECTION
# =====================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        existing = db.get_user(user.id)
    except Exception as e:
        logger.exception("[start] get_user failed for %s", user.id)
        await update.message.reply_text("⚠️ Service temporarily unavailable. Please try again in a moment.")
        return ConversationHandler.END
    is_new = existing is None

    referred_by = None
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref"):
            try:
                ref_id = int(arg[3:])
                if ref_id != user.id:
                    try:
                        ref_user = db.get_user(ref_id)
                        if ref_user is not None:
                            referred_by = ref_id
                    except Exception:
                        pass
            except ValueError:
                pass

    try:
        db_user = db.get_or_create_user(user.id, display_name(user), referred_by=referred_by)
    except Exception as e:
        logger.exception("[start] get_or_create_user failed for %s", user.id)
        await update.message.reply_text("⚠️ Service temporarily unavailable. Please try again in a moment.")
        return ConversationHandler.END
    
    lang = lang_of(db_user)

    if is_new or not db_user["phone"]:
        contact_button = KeyboardButton(get_text("share_phone_button", lang), request_contact=True)
        keyboard = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            get_text("welcome_new", lang), parse_mode="HTML", reply_markup=keyboard
        )
        return PHONE_COLLECT

    await show_main_menu(update, context, db_user)
    return ConversationHandler.END


async def phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    contact = update.message.contact

    if contact is None or contact.user_id != user.id:
        db_user = db.get_user(user.id)
        lang = lang_of(db_user)
        await update.message.reply_text(get_text("share_phone_button", lang))
        return PHONE_COLLECT

    db.set_user_phone(user.id, contact.phone_number)
    db_user = db.get_user(user.id)
    lang = lang_of(db_user)

    prefix = ""
    if db_user["referred_by"] is not None and config.SIGNUP_BONUS > 0:
        db.adjust_balance(user.id, config.SIGNUP_BONUS)
        db.add_bonus_balance(user.id, config.SIGNUP_BONUS)
        db.record_transaction(user.id, "signup_bonus", config.SIGNUP_BONUS, status="completed")
        prefix = get_text("signup_bonus_received", lang, amount=fmt(config.SIGNUP_BONUS))

    await update.message.reply_text(
        prefix + get_text("phone_saved", lang), parse_mode="HTML", reply_markup=ReplyKeyboardRemove()
    )

    db_user = db.get_user(user.id)
    await show_main_menu(update, context, db_user)
    return ConversationHandler.END


async def show_main_menu(update_or_query, context, db_user, edit=False):
    lang = lang_of(db_user)
    text = get_text(
        "main_menu_text", lang,
        username=html.escape(db_user["username"] or str(db_user["user_id"])),
        balance=fmt(db_user["balance"]),
    )
    markup = main_menu_keyboard(lang)

    if edit:
        await safe_edit(update_or_query, text, reply_markup=markup)
    else:
        await update_or_query.message.reply_text(text, parse_mode="HTML", reply_markup=markup)

# =====================================================================
# TEXT INPUT HANDLER (withdraw/transfer amounts from user messages)
# =====================================================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    flow = context.user_data.get("flow")
    db_user = db.get_user(update.effective_user.id)
    if not db_user:
        return

    lang = lang_of(db_user)
    text = (update.message.text or "").strip()

    if flow == "withdraw_amount":
        amount = safe_amount(text)
        if amount is None:
            await update.message.reply_text(get_text("withdraw_invalid_amount", lang))
            return
        if amount < config.MIN_WITHDRAWAL:
            await update.message.reply_text(get_text("withdraw_below_min", lang, min=fmt(config.MIN_WITHDRAWAL)))
            return
        balance = db.get_balance(db_user["user_id"])
        if amount > balance:
            await update.message.reply_text(get_text("withdraw_insufficient", lang, balance=fmt(balance)))
            return
        context.user_data["withdraw_amount"] = amount
        context.user_data["flow"] = "withdraw_phone"
        await update.message.reply_text(
            get_text("withdraw_start", lang, amount=fmt(amount)),
            reply_markup=back_keyboard(lang),
        )
        return WITHDRAW_PHONE

    if flow == "withdraw_phone":
        phone = text
        if not phone.startswith("251") or len(phone) != 12:
            await update.message.reply_text("Enter a valid Telebirr phone (e.g. 2519xxxxxxx):")
            return WITHDRAW_PHONE
        amount = context.user_data.get("withdraw_amount", 0)
        wd_id = db.create_withdrawal(db_user["user_id"], amount, phone)
        context.user_data.pop("flow", None)
        context.user_data.pop("withdraw_amount", None)
        await update.message.reply_text(
            get_text("withdraw_submitted", lang, amount=fmt(amount), phone=phone),
            reply_markup=back_keyboard(lang),
        )
        return ConversationHandler.END

    if flow == "transfer_username":
        username = text.strip().lstrip("@")
        if username.lower() == (db_user["username"] or "").lower():
            await update.message.reply_text(get_text("transfer_cannot_self", lang))
            return TRANSFER_USERNAME
        to_user = db.find_user_by_username(username)
        if not to_user:
            await update.message.reply_text(get_text("transfer_user_not_found", lang, username=username))
            return TRANSFER_USERNAME
        context.user_data["transfer_to"] = to_user["user_id"]
        context.user_data["flow"] = "transfer_amount"
        balance = db.get_balance(db_user["user_id"])
        await update.message.reply_text(
            get_text("transfer_enter_amount", lang, to_username=username, balance=fmt(balance)),
            reply_markup=back_keyboard(lang),
        )
        return TRANSFER_AMOUNT

    if flow == "transfer_amount":
        amount = safe_amount(text)
        if amount is None:
            await update.message.reply_text(get_text("transfer_invalid_amount", lang))
            return TRANSFER_AMOUNT
        if amount < config.MIN_TRANSFER:
            await update.message.reply_text(get_text("transfer_below_min", lang, min=fmt(config.MIN_TRANSFER)))
            return TRANSFER_AMOUNT
        to_id = context.user_data.get("transfer_to")
        success, reason = db.transfer_funds(db_user["user_id"], to_id, amount)
        context.user_data.pop("flow", None)
        context.user_data.pop("transfer_to", None)
        if success:
            await update.message.reply_text(
                get_text("transfer_success", lang, amount=fmt(amount), to_username=db.get_user(to_id)["username"]),
                reply_markup=back_keyboard(lang),
            )
        else:
            await update.message.reply_text(reason, reply_markup=back_keyboard(lang))
        return ConversationHandler.END

    if flow == "deposit_custom":
        amount = safe_amount(text)
        if amount is None or amount < config.MIN_DEPOSIT:
            await update.message.reply_text(
                get_text("deposit_amount_too_low", lang, min=fmt(config.MIN_DEPOSIT))
            )
            return DEPOSIT_CUSTOM_AMOUNT
        accounts = db.get_active_deposit_accounts()
        if not accounts:
            await update.message.reply_text(get_text("deposit_no_account", lang), reply_markup=back_keyboard(lang))
            return ConversationHandler.END
        acc = accounts[0]
        msg = get_text("deposit_instructions", lang, amount=fmt(amount), phone=acc["phone"], name=acc["account_name"])
        await update.message.reply_text(msg, reply_markup=back_keyboard(lang))
        return ConversationHandler.END

    if flow == "admin_broadcast":
        if update.effective_user.id not in config.ADMIN_IDS:
            await update.message.reply_text("⛔ Not authorized.")
            context.user_data.pop("flow", None)
            return ConversationHandler.END
        message_text = text.strip()
        user_ids = db.get_all_user_ids()
        success = 0
        fail = 0
        for uid in user_ids:
            try:
                await context.application.bot.send_message(chat_id=uid, text=message_text)
                success += 1
            except Exception:
                fail += 1
        db.record_admin_action(update.effective_user.id, "broadcast", details={"recipients": len(user_ids), "success": success, "fail": fail})
        context.user_data.pop("flow", None)
        await update.message.reply_text(f"📣 Broadcast sent.\nSent: {success}\nFailed: {fail}", reply_markup=back_keyboard(lang))
        return ConversationHandler.END

    if flow == "admin_house_withdraw_amount":
        if update.effective_user.id not in config.ADMIN_IDS:
            await update.message.reply_text("⛔ Not authorized.")
            context.user_data.pop("flow", None)
            return ConversationHandler.END
        amount = safe_amount(text)
        if amount is None or amount <= 0:
            await update.message.reply_text("Enter a valid amount.", reply_markup=back_keyboard(lang))
            return ADMIN_HOUSE_WITHDRAW_AMOUNT
        success, reason, new_bal = db.withdraw_house_funds(amount)
        context.user_data.pop("flow", None)
        if not success:
            await update.message.reply_text(f"Withdrawal failed: {reason}", reply_markup=back_keyboard(lang))
            return ConversationHandler.END
        db.record_admin_action(update.effective_user.id, "withdraw_house", details={"amount": amount, "new_balance": new_bal})
        await update.message.reply_text(f"🏦 Withdrawn {fmt(amount)} ETB from house wallet.\nNew balance: {fmt(new_bal)} ETB", reply_markup=back_keyboard(lang))
        return ConversationHandler.END

    if flow == "admin_add_account_phone":
        if update.effective_user.id not in config.ADMIN_IDS:
            await update.message.reply_text("⛔ Not authorized.")
            context.user_data.pop("flow", None)
            return ConversationHandler.END
        phone = text.strip()
        if not phone.startswith("251") or len(phone) != 12:
            await update.message.reply_text("Enter a valid Telebirr phone (e.g. 2519xxxxxxx):", reply_markup=back_keyboard(lang))
            return ADMIN_ADD_ACCOUNT_PHONE
        context.user_data["admin_add_account_phone"] = phone
        context.user_data["flow"] = "admin_add_account_name"
        await update.message.reply_text("Enter recipient name:", reply_markup=back_keyboard(lang))
        return ADMIN_ADD_ACCOUNT_NAME

    if flow == "admin_add_account_name":
        if update.effective_user.id not in config.ADMIN_IDS:
            await update.message.reply_text("⛔ Not authorized.")
            context.user_data.pop("flow", None)
            return ConversationHandler.END
        name = text.strip()
        phone = context.user_data.pop("admin_add_account_phone", None)
        context.user_data.pop("flow", None)
        if not name or not phone:
            await update.message.reply_text("Invalid data.", reply_markup=back_keyboard(lang))
            return ConversationHandler.END
        acc_id = db.add_deposit_account(phone, name)
        db.record_admin_action(update.effective_user.id, "add_deposit_account", target_id=acc_id, details={"phone": phone, "name": name})
        await update.message.reply_text(f"✅ Deposit account added: {phone} ({name})", reply_markup=back_keyboard(lang))
        return ConversationHandler.END

    return None

# =====================================================================
# MAIN MENU CALLBACKS
# =====================================================================

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    db_user = db.get_user(user.id)
    if db_user is None:
        await query.answer(get_text("error_generic", config.DEFAULT_LANGUAGE), show_alert=True)
        return
    lang = lang_of(db_user)
    data = query.data

    if data == "back_main":
        db_user = db.get_user(user.id)
        await show_main_menu(query, context, db_user, edit=True)
        context.user_data.pop("flow", None)

    elif data == "menu_balance":
        await safe_edit(
            query,
            get_text("main_menu_text", lang, username=html.escape(db_user["username"] or ""), balance=fmt(db_user["balance"])),
            reply_markup=back_keyboard(lang),
        )

    elif data == "menu_profile":
        joined_date = db_user["created_at"][:10] if db_user["created_at"] else "-"
        text = get_text(
            "profile_text", lang,
            username=html.escape(db_user["username"] or ""),
            user_id=db_user["user_id"],
            phone=db_user["phone"] or "-",
            balance=fmt(db_user["balance"]),
            referrals=db.count_referrals(user.id),
            joined=joined_date,
        )
        await safe_edit(query, text, reply_markup=back_keyboard(lang))

    elif data == "menu_transactions":
        await show_transactions(query, db_user)

    elif data == "menu_bonus":
        await handle_daily_bonus(query, db_user)

    elif data == "menu_referral":
        await handle_referral_info(query, db_user)

    elif data == "menu_language":
        await safe_edit(query, "Language / ቋንቋ", reply_markup=language_keyboard())

    elif data == "lang_en":
        db.set_user_language(user.id, "en")
        await query.answer(get_text("language_switched_en", "en"))
        await show_main_menu(query, context, db.get_user(user.id), edit=True)

    elif data == "lang_am":
        db.set_user_language(user.id, "am")
        await query.answer(get_text("language_switched_am", "am"))
        await show_main_menu(query, context, db.get_user(user.id), edit=True)

    elif data == "menu_deposit":
        await menu_deposit_entry(query, context, db_user)

    elif data.startswith("depamt_"):
        await deposit_amount_chosen(query, context, db_user, data)

    elif data == "menu_withdraw":
        await handle_withdraw_start(query, context, db_user)

    elif data == "menu_transfer":
        await handle_transfer_start(query, context, db_user)

    elif data.startswith("wdapprove_"):
        await admin_approve_withdrawal(query, context, int(data.split("_", 1)[1]))

    elif data.startswith("wdreject_"):
        await admin_reject_withdrawal(query, context, int(data.split("_", 1)[1]))

    elif data.startswith("admin_"):
        await admin_callback(query, context, db_user, data)

    elif data == "noop":
        pass

# =====================================================================
# DEPOSIT FLOW
# =====================================================================

async def menu_deposit_entry(query, context, db_user):
    lang = lang_of(db_user)
    await safe_edit(query, get_text("deposit_welcome_text", lang), reply_markup=deposit_amount_keyboard(lang))


async def deposit_amount_chosen(query, context, db_user, callback_data):
    lang = lang_of(db_user)
    amt_str = callback_data.split("_", 1)[1]

    if amt_str == "custom":
        context.user_data["flow"] = "deposit_custom"
        await safe_edit(query, get_text("deposit_enter_custom", lang, min=fmt(config.MIN_DEPOSIT)))
        return DEPOSIT_CUSTOM_AMOUNT

    amount = float(amt_str)
    accounts = db.get_active_deposit_accounts()
    if not accounts:
        await safe_edit(query, get_text("deposit_no_account", lang), reply_markup=back_keyboard(lang))
        return ConversationHandler.END

    acc = accounts[0]
    msg = get_text("deposit_instructions", lang, amount=fmt(amount), phone=acc["phone"], name=acc["account_name"])
    await safe_edit(query, msg, reply_markup=back_keyboard(lang))

# =====================================================================
# WITHDRAW FLOW
# =====================================================================

async def handle_withdraw_start(query, context, db_user):
    lang = lang_of(db_user)
    context.user_data["flow"] = "withdraw_amount"
    await safe_edit(
        query,
        get_text("withdraw_start", lang, amount=""),
        reply_markup=back_keyboard(lang),
    )
    return WITHDRAW_AMOUNT

# =====================================================================
# TRANSFER FLOW
# =====================================================================

async def handle_transfer_start(query, context, db_user):
    lang = lang_of(db_user)
    context.user_data["flow"] = "transfer_username"
    await safe_edit(
        query,
        get_text("transfer_start", lang),
        reply_markup=back_keyboard(lang),
    )
    return TRANSFER_USERNAME

# =====================================================================
# TRANSACTIONS
# =====================================================================

TX_ICONS = {
    "deposit": "Deposit", "withdraw": "Withdrawal", "withdraw_refund": "Withdrawal Refund",
    "transfer_in": "Transfer In", "transfer_out": "Transfer Out",
    "referral_bonus": "Referral", "signup_bonus": "Signup Bonus", "daily_bonus": "Daily Bonus",
    "house_commission": "House Commission",
}

async def show_transactions(query, db_user):
    lang = lang_of(db_user)
    rows = db.get_user_transactions(db_user["user_id"], limit=10)

    if not rows:
        await safe_edit(query, get_text("no_transactions", lang), reply_markup=back_keyboard(lang))
        return

    lines = [get_text("transactions_header", lang)]
    for r in rows:
        key = f"tx_type_{r['type']}"
        type_label = get_text(key, lang) if key in STRINGS else r["type"]
        icon = TX_ICONS.get(r["type"], "Transaction")
        sign = "+" if r["amount"] >= 0 else ""
        lines.append(get_text(
            "tx_row", lang,
            icon=icon, type_label=type_label, sign=sign, amount=fmt(abs(r["amount"])),
            date=r["created_at"][:16].replace("T", " "),
        ))

    await safe_edit(query, "\n".join(lines), reply_markup=back_keyboard(lang))

# =====================================================================
# BONUS / REFERRAL
# =====================================================================

async def handle_daily_bonus(query, db_user):
    lang = lang_of(db_user)
    user_id = db_user["user_id"]
    can_claim, streak_days, next_bonus_amount = db.can_claim_daily_streak_bonus(user_id)

    if can_claim:
        balance = db.adjust_balance(user_id, next_bonus_amount)
        db.add_bonus_balance(user_id, next_bonus_amount)
        db.record_transaction(user_id, "daily_bonus", next_bonus_amount, status="completed")
        db.set_daily_streak_bonus_claimed(user_id, streak_days)
        await safe_edit(
            query,
            get_text("daily_bonus_claimed", lang, amount=fmt(next_bonus_amount), balance=fmt(balance), streak=streak_days),
            reply_markup=back_keyboard(lang),
        )
    else:
        await safe_edit(query, get_text("daily_bonus_wait", lang, hours=streak_days), reply_markup=back_keyboard(lang))


async def handle_referral_info(query, db_user):
    lang = lang_of(db_user)
    user_id = db_user["user_id"]
    link = f"https://t.me/{config.BOT_USERNAME}?start=ref{user_id}"
    count = db.count_referrals(user_id)
    await safe_edit(
        query,
        get_text(
            "referral_info", lang, link=link,
            signup_bonus=fmt(config.SIGNUP_BONUS), referral_bonus=fmt(config.REFERRAL_BONUS), count=count,
        ),
        reply_markup=back_keyboard(lang),
    )

# =====================================================================
# ADMIN
# =====================================================================

def require_admin(query_or_message):
    if hasattr(query_or_message, 'from_user'):
        user_id = query_or_message.from_user.id
    else:
        user_id = query_or_message.id
    if not is_admin(user_id):
        return False, None
    return True, user_id


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"[ADMIN] /admin triggered user_id={user.id}")
    ok, admin_id = require_admin(user)
    if not ok:
        await update.message.reply_text("⛔ You are not authorized to access the admin panel.")
        return

    await update.message.reply_text(
        "🔐 Admin Panel",
        reply_markup=admin_menu_keyboard(),
    )


async def admin_approve_withdrawal(query, context, wd_id):
    ok, admin_id = require_admin(query)
    if not ok:
        await query.answer("Not authorized.", show_alert=True)
        return
    success = db.update_withdrawal_status(wd_id, "completed")
    if not success:
        await query.answer("Already processed.", show_alert=True)
        return
    wd = db.get_withdrawal(wd_id)
    details = {"amount": wd["amount"], "user_id": wd["user_id"], "phone": wd["phone"]}
    db.record_admin_action(admin_id, "approve_withdrawal", target_id=wd_id, details=details)
    await query.answer("Approved!")
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(f"✅ Withdrawal #{wd_id} approved for {wd['amount']} ETB.")


async def admin_reject_withdrawal(query, context, wd_id):
    ok, admin_id = require_admin(query)
    if not ok:
        await query.answer("Not authorized.", show_alert=True)
        return
    success = db.update_withdrawal_status(wd_id, "rejected")
    if not success:
        await query.answer("Already processed.", show_alert=True)
        return
    wd = db.get_withdrawal(wd_id)
    db.adjust_balance(wd["user_id"], wd["amount"])
    db.record_transaction(wd["user_id"], "withdraw_refund", wd["amount"], status="completed")
    details = {"amount": wd["amount"], "user_id": wd["user_id"], "phone": wd["phone"]}
    db.record_admin_action(admin_id, "reject_withdrawal", target_id=wd_id, details=details)
    await query.answer("Rejected and refunded.")
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(f"❌ Withdrawal #{wd_id} rejected. {wd['amount']} ETB refunded.")


async def admin_callback(query, context, db_user, data):
    if not is_admin(db_user["user_id"]):
        await query.answer("Not authorized.", show_alert=True)
        return

    if data == "admin_dashboard":
        await admin_dashboard(query, context, db_user)
    elif data == "admin_withdrawals":
        await admin_withdrawals(query, context, db_user)
    elif data == "admin_accounts":
        await admin_accounts(query, context, db_user)
    elif data == "admin_broadcast":
        await admin_broadcast_start(query, context, db_user)
    elif data == "admin_house":
        await admin_house(query, context, db_user)
    elif data == "admin_house_custom":
        await admin_house_custom(query, context, db_user)
    elif data.startswith("admin_toggle_account_"):
        await admin_toggle_account(query, context, int(data.split("_")[-1]))
    elif data.startswith("admin_remove_account_"):
        await admin_remove_account(query, context, int(data.split("_")[-1]))
    elif data.startswith("admin_add_account"):
        await admin_add_account_start(query, context, db_user)
    elif data.startswith("admin_withdraw_house_"):
        await admin_house_withdraw(query, context, float(data.split("_")[-1]))


async def admin_dashboard(query, context, db_user):
    total_users = db.count_users()
    total_games = db.get_total_games_played()
    total_deposits = db.get_total_collected()
    total_commission = db.get_net_profit()
    net_profit = total_commission
    house_balance = db.get_house_balance()

    text = (
        f"📊 <b>Admin Dashboard</b>\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🎮 Total Games: {total_games}\n"
        f"💰 Total Deposits: {fmt(total_deposits)} ETB\n"
        f"🏦 House Commission: {fmt(total_commission)} ETB\n"
        f"📈 Net Profit: {fmt(net_profit)} ETB\n"
        f"🏠 House Wallet: {fmt(house_balance)} ETB"
    )
    await safe_edit(query, text, reply_markup=back_keyboard(config.DEFAULT_LANGUAGE))


async def admin_withdrawals(query, context, db_user):
    rows = db.get_pending_withdrawals()[:5]
    if not rows:
        await safe_edit(query, "No pending withdrawals.", reply_markup=back_keyboard(config.DEFAULT_LANGUAGE))
        return

    lines = ["💸 <b>Pending Withdrawals</b>\n"]
    for wd in rows:
        user = db.get_user(wd["user_id"])
        username = user["username"] if user else str(wd["user_id"])
        lines.append(
            f"#{wd['id']} @{html.escape(username)} — {fmt(wd['amount'])} ETB — {wd['phone']} — Status: <b>Pending</b>"
        )
    text = "\n".join(lines)
    await safe_edit(query, text, reply_markup=back_keyboard(config.DEFAULT_LANGUAGE))

    for wd in rows:
        user = db.get_user(wd["user_id"])
        username = user["username"] if user else str(wd["user_id"])
        await query.message.reply_text(
            f"#{wd['id']} @{html.escape(username)} — {fmt(wd['amount'])} ETB — Status: <b>Pending</b>",
            reply_markup=withdraw_approval_keyboard(wd["id"]),
        )


async def admin_accounts(query, context, db_user):
    accounts = db.list_deposit_accounts()
    lines = ["💳 <b>Deposit Accounts</b>\n"]
    keyboard = []
    for acc in accounts:
        status = "✅ Active" if acc["active"] else "⏸ Inactive"
        lines.append(
            f"#{acc['id']} {acc['phone']} ({acc['recipient_name']}) — {status}\n"
            f"Deposits: {acc['deposit_count']}"
        )
        row = [
            InlineKeyboardButton("Toggle", callback_data=f"admin_toggle_account_{acc['id']}"),
            InlineKeyboardButton("Remove", callback_data=f"admin_remove_account_{acc['id']}"),
        ]
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("Add Account", callback_data="admin_add_account")])
    keyboard.append([InlineKeyboardButton("Back", callback_data="back_main")])
    text = "\n".join(lines)
    await safe_edit(query, text, reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_toggle_account(query, context, account_id):
    ok, admin_id = require_admin(query)
    if not ok:
        await query.answer("Not authorized.", show_alert=True)
        return
    accounts = db.list_deposit_accounts()
    target = next((a for a in accounts if a["id"] == account_id), None)
    if not target:
        await query.answer("Account not found.", show_alert=True)
        return
    new_active = 1 if target["active"] == 0 else 0
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE deposit_accounts SET active = ? WHERE id = ?", (new_active, account_id))
    conn.commit()
    conn.close()
    db.record_admin_action(admin_id, "toggle_deposit_account", target_id=account_id, details={"active": bool(new_active)})
    await query.answer(f"Account {'activated' if new_active else 'deactivated'}.")
    await admin_accounts(query, context, db.get_user(admin_id))


async def admin_remove_account(query, context, account_id):
    ok, admin_id = require_admin(query)
    if not ok:
        await query.answer("Not authorized.", show_alert=True)
        return
    accounts = db.list_deposit_accounts()
    target = next((a for a in accounts if a["id"] == account_id), None)
    if not target:
        await query.answer("Account not found.", show_alert=True)
        return
    db.remove_deposit_account(account_id)
    db.record_admin_action(admin_id, "remove_deposit_account", target_id=account_id, details={"phone": target["phone"]})
    await query.answer("Account removed.")
    await admin_accounts(query, context, db.get_user(admin_id))


async def admin_add_account_start(query, context, db_user):
    if not is_admin(db_user["user_id"]):
        await query.answer("Not authorized.", show_alert=True)
        return
    context.user_data["flow"] = "admin_add_account_phone"
    await safe_edit(query, "Enter new deposit account phone number:", reply_markup=back_keyboard(config.DEFAULT_LANGUAGE))


async def admin_broadcast_start(query, context, db_user):
    if not is_admin(db_user["user_id"]):
        await query.answer("Not authorized.", show_alert=True)
        return
    context.user_data["flow"] = "admin_broadcast"
    await safe_edit(query, "📣 Send the message you want to broadcast to all users:", reply_markup=back_keyboard(config.DEFAULT_LANGUAGE))


async def admin_house(query, context, db_user):
    if not is_admin(db_user["user_id"]):
        await query.answer("Not authorized.", show_alert=True)
        return
    balance = db.get_house_balance()
    total_earned = db.get_house_total_earned()
    keyboard_rows = []
    if balance > 0:
        keyboard_rows.append([
            InlineKeyboardButton("Withdraw 50 ETB", callback_data="admin_withdraw_house_50"),
            InlineKeyboardButton("Withdraw 100 ETB", callback_data="admin_withdraw_house_100"),
            InlineKeyboardButton("Custom", callback_data="admin_house_custom"),
        ])
    keyboard_rows.append([InlineKeyboardButton("Back", callback_data="back_main")])
    text = (
        f"🏦 <b>House Wallet</b>\n\n"
        f"Balance: {fmt(balance)} ETB\n"
        f"Total Earned: {fmt(total_earned)} ETB\n\n"
        f"{'Enter amount to withdraw:' if balance > 0 else 'No funds to withdraw.'}"
    )
    await safe_edit(query, text, reply_markup=InlineKeyboardMarkup(keyboard_rows))


async def admin_house_withdraw(query, context, amount):
    ok, admin_id = require_admin(query)
    if not ok:
        await query.answer("Not authorized.", show_alert=True)
        return
    if amount <= 0:
        await query.answer("Invalid amount.", show_alert=True)
        return
    success, reason, new_bal = db.withdraw_house_funds(amount)
    if not success:
        await query.answer(f"Insufficient house balance: {reason}", show_alert=True)
        return
    db.record_admin_action(admin_id, "withdraw_house", target_id=None, details={"amount": amount, "new_balance": new_bal})
    await query.answer(f"Withdrawn {fmt(amount)} ETB. New balance: {fmt(new_bal)} ETB")
    await admin_house(query, context, db.get_user(admin_id))


async def admin_house_custom(query, context, db_user):
    if not is_admin(db_user["user_id"]):
        await query.answer("Not authorized.", show_alert=True)
        return
    context.user_data["flow"] = "admin_house_withdraw_amount"
    await safe_edit(query, "Enter withdrawal amount:", reply_markup=back_keyboard(config.DEFAULT_LANGUAGE))

# =====================================================================
# MAIN
# =====================================================================

async def validate_group_chat(bot):
    chat_id = config.GROUP_CHAT_ID
    if not chat_id or chat_id == "-1001234567890":
        logger.warning("[broadcast] No valid GROUP_CHAT_ID configured — skipping group chat validation. Live broadcasts disabled.")
        return
    try:
        await bot.get_chat(chat_id)
        logger.info(f"[broadcast] GROUP_CHAT_ID validation passed for {chat_id}")
    except Exception as e:
        logger.error(f"[broadcast] GROUP_CHAT_ID validation failed for {chat_id}: {e}")


def main():
    _ensure_single_instance()
    init_monitoring("telegram-bot")
    global application
    application = Application.builder().token(config.BOT_TOKEN).build()
    global _bot_app
    _bot_app = application

    if not config.BOT_TOKEN:
        logger.error("CRITICAL EXCEPTION: BOT_TOKEN is missing inside config.py!")
        return

    import database as db
    db.init_db()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PHONE_COLLECT: [MessageHandler(filters.CONTACT, phone_received)],
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
            WITHDRAW_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
            TRANSFER_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
            TRANSFER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
            DEPOSIT_CUSTOM_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("admin", admin_command)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(menu_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    if config.MINI_APP_URL:
        async def post_init(application):
            await validate_group_chat(application.bot)
            await application.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text=get_text("btn_open_app", config.DEFAULT_LANGUAGE), web_app=WebAppInfo(url=config.MINI_APP_URL))
            )
            asyncio.create_task(auto_start_web_app_games(application))
        application.post_init = post_init
    else:
        async def post_init(application):
            await validate_group_chat(application.bot)
            asyncio.create_task(auto_start_web_app_games(application))
        application.post_init = post_init

    import signal
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def _signal_handler():
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    async def _run_with_scanner():
        scanner_task = asyncio.create_task(auto_start_web_app_games(application))
        try:
            await application.initialize()
            await application.start()
            await application.updater.start_polling()
            logger.info("Bot started successfully")
            while not stop_event.is_set():
                await asyncio.sleep(1)
        finally:
            scanner_task.cancel()
            try:
                await scanner_task
            except asyncio.CancelledError:
                pass
            await application.updater.stop()
            await application.stop()
            await application.shutdown()

    try:
        loop.run_until_complete(_run_with_scanner())
    finally:
        if os.path.exists(_BOT_PID_PATH):
            os.remove(_BOT_PID_PATH)


if __name__ == "__main__":
    main()
