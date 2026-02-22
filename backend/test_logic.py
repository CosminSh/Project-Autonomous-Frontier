import requests
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Agent, ChassisPart, WorldHex, AuctionOrder, Intent, AuditLog

DATABASE_URL = "postgresql://admin:password@localhost:5432/strike_vector"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def verify():
    # 1. Seed Data
    with SessionLocal() as db:
        print("Seeding test data...")
        # Clear existing
        db.query(Intent).delete()
        db.query(ChassisPart).delete()
        db.query(AuditLog).delete()
        db.query(Agent).delete()
        db.query(WorldHex).delete()
        db.query(AuctionOrder).delete()
        
        # Add Agent
        agent = Agent(id=1, owner="tester", name="Unit-01", q=0, r=0, kinetic_force=20)
        db.add(agent)
        
        # Add Part (Drill)
        drill = ChassisPart(agent_id=1, part_type="Actuator", name="Titanium Drill", stats={"bonus_str": 5})
        db.add(drill)
        
        # Add Resource Node
        gold_node = WorldHex(q=1, r=0, terrain_type="PERIMETER", resource_type="ORE", resource_density=1.5)
        db.add(gold_node)
        
        # Add Auction Order
        order = AuctionOrder(item_type="Iron Ingot", order_type="SELL", quantity=10, price=150.0)
        db.add(order)
        
        db.commit()

    # 2. Test Movement Intent
    print("Testing MOVE intent...")
    resp = requests.post("http://localhost:8000/intent/1?action_type=MOVE", json={"target_q": 1, "target_r": 0})
    print(f"Submit Intent Response: {resp.json()}")

    print("Waiting for heartbeat (5s)...")
    time.sleep(7)

    # 3. Verify Movement & Energy
    resp = requests.get("http://localhost:8000/perception/1")
    perception = resp.json()
    print(f"Perception Packet: {perception}")
    
    status = perception['content']['agent_status']
    loc = status['location']
    energy = status['capacitor']
    
    if loc['q'] == 1 and loc['r'] == 0:
        print(f"✅ Movement Successful! Current Energy: {energy}")
        if energy == 95: # 100 - 5
             print("✅ Energy Deduction Correct!")
        else:
             print(f"❌ Energy Deduction Incorrect! Expected 95, got {energy}")
    else:
        print(f"❌ Movement Failed! Agent is at {loc}")

    # 4. Test Mining Intent (Now that agent is on the node)
    print("Testing MINE intent...")
    resp = requests.post("http://localhost:8000/intent/1?action_type=MINE", json={})
    print("Waiting for heartbeat (5s)...")
    time.sleep(7)

    # 5. Check Audit Logs for Mining & Energy
    with SessionLocal() as db:
        agent = db.get(Agent, 1)
        logs = db.query(AuditLog).all()
        if any(log.event_type == "MINING" for log in logs):
            print(f"✅ Mining Successful! Current Energy: {agent.capacitor}")
            if agent.capacitor == 87: # 95 - 10 + 2 (recharge)
                print("✅ Mining Energy & Recharge Correct!")
            else:
                print(f"❌ Energy Calculation Incorrect! Expected 87, got {agent.capacitor}")
            for log in logs:
                print(f"Log: {log.event_type} - {log.details}")
        else:
            print("❌ Mining Failed! No logs found.")

if __name__ == "__main__":
    verify()
