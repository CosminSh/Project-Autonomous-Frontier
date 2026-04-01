import sqlite3

def check_db(db_path):
    print(f"Checking {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(agents);")
        cols = cur.fetchall()
        has_squad = any(c[1] == 'squad_id' for c in cols)
        print(f"  squad_id exists in agents: {has_squad}")
        
        cur.execute("SELECT COUNT(*) FROM agents;")
        count = cur.fetchone()[0]
        print(f"  Total agents: {count}")
    except Exception as e:
        print(f"  Error: {e}")

check_db("terminal_frontier.db")
check_db("backend/terminal_frontier.db")
check_db("terminal_frontier.db")
