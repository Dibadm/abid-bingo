# database.py
# ============================================
# HABESHA BET - DATABASE LAYER
# PostgreSQL via psycopg2, RealDictCursor throughout.
#
# Tables:
#   users            - accounts, balances, phone, language, referrals
#   transactions     - full ledger of every balance change
#   withdrawals      - pending/approved/rejected withdrawal requests
#   deposit_accounts - rotating Telebirr accounts for deposits
#   games            - one row per bingo round (per room)
#   game_players     - players in a game + their auto-win toggle
#   game_cards       - cards sold in a game (ownership + manual marks)
#   game_numbers     - the sequence of called numbers per game
#
# Concurrency notes:
#   - Card purchases use a UNIQUE index on (game_id, card_index) so two
#     players can NEVER buy the same card - the second INSERT fails with
#     IntegrityError and the whole purchase is rolled back.
#   - Transfers use a conditional UPDATE (WHERE balance >= amount) so a
#     user can never go negative even under concurrent requests.
#   - Deposit reference numbers are UNIQUE so the same Telebirr SMS can
#     never be credited twice.
# ============================================

import psycopg2
from psycopg2 import pool, extras, errors
import json
import logging
import os
import shutil
from datetime import datetime, timedelta
from threading import Lock

import config

logger = logging.getLogger("habesha_bet")

_backup_lock = Lock()
_last_backup_ts = None
_db_pool = None
_init_db_lock = Lock()


def get_connection():
    global _db_pool
    if _db_pool is None:
        with _init_db_lock:
            if _db_pool is None:
                db_url = getattr(config, "DATABASE_URL", "") or os.getenv("DATABASE_URL")
                if not db_url:
                    raise RuntimeError(
                        "DATABASE_URL is required for PostgreSQL. "
                        "Set it in your environment/config."
                    )
                _db_pool = pool.ThreadedConnectionPool(
                    minconn=5, maxconn=20, dsn=db_url,
                    connect_timeout=10,
                )
    conn = _db_pool.getconn()
    try:
        conn.rollback()
    except Exception:
        pass
    conn.autocommit = False
    return conn


def release_connection(conn):
    global _db_pool
    if _db_pool is not None and conn is not None:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            _db_pool.putconn(conn)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass


