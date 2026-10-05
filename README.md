# Habesha Bet - Multiplayer Bingo Bot

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BOT_TOKEN` | Yes | - | Telegram bot token from BotFather |
| `ADMIN_IDS` | Yes | `787372880` | Comma-separated Telegram user IDs for admin access |
| `BOT_USERNAME` | Yes | `Vscoodebot` | Bot username (without @) |
| `SUPPORT_USERNAME` | No | `your_support_username` | Support contact username |
| `GROUP_LINK` | No | `https://t.me/your_group` | Telegram group link |
| `GROUP_CHAT_ID` | No | `-1001234567890` | Telegram group/channel numeric ID for broadcasts |
| `MINI_APP_URL` | Yes | `https://chilly-glasses-fold.loca.lt` | Public HTTPS URL for the React Mini App |
| `API_HOST` | No | `0.0.0.0` | API server bind host |
| `API_PORT` | No | `8000` | API server port |
| `DB_PATH` | No | `habesha_bet.db` | SQLite database file path |
| `DEFAULT_LANGUAGE` | No | `am` | Default language (`am` or `en`) |
| `ALLOW_DEV_AUTH` | No | `false` | Allow dev auth bypass (NEVER enable in production) |
| `PRODUCTION` | No | `false` | Enable production mode (backups, stricter auth) |
| `BROADCAST_ENABLED` | No | `false` | Enable broadcast admin tab and endpoints |
| `MAX_BACKUPS` | No | `50` | Maximum number of rotated DB backups |
| `BACKUP_INTERVAL_MINUTES` | No | `30` | Database backup interval in minutes |

## Log Locations

Logs are written using the standard `habesha_bet` logger:
- Backend API and bot logs: `habesha_bet` logger (configure in your deployment)
- SQLite WAL mode is enabled for crash safety
- Database backups are stored in `backend/backups/`

## Pre-Deployment Checklist

- [ ] Set `PRODUCTION=true` in `.env.production`
- [ ] Set `ALLOW_DEV_AUTH=false` in `.env.production`
- [ ] Verify `BOT_TOKEN` is valid and the bot is added to `GROUP_CHAT_ID` as admin
- [ ] Verify `MINI_APP_URL` is the public HTTPS URL (Telegram requires HTTPS)
- [ ] Run `npm run build` inside `miniapp/` to generate `miniapp/dist/`
- [ ] Ensure `backend/backups/` directory exists and is writable
- [ ] Run database migrations via `db.init_db()` on first deploy
- [ ] Verify no `.db` files are committed to git (`.gitignore` covers `*.db`)
- [ ] Test `/health` endpoint returns `{"status": "ok"}`
- [ ] Test `/api/debug/config` endpoint (admin only) returns safe config without secrets
- [ ] Verify admin panel loads correctly and broadcast tab is hidden when `BROADCAST_ENABLED=false`

## Running

```bash
# Terminal 1: Backend API + Bot
cd backend
python bot.py

# Terminal 2: Frontend dev (optional, for local testing)
cd miniapp
npm run dev
```

## Security Notes

- `ALLOW_DEV_AUTH` must remain `false` in production
- `BROADCAST_ENABLED` is `false` by default
- The `/api/debug/config` endpoint only exposes non-sensitive config values
- All API routes (except `/health`) require Telegram initData verification or admin auth
