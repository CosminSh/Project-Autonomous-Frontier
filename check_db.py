import sqlite3
import os

DB_PATH = 'terminal_frontier.db'

def check_columns():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(agents);")
        columns = cursor.fetchall()
        for col in columns:
            print(col[1])
    except Exception as e:
        print(f"Error checking columns: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    check_columns()