def init_db():
    """Create all tables and indexes if they don't exist. Safe to call every startup."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    try:
        _init_tables(cur)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        release_connection(conn)
    init_house_wallet()


def backup_database():
    """PostgreSQL no-op: managed backups on Render."""
    return


def _init_tables(cur):
    try:
        _init_tables_impl(cur)
    except Exception:
        logger.exception("[database] _init_tables failed")
        raise


def _init_tables_impl(cur):

    # ---------------- USERS ----------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            phone TEXT,
            balance NUMERIC(12,2) NOT NULL DEFAULT 0,
            bonus_balance NUMERIC(12,2) NOT NULL DEFAULT 0,
            language TEXT NOT NULL DEFAULT 'am',
            referred_by BIGINT,
            referral_bonus_given INTEGER NOT NULL DEFAULT 0,
            last_bonus_claim TEXT,
            last_transfer_time TEXT,
            created_at TEXT NOT NULL,
            chat_id BIGINT
        )
    """)

    # ---- Migration for chat_id ----
    cur.execute("SAVEPOINT sp_chat_id")
    try:
        cur.execute("ALTER TABLE users ADD COLUMN chat_id INTEGER")
    except errors.DuplicateColumn:
        cur.execute("ROLLBACK TO SAVEPOINT sp_chat_id")

    # ---- Migration for bonus_balance ----
    cur.execute("SAVEPOINT sp_bonus_balance")
    try:
        cur.execute("ALTER TABLE users ADD COLUMN bonus_balance NUMERIC(12,2) NOT NULL DEFAULT 0")
    except errors.DuplicateColumn:
        cur.execute("ROLLBACK TO SAVEPOINT sp_bonus_balance")

    # ---- Migration for language ----
    cur.execute("SAVEPOINT sp_language")
    try:
        cur.execute("ALTER TABLE users ADD COLUMN language TEXT NOT NULL DEFAULT 'am'")
    except errors.DuplicateColumn:
        cur.execute("ROLLBACK TO SAVEPOINT sp_language")

    # ---- Migration for referred_by ----
    cur.execute("SAVEPOINT sp_referred_by")
    try:
        cur.execute("ALTER TABLE users ALTER COLUMN referred_by TYPE BIGINT")
    except errors.DuplicateColumn:
        cur.execute("ROLLBACK TO SAVEPOINT sp_referred_by")

    # ---- Migration for referral_bonus_given ----
    cur.execute("SAVEPOINT sp_referral_bonus_given")
    try:
        cur.execute("ALTER TABLE users ADD COLUMN referral_bonus_given INTEGER NOT NULL DEFAULT 0")
    except errors.DuplicateColumn:
        cur.execute("ROLLBACK TO SAVEPOINT sp_referral_bonus_given")

    # ---- Migration for last_bonus_claim ----
    cur.execute("SAVEPOINT sp_last_bonus_claim")
    try:
        cur.execute("ALTER TABLE users ADD COLUMN last_bonus_claim TEXT")
    except errors.DuplicateColumn:
        cur.execute("ROLLBACK TO SAVEPOINT sp_last_bonus_claim")

    # ---- Migration for last_transfer_time ----
    cur.execute("SAVEPOINT sp_last_transfer_time")
    try:
        cur.execute("ALTER TABLE users ADD COLUMN last_transfer_time TEXT")
    except errors.DuplicateColumn:
        cur.execute("ROLLBACK TO SAVEPOINT sp_last_transfer_time")

    # ---------------- TRANSACTIONS (full ledger) ----------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            type TEXT NOT NULL,
            -- types: deposit, withdraw, withdraw_refund, transfer_in, transfer_out,
            --        bingo_bet, bingo_win, bingo_refund,
            --        referral_bonus, signup_bonus, daily_bonus,
            --        house_commission
            amount NUMERIC(12,2) NOT NULL,
            reference TEXT,
            status TEXT NOT NULL,   -- completed, pending, rejected
            created_at TEXT NOT NULL,
            receipt_no TEXT,
            verification_status TEXT,   -- pending, verified, failed
            verification_raw TEXT
        )
    """)
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_reference
        ON transactions(reference)
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions(user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_type ON transactions(type)")

    # ---------------- WITHDRAWALS ----------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            amount NUMERIC(12,2) NOT NULL,
            phone TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_withdrawals_status ON withdrawals(status)")

    # ---------------- PENDING BROADCASTS ----------------
    # The API process can resolve a game instantly (a manual claim), but
    # only the bot process has a live Telegram connection to actually
    # announce it. This is the handoff: the API queues the announcement
    # text here, and the bot's lifecycle loop drains and sends it on its
    # next check.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pending_broadcasts (
            id SERIAL PRIMARY KEY,
            game_id BIGINT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pending_broadcasts_game ON pending_broadcasts(game_id)")

    # ---------------- ADMIN AUDIT LOG ----------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_audit_log (
            id SERIAL PRIMARY KEY,
            admin_id BIGINT NOT NULL,
            action TEXT NOT NULL,
            target_id BIGINT,
            details TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # ---------------- DEPOSIT ACCOUNTS (rotating Telebirr numbers) ----------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS deposit_accounts (
            id SERIAL PRIMARY KEY,
            phone TEXT NOT NULL,
            recipient_name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 0,
            deposit_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    # ---------------- GAMES ----------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id SERIAL PRIMARY KEY,
            room_fee NUMERIC(12,2) NOT NULL,
            state TEXT NOT NULL DEFAULT 'waiting',  -- waiting, running, finished
            pool NUMERIC(12,2) NOT NULL DEFAULT 0,
            house_cut NUMERIC(12,2),
            winner_ids TEXT,           -- JSON list of user_ids, set when finished
            winner_cards TEXT,          -- JSON map user_id -> [winning card_index,...]
            per_winner_amount NUMERIC(12,2),
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            countdown_started_at TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_games_room_state ON games(room_fee, state)")
    cur.execute("SAVEPOINT sp_games_countdown")
    try:
        cur.execute("ALTER TABLE games ADD COLUMN countdown_started_at TEXT")
    except errors.DuplicateColumn:
        cur.execute("ROLLBACK TO SAVEPOINT sp_games_countdown")
    cur.execute("SAVEPOINT sp_games_winner_cards")
    try:
        cur.execute("ALTER TABLE games ADD COLUMN winner_cards TEXT")
    except errors.DuplicateColumn:
        cur.execute("ROLLBACK TO SAVEPOINT sp_games_winner_cards")

    # ---------------- MANUAL BINGO CLAIMS ----------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS manual_bingo_claims (
            id SERIAL PRIMARY KEY,
            game_id INTEGER NOT NULL,
            user_id BIGINT NOT NULL,
            card_indices TEXT NOT NULL,
            created_at TEXT NOT NULL,
            resolved INTEGER NOT NULL DEFAULT 0
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_manual_claims_game ON manual_bingo_claims(game_id, resolved)")

    # ---------------- GAME PLAYERS ----------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS game_players (
            id SERIAL PRIMARY KEY,
            game_id INTEGER NOT NULL,
            user_id BIGINT NOT NULL,
            cards_count INTEGER NOT NULL DEFAULT 0,
            auto_win INTEGER NOT NULL DEFAULT 0,
            chat_id BIGINT,
            message_id INTEGER,
            created_at TEXT NOT NULL,
            UNIQUE(game_id, user_id)
        )
    """)

    # ---------------- GAME CARDS ----------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS game_cards (
            id SERIAL PRIMARY KEY,
            game_id INTEGER NOT NULL,
            card_index INTEGER NOT NULL,   -- 0-199, position in the 200-card pool
            owner_id BIGINT NOT NULL,
            marked_numbers TEXT NOT NULL DEFAULT '[]',  -- JSON list, manual tap-to-highlight
            created_at TEXT NOT NULL,
            UNIQUE(game_id, card_index)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_game ON game_cards(game_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_owner ON game_cards(game_id, owner_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_owner_only ON game_cards(owner_id)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_cards_game_card ON game_cards(game_id, card_index)")

    # ---------------- GAME NUMBERS (call sequence) ----------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS game_numbers (
            id SERIAL PRIMARY KEY,
            game_id INTEGER NOT NULL,
            call_order INTEGER NOT NULL,   -- 1, 2, 3 ... up to 75
            number INTEGER NOT NULL,       -- the ball number 1-75
            called_at TEXT NOT NULL,
            UNIQUE(game_id, call_order),
            UNIQUE(game_id, number)
        )
    """)

    # ---------------- JACKPOT ----------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS jackpot (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
            room_fee INTEGER NOT NULL,
            triggered INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
    """)

    # ---- Migration for older DBs (safe to run every time) ----
    for column, col_def in [
        ("phone", "TEXT"),
        ("language", "TEXT NOT NULL DEFAULT 'am'"),
        ("referred_by", "BIGINT"),
        ("referral_bonus_given", "INTEGER NOT NULL DEFAULT 0"),
        ("last_bonus_claim", "TEXT"),
        ("last_transfer_time", "TEXT"),
        ("bonus_balance", "NUMERIC(12,2) NOT NULL DEFAULT 0"),
        ("daily_streak", "INTEGER NOT NULL DEFAULT 0"),
        ("last_bonus_claim_date", "TEXT"),
        ("chat_id", "BIGINT"),
        ("onboarding_seen", "INTEGER NOT NULL DEFAULT 0"),
    ]:
        cur.execute(f"SAVEPOINT sp_users_{column}")
        try:
            cur.execute(f"ALTER TABLE users ADD COLUMN {column} {col_def}")
        except errors.DuplicateColumn:
            cur.execute(f"ROLLBACK TO SAVEPOINT sp_users_{column}")

    # ---- Migration for chat_id ----
    cur.execute("SAVEPOINT sp_users_chat_id")
    try:
        cur.execute("ALTER TABLE users ADD COLUMN chat_id BIGINT")
    except errors.DuplicateColumn:
        cur.execute("ROLLBACK TO SAVEPOINT sp_users_chat_id")

    # ---- Migrate existing integer ID columns to BIGINT for Telegram IDs ----
    for column in ["user_id", "referred_by", "chat_id"]:
        cur.execute(f"SAVEPOINT sp_type_{column}")
        try:
            cur.execute(f"ALTER TABLE users ALTER COLUMN {column} TYPE BIGINT USING {column}::BIGINT")
        except Exception:
            cur.execute(f"ROLLBACK TO SAVEPOINT sp_type_{column}")

    # ---- Migration for receipt verification columns on transactions ----
    for column, col_def in [
        ("receipt_no", "TEXT"),
        ("verification_status", "TEXT"),
        ("verification_raw", "TEXT"),
    ]:
        cur.execute(f"SAVEPOINT sp_tx_{column}")
        try:
            cur.execute(f"ALTER TABLE transactions ADD COLUMN {column} {col_def}")
        except errors.DuplicateColumn:
            cur.execute(f"ROLLBACK TO SAVEPOINT sp_tx_{column}")

    # ---- Migrate transactions.user_id to BIGINT ----
    cur.execute("SAVEPOINT sp_tx_user_id_type")
    try:
        cur.execute("ALTER TABLE transactions ALTER COLUMN user_id TYPE BIGINT USING user_id::BIGINT")
    except Exception:
        cur.execute("ROLLBACK TO SAVEPOINT sp_tx_user_id_type")

    # ---- Migrate withdrawals.user_id to BIGINT ----
    cur.execute("SAVEPOINT sp_wd_user_id_type")
    try:
        cur.execute("ALTER TABLE withdrawals ALTER COLUMN user_id TYPE BIGINT USING user_id::BIGINT")
    except Exception:
        cur.execute("ROLLBACK TO SAVEPOINT sp_wd_user_id_type")

    # ---- Migrate admin_audit_log IDs to BIGINT ----
    for column in ["admin_id", "target_id"]:
        cur.execute(f"SAVEPOINT sp_audit_{column}_type")
        try:
            cur.execute(f"ALTER TABLE admin_audit_log ALTER COLUMN {column} TYPE BIGINT USING {column}::BIGINT")
        except Exception:
            cur.execute(f"ROLLBACK TO SAVEPOINT sp_audit_{column}_type")

    # ---- Migrate manual_bingo_claims.user_id to BIGINT ----
    cur.execute("SAVEPOINT sp_mbc_user_id_type")
    try:
        cur.execute("ALTER TABLE manual_bingo_claims ALTER COLUMN user_id TYPE BIGINT USING user_id::BIGINT")
    except Exception:
        cur.execute("ROLLBACK TO SAVEPOINT sp_mbc_user_id_type")

    # ---- Migrate game_players IDs to BIGINT ----
    for column in ["user_id", "chat_id"]:
        cur.execute(f"SAVEPOINT sp_gp_{column}_type")
        try:
            cur.execute(f"ALTER TABLE game_players ALTER COLUMN {column} TYPE BIGINT USING {column}::BIGINT")
        except Exception:
            cur.execute(f"ROLLBACK TO SAVEPOINT sp_gp_{column}_type")

    # ---- Migrate game_cards.owner_id to BIGINT ----
    cur.execute("SAVEPOINT sp_gc_owner_type")
    try:
        cur.execute("ALTER TABLE game_cards ALTER COLUMN owner_id TYPE BIGINT USING owner_id::BIGINT")
    except Exception:
        cur.execute("ROLLBACK TO SAVEPOINT sp_gc_owner_type")


