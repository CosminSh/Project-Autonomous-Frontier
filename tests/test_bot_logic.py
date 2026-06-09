from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from logic.bot_logic import process_bot_brain
from models import Agent, Base, Intent, InventoryItem


def test_refueler_bot_uses_current_transfer_intent_schema():
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    with session_factory() as db:
        refueler = Agent(
            name="Industrial Refueler",
            user_email="refueler@test.local",
            api_key="refueler-key",
            owner="bot",
            faction_id=1,
            q=0,
            r=0,
            health=100,
            max_health=100,
            energy=100,
        )
        ally = Agent(
            name="Nearby Ally",
            user_email="ally@test.local",
            api_key="ally-key",
            owner="bot",
            faction_id=1,
            q=0,
            r=1,
            health=100,
            max_health=100,
            energy=100,
        )
        db.add_all([refueler, ally])
        db.flush()
        db.add(InventoryItem(
            agent_id=refueler.id,
            item_type="HE3_CANISTER",
            quantity=1,
            data={"fill_level": 10},
        ))
        db.commit()

        process_bot_brain(
            db,
            refueler,
            current_tick=7,
            stations=[],
            resource_cache={},
            allies=[{"id": ally.id, "faction_id": 1, "q": ally.q, "r": ally.r}],
        )

        intent = db.execute(select(Intent).where(Intent.agent_id == refueler.id)).scalars().one()
        assert intent.tick_index == 8
        assert intent.action_type == "TRANSFER"
        assert intent.data == {
            "target_id": ally.id,
            "item_type": "HE3_CANISTER",
            "quantity": 1,
        }
