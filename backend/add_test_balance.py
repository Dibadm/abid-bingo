import sqlite3
import os

# Absolute path to the database file where your main server creates it
DB_ABSOLUTE_PATH = r"C:\Users\Ashara\Desktop\New folder\habesha_bet.db"
TEST_BALANCE = 5000.0

def give_test_balance_absolute():
    print(f"🔄 Connecting to absolute database path: {DB_ABSOLUTE_PATH}")
    
    # Fallback check: if it's not in the root folder, check the backend folder
    path_to_use = DB_ABSOLUTE_PATH
    if not os.path.exists(path_to_use):
        path_to_use = r"C:\Users\Ashara\Desktop\New folder\backend\habesha_bet.db"
        print(f"⚠️ Root file not found, switching to backend path: {path_to_use}")

    if not os.path.exists(path_to_use):
        print("❌ Error: Could not find your database file anywhere!")
        return

    conn = sqlite3.connect(path_to_use)
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE users SET balance = ?", (TEST_BALANCE,))
        conn.commit()
        print(f"💰 Success! Set balance to {TEST_BALANCE} ETB for all ({cursor.rowcount}) accounts in {path_to_use}.")
    except Exception as e:
        print(f"❌ Database error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    give_test_balance_absolute()