# =====================================================================
# USERS
# =====================================================================

def find_user_by_username(username: str):
    """Case-insensitive lookup by username (without leading @), used for
    the transfer flow where the sender types the recipient's @handle.
    Returns the most recently created matching user if somehow more than
    one row shares a username (e.g. stale data from a username change)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM users WHERE LOWER(username) = LOWER(%s) ORDER BY created_at DESC LIMIT 1",
        (username,)
    )
    row = cur.fetchone()
    release_connection(conn)
    return row


def get_or_create_user(user_id: int, username: str, referred_by: int = None):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()

    if user is None:
        cur.execute(
            "INSERT INTO users (user_id, username, balance, language, referred_by, created_at) "
            "VALUES (%s, %s, 0, %s, %s, %s)",
            (user_id, username, config.DEFAULT_LANGUAGE, referred_by, datetime.utcnow().isoformat())
        )
        conn.commit()
        cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
    release_connection(conn)
    return user


def get_user(user_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()
    release_connection(conn)
    return user


def get_balance(user_id: int) -> float:
    user = get_user(user_id)
    return float(user["balance"]) if user else 0.0


def get_bonus_balance(user_id: int) -> float:
    user = get_user(user_id)
    if not user:
        return 0.0
    try:
        return float(user["bonus_balance"])
    except (KeyError, IndexError):
        return 0.0


def deduct_balance(user_id: int, amount: float) -> tuple:
    """Atomically deduct from balance if sufficient funds exist.
    Returns (success: bool, new_balance: float)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "UPDATE users SET balance = balance - %s WHERE user_id = %s AND balance >= %s",
        (amount, user_id, amount)
    )
    success = cur.rowcount > 0
    if success:
        conn.commit()
        cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
        new_balance = float(cur.fetchone()["balance"])
    else:
        try:
            conn.rollback()
        except Exception:
            pass
        user = get_user(user_id)
        new_balance = float(user["balance"]) if user else 0.0
    release_connection(conn)
    return success, new_balance


def adjust_balance(user_id: int, amount: float) -> float:
    """Add (or subtract, if negative) to a user's balance. Returns new balance.
    WARNING: this version does NOT guard against negative balances.
    For withdrawals, use deduct_balance() instead."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, user_id))
    conn.commit()
    cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
    new_balance = cur.fetchone()["balance"]
    release_connection(conn)
    return float(new_balance)


def add_bonus_balance(user_id: int, amount: float):
    """Add to a user's lifetime bonus balance (referrals, daily/signup
    bonuses). Kept separate from `balance` so the UI can show how much a
    player has earned from bonuses vs. deposited/won funds."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("UPDATE users SET bonus_balance = bonus_balance + %s WHERE user_id = %s", (amount, user_id))
    conn.commit()
    release_connection(conn)


def subtract_bonus_balance(user_id: int, amount: float) -> bool:
    """Atomically deduct from bonus_balance. Returns True if successful."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "UPDATE users SET bonus_balance = bonus_balance - %s WHERE user_id = %s AND bonus_balance >= %s",
        (amount, user_id, amount)
    )
    success = cur.rowcount > 0
    if success:
        conn.commit()
    release_connection(conn)
    return success


def spend_funds(user_id: int, amount: float, conn=None, cur=None) -> tuple:
    """Spend bonus_balance first, then balance. Atomic within caller
    transaction when conn/cur are provided. Returns (success, reason)."""
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=extras.RealDictCursor)

    cur.execute(
        "UPDATE users SET bonus_balance = bonus_balance - %s WHERE user_id = %s AND bonus_balance >= %s",
        (amount, user_id, amount)
    )
    if cur.rowcount > 0:
        if owns_conn:
            conn.commit()
            release_connection(conn)
        return True, "ok"

    cur.execute(
        "UPDATE users SET balance = balance - %s WHERE user_id = %s AND balance >= %s",
        (amount, user_id, amount)
    )
    if cur.rowcount > 0:
        if owns_conn:
            conn.commit()
            release_connection(conn)
        return True, "ok"

    if owns_conn:
        release_connection(conn)
    return False, "insufficient_funds"


def set_user_phone(user_id: int, phone: str):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("UPDATE users SET phone = %s WHERE user_id = %s", (phone, user_id))
    conn.commit()
    release_connection(conn)


def set_user_language(user_id: int, lang: str):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("UPDATE users SET language = %s WHERE user_id = %s", (lang, user_id))
    conn.commit()
    release_connection(conn)


def mark_onboarding_seen(user_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("UPDATE users SET onboarding_seen = 1 WHERE user_id = %s", (user_id,))
    conn.commit()
    release_connection(conn)


def update_user_chat_id(user_id: int, chat_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("UPDATE users SET chat_id = %s WHERE user_id = %s", (chat_id, user_id))
    conn.commit()
    release_connection(conn)


def get_all_user_ids() -> list:
    """For broadcast - returns all registered user_ids."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT user_id FROM users")
    rows = cur.fetchall()
    release_connection(conn)
    return [r["user_id"] for r in rows]


def count_users() -> int:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT COUNT(*) as c FROM users")
    row = cur.fetchone()
    release_connection(conn)
    return row["c"]


# =====================================================================
# TRANSACTIONS / LEDGER
# =====================================================================

def record_transaction(user_id: int, tx_type: str, amount: float, reference: str = None, status: str = "completed", receipt_no: str = None, verification_status: str = None, verification_raw: str = None):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "INSERT INTO transactions (user_id, type, amount, reference, status, created_at, receipt_no, verification_status, verification_raw) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (user_id, tx_type, amount, reference, status, datetime.utcnow().isoformat(), receipt_no, verification_status, verification_raw)
    )
    conn.commit()
    release_connection(conn)


def reference_already_used(reference: str) -> bool:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT 1 FROM transactions WHERE reference = %s", (reference,))
    row = cur.fetchone()
    release_connection(conn)
    return row is not None


