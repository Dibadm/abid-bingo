# api_handlers.py
# ============================================
# HABESHA BET - MINI APP API HANDLERS
#
# These functions contain the actual business logic behind every Mini
# App API endpoint. They are deliberately framework-agnostic (no
# FastAPI/Flask imports here) so they can be:
#   1. Unit tested directly, without spinning up a web server
#   2. Wrapped by ANY web framework later without rewriting logic
#
# api_server.py (the FastAPI layer) is a thin shim that:
#   - extracts init_data from the request
#   - calls telegram_auth.extract_user_id() to get a verified user_id
#   - calls the matching handler function here with that user_id
#   - serializes the returned dict to JSON
#
# Every handler returns a plain dict shaped like:
#   {"ok": True, ...data...}   on success
#   {"ok": False, "error": "machine_readable_code", "message": "..."}  on failure
#
# This mirrors the (success, reason) tuple pattern already used
# throughout database.py, just reshaped for JSON responses.
# ============================================
import time as _time
from datetime import datetime, time, timedelta
import logging
import config
import database as db
import bingo
import bot
import game_state
from game_state import GAME_COUNTDOWN_START

logger = logging.getLogger("habesha_bet")


def _safe_card_index(c):
    """Coerce a card index from sqlite3.Row/dict/int to a plain int."""
    if isinstance(c, dict) or hasattr(c, "keys"):
        return int(c["card_index"])
    return int(c)


def _countdown_seconds_remaining(game_id: int) -> int:
    """Compute remaining countdown seconds.

    Prefers the in-process monotonic start (bot-side) but falls back to
    the DB timestamp so the Mini App can also show an accurate countdown.
    """
    start = GAME_COUNTDOWN_START.get(game_id)
    if start is None:
        game = db.get_game(game_id)
        if game:
            try:
                ts = game["countdown_started_at"]
            except (KeyError, IndexError, TypeError):
                return 0
            if ts:
                try:
                    start_dt = datetime.fromisoformat(ts)
                    elapsed = (datetime.utcnow() - start_dt).total_seconds()
                    return max(0, config.COUNTDOWN_SECONDS - int(elapsed))
                except Exception:
                    return 0
        else:
            return 0
    if start is None:
        return 0
    elapsed = _time.monotonic() - start
    remaining = config.COUNTDOWN_SECONDS - int(elapsed)
    return max(0, remaining)


def _user_lang(user_id: int) -> str:
    user = db.get_user(user_id)
    if user is None:
        return config.DEFAULT_LANGUAGE
    return user["language"] if user["language"] else config.DEFAULT_LANGUAGE


def _serialize_user(user_row) -> dict:
    try:
        bonus_balance = user_row["bonus_balance"]
    except (KeyError, IndexError):
        bonus_balance = 0
    streak = 0
    try:
        streak = user_row.get("daily_streak", 0) or 0
    except (KeyError, IndexError, AttributeError):
        streak = 0

    can_claim, claim_streak, claim_bonus_amount = db.can_claim_daily_streak_bonus(user_row["user_id"])

    next_streak_day = None
    next_bonus_amount = 0
    for day in sorted(config.DAILY_STREAK_BONUSES.keys()):
        if day > streak:
            next_streak_day = day
            next_bonus_amount = config.DAILY_STREAK_BONUSES[day]
            break

    return {
        "user_id": user_row["user_id"],
        "username": user_row["username"],
        "phone": user_row["phone"],
        "balance": user_row["balance"],
        "bonus_balance": bonus_balance,
        "language": user_row["language"],
        "daily_streak": streak,
        "next_streak_day": next_streak_day,
        "next_bonus_amount": next_bonus_amount,
        "can_claim_bonus": can_claim,
        "claim_bonus_amount": claim_bonus_amount,
        "claim_streak_day": claim_streak,
        "onboarding_seen": bool(user_row.get("onboarding_seen", 0) or 0),
    }


def _serialize_card(card_index: int, called_numbers: list, marked_numbers: list = None) -> dict:
    """A card as JSON: column-major grid of numbers plus which are called/marked.
    The frontend renders this into a 5x5 visual grid itself."""
    card = bingo.get_card(card_index)
    called_set = set(called_numbers)
    marked_set = set(marked_numbers or [])
    return {
        "card_index": card_index,
        "card_number": card_index + 1,  # 1-based for display
        "grid": card,  # list of 5 columns, each a list of 5 numbers (0 = FREE)
        "called": sorted(v for col in card for v in col if v != 0 and v in called_set),
        "marked": sorted(v for col in card for v in col if v != 0 and v in marked_set),
    }


def _serialize_jackpot() -> dict:
    jp = db.get_jackpot()
    return {
        "current_amount": jp.get("current_amount", 0.0),
        "room_fee": jp.get("room_fee", config.JACKPOT_ROOM_FEE),
        "triggered": bool(jp.get("triggered", 0)),
    }


def handle_get_card_preview(card_index: int) -> dict:
    """Return a preview of a single card for the card selection screen."""
    card = bingo.get_card(card_index)
    return {
        "ok": True,
        "card_index": card_index,
        "card_number": card_index + 1,
        "grid": card,
    }


# =====================================================================
# AUTH / BOOTSTRAP
# =====================================================================

