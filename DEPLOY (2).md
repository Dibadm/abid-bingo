# DEPLOY.md — Habesha Bet on Render

## Repo layout

```
repo/
  backend/          Python app (FlatAPI + Telegram bot)
    bot.py          Telegram bot process
    api_server.py   FastAPI: /api/* + serves the built frontend at /
    requirements.txt
    audio/          Pre-generated Amharic number announcements
  miniapp/          React + Vite frontend
```

All backend modules import each other flatly (`import config`,
`import api_handlers`), so **`backend/` must be the Render Root Directory**
— that is what puts the modules on `sys.path`.

## Architecture: two services, not one

`bot.py` only runs the Telegram bot. It does **not** start the API server,
and it never binds `$PORT`. `api_server.py` serves both `/api/*` and the
built Mini App. So they are deployed as two independent Render services:

| Service              | Type            | Start command                                  |
| -------------------- | --------------- | ---------------------------------------------- |
| `habesha-bet-web`    | Web Service     | `uvicorn api_server:app --host 0.0.0.0 --port $PORT` |
| `habesha-bet-bot`    | Background Worker | `python bot.py`                              |

Each gets its own process, GIL, and connection pool, so the bot's game loop
cannot starve API polling and a crash in one does not take down the other.
`backend/render_start.py` runs both in one process, but its own docstring
rejects it for real player load — do not use it as a start command.

`api_server.py` initializes the database on its own startup, so the web
service does not depend on the bot having started first.

## Build command

Identical for both services, with Root Directory set to `backend`:

```
pip install -r requirements.txt && cd ../miniapp && npm install && npm run build
```

`npm run build` writes `miniapp/dist/`. `api_server.py` mounts it at `/`
via `pathlib.Path(__file__).parent.parent / "miniapp" / "dist"`, so the
build must run inside the repo, not inside `backend/`. `dist/` is
gitignored and rebuilt on every deploy.

## Environment variables

Set these in the Render dashboard (**Service → Environment**), on **both**
services. Do not commit them, and do not paste them into `config.py` —
`config.py` reads everything from the environment.

| Variable          | Web | Bot | Value |
| ----------------- | :-: | :-: | ----- |
| `DATABASE_URL`    | yes | yes | Neon/Postgres connection string (see below) |
| `MINI_APP_URL`    | no  | yes | `https://habesha-bet-web.onrender.com` |
| `BOT_TOKEN`       | no  | yes | From @BotFather |
| `BOT_USERNAME`    | no  | yes | e.g. `Vscoodebot` |
| `ADMIN_IDS`       | no  | yes | Comma-separated numeric Telegram IDs |
| `DB_PATH`         | no  | no  | Leave unset — `DATABASE_URL` takes precedence |
| `PRODUCTION`      | no  | no  | `true` to enable scheduled DB backups |

`MINI_APP_URL` must be the **web service** URL with no trailing path. It is
what makes the "Open Habesha Bet" button appear and what `bot.py` passes to
`set_chat_menu_button` on startup. Chicken-and-egg: deploy the web service
first, copy its URL, then set `MINI_APP_URL` on the bot service.

## Database

Use Postgres, not SQLite. `DB_PATH` defaults to a local `habesha_bet.db`
file, and Render's filesystem is ephemeral — every restart and redeploy
would wipe player balances and live games. This bot moves real ETB.

`config.py` selects Postgres automatically when `DATABASE_URL` is set, and
`requirements.txt` already includes `psycopg2-binary`. No code changes
required.

## Deploy order

1. Create the **Web Service** first and let it finish its first build.
2. Copy its URL, then create the **Background Worker**.
3. Set `MINI_APP_URL` on the bot to the web service URL.
4. Push to GitHub — Render auto-deploys on every push to the main branch.

## Verify

- `https://habesha-bet-web.onrender.com/health` → `{"status":"ok"}`
- `https://habesha-bet-web.onrender.com/` → the Mini App loads
- Bot logs show `Bot started successfully`

## Free-tier notes

Free web services sleep after 15 min idle and cold-start on the next
request (10–30s delay). Acceptable for testing. For production either
upgrade to a paid instance or ping `/health` on a 10-minute cron to keep
it warm.

## Troubleshooting

- **Blank Mini App / `{"detail":"Mini App not built"}`** — `dist/` is
  missing, so the build command didn't run. Check the build log.
- **Service reports no live ports** — the start command is `python bot.py`
  on a *Web Service*. The bot never binds `$PORT`; it belongs on a
  Background Worker.
- **401 on every API call** — `BOT_TOKEN` doesn't match the bot the Mini
  App was opened from. `initData` is signed per-bot.
- **Menu button missing** — `MINI_APP_URL` wasn't set before `bot.py`
  started. Set it, then restart the bot service.
- **`relation does not exist`** — the web service creates its schema on
  startup; check its logs. If the bot service errors first, restart it.
- **Bot and API disagree on state** — both must point at the same
  `DATABASE_URL`.