def deposit_funds(user_id: int, amount: float, reference: str = None, receipt_no: str = None, verification_status: str = None, verification_raw: str = None) -> tuple:
    """Atomically credit a user's balance and record the deposit transaction.
    Returns (success: bool, new_balance: float, error: str | None).
    This is a single-connection operation so it cannot be half-applied."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    try:
        if reference:
            cur.execute("SELECT 1 FROM transactions WHERE reference = %s", (reference,))
            if cur.fetchone():
                cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
                return False, float(row["balance"]) if row else 0.0, "already_used"

        cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, user_id))
        cur.execute(
            "INSERT INTO transactions (user_id, type, amount, reference, status, created_at, receipt_no, verification_status, verification_raw) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (user_id, "deposit", amount, reference, "completed", datetime.utcnow().isoformat(), receipt_no, verification_status, verification_raw)
        )
        cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
        new_balance = float(cur.fetchone()["balance"])
        conn.commit()
        return True, new_balance, None
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        release_connection(conn)


def get_user_transactions(user_id: int, limit: int = 10) -> list:
    """Most recent transactions for this user, newest first - used for
    the '/Transactions' menu screen."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM transactions WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
        (user_id, limit)
    )
    rows = cur.fetchall()
    release_connection(conn)
    return rows


def count_deposits(user_id: int) -> int:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "SELECT COUNT(*) as c FROM transactions WHERE user_id = %s AND type = 'deposit' AND status = 'completed'",
        (user_id,)
    )
    row = cur.fetchone()
    release_connection(conn)
    return row["c"] if row else 0


def get_total_collected() -> float:
    """Sum of all completed deposits - for admin dashboard."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT COALESCE(SUM(amount),0) as total FROM transactions WHERE type='deposit' AND status='completed'")
    row = cur.fetchone()
    release_connection(conn)
    return float(row["total"])


def get_net_profit() -> float:
    """Sum of all house_commission transactions - for admin dashboard."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT COALESCE(SUM(amount),0) as total FROM transactions WHERE type='house_commission'")
    row = cur.fetchone()
    release_connection(conn)
    return float(row["total"])


def get_peak_hours() -> list:
    """Returns [(hour_0_23, count), ...] based on bingo_bet transactions (UTC hour)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("""
        SELECT EXTRACT(HOUR FROM created_at)::INTEGER as hour, COUNT(*) as count
        FROM transactions
        WHERE type = 'bingo_bet'
        GROUP BY hour
        ORDER BY hour
    """)
    rows = cur.fetchall()
    release_connection(conn)
    return [(r["hour"], r["count"]) for r in rows]


# =====================================================================
# REFERRALS & BONUSES
# =====================================================================

def count_referrals(user_id: int) -> int:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT COUNT(*) as c FROM users WHERE referred_by = %s", (user_id,))
    row = cur.fetchone()
    release_connection(conn)
    return row["c"] if row else 0


def mark_referral_bonus_given(user_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("UPDATE users SET referral_bonus_given = 1 WHERE user_id = %s", (user_id,))
    conn.commit()
    release_connection(conn)


def can_claim_daily_streak_bonus(user_id: int):
    """Returns (can_claim: bool, streak_days: int, next_bonus_amount: float)."""
    user = get_user(user_id)
    today = datetime.utcnow().date().isoformat()

    if user is None or user["last_bonus_claim_date"] is None:
        return True, 1, config.DAILY_STREAK_BONUSES[1]

    last_date = user["last_bonus_claim_date"]
    last = datetime.fromisoformat(last_date).date()
    now = datetime.utcnow().date()
    delta = (now - last).days

    if delta == 0:
        return False, user["daily_streak"], 0.0

    current_streak = user["daily_streak"]
    if delta == 1:
        current_streak += 1
    else:
        current_streak = 1

    bonus = config.DAILY_STREAK_BONUSES.get(current_streak, config.DAILY_BONUS_AMOUNT)
    return True, current_streak, bonus


def set_daily_streak_bonus_claimed(user_id: int, streak: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "UPDATE users SET last_bonus_claim_date = %s, daily_streak = %s WHERE user_id = %s",
        (datetime.utcnow().date().isoformat(), streak, user_id),
    )
    conn.commit()
    release_connection(conn)


def get_daily_streak(user_id: int) -> int:
    user = get_user(user_id)
    if user is None:
        return 0
    return user["daily_streak"]


# =====================================================================
# TRANSFERS (user to user, atomic with cooldown)
# =====================================================================

def can_transfer(user_id: int):
    """Returns (can_transfer: bool, seconds_remaining: int)."""
    user = get_user(user_id)
    if user is None or user["last_transfer_time"] is None:
        return True, 0

    last = datetime.fromisoformat(user["last_transfer_time"])
    cooldown = timedelta(seconds=config.TRANSFER_COOLDOWN_SECONDS)
    elapsed = datetime.utcnow() - last

    if elapsed >= cooldown:
        return True, 0

    remaining = cooldown - elapsed
    return False, int(remaining.total_seconds())


def transfer_funds(from_id: int, to_id: int, amount: float):
    """Atomically move funds between two users.
    Returns (success: bool, reason: str)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)

    cur.execute("BEGIN")

    # Conditional debit - bonus first, prevents negative balances even under concurrent requests.
    success, reason = spend_funds(from_id, amount, conn=conn, cur=cur)
    if not success:
        conn.rollback()
        release_connection(conn)
        return False, reason

    cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, to_id))
    cur.execute(
        "UPDATE users SET last_transfer_time = %s WHERE user_id = %s",
        (datetime.utcnow().isoformat(), from_id)
    )
    conn.commit()

    record_transaction(from_id, "transfer_out", -amount, status="completed")
    record_transaction(to_id, "transfer_in", amount, status="completed")
    release_connection(conn)
    return True, "ok"


# =====================================================================
# WITHDRAWALS
# =====================================================================

def create_withdrawal(user_id: int, amount: float, phone: str) -> int:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "INSERT INTO withdrawals (user_id, amount, phone, status, created_at) VALUES (%s, %s, %s, 'pending', %s)",
        (user_id, amount, phone, datetime.utcnow().isoformat())
    )
    conn.commit()
    withdrawal_id = cur.lastrowid
    release_connection(conn)
    return withdrawal_id