def handle_bootstrap(user_id: int, username: str) -> dict:
    """Called once when the Mini App opens. Ensures the user exists
    (creating them if this is their very first interaction with the
    bot via the Mini App rather than /start in chat) and returns
    everything the frontend needs to render the home screen."""
    db_user = db.get_or_create_user(user_id, username)
    needs_phone = not bool(db_user["phone"])

    return {
        "ok": True,
        "user": _serialize_user(db_user),
        "needs_phone": needs_phone,
        "is_admin": user_id in config.ADMIN_IDS,
        "rooms": handle_get_rooms()["rooms"],
    }


def handle_set_phone(user_id: int, phone: str) -> dict:
    if not phone or len(phone) < 8:
        return {"ok": False, "error": "invalid_phone", "message": "Phone number looks invalid."}

    is_new_with_referral = False
    db_user = db.get_user(user_id)
    if db_user and db_user["referred_by"] is not None and not db_user["phone"]:
        is_new_with_referral = True

    db.set_user_phone(user_id, phone)

    if is_new_with_referral and config.SIGNUP_BONUS > 0:
        db.adjust_balance(user_id, config.SIGNUP_BONUS)
        db.add_bonus_balance(user_id, config.SIGNUP_BONUS)
        db.record_transaction(user_id, "signup_bonus", config.SIGNUP_BONUS, status="completed")

    return {"ok": True, "user": _serialize_user(db.get_user(user_id))}


def handle_set_language(user_id: int, lang: str) -> dict:
    if lang not in ("en", "am"):
        return {"ok": False, "error": "invalid_language", "message": "lang must be 'en' or 'am'"}
    db.set_user_language(user_id, lang)
    return {"ok": True, "user": _serialize_user(db.get_user(user_id))}


def handle_mark_onboarding_seen(user_id: int) -> dict:
    db.mark_onboarding_seen(user_id)
    return {"ok": True}


# =====================================================================
# ROOMS / LOBBY
# =====================================================================

def handle_get_rooms() -> dict:
    jackpot = _serialize_jackpot()
    games = []
    game_ids = []
    for fee in config.ROOM_FEES:
        game = db.get_or_create_active_game(fee)
        games.append((fee, game))
        game_ids.append(game["id"])

    player_counts = db.get_games_player_counts(game_ids)
    cards_sold_counts = db.get_games_cards_sold(game_ids)

    rooms = []
    for fee, game in games:
        pool = game["pool"]
        house_cut = round(pool * config.HOUSE_COMMISSION_PERCENT / 100, 2)
        prize_pool = round(pool - house_cut, 2)
        rooms.append({
            "room_fee": fee,
            "game_id": game["id"],
            "state": game["state"],
            "pool": pool,
            "prize_pool": prize_pool,
            "cards_sold": cards_sold_counts.get(game["id"], 0),
            "card_pool_size": config.CARD_POOL_SIZE,
            "player_count": player_counts.get(game["id"], 0),
            "jackpot": jackpot if fee == config.JACKPOT_ROOM_FEE else None,
        })
    return {"ok": True, "rooms": rooms}


def handle_get_my_active_game(user_id: int) -> dict:
    """Return the live game the user can resume (i.e. they bought a card
    in a game that is still waiting or running). Lets the frontend show an
    'Open game' option so a player who closed the app mid-round can rejoin.

    Returns has_game=False when there is nothing to resume.
    """
    game = db.get_user_active_game(user_id)
    if game is None:
        return {"ok": True, "has_game": False}

    game_id = game["id"]
    raw_my_cards = db.get_player_cards(game_id, user_id)
    my_cards = sorted(_safe_card_index(c) for c in raw_my_cards)

    return {
        "ok": True,
        "has_game": True,
        "game_id": game_id,
        "state": game["state"],
        "room_fee": game["room_fee"],
        "my_cards": my_cards,
        "countdown_seconds_remaining": _countdown_seconds_remaining(game_id),
        "countdown_total_seconds": config.COUNTDOWN_SECONDS,
    }


def handle_get_room_cards(user_id: int, room_fee: float) -> dict:
    logger.debug("handle_get_room_cards user=%s room=%s", user_id, room_fee)
    try:
        if room_fee not in config.ROOM_FEES:
            return {"ok": False, "error": "invalid_room", "message": "Unknown room fee."}

        game = db.get_or_create_active_game(room_fee)
        game_id = game["id"]
        taken = db.get_taken_cards(game_id)

        raw_my_cards = db.get_player_cards(game_id, user_id)
        my_cards = set(_safe_card_index(c) for c in raw_my_cards)

        countdown_remaining = _countdown_seconds_remaining(game_id)

        result = {
            "ok": True,
            "game_id": game_id,
            "state": game["state"],
            "pool": game["pool"],
            "prize_pool": db.get_prize_pool(game_id),
            "cards_sold": db.count_cards_sold(game_id),
            "card_pool_size": config.CARD_POOL_SIZE,
            "max_cards_per_player": config.MAX_CARDS_PER_PLAYER,
            "taken_cards": sorted(taken),
            "my_cards": sorted(my_cards),
            "countdown_seconds_remaining": countdown_remaining,
            "countdown_total_seconds": config.COUNTDOWN_SECONDS,
            "jackpot": _serialize_jackpot() if room_fee == config.JACKPOT_ROOM_FEE else None,
        }
        logger.debug("handle_get_room_cards success: %s", result)
        return result
    except Exception as e:
        logger.debug("handle_get_room_cards ERROR: %s", e)
        raise


