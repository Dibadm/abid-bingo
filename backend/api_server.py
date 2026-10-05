# api_server.py
# ============================================
# HABESHA BET - MINI APP API SERVER (FastAPI)
#
# Thin HTTP layer. ALL real logic lives in api_handlers.py; this file
# only:
#   1. Defines routes matching what the React Mini App calls
#   2. Extracts + verifies Telegram initData on every request via
#      telegram_auth.extract_user_id() - this is the ONLY source of
#      truth for "who is making this request." The frontend may also
#      send a user_id in the body for convenience/display, but it is
#      NEVER trusted for authorization - every handler call below uses
#      the verified `auth_user_id`, not anything from the request body.
#   3. Serializes handler results to JSON with the right HTTP status
#
# Runs in the SAME process as bot.py (see bot.py's main(), which starts
# this via uvicorn in a background thread/task alongside run_polling()).
# This guarantees there is only ever one process writing to the SQLite
# database, avoiding the multi-writer corruption risk a separate
# process would introduce.
#
# CORS is enabled permissively (allow_origins=["*"]) because Telegram's
# WebView wrapper origin varies by platform/version and is not worth
# pinning down; the REAL security boundary is initData verification,
# not CORS - CORS only stops browser-based cross-origin reads of
# RESPONSES, it does nothing to stop a forged request from curl, so it
# was never the thing protecting this API in the first place.
# ============================================

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel
from typing import Optional, List
import os
import time
import threading
import logging
import base64
import json
from urllib.parse import parse_qs, unquote

import config
import api_handlers as handlers
from telegram_auth import extract_user_id, InitDataInvalid
from database import backup_database
from monitoring import init_monitoring, capture_error

logger = logging.getLogger("habesha_bet")


def _user_id_from_init_data(init_data: str) -> str | None:
    try:
        params = parse_qs(init_data)
        user_str = params.get("user", [""])[0]
        if user_str:
            user = json.loads(unquote(user_str))
            return str(user.get("id"))
    except Exception:
        pass
    return None

app = FastAPI(title="Habesha Bet Mini App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup_monitoring():
    init_monitoring("api-server")
    # Previously this relied entirely on bot.py having already called
    # init_db() first (fragile — depended on start order/timing). Calling
    # it here too is safe: init_db() is idempotent (CREATE TABLE IF NOT
    # EXISTS / guarded column migrations), so this makes api_server.py
    # correct whether it's running alongside the bot or as its own
    # standalone service.
    from database import init_db
    init_db()


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    # HTTPException (including the ok:False -> 400 mapping in _respond) is
    # normal control flow, already shaped for the frontend — don't re-report
    # it as a crash. Only genuinely unexpected exceptions get captured here.
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        detail = exc.detail if isinstance(exc.detail, dict) else {"ok": False, "error": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content=detail)

    logger.exception(f"[api] unhandled exception on {request.method} {request.url.path}")
    capture_error(f"unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": "internal_error", "message": "Something went wrong. Please try again."},
    )


def _schedule_backups():
    interval = config.BACKUP_INTERVAL_MINUTES * 60
    while True:
        time.sleep(interval)
        try:
            backup_database()
        except Exception:
            logger.exception("backup failed")


_RATE_LIMIT_STORE = {}
_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_MAX = 300
_RATE_LIMIT_WINDOW = 60


class RateLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope["path"]
        if path == "/health":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        user_id = headers.get(b"x-dev-user-id")
        if not user_id:
            init_data = headers.get(b"x-init-data", b"").decode()
            user_id = _user_id_from_init_data(init_data)
        if user_id:
            user_id = user_id.decode() if isinstance(user_id, bytes) else user_id
            now = time.time()
            with _RATE_LIMIT_LOCK:
                window = _RATE_LIMIT_STORE.get(user_id)
                if not window:
                    window = []
                    _RATE_LIMIT_STORE[user_id] = window
                cutoff = now - _RATE_LIMIT_WINDOW
                while window and window[0] < cutoff:
                    window.pop(0)
                prune_cutoff = now - _RATE_LIMIT_WINDOW * 2
                while window and window[0] < prune_cutoff:
                    window.pop(0)
                if len(window) >= _RATE_LIMIT_MAX:
                    from starlette.responses import JSONResponse
                    resp = JSONResponse({"detail": "Too Many Requests"}, status_code=429)
                    await resp(scope, receive, send)
                    return
                window.append(now)

        await self.app(scope, receive, send)


app.add_middleware(RateLimitMiddleware)


class RequestIdMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        import uuid
        request_id = str(uuid.uuid4())[:8]
        scope["state"] = getattr(scope, "state", {})
        scope["state"]["request_id"] = request_id

        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])
                headers.append([b"x-request-id", request_id.encode()])
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_request_id)


app.add_middleware(RequestIdMiddleware)


def _auth(x_init_data: Optional[str], x_dev_user_id: Optional[int] = None) -> int:
    """Shared dependency logic: verify the X-Init-Data header and return
    a trustworthy user_id, or raise a 401 the frontend can recognize and
    react to (e.g. by reopening the Mini App so Telegram reissues fresh
    initData).

    Dev bypass: when running locally behind localtunnel, Telegram often
    sends empty initData. To keep testing, pass X-Dev-User-Id header
    with a fake user_id. NEVER merge this to production.
    """
    if x_dev_user_id is not None:
        if os.getenv("ALLOW_DEV_AUTH", "false").lower() != "true":
            raise HTTPException(status_code=403, detail="dev_auth_disabled")
        if os.getenv("DEBUG"):
            logger.warning("DEV AUTH ACTIVE — initData verification bypassed user_id=%s", x_dev_user_id)
        return int(x_dev_user_id)
    if not x_init_data:
        logger.debug("[AUTH] REJECT missing initData")
        raise HTTPException(status_code=401, detail="missing_init_data")
    try:
        uid = extract_user_id(x_init_data, bot_token=config.BOT_TOKEN)
        logger.debug("[AUTH] initData user_id=%s", uid)
        return uid
    except InitDataInvalid as e:
        logger.debug("[AUTH] REJECT invalid initData: %s", e)
        raise HTTPException(status_code=401, detail=f"invalid_init_data: {e}")


def _respond(result: dict):
    """Handlers return {"ok": True/False, ...}. Map ok=False to HTTP 400
    so the frontend's generic error handling (anything non-2xx -> show
    error toast) works without inspecting the body, while still
    returning the full body so it CAN inspect `error`/`message` for a
    nicer in-app message."""
    if result.get("ok") is False:
        raise HTTPException(status_code=400, detail=result)
    return result


def _admin_auth(x_init_data: Optional[str], x_dev_user_id: Optional[int] = None) -> int:
    user_id = _auth(x_init_data, x_dev_user_id)
    if user_id not in config.ADMIN_IDS:
        raise HTTPException(status_code=403, detail="not_admin")
    return user_id


# =====================================================================
# REQUEST BODY MODELS
# =====================================================================

class SetPhoneBody(BaseModel):
    phone: str


class SetLanguageBody(BaseModel):
    language: str


class BuyCardsBody(BaseModel):
    room_fee: float
    card_indices: List[int]


class ToggleAutoBody(BaseModel):
    game_id: int
    enabled: bool


class MarkNumberBody(BaseModel):
    game_id: int
    card_index: int
    number: int


class ClaimBingoBody(BaseModel):
    game_id: int


class SubmitSmsBody(BaseModel):
    sms_text: str
    expected_amount: Optional[float] = None


class WithdrawBody(BaseModel):
    amount: float


class TransferBody(BaseModel):
    to_username: str
    amount: float


class BroadcastBody(BaseModel):
    message: str


class BroadcastImageBody(BaseModel):
    message: Optional[str] = ""
    image_url: Optional[str] = None
    image_file_id: Optional[str] = None


class HouseWithdrawBody(BaseModel):
    amount: float


class GameIdBody(BaseModel):
    game_id: int


class DepositAccountCreateBody(BaseModel):
    phone: str
    recipient_name: str


# =====================================================================
# AUTH / BOOTSTRAP
# =====================================================================

@app.get("/api/bootstrap")
def bootstrap(x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None), x_username: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    username = x_username or str(user_id)
    return _respond(handlers.handle_bootstrap(user_id, username))


@app.post("/api/set-phone")
def set_phone(body: SetPhoneBody, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_set_phone(user_id, body.phone))


@app.post("/api/set-language")
def set_language(body: SetLanguageBody, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_set_language(user_id, body.language))


@app.post("/api/onboarding-seen")
def onboarding_seen(x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_mark_onboarding_seen(user_id))


@app.get("/api/rooms")
def get_rooms(x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_get_rooms())


@app.get("/api/my-active-game")
def my_active_game(x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_get_my_active_game(user_id))


@app.get("/api/rooms/{room_fee}/cards")
def get_room_cards(room_fee: float, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_get_room_cards(user_id, room_fee))


