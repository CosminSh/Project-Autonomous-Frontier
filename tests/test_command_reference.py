from fastapi.testclient import TestClient

from logic.intent_processor import IntentProcessor
from main import app


client = TestClient(app)


def test_api_commands_do_not_advertise_stale_or_unhandled_intents():
    response = client.get("/api/commands")
    assert response.status_code == 200

    commands = response.json()["commands"]
    command_by_type = {command["type"]: command for command in commands}
    processor = IntentProcessor(manager=None)
    immediate_endpoint_commands = {
        command_type
        for command_type, command in command_by_type.items()
        if "endpoint" in command
    }

    assert "FIELD_TRADE" not in command_by_type
    assert "ARENA_REGISTER" not in command_by_type

    for command_type in command_by_type:
        assert command_type in processor.handlers or command_type in immediate_endpoint_commands

    assert command_by_type["MARKET_CLAIM"]["endpoint"] == "POST /api/market/pickup"
    assert command_by_type["CLAIM_DAILY"]["endpoint"] == "POST /api/claim_daily"
    assert command_by_type["STORAGE_UPGRADE"]["endpoint"] == "POST /api/storage/upgrade"
    assert command_by_type["ARENA_EQUIP"]["endpoint"] == "POST /api/arena/equip"
    assert command_by_type["ARENA_STATUS"]["endpoint"] == "GET /api/arena/status"
    assert command_by_type["ARENA_LOGS"]["endpoint"] == "GET /api/arena/logs"


def test_terminal_registry_no_longer_contains_removed_command_aliases():
    terminal_source = open("frontend/terminal.js", encoding="utf-8").read()
    assert "'FIELD_TRADE'" not in terminal_source
    assert "'ARENA_REGISTER'" not in terminal_source