def handle_buy_cards(user_id: int, room_fee: float, card_indices: list) -> dict:
    """Purchase one or more cards.

    On success the response now includes:
      • game_id                   — so the frontend can immediately
                                    start polling handle_get_game_state.
      • state                     — current game state after purchase.
      • countdown_seconds_remaining — seconds left in the lobby
                                    countdown so the frontend can render
                                    the timer right away without waiting
                                    for the next poll cycle.
      • countdown_total_seconds   — config value for the progress bar.
      • my_cards                  — full list of this player's cards
                                    in the game (plain int list, safe).
    """
    if room_fee not in config.ROOM_FEES:
        return {"ok": False, "error": "invalid_room", "message": "Unknown room fee."}

    if not card_indices:
        return {"ok": False, "error": "no_cards_selected", "message": "Select at least one card."}

    if any(
        not isinstance(i, int) or i < 0 or i >= config.CARD_POOL_SIZE
        for i in card_indices
    ):
        return {"ok": False, "error": "invalid_card_index", "message": "Card index out of range."}

    game = db.get_or_create_active_game(room_fee)
    game_id = game["id"]

    if game["state"] != "waiting":
        return {"ok": False, "error": "room_busy", "message": "A round is already in progress."}

    success, reason = db.purchase_cards(game_id, user_id, card_indices, room_fee)

    if not success:
        return {"ok": False, "error": reason, "message": _purchase_error_message(reason)}

    # Re-fetch updated values after purchase.
    raw_my_cards = db.get_player_cards(game_id, user_id)
    my_cards_ints = [_safe_card_index(c) for c in raw_my_cards]

    # Compute countdown remaining — will be None until the lifecycle
    # task starts (i.e. until bot.py calls ensure_game_lifecycle_started).
    # The frontend should treat None as "countdown not yet started".
    countdown_remaining = _countdown_seconds_remaining(game_id)

    # Re-read game to get current pool after the purchase.
    refreshed_game = db.get_game(game_id)
    current_state = refreshed_game["state"] if refreshed_game else "waiting"
    current_pool = refreshed_game["pool"] if refreshed_game else db.get_pool(game_id)

    return {
        "ok": True,
        "balance": db.get_balance(user_id),
        "game_id": game_id,
        "state": current_state,
        "my_cards": sorted(my_cards_ints),
        "cards_sold": db.count_cards_sold(game_id),
        "pool": current_pool,
        # Countdown timing — allows the frontend lobby timer to start
        # the instant a purchase is confirmed.
        "countdown_seconds_remaining": countdown_remaining,
        "countdown_total_seconds": config.COUNTDOWN_SECONDS,
    }


def _purchase_error_message(reason: str) -> str:
    return {
        "insufficient_balance": "Insufficient balance.",
        "card_taken": "One or more selected cards were just taken by someone else.",
        "max_cards_exceeded": f"You can hold at most {config.MAX_CARDS_PER_PLAYER} cards per round.",
    }.get(reason, "Could not complete purchase.")

# =====================================================================
# LIVE GAME STATE (polled by the frontend every ~1.5-2s during play)
# =====================================================================


