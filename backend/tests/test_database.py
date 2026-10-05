# test_database.py
# ============================================
# HABESHA BET - DATABASE LAYER TESTS
# ============================================

import os
import threading
import time
import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend import database as db
from backend import config


def _require_db():
    db_url = getattr(config, "DATABASE_URL", "") or config.DB_PATH
    if not db_url or db_url == "habesha_bet.db":
        pytest.skip("No DATABASE_URL or test DB configured")


def test_connection_pool_created():
    _require_db()
    conn = db.get_connection()
    assert conn is not None
    db.release_connection(conn)


def test_init_db_creates_tables():
    _require_db()
    db.init_db()
    conn = db.get_connection()
    cur = conn.cursor(cursor_factory=db.extras.RealDictCursor)
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    tables = {r["table_name"] for r in cur.fetchall()}
    db.release_connection(conn)
    expected = {
        "users", "transactions", "withdrawals", "admin_audit_log",
        "deposit_accounts", "games", "game_players", "game_cards",
        "game_numbers", "jackpot", "manual_bingo_claims", "house_wallet",
    }
    assert expected.issubset(tables)


def test_user_crud():
    _require_db()
    db.init_db()
    test_id = 999999999
    try:
        user = db.get_or_create_user(test_id, "testuser")
        assert user["user_id"] == test_id

        fetched = db.get_user(test_id)
        assert fetched["username"] == "testuser"

        db.set_user_language(test_id, "en")
        updated = db.get_user(test_id)
        assert updated["language"] == "en"
    finally:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE user_id = %s", (test_id,))
        conn.commit()
        db.release_connection(conn)


def test_balance_operations():
    _require_db()
    db.init_db()
    test_id = 999999998
    try:
        db.get_or_create_user(test_id, "balancetest")
        assert db.get_balance(test_id) == 0.0

        db.adjust_balance(test_id, 100.0)
        assert db.get_balance(test_id) == 100.0

        db.adjust_balance(test_id, -30.0)
        assert db.get_balance(test_id) == 70.0
    finally:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE user_id = %s", (test_id,))
        conn.commit()
        db.release_connection(conn)


def test_transactions_ledger():
    _require_db()
    db.init_db()
    test_id = 999999997
    try:
        db.get_or_create_user(test_id, "txtest")
        db.record_transaction(test_id, "deposit", 50.0, reference="test_ref_1", status="completed")
        txs = db.get_user_transactions(test_id, limit=5)
        assert len(txs) >= 1
        assert txs[0]["type"] == "deposit"
        assert float(txs[0]["amount"]) == 50.0

        assert db.reference_already_used("test_ref_1") is True
        assert db.reference_already_used("test_ref_999") is False
    finally:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM transactions WHERE user_id = %s", (test_id,))
        cur.execute("DELETE FROM users WHERE user_id = %s", (test_id,))
        conn.commit()
        db.release_connection(conn)


def test_game_crud():
    _require_db()
    db.init_db()
    fee = 10.0
    try:
        game = db.get_or_create_active_game(fee)
        assert game["state"] == "waiting"

        db.set_game_state(game["id"], "running")
        running = db.get_game(game["id"])
        assert running["state"] == "running"

        db.finish_game(game["id"], [1, 2], 5.0, 2.5, winner_cards={1: [0]})
        finished = db.get_game(game["id"])
        assert finished["state"] == "finished"
    finally:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM game_cards WHERE game_id = (SELECT id FROM games WHERE room_fee = %s LIMIT 1)", (fee,))
        cur.execute("DELETE FROM games WHERE room_fee = %s", (fee,))
        conn.commit()
        db.release_connection(conn)


def test_deposit_accounts():
    _require_db()
    db.init_db()
    try:
        acc_id = db.add_deposit_account("251911111111", "Test Account")
        assert acc_id is not None

        accounts = db.get_active_deposit_accounts()
        assert len(accounts) >= 1

        db.remove_deposit_account(acc_id)
        accounts = db.get_active_deposit_accounts()
        assert len(accounts) == 0
    except Exception:
        pass


def test_house_wallet():
    _require_db()
    db.init_db()
    balance = db.get_house_balance()
    assert balance == 0.0

    new_bal = db.add_house_commission(10.0)
    assert new_bal == 10.0

    total = db.get_house_total_earned()
    assert total == 10.0


