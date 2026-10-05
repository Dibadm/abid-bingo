"""
⚠️ NOT RECOMMENDED FOR PRODUCTION AT REAL PLAYER VOLUMES.

This runs the bot and the API in the same process (two threads sharing one
Python GIL and one database connection pool). Under real concurrent load —
the bot's game loop calling numbers/checking wins for active games at the
same moment many players are polling the API — the two workloads compete
for the same GIL time and the same limited DB connections. That contention
is the likely cause of "the API seems to stop responding" during live
games: it isn't crashing, it's being starved by the bot thread.

The correct production setup is two independent Render services:
  1. Web Service   — start command: uvicorn api_server:app --host 0.0.0.0 --port $PORT
  2. Background Worker — start command: python bot.py

Each gets its own Python process (own GIL, own DB pool), so neither can
starve the other, and a crash in one doesn't take the other down with it.
api_server.py now initializes the database on its own startup, so it's
safe to run standalone this way — it no longer depends on bot.py having
started first.

This file is kept for local development convenience only (one command to
run everything). Do not use it as the production start command once
you've set up the two services above.
"""
import os
import sys
import threading
import time
import asyncio
import uvicorn
import bot

PORT = os.environ.get("PORT", os.environ.get("API_PORT", "8000"))

def run_api():
    uvicorn.run("api_server:app", host="0.0.0.0", port=int(PORT), log_level="info")

if __name__ == "__main__":
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    time.sleep(2)

    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    bot.main()