def handle_get_game_state(user_id: int, game_id: int) -> dict:
    """The single endpoint the frontend polls while a game is running.

    Manual-mode behaviour (auto_win == False):
      • called_numbers is returned as an EMPTY LIST in the response so
        the frontend cannot auto-highlight all called squares.
      • Each card's "called" field is also empty for the same reason.
      • Each card's "marked" field contains the player's DB-persisted
        manual tap selections — these are the ONLY highlights shown.
      • call_count and last_call are still included so the game-info
        bar ("X/75 numbers called") stays accurate.

    Auto-mode behaviour (auto_win == True):
      • called_numbers is returned in full — the frontend highlights
        every called square automatically and win detection is instant.
    """
    game = db.get_game(game_id)
    if game is None:
        return {"ok": False, "error": "game_not_found", "message": "Game not found."}

    called_numbers = db.get_called_numbers(game_id)
    raw_card_indices = db.get_player_cards(game_id, user_id)
    # Defensive coercion — ensures plain ints even if the DB layer ever
    # returns Row objects directly (guard against data-type mismatch).
    my_card_indices = [_safe_card_index(c) for c in raw_card_indices]

    gp = db.get_game_player(game_id, user_id)
    auto_win = bool(gp["auto_win"]) if gp else False

    marked_map = db.get_all_marked_numbers(game_id) if my_card_indices else {}

    my_cards = []
    for idx in my_card_indices:
        marked = marked_map.get(idx, [])
        # Auto mode: called numbers are pre-highlighted so the user sees
        # matches automatically. Manual mode: called_numbers is passed as
        # [] so the frontend does NOT auto-mark cells; the user must tap
        # each called number themselves to mark it.
        visible_called = called_numbers if auto_win else []
        my_cards.append(_serialize_card(idx, visible_called, marked))

    result = {
        "ok": True,
        "game_id": game_id,
        "state": game["state"],
        "room_fee": game["room_fee"],
        "pool": game["pool"],
        "prize_pool": db.get_prize_pool(game_id),
        "called_numbers": called_numbers,
        "call_count": len(called_numbers),
        "max_calls": config.MAX_NUMBERS_CALLED,
        "player_count": len(db.get_game_players(game_id)),
        "my_cards": my_cards,
        "auto_win": auto_win,
        "manual_mode": not auto_win,
        "countdown_seconds_remaining": _countdown_seconds_remaining(game_id),
        "countdown_total_seconds": config.COUNTDOWN_SECONDS,
        "jackpot": _serialize_jackpot() if game["room_fee"] == config.JACKPOT_ROOM_FEE else None,
    }

    # last_call is always returned (the caller just announced a number;
    # the player heard the audio/saw the ball — hiding it would be wrong).
    if called_numbers:
        last_number = called_numbers[-1]
        result["last_call"] = {
            "number": last_number,
            "letter": bingo.number_to_letter(last_number),
            "amharic": bingo.number_to_amharic(last_number),
        }
        # Most-recent-first, for the on-screen call history strip. Same
        # source data as the top-level called_numbers field above — this
        # doesn't expose anything that field doesn't already.
        result["recent_calls"] = [
            {"number": n, "letter": bingo.number_to_letter(n)}
            for n in called_numbers[-6:][::-1]
        ]

    if game["state"] == "finished":
        import json
        winner_ids = json.loads(game["winner_ids"]) if game["winner_ids"] else []
        result["winners"] = winner_ids
        result["per_winner_amount"] = game["per_winner_amount"]
        result["i_won"] = user_id in winner_ids

        # Winner details for everyone (including losers) so non-winners can
        # see who won, the masked username, and the winning card number(s).
        # NOTE: sqlite3.Row does not implement `in` reliably, so we read
        # the column directly. The try/except keeps very old DBs safe.
        raw_winner_cards = {}
        try:
            if game["winner_cards"]:
                raw_winner_cards = json.loads(game["winner_cards"]) or {}
        except (KeyError, ValueError, TypeError):
            raw_winner_cards = {}
        winner_details = []
        for wid in winner_ids:
            wcards = raw_winner_cards.get(str(wid), raw_winner_cards.get(wid, []))
            if not wcards:
                # Fallback for games finished before winner_cards was
                # recorded: recompute the winning card(s) from the winner's
                # owned cards + the called numbers so the preview still works.
                owned = [_safe_card_index(c) for c in db.get_player_cards(game_id, wid)]
                wcards = bingo.evaluate_player_cards(owned, called_numbers)
            wuser = db.get_user(wid)
            cards_preview = []
            for cidx in wcards:
                card = bingo.get_card(int(cidx))
                winning = bingo.get_winning_lines(card, set(called_numbers))
                patterns = [label for label, _ in winning]
                win_nums = sorted(
                    card[c][r] for _, cells in winning for c, r in cells
                    if card[c][r] != 0
                )
                cards_preview.append({
                    "card_number": int(cidx) + 1,
                    "grid": card,  # column-major: grid[col][row]
                    "pattern": " · ".join(patterns) if patterns else "Win",
                    "winning_numbers": win_nums,
                })
            winner_details.append({
                "user_id": wid,
                "username_masked": bingo.mask_username(wuser["username"] if wuser else ""),
                "cards": cards_preview,
            })
        result["winner_details"] = winner_details

    return result


def handle_toggle_auto_win(user_id: int, game_id: int, enabled: bool) -> dict:
    gp = db.get_game_player(game_id, user_id)
    if gp is None:
        return {"ok": False, "error": "not_in_game", "message": "You are not in this game."}
    db.set_auto_win(game_id, user_id, enabled)
    return {"ok": True, "auto_win": enabled}


def handle_mark_number(user_id: int, game_id: int, card_index: int, number: int) -> dict:
    """Mark a called number. If the player owns multiple cards and the
    number appears on more than one, it's marked on all of them at once —
    manual mode still requires an explicit tap to mark anything (nothing
    is auto-marked from a call alone), it just applies that one tap to
    every one of your own cards that has the number, instead of making
    you repeat the same tap per card."""
    game = db.get_game(game_id)
    if game is None or game["state"] != "running":
        return {"ok": False, "error": "game_not_running", "message": "Game is not running."}

    called = set(db.get_called_numbers(game_id))
    if number not in called:
        return {"ok": False, "error": "number_not_called", "message": "This number has not been called yet."}

    my_cards = db.get_player_cards(game_id, user_id)
    if card_index not in my_cards:
        return {"ok": False, "error": "not_your_card", "message": "You don't own this card."}

    updated = []
    for idx in my_cards:
        grid = bingo.get_card(idx)
        if not any(number == v for col in grid for v in col):
            continue
        marked = set(db.get_marked_numbers(game_id, idx))
        if number not in marked:
            marked.add(number)
            db.update_marked_numbers(game_id, idx, sorted(marked))
        updated.append({"card_index": idx, "marked": sorted(marked)})

    return {"ok": True, "cards": updated}