@app.get("/api/cards/{card_index}/preview")
def get_card_preview(card_index: int, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_get_card_preview(card_index))


@app.post("/api/buy-cards")
def buy_cards(body: BuyCardsBody, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_buy_cards(user_id, body.room_fee, body.card_indices))


@app.get("/api/games/{game_id}/state")
def get_game_state(game_id: int, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_get_game_state(user_id, game_id))


@app.post("/api/toggle-auto-win")
def toggle_auto_win(body: ToggleAutoBody, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_toggle_auto_win(user_id, body.game_id, body.enabled))


@app.post("/api/mark-number")
def mark_number(body: MarkNumberBody, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_mark_number(user_id, body.game_id, body.card_index, body.number))


@app.post("/api/claim-bingo")
def claim_bingo(body: ClaimBingoBody, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_claim_bingo(user_id, body.game_id))



# =====================================================================
# DEPOSIT / WITHDRAW / TRANSFER
# =====================================================================

@app.get("/api/deposit-account")
def get_deposit_account(x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_get_deposit_account())


@app.post("/api/submit-deposit-sms")
def submit_deposit_sms(body: SubmitSmsBody, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_submit_deposit_sms(user_id, body.sms_text, body.expected_amount))


@app.post("/api/withdraw")
def withdraw(body: WithdrawBody, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_withdraw(user_id, body.amount))


@app.post("/api/transfer")
def transfer(body: TransferBody, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_transfer(user_id, body.to_username, body.amount))


# =====================================================================
# PROFILE / TRANSACTIONS / REFERRAL / BONUS
# =====================================================================

@app.get("/api/profile")
def get_profile(x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_get_profile(user_id))


@app.get("/api/transactions")
def get_transactions(limit: int = 20, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_get_transactions(user_id, limit))


@app.get("/api/referral")
def get_referral(x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_get_referral_info(user_id))


@app.post("/api/daily-bonus")
def claim_daily_bonus(x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    user_id = _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_claim_daily_bonus(user_id))


@app.get("/api/jackpot")
def get_jackpot(x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_get_jackpot())


@app.get("/api/recent-winners")
def get_recent_winners(x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    _auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_get_recent_winners())


# =====================================================================
# ADMIN
# All routes require admin privileges via ADMIN_IDS in config.
# =====================================================================

@app.get("/api/admin/dashboard")
def admin_dashboard(x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    _admin_auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_admin_dashboard())


@app.get("/api/admin/withdrawals")
def admin_withdrawals(x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    _admin_auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_admin_withdrawals())


@app.post("/api/admin/withdrawals/{withdrawal_id}/approve")
def admin_approve_withdrawal_route(withdrawal_id: int, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    admin_id = _admin_auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_admin_approve_withdrawal(admin_id, withdrawal_id))


@app.post("/api/admin/withdrawals/{withdrawal_id}/reject")
def admin_reject_withdrawal_route(withdrawal_id: int, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    admin_id = _admin_auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_admin_reject_withdrawal(admin_id, withdrawal_id))


@app.get("/api/admin/deposit-accounts")
def admin_get_deposit_accounts(x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    _admin_auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_admin_get_deposit_accounts())


@app.post("/api/admin/deposit-accounts")
def admin_add_deposit_account(body: DepositAccountCreateBody, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    admin_id = _admin_auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_admin_add_deposit_account(admin_id, body.phone, body.recipient_name))


@app.delete("/api/admin/deposit-accounts/{account_id}")
def admin_remove_deposit_account(account_id: int, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    admin_id = _admin_auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_admin_remove_deposit_account(admin_id, account_id))


@app.post("/api/admin/broadcast")
async def admin_broadcast(body: BroadcastBody, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    admin_id = _admin_auth(x_init_data, x_dev_user_id)
    return _respond(await handlers.handle_admin_broadcast(admin_id, body.message))


@app.post("/api/admin/broadcast/image")
async def admin_broadcast_image(body: BroadcastImageBody, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    admin_id = _admin_auth(x_init_data, x_dev_user_id)
    return _respond(await handlers.handle_admin_broadcast_image(admin_id, body.message, body.image_url, body.image_file_id))


@app.post("/api/admin/deposit-accounts/{account_id}/toggle")
async def admin_toggle_deposit_account(account_id: int, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    admin_id = _admin_auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_admin_toggle_deposit_account(admin_id, account_id))


@app.get("/api/admin/house-wallet")
def admin_get_house_wallet(x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[str] = Header(None)):
    _admin_auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_admin_get_house_wallet())


@app.post("/api/admin/house-wallet/withdraw")
def admin_withdraw_house(body: HouseWithdrawBody, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[int] = Header(None)):
    admin_id = _admin_auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_admin_withdraw_house(admin_id, body.amount))


