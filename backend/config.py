# config.py
# ============================================
# HABESHA BET - MULTIPLAYER BINGO BOT CONFIG
# Fill in the values marked "FILL IN" before running.
# ============================================


import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


# ---------- TELEGRAM CORE ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "787372880").split(",") if x.strip()]

# ---------- TELEGRAM CHAT ID FORMAT ----------
# Private user chats use the numeric user ID (e.g. 787372880).
# Groups and channels use the -100-prefixed numeric ID (e.g. -1001234567890).
ADMIN_NOTIFICATION_CHAT_IDS = os.getenv("ADMIN_NOTIFICATION_CHAT_IDS", "")
# If empty, alerts fall back to ADMIN_IDS.
BOT_USERNAME = os.getenv("BOT_USERNAME", "Vscoodebot")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "your_support_username")

# ---------- ERROR MONITORING ----------
# Optional. Leave unset and error tracking simply doesn't activate — nothing
# else in the app depends on this being configured. Create a free project at
# sentry.io, paste its DSN here (or set the SENTRY_DSN env var) to get
# searchable errors with stack traces instead of just log lines.
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
GROUP_LINK = os.getenv("GROUP_LINK", "https://t.me/your_group")
# For Telegram supergroups/channels, this must be the numeric chat ID
# with the -100 prefix (e.g. -1001234567890). To find it:
#   1. Add your bot to the group/channel as admin
#   2. Forward a message from the group to @getidsbot or use
#      https://api.telegram.org/bot<TOKEN>/getUpdates in a browser
#      while posting in the group.
#   3. The bot must be an admin with permission to send messages.
# In .env use the raw striped numeric ID, e.g.:
#   GROUP_CHAT_ID=-1001234567890
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID", "").strip().strip('"').strip("'")
BROADCAST_ENABLED = os.getenv("BROADCAST_ENABLED", "false").lower() == "true"

# ---------- MINI APP ----------
# Public HTTPS URL where the React Mini App is hosted (e.g. Render/Vercel
# static site URL). Telegram REQUIRES https - http:// and localhost URLs
# will be rejected when setting the menu button or opening a WebApp.
# Leave as None to disable the Mini App button entirely and fall back to
# the original chat-only menu (useful for local testing before the
# frontend is deployed).
MINI_APP_URL = os.getenv("MINI_APP_URL", "https://chilly-glasses-fold.loca.lt")

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

DB_PATH = os.getenv("DB_PATH", "habesha_bet.db")
DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL:
    use_postgres = True
elif DB_PATH.startswith(("postgres://", "postgresql://")):
    use_postgres = True
    DATABASE_URL = DB_PATH
else:
    use_postgres = False

DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "am")

# ============================================
# TELEBIRR RECEIPT ONLINE VERIFICATION
# ============================================
TELEBIRR_VERIFY_ENABLED = os.getenv("TELEBIRR_VERIFY_ENABLED", "true").lower() == "true"
TELEBIRR_VERIFY_TIMEOUT = int(os.getenv("TELEBIRR_VERIFY_TIMEOUT", "10"))

# ============================================
# BINGO ROOMS
# ============================================
# 4 permanent rooms, always available.
ROOM_FEES = [10, 20, 50, 100]   # ETB entry fee per card

CARD_POOL_SIZE = 200             # cards per room
MAX_CARDS_PER_PLAYER = 5         # max cards a single player can buy in one room

MIN_CARDS_TO_START = 2           # minimum cards sold before a game can start
COUNTDOWN_SECONDS = 30           # lobby countdown before game starts

CALL_DELAY_SECONDS = 4           # seconds between number calls
MAX_NUMBERS_CALLED = 75          # call all 75 balls maximum

# ---------- PRIZE SPLIT ----------
HOUSE_COMMISSION_PERCENT = 20    # house keeps 20% of the pool
# Remaining 80% is split equally among all winners of that round

# ---------- WIN TYPES ----------
# Only "line" (row/column/diagonal) and "corners" count as valid wins.
# Full House is intentionally NOT a separate win condition.
ENABLE_LINE_WIN = True
ENABLE_CORNERS_WIN = True
ENABLE_FULL_HOUSE_WIN = False

# ============================================
# DEPOSITS (TELEBIRR)
# ============================================
# Multiple Telebirr accounts can be configured; the active account
# rotates automatically after ROTATE_AFTER_DEPOSITS successful deposits.
# Accounts themselves are stored in the database (deposit_accounts table)
# so the admin can add/remove them live via /admin without redeploying.
ROTATE_AFTER_DEPOSITS = 20

MIN_DEPOSIT = 20      # ETB
DEPOSIT_QUICK_AMOUNTS = [50, 100, 200, 500, 1000]   # quick-select buttons; "Custom" always also offered

# ============================================
# WITHDRAWALS
# ============================================
MIN_WITHDRAWAL = 30   # ETB

# ============================================
# TRANSFERS (user to user)
# ============================================
MIN_TRANSFER = 10                # ETB
TRANSFER_COOLDOWN_SECONDS = 3600  # 1 hour between transfers per user

# ============================================
# REFERRAL & BONUS SETTINGS
# ============================================
REFERRAL_BONUS = 10          # ETB to referrer when their friend makes a first deposit
SIGNUP_BONUS = 5             # ETB to a new user who joined via a referral link
DAILY_BONUS_AMOUNT = 5       # ETB (legacy, kept for backward compat)
DAILY_BONUS_COOLDOWN_HOURS = 24
DAILY_STREAK_BONUSES = {1: 5, 2: 10, 3: 15, 5: 25, 7: 50, 14: 100, 30: 250}
JACKPOT_ROOM_FEE = 10
JACKPOT_TRIGGER_AMOUNT = 1000
JACKPOT_CONTRIBUTION_PERCENT = 2

# ============================================
# AUDIO (Amharic voice announcements)
# ============================================
# If a file named "{number}.mp3" exists in AUDIO_DIR (e.g. "12.mp3"),
# it speaks the column letter + Amharic number name (e.g. "B አንድ")
# when that ball is called, both in the Mini App and as a bot voice note.
# Generate them with backend/generate_audio.py (gTTS, lang='am').
# English audio is intentionally NOT supported - Amharic only.
AUDIO_DIR = "audio"
ENABLE_VOICE_ANNOUNCEMENTS = True

# ============================================
# HOUSE WALLET
# ============================================
# House commission is tracked in its own dedicated `house_wallet` table
# (balance = withdrawable now, total_earned = cumulative all-time).
# This ID is unused by the table design but kept reserved in case a
# pseudo-user representation is ever needed elsewhere.
HOUSE_ACCOUNT_ID = 0


# ============================================
# DATABASE BACKUP
# ============================================
BACKUP_INTERVAL_MINUTES = int(os.getenv("BACKUP_INTERVAL_MINUTES", "30"))
MAX_BACKUPS = int(os.getenv("MAX_BACKUPS", "50"))
PRODUCTION = os.getenv("PRODUCTION", "false").lower() == "true"


# ============================================
# MASKING (for "last buyer" display, winner display, etc.)
# ============================================
# e.g. "@fUCijZmjgEq" -> "@fUC***" or "Abdi Mohammed" -> "@Ab8***"
MASK_VISIBLE_CHARS = 3

