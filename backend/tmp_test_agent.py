from models import Agent, Base, engine, sessionmaker
Session = sessionmaker(bind=engine)
session = Session()

try:
    a = Agent(name="test", health=80, is_bot=True)
    print(a.health)
except Exception as e:
    print(repr(e))