def handle_claim_bingo(user_id: int, game_id: int) -> dict:
    """Manual BINGO claim from the Mini App. Validates the win and, if
    valid, resolves and pays out the game immediately — right here, in
    this request — instead of writing a claim and waiting for the bot's
    lifecycle loop to notice it on its next cycle. The bot and the API
    run as separate processes in production, so the actual Telegram
    group announcement is queued for the bot to send on its next check
    (only it has a live connection to Telegram), but the payout itself
    and this player's own confirmation happen instantly, synchronously,
    in this call."""
    game = db.get_game(game_id)
    if game is None or game["state"] != "running":
        return {"ok": False, "error": "game_not_running", "message": "This game is not currently running."}

    called_numbers = db.get_called_numbers(game_id)
    card_indices = db.get_player_cards(game_id, user_id)
    detected = bingo.evaluate_player_cards_detailed(card_indices, called_numbers)

    if not detected:
        return {"ok": False, "error": "no_valid_win", "message": "No valid win on your cards yet."}

    db.record_manual_bingo_claim(game_id, user_id, card_indices)

    if not db.try_claim_game_resolution(game_id):
        # Something else — the bot's own auto-win check, or another
        # manual claim landing in the same instant — got there first.
        # Don't pay out again; find out what actually happened instead.
        return _claim_outcome_after_race(user_id, game_id)

    # We won the race to resolve this game. Gather every other pending
    # manual claim too (another player's claim could have arrived at
    # nearly the same moment — multiple winners split the pool, same as
    # the bot's own detection does), re-validate everyone against the
    # same called-numbers snapshot, and pay out.
    winners_found = {user_id: detected}
    for claim_uid, claimed_cards in db.get_manual_bingo_claims(game_id).items():
        if claim_uid == user_id:
            continue
        other_detected = bingo.evaluate_player_cards_detailed(claimed_cards, called_numbers)
        if other_detected:
            winners_found[claim_uid] = other_detected

    result = db.resolve_game_winners(game_id, winners_found)
    db.clear_manual_bingo_claims(game_id)

    winner_lines_text = "\n".join(
        f"• @{bingo.mask_username(w['username'] or str(w['user_id']))} — {bot.fmt(w['amount'])} ETB"
        for w in result["winner_lines"]
    )
    db.queue_broadcast(game_id, f"🎉 Winners ({len(result['winner_ids'])})\n\n{winner_lines_text}")

    won = user_id in result["winner_ids"]
    return {
        "ok": True,
        "message": "🎉 BINGO confirmed! You won." if won else "Confirmed — resolved by another player's claim.",
        "won": won,
        "amount": result["per_winner_amount"] if won else 0,
    }


def _claim_outcome_after_race(user_id: int, game_id: int) -> dict:
    """Someone else already claimed the right to resolve this game by the
    time we tried (a rare race: the bot's own auto-win detection, or
    another manual claim, landed first). Check what actually happened
    instead of just reporting failure — the other resolver may have
    already correctly paid out this exact user, and we should say so."""
    import time
    import json
    for _ in range(20):  # poll briefly — the other resolver is mid-flight, not stuck
        game = db.get_game(game_id)
        if game and game["state"] == "finished":
            winner_ids = json.loads(game["winner_ids"]) if game["winner_ids"] else []
            if user_id in winner_ids:
                per_winner = float(game["per_winner_amount"] or 0)
                return {"ok": True, "message": "🎉 BINGO confirmed! You won.", "won": True, "amount": per_winner}
            return {
                "ok": False,
                "error": "already_resolved",
                "message": "This game was just resolved — you weren't among the winners this time.",
            }
        time.sleep(0.1)
    return {"ok": False, "error": "resolution_pending", "message": "Still resolving — please check back in a moment."}

# =====================================================================
# DEPOSIT / WITHDRAW / TRANSFER
# =====================================================================

def handle_get_deposit_account() -> dict:
    account = db.get_active_deposit_account()
    if account is None:
        return {"ok": False, "error": "no_account", "message": "Deposits are temporarily unavailable."}
    return {"ok": True, "phone": account["phone"], "recipient_name": account["recipient_name"]}


