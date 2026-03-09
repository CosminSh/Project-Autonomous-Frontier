import os
import random
import logging
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from models import Base, Sector, WorldHex, Agent, InventoryItem, ChassisPart
from config import MAP_MIN_Q, MAP_MAX_Q, MAP_MIN_R, MAP_MAX_R, PART_DEFINITIONS
from game_helpers import get_hex_terrain_data

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./terminal_frontier.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

logger = logging.getLogger("seed_world")
logging.basicConfig(level=logging.INFO)

# ─── Feral Templates by Tier ────────────────────────────────────────────────
FERAL_TEMPLATES = {
    "tier1": {
        "name_prefix": "Feral-Drifter",
        "is_aggressive": False,
        "base_health": 80, "hp_scale": 10,
        "base_damage": 8, "dmg_scale": 2,
        "base_accuracy": 5, "base_speed": 10, "base_armor": 2,
        "part_name": "Scrap Claws",
        "loot": [("SYNTHETIC_WEAVE", 1, 3)],
        "rare_loot": "VOID_CHIP"
    },
    "tier2": {
        "name_prefix": "Feral-Scrapper",
        "is_aggressive": True,
        "base_health": 120, "hp_scale": 15,
        "base_damage": 14, "dmg_scale": 3,
        "base_accuracy": 8, "base_speed": 10, "base_armor": 5,
        "part_name": "Rusty Blaster",
        "loot": [("SCRAP_METAL", 3, 8), ("ELECTRONICS", 1, 2)],
        "rare_loot": "VOID_CHIP"
    },
    "tier3": {
        "name_prefix": "Feral-Raider",
        "is_aggressive": True,
        "base_health": 180, "hp_scale": 25,
        "base_damage": 20, "dmg_scale": 5,
        "base_accuracy": 12, "base_speed": 12, "base_armor": 10,
        "part_name": "Plasma Cutter",
        "loot": [("ELECTRONICS", 2, 5), ("FERAL_CORE", 1, 1, 0.4)],
        "rare_loot": "ANCIENT_CIRCUIT"
    },
    "tier4": {
        "name_prefix": "Feral-Apex",
        "is_aggressive": True,
        "base_health": 400, "hp_scale": 50,
        "base_damage": 50, "dmg_scale": 10,
        "base_accuracy": 20, "base_speed": 15, "base_armor": 20,
        "part_name": "Quantum Shredder",
        "loot": [("FERAL_CORE", 1, 3, 1.0)],
        "rare_loot": "ANCIENT_CIRCUIT"
    },
}