def get_withdrawal(withdrawal_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT * FROM withdrawals WHERE id = %s", (withdrawal_id,))
    row = cur.fetchone()
    release_connection(conn)
    return row


def get_pending_withdrawals() -> list:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT * FROM withdrawals WHERE status = 'pending' ORDER BY created_at ASC")
    rows = cur.fetchall()
    release_connection(conn)
    return rows


def update_withdrawal_status(withdrawal_id: int, status: str):
    """Update status only if currently pending. Returns True if updated."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("UPDATE withdrawals SET status = %s WHERE id = %s AND status = 'pending'", (status, withdrawal_id))
    success = cur.rowcount > 0
    conn.commit()
    release_connection(conn)
    return success


# =====================================================================
# DEPOSIT ACCOUNTS (rotating Telebirr numbers)
# =====================================================================

def add_deposit_account(phone: str, recipient_name: str) -> int:
    """Add a new deposit account. If it's the first account, make it active."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT COUNT(*) as c FROM deposit_accounts")
    is_first = cur.fetchone()["c"] == 0

    cur.execute(
        "INSERT INTO deposit_accounts (phone, recipient_name, active, deposit_count, created_at) VALUES (%s, %s, %s, 0, %s)",
        (phone, recipient_name, 1 if is_first else 0, datetime.utcnow().isoformat())
    )
    conn.commit()
    account_id = cur.lastrowid
    release_connection(conn)
    return account_id


def remove_deposit_account(account_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)

    cur.execute("SELECT active FROM deposit_accounts WHERE id = %s", (account_id,))
    row = cur.fetchone()
    was_active = row["active"] if row else 0

    cur.execute("DELETE FROM deposit_accounts WHERE id = %s", (account_id,))

    if was_active:
        # Promote another account to active, if any remain
        cur.execute("SELECT id FROM deposit_accounts ORDER BY id LIMIT 1")
        next_row = cur.fetchone()
        if next_row:
            cur.execute("UPDATE deposit_accounts SET active = 1 WHERE id = %s", (next_row["id"],))

    conn.commit()
    release_connection(conn)


def list_deposit_accounts() -> list:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT * FROM deposit_accounts ORDER BY id")
    rows = cur.fetchall()
    release_connection(conn)
    return rows


def get_active_deposit_accounts() -> list:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT * FROM deposit_accounts WHERE active = 1 ORDER BY id")
    rows = cur.fetchall()
    release_connection(conn)
    return rows


def get_active_deposit_account():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT * FROM deposit_accounts WHERE active = 1 LIMIT 1")
    row = cur.fetchone()
    release_connection(conn)
    return row


def record_deposit_for_account(account_id: int):
    """Increment the active account's deposit counter. If it reaches the
    rotation threshold, switch the active flag to the next account
    (round-robin by id) and reset this account's counter."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)

    cur.execute("UPDATE deposit_accounts SET deposit_count = deposit_count + 1 WHERE id = %s", (account_id,))
    cur.execute("SELECT deposit_count FROM deposit_accounts WHERE id = %s", (account_id,))
    row = cur.fetchone()

    if row and row["deposit_count"] >= config.ROTATE_AFTER_DEPOSITS:
        cur.execute("SELECT id FROM deposit_accounts ORDER BY id")
        all_ids = [r["id"] for r in cur.fetchall()]

        if len(all_ids) > 1:
            current_index = all_ids.index(account_id)
            next_id = all_ids[(current_index + 1) % len(all_ids)]

            cur.execute("UPDATE deposit_accounts SET active = 0 WHERE id = %s", (account_id,))
            cur.execute("UPDATE deposit_accounts SET active = 1, deposit_count = 0 WHERE id = %s", (next_id,))
        else:
            # Only one account - just reset its counter
            cur.execute("UPDATE deposit_accounts SET deposit_count = 0 WHERE id = %s", (account_id,))

    conn.commit()
    release_connection(conn)


# =====================================================================
# GAMES
# =====================================================================

def is_game_stuck(game_id: int) -> tuple:
    """Return (stuck, reason_string) if a game has been in waiting/running
    longer than the maximum possible round duration."""
    game = get_game(game_id)
    if not game or game["state"] not in ("waiting", "running"):
        return False, "not_active"

    now = datetime.utcnow()

    if game["state"] == "waiting":
        if not game["countdown_started_at"]:
            return False, "no_countdown"
        ts = datetime.fromisoformat(game["countdown_started_at"])
        max_duration = config.COUNTDOWN_SECONDS + 60
    else:
        if game["countdown_started_at"]:
            ts = datetime.fromisoformat(game["countdown_started_at"])
            max_duration = (
                config.COUNTDOWN_SECONDS
                + config.MAX_NUMBERS_CALLED * config.CALL_DELAY_SECONDS
                + 60
            )
        elif game["started_at"]:
            ts = datetime.fromisoformat(game["started_at"])
            max_duration = config.MAX_NUMBERS_CALLED * config.CALL_DELAY_SECONDS + 60
        else:
            return False, "no_timestamp"

    try:
        elapsed = (now - ts).total_seconds()
        if elapsed > max_duration:
            return True, f"elapsed={int(elapsed)}s max={max_duration}s state={game['state']}"
    except Exception:
        pass
    return False, ""


def get_or_create_active_game(room_fee: float):
    """Get the current waiting/running game for this room fee,
    or create a fresh 'waiting' game if none exists."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM games WHERE room_fee = %s AND state IN ('waiting','running') ORDER BY id DESC LIMIT 1",
        (room_fee,)
    )
    game = cur.fetchone()

    if game is None:
        cur.execute(
            "INSERT INTO games (room_fee, state, pool, created_at) VALUES (%s, 'waiting', 0, %s) RETURNING id",
            (room_fee, datetime.utcnow().isoformat())
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
        cur.execute("SELECT * FROM games WHERE id = %s", (new_id,))
        game = cur.fetchone()
    release_connection(conn)
    return game


def get_game(game_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT * FROM games WHERE id = %s", (game_id,))
    row = cur.fetchone()
    release_connection(conn)
    return row


def set_game_state(game_id: int, state: str):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    if state == "running":
        cur.execute(
            "UPDATE games SET state = %s, started_at = %s WHERE id = %s",
            (state, datetime.utcnow().isoformat(), game_id)
        )
    else:
        cur.execute("UPDATE games SET state = %s WHERE id = %s", (state, game_id))
    conn.commit()
    release_connection(conn)


def finish_game(game_id: int, winner_ids: list, house_cut: float, per_winner_amount: float, winner_cards: dict = None):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "UPDATE games SET state = 'finished', winner_ids = %s, winner_cards = %s, house_cut = %s, "
        "per_winner_amount = %s, finished_at = %s WHERE id = %s",
        (json.dumps(winner_ids), json.dumps(winner_cards or {}), house_cut, per_winner_amount, datetime.utcnow().isoformat(), game_id)
    )
    conn.commit()
    release_connection(conn)


def try_claim_game_resolution(game_id: int) -> bool:
    """Atomically claim the right to resolve (finish) this game.

    Both the API process (an instant manual BINGO claim) and the bot
    process (its own auto-win detection, or a no-winner timeout) can
    reach "this game is over, pay out and finish it" independently,
    since they're separate processes in production with no shared
    in-memory state. Without a guard here, both could pay out the same
    pool at once -- the same class of bug as the withdrawal and jackpot
    races fixed earlier this session.

    Uses a single guarded UPDATE (WHERE state = 'running') exactly like
    those earlier fixes: only one caller's UPDATE can affect a row, so
    only one caller gets to proceed to resolve_game_winners. Returns
    True if this call just moved the game from 'running' to
    'resolving' (the caller now owns finishing it and MUST follow up
    with resolve_game_winners or set it back); False if someone else
    already claimed it moments ago (the caller must NOT pay out or
    finish the game itself)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "UPDATE games SET state = 'resolving' WHERE id = %s AND state = 'running'",
        (game_id,),
    )
    claimed = cur.rowcount > 0
    conn.commit()
    release_connection(conn)
    return claimed


def get_cards_for_players(game_id: int, user_ids: list) -> dict:
    """Batched version of get_player_cards for many players at once --
    one query instead of one query per player. Returns
    {user_id: [card_index, ...]}. Used by the per-call win check, which
    runs for every active game on every single number call, so N
    sequential per-player queries there scales badly as player counts
    grow."""
    if not user_ids:
        return {}
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "SELECT owner_id, card_index FROM game_cards WHERE game_id = %s AND owner_id = ANY(%s)",
        (game_id, list(user_ids)),
    )
    rows = cur.fetchall()
    release_connection(conn)
    out = {uid: [] for uid in user_ids}
    for r in rows:
        out.setdefault(r["owner_id"], []).append(r["card_index"])
    return out


def resolve_game_winners(game_id: int, winners_found: dict) -> dict:
    """Pay out winners and finalize the game.

    The caller MUST have already won try_claim_game_resolution for this
    game_id — this function does not itself guard against concurrent
    resolution; it assumes that's already been handled, so it's safe to
    call from either the API process (an instant manual claim) or the
    bot process (auto-win detection) using the exact same logic either
    way, instead of two separately-maintained payout code paths.

    Returns a dict describing what happened, for the caller to build an
    announcement from — this function never talks to Telegram itself,
    since the API process has no bot connection to do that with."""
    game = get_game(game_id)
    pool = float(game["pool"])
    house_cut = round(pool * config.HOUSE_COMMISSION_PERCENT / 100, 2)
    prize_pool = round(pool - house_cut, 2)

    winner_ids = list(winners_found.keys())
    per_winner = round(prize_pool / len(winner_ids), 2) if winner_ids else 0.0
    credit_house(house_cut)

    for uid in winner_ids:
        adjust_balance(uid, per_winner)
        record_transaction(uid, "bingo_win", per_winner, status="completed")

    winner_cards = {uid: list(winners_found[uid].keys()) for uid in winner_ids}
    finish_game(game_id, winner_ids, house_cut, per_winner, winner_cards)

    winner_lines = []
    for uid in winner_ids:
        user = get_user(uid)
        cards = get_player_cards(game_id, uid)
        win_type = list(winners_found[uid].values())[0]
        winner_lines.append({
            "user_id": uid,
            "username": user["username"] if user else None,
            "amount": per_winner,
            "card_index": cards[0] if cards else None,
            "win_type": win_type,
        })

    return {
        "winner_ids": winner_ids,
        "per_winner_amount": per_winner,
        "winner_lines": winner_lines,
    }


def queue_broadcast(game_id: int, text: str):
    """Queue a message for the bot process to send to the game's group
    chat. Used when a game is resolved by the API process (an instant
    manual claim), which has no live Telegram connection of its own."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "INSERT INTO pending_broadcasts (game_id, text, created_at) VALUES (%s, %s, %s)",
        (game_id, text, datetime.utcnow().isoformat()),
    )
    conn.commit()
    release_connection(conn)