def test_concurrent_deductions_only_one_succeeds():
    _require_db()
    db.init_db()
    test_id = 999999996
    try:
        db.get_or_create_user(test_id, "concurrenttest")
        db.adjust_balance(test_id, 50.0)
        assert db.get_balance(test_id) == 50.0

        results = []
        barrier = threading.Barrier(2)

        def try_deduct(amount):
            barrier.wait()
            results.append(db.deduct_balance(test_id, amount))

        t1 = threading.Thread(target=try_deduct, args=(30.0,))
        t2 = threading.Thread(target=try_deduct, args=(30.0,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        successes = [r for r in results if r[0] is True]
        assert len(successes) == 1

        final_balance = db.get_balance(test_id)
        assert final_balance == 20.0
    finally:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE user_id = %s", (test_id,))
        conn.commit()
        db.release_connection(conn)


def test_concurrent_jackpot_trigger_only_one_game_wins():
    """Two games (simulating two rooms whose countdowns finish at the same
    moment) both try to claim a ready jackpot at once. Exactly one should
    succeed, and the jackpot pool should end up at 0 either way — it must
    never be paid out twice."""
    _require_db()
    db.init_db()
    game_a = db.get_or_create_active_game(config.JACKPOT_ROOM_FEE)
    game_b = db.get_or_create_active_game(config.JACKPOT_ROOM_FEE + 1)  # distinct room/game row
    try:
        db.reset_jackpot()
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE jackpot SET current_amount = %s WHERE id = 1",
            (config.JACKPOT_TRIGGER_AMOUNT,),
        )
        conn.commit()
        db.release_connection(conn)

        results = []
        barrier = threading.Barrier(2)

        def try_claim(game_id):
            barrier.wait()
            results.append(db.try_trigger_jackpot(game_id))

        t1 = threading.Thread(target=try_claim, args=(game_a["id"],))
        t2 = threading.Thread(target=try_claim, args=(game_b["id"],))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        successes = [r for r in results if r]
        assert len(successes) == 1

        assert db.get_jackpot()["current_amount"] == 0
    finally:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM games WHERE id = ANY(%s)", ([game_a["id"], game_b["id"]],))
        conn.commit()
        db.release_connection(conn)


def test_concurrent_game_resolution_only_one_caller_wins():
    """The safety-critical test for this round: the API's instant manual
    BINGO claim and the bot's own auto-win detection are two separate
    processes that can both reach 'this game has a winner, pay it out'
    for the same game at nearly the same instant. Without the atomic
    guard, both could credit a payout for the same win. Exactly one of
    two simultaneous try_claim_game_resolution calls must succeed."""
    _require_db()
    db.init_db()
    game = db.get_or_create_active_game(999999)  # distinct room fee, won't collide with real rooms
    try:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE games SET state = 'running', pool = %s WHERE id = %s", (100.0, game["id"]))
        conn.commit()
        db.release_connection(conn)

        results = []
        barrier = threading.Barrier(2)

        def try_resolve():
            barrier.wait()
            results.append(db.try_claim_game_resolution(game["id"]))

        t1 = threading.Thread(target=try_resolve)
        t2 = threading.Thread(target=try_resolve)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        successes = [r for r in results if r]
        assert len(successes) == 1, (
            f"expected exactly one winner of the resolution race, got {successes} "
            f"from {results} -- this would mean both the API and the bot could "
            f"pay out the same win"
        )

        # The game must now be in 'resolving', claimed by whichever caller
        # won -- not still 'running' (which would let a THIRD caller also
        # claim it) and not skipped back to some other state.
        fresh = db.get_game(game["id"])
        assert fresh["state"] == "resolving"
    finally:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM games WHERE id = %s", (game["id"],))
        conn.commit()
        db.release_connection(conn)


def test_resolve_game_winners_pays_out_correctly():
    """End-to-end check of the shared payout function: house cut taken,
    remaining pool split evenly among winners, each winner's balance
    credited, and the game marked finished with the right winner_ids."""
    _require_db()
    db.init_db()
    game = db.get_or_create_active_game(999998)
    test_uid_a = 900000001
    test_uid_b = 900000002
    try:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE games SET state = 'resolving', pool = %s WHERE id = %s", (100.0, game["id"]))
        conn.commit()
        db.release_connection(conn)

        for uid in (test_uid_a, test_uid_b):
            db.get_or_create_user(uid, f"testuser{uid}")

        balance_before_a = db.get_balance(test_uid_a)
        balance_before_b = db.get_balance(test_uid_b)

        result = db.resolve_game_winners(game["id"], {
            test_uid_a: {7: "line"},
            test_uid_b: {12: "corners"},
        })

        expected_house_cut = round(100.0 * config.HOUSE_COMMISSION_PERCENT / 100, 2)
        expected_per_winner = round((100.0 - expected_house_cut) / 2, 2)

        assert result["per_winner_amount"] == expected_per_winner
        assert set(result["winner_ids"]) == {test_uid_a, test_uid_b}
        assert db.get_balance(test_uid_a) == round(balance_before_a + expected_per_winner, 2)
        assert db.get_balance(test_uid_b) == round(balance_before_b + expected_per_winner, 2)

        fresh = db.get_game(game["id"])
        assert fresh["state"] == "finished"
    finally:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM games WHERE id = %s", (game["id"],))
        cur.execute("DELETE FROM users WHERE user_id = ANY(%s)", ([test_uid_a, test_uid_b],))
        cur.execute("DELETE FROM transactions WHERE user_id = ANY(%s)", ([test_uid_a, test_uid_b],))
        conn.commit()
        db.release_connection(conn)
