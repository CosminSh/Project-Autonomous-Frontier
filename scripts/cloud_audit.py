import sqlite3
import json

# Path to the database on your Oracle Cloud instance
DB_PATH = "./terminal_frontier.db"
AGENT_ID = 15 # Your reported Agent ID

def audit_combat():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print(f"Scanning ALL logs for interactions with Agent ID {AGENT_ID}...")
    
    # 1. Search for items where your agent was the target
    # In COMBAT_HIT, the details look like: {"target_id": 15, "damage": 10, "log": [...]}
    cursor.execute("""
        SELECT id, agent_id, event_type, details, time 
        FROM audit_logs 
        WHERE details LIKE ? 
        ORDER BY id DESC 
        LIMIT 100
    """, (f'%{AGENT_ID}%',))
    
    attacker_logs = cursor.fetchall()
    
    if not attacker_logs:
        print("No external attacks found in the last 100 relative logs.")
    else:
        print(f"\nFound {len(attacker_logs)} incoming interactions:")
        for log_id, attacker_id, event, details_json, ts in attacker_logs:
            details = json.loads(details_json)
            # Verify if it's actually an attack on our target
            if details.get("target_id") == AGENT_ID or str(details.get("target_id")) == str(AGENT_ID):
                print(f"[{ts}] Agent {attacker_id} -> {event}: {details.get('damage', 0)} DMG")
                if "log" in details:
                    print(f"      Combat Log: {details['log'][-1]}") # Show last round

    conn.close()

if __name__ == "__main__":
    audit_combat()
