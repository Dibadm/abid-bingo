import sqlite3

db_path = "habesha_bet.db"
print(f"Connecting directly to: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Let's see what rooms are actually inside the table right now
    cursor.execute("SELECT id, state FROM games")
    rows = cursor.fetchall()
    
    print("\n--- Current Rooms in Database ---")
    if not rows:
        print("The games table is completely empty!")
    for row in rows:
        print(f"Room ID: {row['id']} | Current State Value: '{row['state']}'")
    print("---------------------------------\n")
    
    # 2. Force change ALL rooms to a finished state ('cancelled' or 'finished' or 2 depending on your schema)
    # We will try setting it to 'cancelled'. If your system uses numbers, change 'cancelled' to 2 or 3.
    cursor.execute("UPDATE games SET state = 'cancelled'")
    conn.commit()
    print(f"🧹 Force-updated {cursor.rowcount} total rooms to 'cancelled'.")
    
    conn.close()
except Exception as e:
    print(f"⚠️ Error running inspection: {e}")