def handle_submit_deposit_sms(user_id: int, sms_text: str, expected_amount: float = None) -> dict:
    from sms_parser import parse_telebirr_sms, verify_recipient, validate_deposit_amount, extract_receipt_number
    from telebirr_verify import verify_receipt_online

    account = db.get_active_deposit_account()
    if account is None:
        return {"ok": False, "error": "no_account", "message": "Deposits are temporarily unavailable."}

    parsed = parse_telebirr_sms(sms_text)
    if parsed is None:
        return {"ok": False, "error": "invalid_sms", "message": "Could not read this SMS."}

    expected_last4 = account["phone"][-4:]
    ok, reason = verify_recipient(parsed, account["recipient_name"], expected_last4)
    if not ok:
        return {"ok": False, "error": "wrong_account", "message": "Payment was not sent to our active account."}

    if db.reference_already_used(parsed["reference"]):
        return {"ok": False, "error": "already_used", "message": "This transaction has already been credited."}

    receipt_no = extract_receipt_number(sms_text)
    verification_status = "skipped"
    verification_raw = None

    if config.TELEBIRR_VERIFY_ENABLED and receipt_no:
        verification_status = "pending"
        verification = verify_receipt_online(receipt_no, timeout=config.TELEBIRR_VERIFY_TIMEOUT)

        if not verification.get("ok"):
            verification_status = "failed"
            verification_raw = verification.get("error")
            logger.warning(
                "[telebirr_verify] failed for user=%s receipt=%s error=%s",
                user_id, receipt_no, verification_raw,
            )
            if verification.get("error") in ("receipt_site_unreachable", "receipt_site_timeout", "receipt_fetch_error"):
                logger.warning("[telebirr_verify] site down, falling back to regex-only for this deposit")
            else:
                return {
                    "ok": False,
                    "error": "receipt_verification_failed",
                    "message": "Could not verify receipt. Please try again later.",
                }
        else:
            verification_status = "verified"
            verification_raw = None

            if verification.get("amount") is not None and abs(verification["amount"] - parsed["amount"]) > 0.01:
                return {
                    "ok": False,
                    "error": "receipt_amount_mismatch",
                    "message": f"Receipt shows {verification['amount']} ETB but SMS shows {parsed['amount']} ETB.",
                }

            if verification.get("recipient_name") and parsed.get("recipient_name"):
                if verification["recipient_name"].strip().lower() != parsed["recipient_name"].strip().lower():
                    return {
                        "ok": False,
                        "error": "receipt_recipient_mismatch",
                        "message": "Receipt recipient does not match deposit details.",
                    }

            if verification.get("recipient_phone_last4") and parsed.get("recipient_last4"):
                if verification["recipient_phone_last4"] != parsed["recipient_last4"]:
                    return {
                        "ok": False,
                        "error": "receipt_phone_mismatch",
                        "message": "Receipt phone number does not match deposit details.",
                    }

    if expected_amount is not None:
        amount_ok, _ = validate_deposit_amount(parsed, expected_amount=expected_amount)
        if not amount_ok:
            return {
                "ok": False, "error": "amount_mismatch",
                "message": f"SMS shows {parsed['amount']} ETB but {expected_amount} ETB was expected.",
            }

    success, new_balance, error = db.deposit_funds(
        user_id, parsed["amount"],
        reference=parsed["reference"],
        receipt_no=receipt_no,
        verification_status=verification_status,
        verification_raw=verification_raw,
    )
    if not success:
        return {"ok": False, "error": error or "deposit_failed", "message": "This transaction has already been credited."}

    db.record_deposit_for_account(account["id"])

    _maybe_award_referral_bonus(user_id)

    return {"ok": True, "amount_credited": parsed["amount"], "balance": new_balance}


def _maybe_award_referral_bonus(user_id: int):
    db_user = db.get_user(user_id)
    if (
        db_user["referred_by"] is not None
        and db_user["referral_bonus_given"] == 0
        and db.count_deposits(user_id) == 1
    ):
        referrer_id = db_user["referred_by"]
        db.adjust_balance(referrer_id, config.REFERRAL_BONUS)
        db.add_bonus_balance(referrer_id, config.REFERRAL_BONUS)
        db.record_transaction(referrer_id, "referral_bonus", config.REFERRAL_BONUS, status="completed")
        db.mark_referral_bonus_given(user_id)


def handle_withdraw(user_id: int, amount: float) -> dict:
    db_user = db.get_user(user_id)
    if db_user is None:
        return {"ok": False, "error": "user_not_found", "message": "User not found."}

    if not db_user["phone"]:
        return {"ok": False, "error": "no_phone", "message": "Register a phone number first."}

    if amount < config.MIN_WITHDRAWAL:
        return {"ok": False, "error": "below_minimum", "message": f"Minimum withdrawal is {config.MIN_WITHDRAWAL} ETB."}

    success, new_balance = db.deduct_balance(user_id, amount)
    if not success:
        return {"ok": False, "error": "insufficient_balance", "message": "Insufficient balance.", "balance": db.get_balance(user_id)}

    withdrawal_id = db.create_withdrawal(user_id, amount, db_user["phone"])
    db.record_transaction(user_id, "withdraw", -amount, reference=f"withdraw_{withdrawal_id}", status="pending")

    try:
        import asyncio
        from bot import send_admin_alert
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(send_admin_alert(
                f"💸 Withdrawal Request\n\n"
                f"User: {user_id}\n"
                f"Amount: {amount} ETB\n"
                f"Phone: {db_user['phone']}\n"
                f"Withdrawal ID: {withdrawal_id}\n"
                f"Status: Pending — please review and send money manually"
            ))
        else:
            loop.run_until_complete(send_admin_alert(
                f"💸 Withdrawal Request\n\n"
                f"User: {user_id}\n"
                f"Amount: {amount} ETB\n"
                f"Phone: {db_user['phone']}\n"
                f"Withdrawal ID: {withdrawal_id}\n"
                f"Status: Pending — please review and send money manually"
            ))
    except Exception:
        pass

    return {"ok": True, "withdrawal_id": withdrawal_id, "balance": new_balance}


def handle_transfer(user_id: int, to_username: str, amount: float) -> dict:
    can, seconds_remaining = db.can_transfer(user_id)
    if not can:
        return {
            "ok": False, "error": "cooldown",
            "message": f"You can only transfer once per hour. Try again in {seconds_remaining // 60} min.",
            "seconds_remaining": seconds_remaining,
        }

    if amount < config.MIN_TRANSFER:
        return {"ok": False, "error": "below_minimum", "message": f"Minimum transfer is {config.MIN_TRANSFER} ETB."}

    target = db.find_user_by_username(to_username.lstrip("@"))
    if target is None:
        return {"ok": False, "error": "user_not_found", "message": f"User @{to_username} not found."}

    if target["user_id"] == user_id:
        return {"ok": False, "error": "cannot_self_transfer", "message": "You cannot transfer to yourself."}

    success, reason = db.transfer_funds(user_id, target["user_id"], amount)
    if not success:
        return {"ok": False, "error": reason, "message": "Transfer failed."}

    return {"ok": True, "balance": db.get_balance(user_id)}