def drain_broadcasts(game_id: int) -> list:
    """Fetch and clear any pending broadcast messages queued for this
    game, so the bot process can actually send them. Safe to call even
    when nothing is queued (returns an empty list)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT id, text FROM pending_broadcasts WHERE game_id = %s ORDER BY id ASC", (game_id,))
    rows = cur.fetchall()
    if rows:
        ids = [r["id"] for r in rows]
        cur.execute("DELETE FROM pending_broadcasts WHERE id = ANY(%s)", (ids,))
        conn.commit()
    release_connection(conn)
    return [r["text"] for r in rows]


def set_game_countdown_start(game_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "UPDATE games SET countdown_started_at = %s WHERE id = %s",
        (datetime.utcnow().isoformat(), game_id)
    )
    conn.commit()
    release_connection(conn)


def clear_game_countdown_start(game_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "UPDATE games SET countdown_started_at = NULL WHERE id = %s",
        (game_id,)
    )
    conn.commit()
    release_connection(conn)


def get_pool(game_id: int) -> float:
    game = get_game(game_id)
    return float(game["pool"]) if game else 0.0


def get_prize_pool(game_id: int) -> float:
    game = get_game(game_id)
    if not game:
        return 0.0
    pool = float(game["pool"])
    house_cut = round(pool * config.HOUSE_COMMISSION_PERCENT / 100, 2)
    return round(pool - house_cut, 2)


# =====================================================================
# GAME PLAYERS
# =====================================================================

def upsert_game_player_message(game_id: int, user_id: int, chat_id: int, message_id: int):
    """Store/update where this player's live game message lives, so the
    number-calling loop can edit it directly."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT id FROM game_players WHERE game_id = %s AND user_id = %s", (game_id, user_id))
    row = cur.fetchone()

    if row:
        cur.execute(
            "UPDATE game_players SET chat_id = %s, message_id = %s WHERE game_id = %s AND user_id = %s",
            (chat_id, message_id, game_id, user_id)
        )
    else:
        cur.execute(
            "INSERT INTO game_players (game_id, user_id, cards_count, auto_win, chat_id, message_id, created_at) "
            "VALUES (%s, %s, 0, 0, %s, %s, %s)",
            (game_id, user_id, chat_id, message_id, datetime.utcnow().isoformat())
        )
    conn.commit()
    release_connection(conn)


def get_game_player(game_id: int, user_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT * FROM game_players WHERE game_id = %s AND user_id = %s", (game_id, user_id))
    row = cur.fetchone()
    release_connection(conn)
    return row


def get_game_players(game_id: int) -> list:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT * FROM game_players WHERE game_id = %s ORDER BY id ASC", (game_id,))
    rows = cur.fetchall()
    release_connection(conn)
    return rows


def get_user_chat_id(user_id: int):
    user = get_user(user_id)
    if user and user.get("chat_id"):
        return user["chat_id"]
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT chat_id FROM game_players WHERE user_id = %s AND chat_id IS NOT NULL ORDER BY id DESC LIMIT 1", (user_id,))
    row = cur.fetchone()
    release_connection(conn)
    return row["chat_id"] if row else None


def set_auto_win(game_id: int, user_id: int, value: bool):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "UPDATE game_players SET auto_win = %s WHERE game_id = %s AND user_id = %s",
        (1 if value else 0, game_id, user_id)
    )
    conn.commit()
    release_connection(conn)


# =====================================================================
# GAME CARDS
# =====================================================================

def get_taken_cards(game_id: int) -> set:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT card_index FROM game_cards WHERE game_id = %s", (game_id,))
    rows = cur.fetchall()
    release_connection(conn)
    return {r["card_index"] for r in rows}


def get_player_cards(game_id: int, user_id: int) -> list:
    """Returns list of card_index values owned by this user in this game, ordered."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "SELECT card_index FROM game_cards WHERE game_id = %s AND owner_id = %s ORDER BY card_index ASC",
        (game_id, user_id)
    )
    rows = cur.fetchall()
    release_connection(conn)
    return [r["card_index"] for r in rows]


def get_user_active_game(user_id: int):
    """Return the most recent game the user owns cards in that is still
    joinable (waiting or running), or None if they have no live game to
    resume. Used to surface an 'Open game' / rejoin option when a player
    re-opens the Mini App after closing it mid-round."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        """
        SELECT g.* FROM games g
        JOIN game_cards c ON c.game_id = g.id
        WHERE c.owner_id = %s
          AND g.state IN ('waiting','running')
        GROUP BY g.id
        ORDER BY g.id DESC
        LIMIT 1
        """,
        (user_id,)
    )
    row = cur.fetchone()
    release_connection(conn)
    return row


def count_cards_sold(game_id: int) -> int:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT COUNT(*) as c FROM game_cards WHERE game_id = %s", (game_id,))
    row = cur.fetchone()
    release_connection(conn)
    return row["c"]


def get_all_game_cards(game_id: int) -> list:
    """Returns all cards in a game with owner info - used for refunds / payouts."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT * FROM game_cards WHERE game_id = %s", (game_id,))
    rows = cur.fetchall()
    release_connection(conn)
    return rows


