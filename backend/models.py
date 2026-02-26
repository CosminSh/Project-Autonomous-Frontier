from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON, BigInteger, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, unique=True, index=True)
    api_key = Column(String, unique=True, index=True)
    owner = Column(String, index=True)
    name = Column(String, unique=True, index=True)
    
    # Primary Stats
    structure = Column(Integer, server_default="100")
    max_structure = Column(Integer, server_default="100")
    capacitor = Column(Integer, server_default="100")
    kinetic_force = Column(Integer, server_default="10")
    logic_precision = Column(Integer, server_default="10")
    overclock = Column(Integer, server_default="10")
    integrity = Column(Integer, server_default="5")
    max_mass = Column(Float, server_default="100.0")
    
    # Coordinates (Hex Grid q, r)
    q = Column(Integer, default=0)
    r = Column(Integer, default=0)
    
    is_bot = Column(Boolean, server_default="0")
    is_feral = Column(Boolean, server_default="0")
    is_aggressive = Column(Boolean, server_default="0")
    faction_id = Column(Integer, nullable=True)
    heat = Column(Integer, server_default="0")
    overclock_ticks = Column(Integer, server_default="0")
    wear_and_tear = Column(Float, server_default="0.0")
    last_faction_change_tick = Column(Integer, server_default="0")
    unlocked_recipes = Column(JSON, nullable=True) # List of strings: ["DRILL_UNIT", "ENGINE_UNIT"]
    
    # Relationships
    parts = relationship("ChassisPart", back_populates="agent")
    intents = relationship("Intent", back_populates="agent")
    inventory = relationship("InventoryItem", back_populates="agent")

class ChassisPart(Base):
    __tablename__ = "chassis_parts"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    part_type = Column(String) # Actuator, Sensor, Processor, Frame
    slot_index = Column(Integer) # For parts like Actuators (0, 1)
    name = Column(String)
    rarity = Column(String, server_default="STANDARD") # SCRAP, STANDARD, REFINED, PRIME, RELIC
    stats = Column(JSON) # Base stats provided by this part template
    affixes = Column(JSON, nullable=True) # Randomized bonuses (e.g., {"bonus_str": 5})
    
    agent = relationship("Agent", back_populates="parts")

class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    item_type = Column(String) # IRON_ORE, CREDITS, etc.
    quantity = Column(Integer, default=1)
    data = Column(JSON, nullable=True) # Metadata (e.g., {"fill_level": 50})

    agent = relationship("Agent", back_populates="inventory")

class Sector(Base):
    __tablename__ = "sectors"
    id = Column(Integer, primary_key=True, index=True)
    q = Column(Integer, index=True)
    r = Column(Integer, index=True)
    name = Column(String)

class WorldHex(Base):
    __tablename__ = "world_hexes"

    id = Column(Integer, primary_key=True, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=True)
    q = Column(Integer, index=True)
    r = Column(Integer, index=True)
    terrain_type = Column(String) # VOID, NEBULA, ASTEROID, OBSTACLE
    resource_type = Column(String, nullable=True) # ORE, GAS, etc.
    resource_density = Column(Float, default=0.0)
    
    # Station attributes
    is_station = Column(Boolean, default=False)
    station_type = Column(String, nullable=True) # SMELTER, CRAFTER, MARKET, REPAIR
    
    sector = relationship("Sector")

class AuctionOrder(Base):
    __tablename__ = "auction_house"

    id = Column(Integer, primary_key=True, index=True)
    item_type = Column(String, index=True) # Raw Ore, Refined Ingot
    order_type = Column(String) # BUY, SELL
    quantity = Column(Integer)
    price = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner = Column(String)

class Intent(Base):
    __tablename__ = "intents"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    tick_index = Column(BigInteger, index=True)
    action_type = Column(String) # MOVE, MINE, ATTACK, TRADE
    data = Column(JSON) # e.g., {"target_q": 1, "target_r": 0}
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    agent = relationship("Agent", back_populates="intents")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    time = Column(DateTime(timezone=True), index=True, server_default=func.now())
    agent_id = Column(Integer, index=True)
    event_type = Column(String)
    details = Column(JSON)

class GlobalState(Base):
    __tablename__ = "global_state"
    
    id = Column(Integer, primary_key=True)
    tick_index = Column(BigInteger, default=0)
    phase = Column(String, default="PERCEPTION") # PERCEPTION, STRATEGY, CRUNCH
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
class Bounty(Base):
    __tablename__ = "bounties"
    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("agents.id"))
    reward = Column(Float)
    issuer = Column(String, default="Colonial Administration")
    is_open = Column(Boolean, default=True)

class LootDrop(Base):
    __tablename__ = "loot_drops"
    id = Column(Integer, primary_key=True, index=True)
    q = Column(Integer, index=True)
    r = Column(Integer, index=True)
    item_type = Column(String)
    quantity = Column(Integer)
