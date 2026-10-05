# game_state.py
# ============================================
# HABESHA BET — SHARED IN-PROCESS GAME STATE
#
# Lives here so both bot.py (Telegram polling loop) and api_handlers.py
# (FastAPI/uvicorn thread) can import the SAME dict objects.  Because
# uvicorn runs as a daemon thread inside the SAME Python process as
# bot.py (see run_api_server_in_thread), importing this module from
# either side gives both sides references to the same objects — standard
# Python module-cache behaviour.
#
# ACTIVE_GAME_TASKS   — {room_fee: asyncio.Task}  one task per room
# ROOM_LOCKS          — {room_fee: asyncio.Lock}   prevents double-start
# GAME_MANUAL_CLAIMS  — {game_id: {user_id: [card_index, ...]}}
#                       Written by game_bingo_claim (bot) and
#                       handle_claim_bingo (api_handlers); read by the
#                       run_game_lifecycle loop on every call cycle.
# GAME_COUNTDOWN_START — {game_id: float (time.monotonic())}
#                       Written when the lifecycle task begins its
#                       countdown phase; read by api_handlers to compute
#                       seconds-remaining for the lobby screen.
# ============================================

import asyncio
import config

# One asyncio.Task per room; None / done() == no active lifecycle.
ACTIVE_GAME_TASKS: dict = {}

# Per-room asyncio.Lock — ensures only one lifecycle task is ever spawned
# per room even under near-simultaneous purchases.
ROOM_LOCKS: dict = {fee: asyncio.Lock() for fee in config.ROOM_FEES}

# Countdown start times (time.monotonic()) keyed by game_id.
# Set when run_game_lifecycle enters the countdown phase so
# api_handlers can compute seconds_remaining without a DB round-trip.
GAME_COUNTDOWN_START: dict = {}

# Group broadcast message_id per game_id so we can edit instead of sending.
GROUP_BROADCAST_MSG: dict = {}
