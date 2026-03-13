import sqlite3

def check_hexes():
    conn = sqlite3.connect('terminal_frontier.db')
    cursor = conn.cursor()
    
    print("Checking hexes at r=1:")
    cursor.execute("SELECT q, r, is_station, station_type FROM world_hexes WHERE r = 1")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    
    print("\nChecking hexes at r=99:")
    cursor.execute("SELECT q, r, is_station, station_type FROM world_hexes WHERE r = 99")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
        
    conn.close()

if __name__ == "__main__":
    check_hexes()