@app.post("/api/admin/games/{game_id}/force-finish")
def admin_force_finish_game(game_id: int, x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[int] = Header(None)):
    admin_id = _admin_auth(x_init_data, x_dev_user_id)
    return _respond(handlers.handle_admin_force_finish_stuck_game(admin_id, game_id))


@app.get("/api/debug/config")
def debug_config(x_init_data: Optional[str] = Header(None), x_dev_user_id: Optional[int] = Header(None)):
    _admin_auth(x_init_data, x_dev_user_id)
    safe = {
        "PRODUCTION": getattr(config, "PRODUCTION", False),
        "BROADCAST_ENABLED": config.BROADCAST_ENABLED,
        "API_HOST": config.API_HOST,
        "API_PORT": config.API_PORT,
        "DB_PATH": config.DB_PATH,
        "DEFAULT_LANGUAGE": config.DEFAULT_LANGUAGE,
        "BACKUP_INTERVAL_MINUTES": config.BACKUP_INTERVAL_MINUTES,
        "MAX_BACKUPS": getattr(config, "MAX_BACKUPS", 50),
        "ROOM_FEES": config.ROOM_FEES,
        "CARD_POOL_SIZE": config.CARD_POOL_SIZE,
        "MAX_CARDS_PER_PLAYER": config.MAX_CARDS_PER_PLAYER,
        "HOUSE_COMMISSION_PERCENT": config.HOUSE_COMMISSION_PERCENT,
        "MIN_DEPOSIT": config.MIN_DEPOSIT,
        "MIN_WITHDRAWAL": config.MIN_WITHDRAWAL,
        "MIN_TRANSFER": config.MIN_TRANSFER,
        "TRANSFER_COOLDOWN_SECONDS": config.TRANSFER_COOLDOWN_SECONDS,
        "REFERRAL_BONUS": config.REFERRAL_BONUS,
        "SIGNUP_BONUS": config.SIGNUP_BONUS,
        "JACKPOT_ROOM_FEE": config.JACKPOT_ROOM_FEE,
        "JACKPOT_TRIGGER_AMOUNT": config.JACKPOT_TRIGGER_AMOUNT,
    }
    return {"ok": True, "config": safe}


# =====================================================================
# HEALTH CHECK
# Free hosts (Render/Railway) ping a root or /health path to know the
# service is alive - without this many free tiers will mark the
# service unhealthy and cycle/sleep it. Declared BEFORE the static
# mount below for unambiguous route precedence.
# =====================================================================

@app.get("/health")
def health():
    return {"status": "ok"}


# =====================================================================
# STATIC FILE SERVING (the built React Mini App)
#
# One-host deployment: this SAME FastAPI server serves both the JSON
# API under /api/* AND the built frontend (miniapp/dist/ after running
# `npm run build`) at the root. Telegram's Mini App button points at
# this server's root URL, so "/" must return the app's index.html, not
# a JSON response.
#
# StaticFiles with html=True serves index.html for unmatched paths too
# (needed because this is a client-side-routed SPA conceptually, even
# though the current app uses in-memory view state rather than a
# router - if that ever changes to use react-router with real URLs,
# this fallback is what makes refreshing a deep link work).
# =====================================================================

from fastapi.staticfiles import StaticFiles
import pathlib

# Pre-generated Amharic number announcements, served for the Mini App to
# play when a ball is called. Mounted BEFORE the SPA root so /audio/* wins.
_AUDIO_DIR = pathlib.Path(__file__).parent / config.AUDIO_DIR
if _AUDIO_DIR.exists():
    app.mount("/audio", StaticFiles(directory=str(_AUDIO_DIR)), name="audio")

_DIST_DIR = pathlib.Path(__file__).parent.parent / "miniapp" / "dist"

if _DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_DIST_DIR), html=True), name="miniapp")
else:
    @app.get("/")
    def root_not_built():
        return {
            "status": "ok",
            "service": "habesha-bet-api",
            "note": f"Looked in {_DIST_DIR} but it was not found. Run `npm run build` inside miniapp/ to build the frontend.",
        }


if __name__ == "__main__":
    if getattr(config, "PRODUCTION", False):
        _backup_thread = threading.Thread(target=_schedule_backups, daemon=True)
        _backup_thread.start()
    import uvicorn
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
