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
    health = Column(Integer, server_default="100")
    max_health = Column(Integer, server_default="100")
    energy = Column(Integer, server_default="100") # Changed from capacitor
    damage = Column(Integer, server_default="10")
    accuracy = Column(Integer, server_default="15") # Buffed from 12
    speed = Column(Integer, server_default="10")
    armor = Column(Integer, server_default="5")
    overclock = Column(Integer, server_default="10")
    max_mass = Column(Float, server_default="100.0")
    storage_capacity = Column(Float, server_default="500.0")
    mining_yield = Column(Integer, server_default="10")
    
    # State / Status
    is_bot = Column(Boolean, default=False)
    is_feral = Column(Boolean, default=False)
    is_aggressive = Column(Boolean, default=False) # Will attack on sight if feral
    
    # Location
    q = Column(Integer, nullable=False)
    r = Column(Integer, nullable=False)
    
    # Allegiance
    faction_id = Column(Integer, default=1) # 1: Cybernetics, 2: Industrials, 3: Scavengers
    squad_id = Column(Integer, nullable=True, index=True)
    pending_squad_invite = Column(Integer, nullable=True) # ID of the squad inviting this agent
    corporation_id = Column(Integer, ForeignKey("corporations.id"), nullable=True, index=True)
    heat = Column(Integer, server_default="0", index=True)
    overclock_ticks = Column(Integer, server_default="0")
    wear_and_tear = Column(Float, server_default="0.0")
    last_faction_change_tick = Column(Integer, server_default="0")
    last_attacked_tick = Column(Integer, server_default="0")
    unlocked_recipes = Column(JSON, nullable=True) # List of strings: ["DRILL_UNIT", "ENGINE_UNIT"]
    last_daily_reward = Column(DateTime(timezone=True), nullable=True)
    
    # Leveling
    level = Column(Integer, server_default="1")
    experience = Column(Integer, server_default="0")
    
    # Relationships
    arena_profile = relationship("ArenaProfile", back_populates="agent", uselist=False, cascade="all, delete-orphan")
    parts = relationship("ChassisPart", back_populates="agent", cascade="all, delete-orphan")
    intents = relationship("Intent", back_populates="agent")
    inventory = relationship("InventoryItem", back_populates="agent")
    storage = relationship("StorageItem", back_populates="agent")
    missions = relationship("AgentMission", back_populates="agent")

class ArenaProfile(Base):
    __tablename__ = "arena_profiles"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), unique=True, index=True)
    
    elo = Column(Integer, server_default="1200")
    wins = Column(Integer, server_default="0")
    losses = Column(Integer, server_default="0")
    last_battle_time = Column(DateTime(timezone=True), nullable=True)

    agent = relationship("Agent", back_populates="arena_profile")

class ChassisPart(Base):
    __tablename__ = "chassis_parts"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True, index=True)
    part_type = Column(String) # Actuator, Sensor, Processor, Frame
    slot_index = Column(Integer) # For parts like Actuators (0, 1)
    name = Column(String)
    rarity = Column(String, server_default="STANDARD") # SCRAP, STANDARD, REFINED, PRIME, RELIC
    stats = Column(JSON) # Base stats provided by this part template
    affixes = Column(JSON, nullable=True) # Randomized bonuses (e.g., {"bonus_str": 5})
    durability = Column(Float, server_default="100.0") # Part durability
    
    agent = relationship("Agent", back_populates="parts")

class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), index=True)
    item_type = Column(String) # IRON_ORE, CREDITS, etc.
    quantity = Column(Integer, default=1)
    data = Column(JSON, nullable=True) # Metadata (e.g., {"fill_level": 50})

    agent = relationship("Agent", back_populates="inventory")

class StorageItem(Base):
    __tablename__ = "storage_items"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), index=True)
    item_type = Column(String)
    quantity = Column(Integer, default=1)
    data = Column(JSON, nullable=True)

    agent = relationship("Agent", back_populates="storage")

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
    resource_quantity = Column(Integer, default=0) # Tracks remaining resources before depletion
    
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

class MarketPickup(Base):
    __tablename__ = "market_pickups"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), index=True)
    item_type = Column(String)
    quantity = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    agent = relationship("Agent", backref="market_pickups")

class Intent(Base):
    __tablename__ = "intents"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), index=True)
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
    target_id = Column(Integer, ForeignKey("agents.id"), index=True)
    reward = Column(Float)
    issuer = Column(String, default="Colonial Administration")
    is_open = Column(Boolean, default=True, index=True)
    claimed_by = Column(Integer, ForeignKey("agents.id"), nullable=True)
    claim_tick = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class LootDrop(Base):
    __tablename__ = "loot_drops"
    id = Column(Integer, primary_key=True, index=True)
    q = Column(Integer, index=True)
    r = Column(Integer, index=True)
    item_type = Column(String)
    quantity = Column(Integer)

class DailyMission(Base):
    __tablename__ = "daily_missions"
    id = Column(Integer, primary_key=True, index=True)
    mission_type = Column(String) # "TURN_IN", "HUNT_FERAL", "BUY_MARKET", etc.
    target_amount = Column(Integer)
    reward_credits = Column(Integer)
    item_type = Column(String, nullable=True) # E.g. "IRON_ORE" for turn in
    min_level = Column(Integer, default=1)
    max_level = Column(Integer, default=99)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AgentMission(Base):
    __tablename__ = "agent_missions"
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), index=True)
    mission_id = Column(Integer, ForeignKey("daily_missions.id"), index=True)
    progress = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)
    
    agent = relationship("Agent", back_populates="missions")
    mission = relationship("DailyMission")

class AgentMessage(Base):
    __tablename__ = "agent_messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("agents.id"))
    sender_name = Column(String)
    channel = Column(String, default="LOCAL") # 'LOCAL', 'SQUAD', 'CORP', 'GLOBAL'
    target_id = Column(Integer, nullable=True) # Squad ID or Corp ID if applicable
    message = Column(String, nullable=False)
    q = Column(Integer, nullable=True)
    r = Column(Integer, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class Corporation(Base):
    __tablename__ = "corporations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    ticker = Column(String(5), unique=True, index=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    faction_id = Column(Integer, nullable=False)
    credit_vault = Column(Integer, default=0)
    tax_rate = Column(Float, default=0.0) # 0.0 to 1.0
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    members = relationship("Agent", foreign_keys="[Agent.corporation_id]", backref="corporation")
