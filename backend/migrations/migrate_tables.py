import os
from sqlalchemy import create_engine
from models import Base

def migrate_tables():
    db_files = [f for f in os.listdir('.') if f.endswith('.db')]
    
    for db_path in db_files:
        print(f"Checking missing tables for {db_path}...")
        engine = create_engine(f"sqlite:///{db_path}")
        
        try:
            # create_all only creates tables that do not exist yet.
            # It will NOT overwrite or drop existing tables.
            Base.metadata.create_all(bind=engine)
            print(f"  Successfully verified/created missing tables for {db_path}.")
        except Exception as e:
            print(f"  Error checking {db_path}: {e}")

if __name__ == '__main__':
    migrate_tables()
    print("Table migration check completed.")
