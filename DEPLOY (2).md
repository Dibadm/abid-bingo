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

Identical for both services. **Leave Root Directory empty** — the build
command below is written relative to the repo root:

```
cd backend && python3 -m pip install -r requirements.txt && cd .. && bash -lc "cd miniapp && npm install --include=dev && npm run build"
```

`npm run build` writes `miniapp/dist/`. `api_server.py` mounts it at `/`
via `pathlib.Path(__file__).parent.parent / "miniapp" / "dist"`, so the
build must run inside the repo, not inside `backend/`. `dist/` is
gitignored and rebuilt on every deploy.

Every one of those four details is load-bearing. Each was a separate
`build_failed`:

- **`python3 -m pip`, not bare `pip`.** The bare `pip` on Render's Python
  image is bound to a different interpreter and dies on
  `pip install -r requirements.txt`.
- **`bash -lc` around the npm part.** `node` is not on `PATH` in
  Render's non-login build shell (`node -v` fails, `npm -v` works). A
  login shell sources the profile that puts Node on `PATH`.
- **`cd miniapp` from the repo root, not `cd ../miniapp` from `backend/`.**
  The login shell does not reliably inherit the `cd backend` working
  directory, so the relative path resolves to a directory that does not
  exist.
- **`npm install --include=dev`.** `vite` and `@vitejs/plugin-react` are
  devDependencies and are skipped otherwise, so `npm run build` fails with
  `vite: not found`.

## Pin the Python version

Set **`PYTHON_VERSION=3.13.4`** as an environment variable on both
services.

This is the single most important setting. Without it Render picks a
default Python that has no prebuilt wheel for `pydantic-core` 2.23.4
(pinned transitively by `pydantic==2.9.2`), so pip falls back to
compiling it from source with Rust and the whole build fails with:

```
error: metadata-generation-failed
× Encountered error while generating package metadata.
╰─> pydantic-core
```

The same `requirements.txt` installs fine on a machine with Python 3.13,
which is what makes this confusing to debug locally.

## Environment variables

Set these in the Render dashboard (**Service → Environment**), on **both**
services. Do not commit them, and do not paste them into `config.py` —
`config.py` reads everything from the environment.

| Variable          | Web | Bot | Value |
| ----------------- | :-: | :-: | ----- |
| `PYTHON_VERSION`  | yes | yes | `3.13.4` — required, see above |
| `DATABASE_URL`    | yes | yes | Neon/Postgres connection string (see below) |
| `MINI_APP_URL`    | no  | yes | `https://habesha-bet-web.onrender.com` |
| `BOT_TOKEN`       | yes | yes | From @BotFather — the **web service needs it too**, it signs `initData` |
| `BOT_USERNAME`    | no  | yes | e.g. `abid1wbot` |
| `ADMIN_IDS`       | yes | yes | Comma-separated numeric Telegram IDs |
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

Render's API does not expose build logs, so a `build_failed` gives you no
error text. Bisect by replacing the build command with progressively
larger pieces and watching whether it reaches `update_in_progress`.

- **`metadata-generation-failed` / `pydantic-core`** — `PYTHON_VERSION` is
  not set. See above.
- **`vite: not found`** — `npm install` skipped devDependencies. Use
  `--include=dev`.
- **`node: command not found`** — the npm commands are not wrapped in
  `bash -lc`.
- **`pip: command not found`, or pip dies mid-install** — use
  `python3 -m pip`, not `pip`.
- **Build is fine, service has no live ports** — the start command is
  `python bot.py` on a *Web Service*. The bot never binds `$PORT`; it
  belongs on a Background Worker.
- **Blank Mini App / `{"detail":"Mini App not built"}`** — `dist/` is
  missing, so the build command didn't run. Check the build log.
- **401 on every API call** — `BOT_TOKEN` doesn't match the bot the Mini
  App was opened from. `initData` is signed per-bot. The web service needs
  `BOT_TOKEN` too, not just the bot.
- **Menu button missing** — `MINI_APP_URL` wasn't set before `bot.py`
  started. Set it, then restart the bot service. Confirm with
  `getChatMenuButton`; it should report `type: web_app`, not `commands`.
- **`relation does not exist`** — the web service creates its schema on
  startup; check its logs. If the bot service errors first, restart it.
- **Bot and API disagree on state** — both must point at the same
  `DATABASE_URL`.
- **Free web service sleeps mid-game** — expected; ping `/health` on a
  cron or upgrade.
