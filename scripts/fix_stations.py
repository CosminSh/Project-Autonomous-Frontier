import sys
sys.path.append('backend')
from database import SessionLocal
from models import WorldHex
from sqlalchemy import select

def fix_stations():
    db = SessionLocal()
    
    stations = [
        (0, 0, "MARKET"),
        (10, 0, "SMELTER"),
        (0, 10, "CRAFTER"),
        (-10, 0, "REPAIR"),
        (0, -10, "REFINERY")
    ]
    
    for q, r, st_type in stations:
        hexes = db.execute(select(WorldHex).where(WorldHex.q == q, WorldHex.r == r)).scalars().all()
        if not hexes:
            h = WorldHex(
                sector_id=1,
                q=q, r=r,
                terrain_type="STATION",
                is_station=True,
                station_type=st_type
            )
            db.add(h)
        else:
            h = hexes[0]
            h.terrain_type = "STATION"
            h.is_station = True
            h.station_type = st_type
            
    db.commit()
    print("Stations fixed!")

if __name__ == "__main__":
    fix_stations()