def get_games_player_counts(game_ids: list) -> dict:
    """Return {game_id: player_count} for all given game_ids in one query."""
    if not game_ids:
        return {}
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    placeholders = ",".join(["%s"] * len(game_ids))
    cur.execute(f"SELECT game_id, COUNT(*) as c FROM game_players WHERE game_id IN ({placeholders}) GROUP BY game_id", game_ids)
    rows = cur.fetchall()
    release_connection(conn)
    return {r["game_id"]: r["c"] for r in rows}


def get_games_cards_sold(game_ids: list) -> dict:
    """Return {game_id: cards_sold} for all given game_ids in one query."""
    if not game_ids:
        return {}
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    placeholders = ",".join(["%s"] * len(game_ids))
    cur.execute(f"SELECT game_id, COUNT(*) as c FROM game_cards WHERE game_id IN ({placeholders}) GROUP BY game_id", game_ids)
    rows = cur.fetchall()
    release_connection(conn)
    return {r["game_id"]: r["c"] for r in rows}


def update_marked_numbers(game_id: int, card_index: int, marked_list: list):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "UPDATE game_cards SET marked_numbers = %s WHERE game_id = %s AND card_index = %s",
        (json.dumps(marked_list), game_id, card_index)
    )
    conn.commit()
    release_connection(conn)


def get_marked_numbers(game_id: int, card_index: int) -> list:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "SELECT marked_numbers FROM game_cards WHERE game_id = %s AND card_index = %s",
        (game_id, card_index)
    )
    row = cur.fetchone()
    release_connection(conn)
    if row is None:
        return []
    return json.loads(row["marked_numbers"])


def get_all_marked_numbers(game_id: int) -> dict:
    """Return {card_index: marked_numbers_list} for all cards in a game.
    Single query instead of N separate queries."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "SELECT card_index, marked_numbers FROM game_cards WHERE game_id = %s",
        (game_id,)
    )
    rows = cur.fetchall()
    release_connection(conn)
    return {row["card_index"]: json.loads(row["marked_numbers"]) for row in rows}


def purchase_cards(game_id: int, user_id: int, card_indices: list, fee_per_card: float):
    """Atomically purchase one or more cards for a game.

    Validates:
      - sufficient balance for total cost
      - none of the requested cards are already taken (UNIQUE constraint)
      - player's total cards in this game won't exceed MAX_CARDS_PER_PLAYER

    On success: deducts balance, adds to the game pool, records ownership,
    and updates/creates the game_players row.

    Returns (success: bool, reason: str)
      reason in {"ok", "insufficient_balance", "card_taken", "max_cards_exceeded"}
    """
    total_cost = fee_per_card * len(card_indices)
    now = datetime.utcnow().isoformat()

    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    try:
        cur.execute("BEGIN")

        # --- Check max cards per player ---
        cur.execute("SELECT cards_count FROM game_players WHERE game_id = %s AND user_id = %s", (game_id, user_id))
        gp = cur.fetchone()
        existing_count = gp["cards_count"] if gp else 0

        if existing_count + len(card_indices) > config.MAX_CARDS_PER_PLAYER:
            conn.rollback()
            release_connection(conn)
            return False, "max_cards_exceeded"

        # --- Conditional balance debit (atomic, bonus first, prevents negative balance) ---
        success, reason = spend_funds(user_id, total_cost, conn=conn, cur=cur)
        if not success:
            conn.rollback()
            release_connection(conn)
            return False, reason

        # --- Insert cards (UNIQUE constraint prevents double-selling) ---
        for card_index in card_indices:
            cur.execute(
                "INSERT INTO game_cards (game_id, card_index, owner_id, marked_numbers, created_at) "
                "VALUES (%s, %s, %s, '[]', %s)",
                (game_id, card_index, user_id, now)
            )

        # --- Update pool ---
        cur.execute("UPDATE games SET pool = pool + %s WHERE id = %s", (total_cost, game_id))

        # --- Upsert game_players ---
        if gp is None:
            cur.execute(
                "INSERT INTO game_players (game_id, user_id, cards_count, auto_win, created_at) "
                "VALUES (%s, %s, %s, 0, %s)",
                (game_id, user_id, len(card_indices), now)
            )
        else:
            cur.execute(
                "UPDATE game_players SET cards_count = cards_count + %s WHERE game_id = %s AND user_id = %s",
                (len(card_indices), game_id, user_id)
            )

        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        release_connection(conn)
        return False, "card_taken"
    except Exception:
        conn.rollback()
        release_connection(conn)
        raise
    finally:
        pass

    try:
        record_transaction(user_id, "bingo_bet", -total_cost, status="completed")
    finally:
        release_connection(conn)
    return True, "ok"


def refund_game(game_id: int):
    """Refund every player for every card they bought in this game.
    Used when <2 cards sold at countdown end, or no winner after 75 calls."""
    cards = get_all_game_cards(game_id)
    game = get_game(game_id)
    fee = game["room_fee"]

    refunded = {}
    for card in cards:
        owner = card["owner_id"]
        refunded[owner] = refunded.get(owner, 0) + fee

    for user_id, amount in refunded.items():
        adjust_balance(user_id, amount)
        record_transaction(user_id, "bingo_refund", amount, status="completed")

    return refunded  # {user_id: amount_refunded}


# =====================================================================
# GAME NUMBERS (call sequence)
# =====================================================================

def add_called_number(game_id: int, call_order: int, number: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "INSERT INTO game_numbers (game_id, call_order, number, called_at) VALUES (%s, %s, %s, %s)",
        (game_id, call_order, number, datetime.utcnow().isoformat())
    )
    conn.commit()
    release_connection(conn)


def get_called_numbers(game_id: int) -> list:
    """Returns the called numbers in call order."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT number FROM game_numbers WHERE game_id = %s ORDER BY call_order ASC", (game_id,))
    rows = cur.fetchall()
    release_connection(conn)
    return [r["number"] for r in rows]


def get_call_count(game_id: int) -> int:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT COUNT(*) as c FROM game_numbers WHERE game_id = %s", (game_id,))
    row = cur.fetchone()
    release_connection(conn)
    return row["c"]


# =====================================================================
# ADMIN AUDIT LOG
# =====================================================================

def record_admin_action(admin_id: int, action: str, target_id=None, details=None):
    if details is not None and not isinstance(details, str):
        details = json.dumps(details)
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "INSERT INTO admin_audit_log (admin_id, action, target_id, details, created_at) VALUES (%s, %s, %s, %s, %s)",
        (admin_id, action, target_id, details, datetime.utcnow().isoformat())
    )
    conn.commit()
    release_connection(conn)


def get_total_games_played() -> int:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT COUNT(*) as c FROM games WHERE state = 'finished'")
    row = cur.fetchone()
    release_connection(conn)
    return row["c"]


