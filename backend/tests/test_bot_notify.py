# test_bot_notify.py
# ============================================
# Regression test for the "15 second delay after countdown" bug.
#
# notify_game_players used to be awaited directly in the game-start path
# (run_game_lifecycle), so sending one DM per player -- one at a time --
# could add real, multi-second delay (Telegram's own per-message latency
# adds up fast in a sequential loop) before the first number was ever
# called. That delay had nothing to do with the game itself.
# ============================================

import asyncio
import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "postgresql://fake/fake")

import bot  # noqa: E402


def test_notify_game_players_async_does_not_block():
    """notify_game_players_async must return immediately regardless of how
    slow or numerous the underlying Telegram sends are -- the actual
    sending happens in the background."""

    fake_players = [{"user_id": i} for i in range(10)]

    async def slow_send_message(chat_id, text):
        await asyncio.sleep(0.2)  # simulate real Telegram per-message latency

    fake_bot = MagicMock()
    fake_bot.send_message = AsyncMock(side_effect=slow_send_message)

    async def scenario():
        with patch.object(bot.db, "get_game_players", return_value=fake_players), \
             patch.object(bot.db, "get_user_chat_id", side_effect=lambda uid: 1000 + uid):

            start = time.monotonic()
            bot.notify_game_players_async(fake_bot, game_id=1, text="hi")
            elapsed = time.monotonic() - start

            # Ten sequential 0.2s sends would take ~2s if awaited directly.
            # Returning should be near-instant.
            assert elapsed < 0.05, (
                f"notify_game_players_async blocked the caller for {elapsed:.3f}s "
                "-- it should return immediately and send in the background."
            )

            # Give the background task time to actually finish, then
            # confirm it really did message every player (fire-and-forget,
            # not fire-and-drop).
            await asyncio.sleep(3)
            assert fake_bot.send_message.await_count == 10

    asyncio.run(scenario())


def test_notify_game_players_async_survives_internal_crash():
    """If something inside notify_game_players raises unexpectedly, the
    background task must not vanish silently -- it should be reported via
    the monitoring hook, not just swallowed by asyncio."""

    fake_bot = MagicMock()

    async def scenario():
        with patch.object(bot.db, "get_game_players", side_effect=RuntimeError("db exploded")), \
             patch("bot.capture_error") as mock_capture:

            bot.notify_game_players_async(fake_bot, game_id=1, text="hi")
            await asyncio.sleep(0.1)
            assert mock_capture.called

    asyncio.run(scenario())
