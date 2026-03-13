import os
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_poles")

def migrate():
    db_path = "terminal_frontier.db"
    if not os.path.exists(db_path):
        logger.error(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Update Agent positions
    logger.info("Migrating agents from r=1 to r=0 and r=99 to r=100...")
    cursor.execute("UPDATE agents SET q = 0, r = 0 WHERE r = 1")
    cursor.execute("UPDATE agents SET q = 0, r = 100 WHERE r = 99")
    logger.info(f"Agents migrated: {cursor.rowcount}")

    # 2. Consolidate Polar Hexes
    logger.info("De-duplicating polar hexes (r=0, 1, 99, 100)...")
    
    # Keep only (0,0) and (0,100)
    cursor.execute("DELETE FROM world_hexes WHERE r = 1 OR r = 99")
    logger.info(f"Redundant ring hexes deleted: {cursor.rowcount}")
    
    cursor.execute("DELETE FROM world_hexes WHERE (r = 0 OR r = 100) AND q != 0")
    logger.info(f"Redundant pole hexes deleted: {cursor.rowcount}")

    # 3. Relocate Stations
    NEW_STATIONS = {
        (0, 0): "STATION_HUB",
        (25, 2): "SMELTER",
        (50, 2): "CRAFTER",
        (75, 2): "REPAIR",
        (0, 3): "REFINERY"
    }

    logger.info("Resetting station flags...")
    cursor.execute("UPDATE world_hexes SET is_station = 0, station_type = NULL")

    for (q, r), s_type in NEW_STATIONS.items():
        logger.info(f"Setting {s_type} at ({q}, {r})...")
        # Check if hex exists, if not, create it (procedural generation fallback usually handles this, but let's be safe)
        cursor.execute("SELECT id FROM world_hexes WHERE q = ? AND r = ?", (q, r))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE world_hexes SET is_station = 1, station_type = ? WHERE q = ? AND r = ?", (s_type, q, r))
        else:
            # Need a sector_id. In seed_world, sq = q // 10, sr = r // 10
            sq, sr = q // 10, r // 10
            cursor.execute("SELECT id FROM sectors WHERE q = ? AND r = ?", (sq, sr))
            sector_row = cursor.fetchone()
            if not sector_row:
                cursor.execute("INSERT INTO sectors (q, r, name) VALUES (?, ?, ?)", (sq, sr, f"Sector {sq}:{sr}"))
                sector_id = cursor.lastrowid
            else:
                sector_id = sector_row[0]
            
            # Simple insertion with neutral terrain
            cursor.execute("""
                INSERT INTO world_hexes (sector_id, q, r, terrain_type, is_station, station_type)
                VALUES (?, ?, ?, 'VOID', 1, ?)
            """, (sector_id, q, r, s_type))

    conn.commit()
    conn.close()
    logger.info("Migration complete!")

if __name__ == "__main__":
    migrate()