def get_total_unique_players() -> int:
    """Number of distinct users who have ever bought a bingo card."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT COUNT(DISTINCT owner_id) as c FROM game_cards")
    row = cur.fetchone()
    release_connection(conn)
    return row["c"]


# =====================================================================
# HOUSE WALLET
# Single-row table tracking cumulative house commission.
# Admin can view and withdraw from it via /admin panel.
# =====================================================================

def init_house_wallet():
    """Ensure house_wallet table and its single row exist.
    Called inside init_db() automatically."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS house_wallet (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            balance NUMERIC(12,2) NOT NULL DEFAULT 0,
            total_earned NUMERIC(12,2) NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        INSERT INTO house_wallet (id, balance, total_earned, updated_at)
        VALUES (1, 0, 0, %s)
        ON CONFLICT (id) DO NOTHING
    """, (datetime.utcnow().isoformat(),))

    cur.execute("""
        INSERT INTO jackpot (id, current_amount, room_fee, triggered, updated_at)
        VALUES (1, 0, %s, 0, %s)
        ON CONFLICT (id) DO NOTHING
    """, (config.JACKPOT_ROOM_FEE, datetime.utcnow().isoformat()))
    conn.commit()
    release_connection(conn)


def get_house_balance() -> float:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT balance FROM house_wallet WHERE id = 1")
    row = cur.fetchone()
    release_connection(conn)
    return float(row["balance"]) if row else 0.0


def get_house_total_earned() -> float:
    """Cumulative all-time commission - never decreases."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT total_earned FROM house_wallet WHERE id = 1")
    row = cur.fetchone()
    release_connection(conn)
    return float(row["total_earned"]) if row else 0.0


def add_house_commission(amount: float) -> float:
    """Credit the house wallet. Returns new balance."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("""
        UPDATE house_wallet
        SET balance = balance + %s,
            total_earned = total_earned + %s,
            updated_at = %s
        WHERE id = 1
    """, (amount, amount, datetime.utcnow().isoformat()))

    jackpot_contrib = round(amount * config.JACKPOT_CONTRIBUTION_PERCENT / 100, 2)
    if jackpot_contrib > 0:
        cur.execute(
            "UPDATE jackpot SET current_amount = current_amount + %s, updated_at = %s WHERE id = 1",
            (jackpot_contrib, datetime.utcnow().isoformat()),
        )

    conn.commit()
    cur.execute("SELECT balance FROM house_wallet WHERE id = 1")
    new_balance = cur.fetchone()["balance"]
    release_connection(conn)
    return float(new_balance)


def credit_house(amount: float) -> float:
    """Credit the house wallet AND record a house_commission ledger entry.
    Call once per finished game with that game's house cut.
    Returns the new house wallet balance."""
    new_balance = add_house_commission(amount)
    record_transaction(config.HOUSE_ACCOUNT_ID, "house_commission", amount, status="completed")
    return new_balance


def get_recent_winners(limit: int = 8) -> list:
    """Recent bingo wins for the Home-screen activity feed. Joins to users
    for a display name, masked for privacy (no phone/full username shown
    to other players)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        """SELECT t.user_id, t.amount, t.created_at, u.username
           FROM transactions t
           JOIN users u ON u.user_id = t.user_id
           WHERE t.type = 'bingo_win' AND t.status = 'completed'
           ORDER BY t.created_at DESC
           LIMIT %s""",
        (limit,),
    )
    rows = cur.fetchall()
    release_connection(conn)
    out = []
    for r in rows:
        uname = r.get("username")
        if uname:
            display = f"@{uname[:3]}***" if len(uname) > 3 else f"@{uname}***"
        else:
            display = f"Player #{str(r['user_id'])[-4:]}"
        out.append({
            "display_name": display,
            "amount": float(r["amount"]),
            "created_at": r["created_at"],
        })
    return out


def get_jackpot() -> dict:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT * FROM jackpot WHERE id = 1")
    row = cur.fetchone()
    release_connection(conn)
    if row is None:
        return {
            "id": 1,
            "current_amount": 0.0,
            "room_fee": config.JACKPOT_ROOM_FEE,
            "triggered": 0,
            "updated_at": datetime.utcnow().isoformat(),
        }
    return dict(row)


def reset_jackpot():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "UPDATE jackpot SET current_amount = 0, triggered = 0, updated_at = %s WHERE id = 1",
        (datetime.utcnow().isoformat(),),
    )
    conn.commit()
    release_connection(conn)


def trigger_jackpot(game_id: int) -> float:
    """Deprecated in favor of try_trigger_jackpot, which is race-safe when
    multiple games can reach 'starting' at the same time. Kept only in case
    something still imports it directly."""
    return try_trigger_jackpot(game_id) or 0.0


def try_trigger_jackpot(game_id: int):
    """Atomically claim the jackpot for this game, if it's ready.

    Uses a single guarded UPDATE (WHERE triggered = 0 AND current_amount >= X)
    instead of a read-then-write check, so when two games finish their
    countdown around the same moment (each running as its own asyncio task),
    only one of them can win the row lock and see rowcount > 0 — the other's
    UPDATE affects zero rows once it re-checks the now-committed state.
    Returns the bonus amount if this call claimed it, otherwise None.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    bonus = float(config.JACKPOT_TRIGGER_AMOUNT)
    cur.execute(
        """UPDATE jackpot
           SET current_amount = 0, triggered = 1, updated_at = %s
           WHERE id = 1 AND triggered = 0 AND current_amount >= %s""",
        (datetime.utcnow().isoformat(), bonus),
    )
    claimed = cur.rowcount > 0
    if claimed:
        cur.execute("UPDATE games SET pool = pool + %s WHERE id = %s", (bonus, game_id))
    conn.commit()
    release_connection(conn)
    return bonus if claimed else None


def withdraw_house_funds(amount: float):
    """Deduct from house wallet. Returns (success, reason, new_balance)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("BEGIN")
    cur.execute("SELECT balance FROM house_wallet WHERE id = 1")
    row = cur.fetchone()
    if row is None or float(row["balance"]) < amount:
        conn.rollback()
        release_connection(conn)
        return False, "insufficient_house_balance", 0.0

    cur.execute("""
        UPDATE house_wallet SET balance = balance - %s, updated_at = %s
        WHERE id = 1
    """, (amount, datetime.utcnow().isoformat()))
    conn.commit()
    cur.execute("SELECT balance FROM house_wallet WHERE id = 1")
    new_bal = float(cur.fetchone()["balance"])
    release_connection(conn)
    return True, "ok", new_bal


def record_manual_bingo_claim(game_id: int, user_id: int, card_indices: list):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "INSERT INTO manual_bingo_claims (game_id, user_id, card_indices, created_at) VALUES (%s, %s, %s, %s)",
        (game_id, user_id, json.dumps(card_indices), datetime.utcnow().isoformat())
    )
    conn.commit()
    release_connection(conn)


def get_manual_bingo_claims(game_id: int) -> dict:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute(
        "SELECT user_id, card_indices FROM manual_bingo_claims WHERE game_id = %s AND resolved = 0",
        (game_id,)
    )
    rows = cur.fetchall()
    release_connection(conn)
    return {row["user_id"]: json.loads(row["card_indices"]) for row in rows}


def clear_manual_bingo_claims(game_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("DELETE FROM manual_bingo_claims WHERE game_id = %s", (game_id,))
    conn.commit()
    release_connection(conn)


def force_finish_stuck_game(game_id: int) -> tuple:
    """Admin helper: force-finish a stuck game and refund all players."""
    game = get_game(game_id)
    if game is None or game["state"] == "finished":
        return False, "game_not_found_or_finished"
    try:
        refund_game(game_id)
        clear_manual_bingo_claims(game_id)
        set_game_state(game_id, "finished")
        logger.info("[force-finish] game %s force-finished", game_id)
        return True, "ok"
    except Exception:
        logger.exception("[force-finish] failed for game %s", game_id)
        return False, "db_error"
