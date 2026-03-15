import sqlite3
import os

db_files = ["terminal_frontier.db", "strike_vector.db", "game.db", "verify.db"]

for db in db_files:
    if os.path.exists(db):
        try:
            conn = sqlite3.connect(db)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='corporations';")
            result = cursor.fetchone()
            if result:
                print(f"FOUND 'corporations' table in: {db}")
            conn.close()
        except:
            pass
