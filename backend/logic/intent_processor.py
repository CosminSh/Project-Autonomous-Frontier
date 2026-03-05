import logging
from logic.actions import movement, mining, combat, industry, economy, utility, garage
from logic.mission_logic import handle_turn_in

logger = logging.getLogger("heartbeat.intent_processor")

class IntentProcessor:
    def __init__(self, manager):
        self.manager = manager
        # Action Mapping
        self.handlers = {
            "STOP": movement.handle_stop,
            "MOVE": movement.handle_move,
            "MINE": mining.handle_mine,
            "ATTACK": combat.handle_attack,
            "INTIMIDATE": combat.handle_intimidate,
            "LOOT": combat.handle_loot_attack,
            "DESTROY": combat.handle_destroy,
            "LIST": economy.handle_list,
            "BUY": economy.handle_buy,
            "CANCEL_ORDER": economy.handle_cancel,
            "SMELT": industry.handle_smelt,
            "REFINE_GAS": industry.handle_refine_gas,
            "CRAFT": industry.handle_craft,
            "REPAIR": industry.handle_repair,
            "RESTORE_HP": industry.handle_repair,
            "SALVAGE": industry.handle_salvage,
            "CORE_SERVICE": industry.handle_core_service,
            "RESET_WEAR": industry.handle_core_service,
            "CONSUME": utility.handle_consume,
            "DROP_LOAD": utility.handle_drop_load,
            "CHANGE_FACTION": utility.handle_change_faction,
            "LEARN_RECIPE": utility.handle_learn_recipe,
            "UPGRADE_GEAR": utility.handle_upgrade_gear,
            "EQUIP": garage.handle_equip,
            "UNEQUIP": garage.handle_unequip,
            "TURN_IN": handle_turn_in,
            "RESCUE": utility.handle_rescue,
            "RESCUE_STEP": utility.handle_rescue_step
        }

    async def process_intent(self, db, agent, intent, tick_count):
        """Dispatches an intent to the appropriate specialized handler."""
        handler = self.handlers.get(intent.action_type)
        if not handler:
            logger.warning(f"No handler registered for action: {intent.action_type}")
            return

        try:
            # Defensively normalize item string inputs
            if intent.data:
                for key in ["item_type", "ore_type"]:
                    val = intent.data.get(key)
                    if isinstance(val, str):
                        intent.data[key] = val.strip().upper().replace(" ", "_").replace("-", "_")

            # Execute action
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logger.debug(f"Processing {intent.action_type} for Agent {agent.id}")
            
            # Most handlers are async, some might be sync (like handle_stop)
            import inspect
            if inspect.iscoroutinefunction(handler):
                await handler(db, agent, intent, tick_count, self.manager)
            else:
                handler(db, agent, intent, tick_count)
                
        except Exception as e:
            logger.error(f"Error processing {intent.action_type} for Agent {agent.id}: {e}", exc_info=True)
            db.rollback()