def _spawn_feral(db, tier_key: str, level: int, q: int, r: int, index: int):
    t = FERAL_TEMPLATES[tier_key]
    
    # Scale stats by level
    health = t["base_health"] + (level * t["hp_scale"])
    damage = t["base_damage"] + (level * t["dmg_scale"])
    
    feral = Agent(
        name=f"{t['name_prefix']}-L{level}-{index}",
        q=q, r=r,
        is_bot=True, is_feral=True,
        level=level,
        is_aggressive=t["is_aggressive"],
        damage=damage,
        accuracy=t["base_accuracy"] + (level // 2),
        speed=t["base_speed"] + (level // 5),
        armor=t["base_armor"] + (level // 3),
        health=health,
        max_health=health,
        energy=100,
    )
    db.add(feral)
    db.flush()
    
    db.add(ChassisPart(
        agent_id=feral.id,
        part_type="Actuator",
        name=t["part_name"],
        stats={"damage": damage // 2}
    ))
    
    # Standard Loot
    for loot in t["loot"]:
        item_type, qty_min, qty_max = loot[0], loot[1], loot[2]
        drop_chance = loot[3] if len(loot) > 3 else 1.0
        if random.random() < drop_chance:
            db.add(InventoryItem(agent_id=feral.id, item_type=item_type, quantity=random.randint(qty_min, qty_max)))
            
    # Rare Loot (5% constant)
    if t.get("rare_loot") and random.random() < 0.05:
        db.add(InventoryItem(agent_id=feral.id, item_type=t["rare_loot"], quantity=1))


def _random_pos_at_dist(target_dist: int, spread: int = 3):
    """Returns a random (q, r) in the axial range around a given distance from origin."""
    while True:
        r = random.randint(max(0, target_dist - spread), target_dist + spread)
        q = random.randint(0, 99)
        actual_dist = (abs(q) + abs(q + r) + abs(r)) // 2
        # Just use any position in a ring — the feral walker will keep it in zone
        return q % 100, r % 101


def seed_world():
    logger.info("Initializing tables (if not exist)...")
    Base.metadata.create_all(engine)
    db = SessionLocal()

    existing_hex_count = db.query(WorldHex).count()

    # ── Full re-seed: wipe old world, keep players ────────────────────────────
    logger.info("Wiping world map (Cleaning hexes/sectors)...")
    if DATABASE_URL.startswith("sqlite"):
        db.execute(text("DELETE FROM world_hexes"))
        db.execute(text("DELETE FROM sectors"))
    else:
        db.execute(text("TRUNCATE TABLE world_hexes, sectors CASCADE"))
    db.commit()

    logger.info("Wiping bots and resetting players...")
    # Delete all bots and ferals
    bots = db.execute(select(Agent).where(Agent.is_bot == True)).scalars().all()
    for bot in bots:
        db.execute(text(f"DELETE FROM chassis_parts WHERE agent_id = {bot.id}"))
        db.execute(text(f"DELETE FROM inventory_items WHERE agent_id = {bot.id}"))
        db.delete(bot)
    db.commit()

    # Teleport all real players back to Hub (0, 0)
    real_players = db.execute(select(Agent).where(Agent.is_bot == False)).scalars().all()
    for player in real_players:
        player.q = 0
        player.r = 0
        logger.info(f"Teleported player '{player.name}' to (0, 0)")
    db.commit()

    # ── Generate Sectors ──────────────────────────────────────────────────────
    logger.info("Generating sectors...")
    for sq in range(10):
        for sr in range(11):
            db.add(Sector(q=sq, r=sr, name=f"Sector {sq}:{sr}"))
    db.commit()

    # ── Generate World Hexes ─────────────────────────────────────────────────
    logger.info(f"Seeding Spherical World ({MAP_MAX_Q+1}x{MAP_MAX_R+1})...")
    for q in range(MAP_MIN_Q, MAP_MAX_Q + 1):
        for r in range(MAP_MIN_R, MAP_MAX_R + 1):
            data = get_hex_terrain_data(q, r)
            sq, sr = q // 10, r // 10
            sector = db.query(Sector).filter_by(q=sq, r=sr).first()
            if not sector:
                # Fallback if sector missing for some reason
                sector = Sector(q=sq, r=sr, name=f"Sector {sq}:{sr}")
                db.add(sector)
                db.flush()

            db.add(WorldHex(
                sector_id=sector.id,
                q=q, r=r,
                terrain_type=data["terrain_type"],
                resource_type=data["resource_type"],
                resource_density=data["resource_density"],
                resource_quantity=data["resource_quantity"],
                is_station=data["is_station"],
                station_type=data["station_type"]
            ))
        
        # Memory Optimization: Commit and clear session every slice
        db.commit() 
        logger.info(f"  Generated slice q={q}...")

    # ── Spawn Worker Bots (near Hub) ─────────────────────────────────────────
    logger.info("Spawning industrial bots near hub...")
    for i in range(5):
        q_off = random.choice([-1, 0, 1])
        r_off = random.choice([-1, 0, 1])
        bot = Agent(
            name=f"Worker-Bot-{i}",
            q=max(0, q_off), r=max(0, r_off),
            is_bot=True, energy=100,
            health=100, max_health=100
        )
        db.add(bot)
        db.flush()
        db.add(InventoryItem(agent_id=bot.id, item_type="CREDITS", quantity=500))
        drill_def = PART_DEFINITIONS.get("DRILL_UNIT")
        db.add(ChassisPart(agent_id=bot.id, part_type="Actuator", name=drill_def["name"], stats=drill_def["stats"]))

    # ── Spawn Ferals by Zone ──────────────────────────────────────────────────
    logger.info("Spawning tiered feral AIs...")

    # Zone 1: Tier 1, Levels 1-10, dist 6-15 (Iron Belt)
    for i in range(15):
        q = random.randint(0, 99)
        r = random.randint(6, 15)
        lvl = random.randint(1, 10)
        _spawn_feral(db, "tier1", lvl, q, r, i)

    # Zone 2: Tier 2, Levels 11-20, dist 16-30 (Copper Belt)
    for i in range(12):
        q = random.randint(0, 99)
        r = random.randint(16, 30)
        lvl = random.randint(11, 20)
        _spawn_feral(db, "tier2", lvl, q, r, 100 + i)

    # Zone 3: Tier 3, Levels 21-30, dist 31-50 (Gold Fields)
    for i in range(10):
        q = random.randint(0, 99)
        r = random.randint(31, 50)
        lvl = random.randint(21, 30)
        _spawn_feral(db, "tier3", lvl, q, r, 200 + i)

    # Zone 4: Tier 4, Levels 31-45, dist 51+ (Deep Dark)
    for i in range(8):
        q = random.randint(0, 99)
        r = random.randint(55, 90)
        lvl = random.randint(31, 45)
        _spawn_feral(db, "tier4", lvl, q, r, 300 + i)

    db.commit()
    db.close()
    logger.info("World seeding complete!")


if __name__ == "__main__":
    seed_world()
