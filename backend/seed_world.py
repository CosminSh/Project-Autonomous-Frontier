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

# ─── Feral Templates by Zone ──────────────────────────────────────────────────
FERAL_TEMPLATES = {
    "passive_lvl1": {
        "name_prefix": "Feral-Drifter",
        "is_aggressive": False,
        "structure": 80, "max_structure": 80,
        "kinetic_force": 8, "logic_precision": 5,
        "part_name": "Scrap Claws", "part_stats": {"kinetic_force": 5},
        "loot": [("SCRAP_METAL", 3, 8)],
    },
    "mixed_lvl2": {
        "name_prefix": "Feral-Scrapper",
        "is_aggressive": True,
        "structure": 120, "max_structure": 120,
        "kinetic_force": 14, "logic_precision": 8,
        "part_name": "Rusty Blaster", "part_stats": {"kinetic_force": 12},
        "loot": [("SCRAP_METAL", 5, 12), ("ELECTRONICS", 1, 3, 0.4)],
    },
    "elite_lvl3": {
        "name_prefix": "Feral-Raider",
        "is_aggressive": True,
        "structure": 200, "max_structure": 200,
        "kinetic_force": 22, "logic_precision": 12,
        "part_name": "Plasma Cutter", "part_stats": {"kinetic_force": 20},
        "loot": [("SCRAP_METAL", 8, 20), ("ELECTRONICS", 2, 6, 0.6), ("IRON_INGOT", 1, 3, 0.3)],
    },
    "apex_lvl4": {
        "name_prefix": "Feral-Apex",
        "is_aggressive": True,
        "structure": 350, "max_structure": 350,
        "kinetic_force": 40, "logic_precision": 20,
        "part_name": "Quantum Shredder", "part_stats": {"kinetic_force": 35},
        "loot": [("SCRAP_METAL", 10, 30), ("ELECTRONICS", 3, 8, 0.8), ("COBALT_ORE", 5, 15, 0.5)],
    },
}


def _spawn_feral(db, template_key: str, q: int, r: int, index: int):
    t = FERAL_TEMPLATES[template_key]
    feral = Agent(
        name=f"{t['name_prefix']}-{index}",
        q=q, r=r,
        is_bot=True, is_feral=True,
        is_aggressive=t["is_aggressive"],
        kinetic_force=t["kinetic_force"],
        logic_precision=t["logic_precision"],
        structure=t["structure"],
        max_structure=t["max_structure"],
        capacitor=100,
    )
    db.add(feral)
    db.flush()
    db.add(ChassisPart(
        agent_id=feral.id,
        part_type="Actuator",
        name=t["part_name"],
        stats=t["part_stats"]
    ))
    for loot in t["loot"]:
        item_type, qty_min, qty_max = loot[0], loot[1], loot[2]
        drop_chance = loot[3] if len(loot) > 3 else 1.0
        if random.random() < drop_chance:
            db.add(InventoryItem(agent_id=feral.id, item_type=item_type, quantity=random.randint(qty_min, qty_max)))


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
    logger.info("Wiping world map (Truncating hexes/sectors)...")
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
            is_bot=True, capacitor=100,
            structure=100, max_structure=100
        )
        db.add(bot)
        db.flush()
        db.add(InventoryItem(agent_id=bot.id, item_type="CREDITS", quantity=500))
        drill_def = PART_DEFINITIONS.get("DRILL_UNIT")
        db.add(ChassisPart(agent_id=bot.id, part_type="Actuator", name=drill_def["name"], stats=drill_def["stats"]))

    # ── Spawn Ferals by Zone ──────────────────────────────────────────────────
    logger.info("Spawning feral AIs by tier zone...")

    # Zone 1: Passive ferals, dist 6-15 (Iron Belt)
    for i in range(10):
        q = random.randint(0, 99)
        r = random.randint(6, 15)
        _spawn_feral(db, "passive_lvl1", q, r, i)

    # Zone 2: Mixed ferals (50% aggressive), dist 16-30 (Copper Belt)
    for i in range(12):
        q = random.randint(0, 99)
        r = random.randint(16, 30)
        template = "mixed_lvl2" if i >= 6 else "passive_lvl1"
        _spawn_feral(db, template, q, r, 100 + i)

    # Zone 3: Elite mostly-aggressive ferals, dist 31-50 (Gold Fields)
    for i in range(8):
        q = random.randint(0, 99)
        r = random.randint(31, 50)
        _spawn_feral(db, "elite_lvl3", q, r, 200 + i)

    # Zone 4: Apex ferals, dist 51+ (Deep Dark)
    for i in range(5):
        q = random.randint(0, 99)
        r = random.randint(55, 90)
        _spawn_feral(db, "apex_lvl4", q, r, 300 + i)

    db.commit()
    db.close()
    logger.info("World seeding complete!")


if __name__ == "__main__":
    seed_world()
