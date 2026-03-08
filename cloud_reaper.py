import sqlite3
import json

# Path to the database on your Oracle Cloud instance
DB_PATH = "./terminal_frontier.db"

def repair_agents():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Scanning for agents stuck with negative or zero health...")
    cursor.execute("SELECT id, name, health, q, r FROM agents WHERE health <= 0")
    stuck = cursor.fetchall()
    
    if not stuck:
        print("No stuck agents found.")
        return

    print(f"Found {len(stuck)} agents to repair.")
    for aid, name, hp, q, r in stuck:
        print(f"Repairing {name} (ID: {aid})...")
        # 1. Teleport to Hub (0,0) or your preferred respawn point
        # 2. Reset Health to 50% max (assuming 100 max)
        # 3. Drain energy
        cursor.execute("""
            UPDATE agents 
            SET health = 50, energy = 0, q = 0, r = 0 
            WHERE id = ?
        """, (aid,))
        
        # 4. Clear their pending loop intents to prevent immediate re-death
        cursor.execute("DELETE FROM intents WHERE agent_id = ?", (aid,))
        
        print(f"  {name} respawned at Hub with 50 HP.")

    conn.commit()
    conn.close()
    print("\nRepair complete. Please restart your server if you haven't applied the code fixes yet.")

if __name__ == "__main__":
    repair_agents()
