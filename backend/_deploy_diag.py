# _deploy_diag.py
# TEMPORARY build-diagnostic helper. Reads a log file and writes it to a
# scratch table in DATABASE_URL so build failures can be debugged when
# Render's API does not expose build logs. Delete after use.
import os
import sys
import psycopg2

path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/b.log"
try:
    with open(path, "r", errors="replace") as f:
        body = f.read()
except Exception as e:  # noqa: BLE001
    body = f"could not read {path}: {e}"

body = body[-16000:]
print(f"[diag] captured {len(body)} chars from {path}")

try:
    conn = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS hb_deploy_diag "
        "(id serial primary key, ts timestamptz default now(), log text)"
    )
    cur.execute("INSERT INTO hb_deploy_diag (log) VALUES (%s)", (body,))
    conn.close()
    print("[diag] uploaded to hb_deploy_diag")
except Exception as e:  # noqa: BLE001
    print(f"[diag] upload failed: {e}")