# =====================================================================
# PROFILE / TRANSACTIONS / REFERRAL / BONUS
# =====================================================================

def handle_get_jackpot() -> dict:
    return {"ok": True, "jackpot": _serialize_jackpot()}


def handle_get_recent_winners() -> dict:
    return {"ok": True, "winners": db.get_recent_winners(limit=8)}


def handle_get_profile(user_id: int) -> dict:
    db_user = db.get_user(user_id)
    if db_user is None:
        return {"ok": False, "error": "user_not_found", "message": "User not found."}
    return {
        "ok": True,
        "user": _serialize_user(db_user),
        "referral_count": db.count_referrals(user_id),
        "joined": db_user["created_at"],
    }


def handle_get_transactions(user_id: int, limit: int = 20) -> dict:
    rows = db.get_user_transactions(user_id, limit=limit)
    return {
        "ok": True,
        "transactions": [
            {
                "type": r["type"], "amount": r["amount"], "status": r["status"],
                "created_at": r["created_at"], "reference": r["reference"],
            }
            for r in rows
        ],
    }


def handle_get_referral_info(user_id: int) -> dict:
    link = f"https://t.me/{config.BOT_USERNAME}?start=ref{user_id}"
    return {
        "ok": True,
        "link": link,
        "referral_count": db.count_referrals(user_id),
        "signup_bonus": config.SIGNUP_BONUS,
        "referral_bonus": config.REFERRAL_BONUS,
    }


def handle_claim_daily_bonus(user_id: int) -> dict:
    can_claim, streak_days, next_bonus_amount = db.can_claim_daily_streak_bonus(user_id)
    if not can_claim:
        user = db.get_user(user_id)
        now = datetime.utcnow()
        last = datetime.fromisoformat(user["last_bonus_claim_date"]).date()
        next_claim = datetime.combine(last + timedelta(days=1), time.min)
        hours_remaining = max(1, int((next_claim - now).total_seconds() / 3600))
        return {"ok": False, "error": "cooldown", "hours_remaining": hours_remaining}

    bonus_to_add = config.DAILY_STREAK_BONUSES.get(streak_days, config.DAILY_BONUS_AMOUNT)
    db.add_bonus_balance(user_id, bonus_to_add)
    db.record_transaction(user_id, "daily_bonus", bonus_to_add, status="completed")
    db.set_daily_streak_bonus_claimed(user_id, streak_days)
    return {
        "ok": True,
        "amount": bonus_to_add,
        "streak_days": streak_days,
        "next_bonus_amount": next_bonus_amount,
        "balance": db.get_balance(user_id),
        "bonus_balance": db.get_bonus_balance(user_id),
    }


# =====================================================================
# ADMIN HANDLERS
# =====================================================================

def handle_admin_dashboard() -> dict:
    return {
        "ok": True,
        "total_users": db.count_users(),
        "total_games": db.get_total_games_played(),
        "total_deposits": db.get_total_collected(),
        "total_house_commission": db.get_net_profit(),
        "net_profit": db.get_net_profit(),
        "house_balance": db.get_house_balance(),
        "house_total_earned": db.get_house_total_earned(),
    }


def handle_admin_withdrawals() -> dict:
    rows = db.get_pending_withdrawals()[:10]
    withdrawals = []
    for wd in rows:
        withdrawals.append({
            "id": wd["id"],
            "user_id": wd["user_id"],
            "amount": wd["amount"],
            "phone": wd["phone"],
            "status": wd["status"],
            "created_at": wd["created_at"],
        })
    return {"ok": True, "withdrawals": withdrawals}


def handle_admin_approve_withdrawal(admin_id: int, withdrawal_id: int) -> dict:
    success = db.update_withdrawal_status(withdrawal_id, "completed")
    if not success:
        return {"ok": False, "error": "already_processed", "message": "Withdrawal was already handled."}
    wd = db.get_withdrawal(withdrawal_id)
    details = {"amount": wd["amount"], "user_id": wd["user_id"], "phone": wd["phone"]}
    db.record_admin_action(admin_id, "approve_withdrawal", target_id=withdrawal_id, details=details)
    return {"ok": True, "withdrawal_id": withdrawal_id, "status": "completed"}


def handle_admin_reject_withdrawal(admin_id: int, withdrawal_id: int) -> dict:
    success = db.update_withdrawal_status(withdrawal_id, "rejected")
    if not success:
        return {"ok": False, "error": "already_processed", "message": "Withdrawal was already handled."}
    wd = db.get_withdrawal(withdrawal_id)
    db.adjust_balance(wd["user_id"], wd["amount"])
    db.record_transaction(wd["user_id"], "withdraw_refund", wd["amount"], status="completed")
    details = {"amount": wd["amount"], "user_id": wd["user_id"], "phone": wd["phone"]}
    db.record_admin_action(admin_id, "reject_withdrawal", target_id=withdrawal_id, details=details)
    return {"ok": True, "withdrawal_id": withdrawal_id, "status": "rejected", "refunded": wd["amount"]}


