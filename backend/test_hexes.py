import os
os.environ["DATABASE_URL"] = "sqlite:///./strike_vector.db"
from sqlalchemy import select
from database import SessionLocal
from models import WorldHex

db = SessionLocal()
stations = db.execute(select(WorldHex).where(WorldHex.is_station == True)).scalars().all()
print(f"Stations found via boolean == True: {len(stations)}")

stations2 = db.execute(select(WorldHex).where(WorldHex.station_type != None)).scalars().all()
print(f"Stations found via station_type != None: {len(stations2)}")

if len(stations2) > 0:
    s = stations2[0]
    print(f"Station example: is_station={s.is_station}, type={type(s.is_station)}, station_type={s.station_type}")