def handle_admin_get_deposit_accounts() -> dict:
    accounts = db.list_deposit_accounts()
    return {
        "ok": True,
        "accounts": [
            {
                "id": a["id"],
                "phone": a["phone"],
                "recipient_name": a["recipient_name"],
                "active": bool(a["active"]),
                "deposit_count": a["deposit_count"],
            }
            for a in accounts
        ],
    }


def handle_admin_add_deposit_account(admin_id: int, phone: str, recipient_name: str) -> dict:
    if not phone.startswith("251") or len(phone) != 12:
        return {"ok": False, "error": "invalid_phone", "message": "Phone must be 2519xxxxxxx"}
    acc_id = db.add_deposit_account(phone, recipient_name)
    details = {"phone": phone, "name": recipient_name}
    db.record_admin_action(admin_id, "add_deposit_account", target_id=acc_id, details=details)
    return {"ok": True, "account_id": acc_id}


def handle_admin_remove_deposit_account(admin_id: int, account_id: int) -> dict:
    accounts = db.list_deposit_accounts()
    target = next((a for a in accounts if a["id"] == account_id), None)
    if not target:
        return {"ok": False, "error": "not_found", "message": "Account not found."}
    db.remove_deposit_account(account_id)
    details = {"phone": target["phone"], "name": target["recipient_name"]}
    db.record_admin_action(admin_id, "remove_deposit_account", target_id=account_id, details=details)
    return {"ok": True}


async def handle_admin_broadcast(admin_id: int, message: str) -> dict:
    if not config.BROADCAST_ENABLED:
        return {"ok": False, "error": "broadcast_disabled", "message": "Broadcasts are disabled."}
    user_ids = db.get_all_user_ids()
    details = {"recipients": len(user_ids), "message": message}
    db.record_admin_action(admin_id, "broadcast", details=details)

    sent = 0
    failed = 0
    skipped_no_chat = 0
    for uid in user_ids:
        chat_id = db.get_user_chat_id(uid)
        if chat_id is None:
            skipped_no_chat += 1
            continue
        ok = await bot.send_message_to_chat(chat_id, message)
        if ok:
            sent += 1
        else:
            failed += 1

    logger.info(
        "[broadcast] complete: total=%d sent=%d failed=%d skipped_no_chat=%d",
        len(user_ids), sent, failed, skipped_no_chat,
    )
    return {"ok": True, "sent": sent, "failed": failed, "skipped_no_chat": skipped_no_chat}


async def handle_admin_broadcast_image(admin_id: int, message: str, image_url: str = None, image_file_id: str = None) -> dict:
    if not config.BROADCAST_ENABLED:
        return {"ok": False, "error": "broadcast_disabled", "message": "Broadcasts are disabled."}
    user_ids = db.get_all_user_ids()
    details = {"recipients": len(user_ids), "message": message, "image_url": image_url, "image_file_id": image_file_id}
    db.record_admin_action(admin_id, "broadcast_image", details=details)

    photo = image_file_id or image_url
    sent = 0
    failed = 0
    skipped_no_chat = 0
    for uid in user_ids:
        chat_id = db.get_user_chat_id(uid)
        if chat_id is None:
            skipped_no_chat += 1
            continue
        try:
            if photo:
                ok = await bot.send_photo_to_chat(chat_id, photo, message if message else None)
            else:
                ok = await bot.send_message_to_chat(chat_id, message)
            if ok:
                sent += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    logger.info(
        "[broadcast_image] complete: total=%d sent=%d failed=%d skipped_no_chat=%d",
        len(user_ids), sent, failed, skipped_no_chat,
    )
    return {"ok": True, "sent": sent, "failed": failed, "skipped_no_chat": skipped_no_chat}


def handle_admin_toggle_deposit_account(admin_id: int, account_id: int) -> dict:
    accounts = db.list_deposit_accounts()
    target = next((a for a in accounts if a["id"] == account_id), None)
    if not target:
        return {"ok": False, "error": "not_found", "message": "Account not found."}
    new_active = 1 if target["active"] == 0 else 0
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE deposit_accounts SET active = ? WHERE id = ?", (new_active, account_id))
    conn.commit()
    conn.close()
    db.record_admin_action(admin_id, "toggle_deposit_account", target_id=account_id, details={"active": bool(new_active)})
    return {"ok": True, "active": bool(new_active)}


def handle_admin_get_house_wallet() -> dict:
    return {
        "ok": True,
        "balance": db.get_house_balance(),
        "total_earned": db.get_house_total_earned(),
    }


def handle_admin_withdraw_house(admin_id: int, amount: float) -> dict:
    success, reason, new_bal = db.withdraw_house_funds(amount)
    if not success:
        return {"ok": False, "error": "insufficient_balance", "message": reason}
    details = {"amount": amount, "new_balance": new_bal}
    db.record_admin_action(admin_id, "withdraw_house", details=details)
    return {"ok": True, "amount": amount, "new_balance": new_bal}


def handle_admin_force_finish_stuck_game(admin_id: int, game_id: int) -> dict:
    success, reason = db.force_finish_stuck_game(game_id)
    details = {"game_id": game_id, "reason": reason}
    db.record_admin_action(admin_id, "force_finish_stuck_game", target_id=game_id, details=details)
    if not success:
        return {"ok": False, "error": reason, "message": f"Game {game_id} could not be force-finished: {reason}"}
    return {"ok": True, "game_id": game_id, "status": "finished"}



