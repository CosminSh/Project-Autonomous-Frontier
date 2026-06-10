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
    assert command_by_type["LIST"]["range"] == "N/A"
    assert command_by_type["BUY"]["range"] == "N/A"
    assert command_by_type["MARKET_CLAIM"]["station_required"] == "MARKET or STATION_HUB"


def test_wiki_commands_are_projected_from_live_command_reference():
    live_response = client.get("/api/commands")
    wiki_response = client.get("/api/wiki/commands")

    assert live_response.status_code == 200
    assert wiki_response.status_code == 200

    live_commands = live_response.json()["commands"]
    wiki_commands = wiki_response.json()

    assert [command["type"] for command in wiki_commands] == [command["type"] for command in live_commands]
    for live, wiki in zip(live_commands, wiki_commands):
        assert wiki["desc"] == live["description"]
        if "endpoint" in live:
            assert wiki["endpoint"] == live["endpoint"]


def test_terminal_registry_no_longer_contains_removed_command_aliases():
    terminal_source = open("frontend/terminal.js", encoding="utf-8").read()
    command_source = open("frontend/terminal-commands.js", encoding="utf-8").read()

    assert "TERMINAL_COMMANDS" in terminal_source
    assert "Establish a new corporation" not in terminal_source
    assert "CORP_UPGRADE_PURCHASE" in command_source
    assert "Establish a new corporation" in command_source
    assert "'FIELD_TRADE'" not in terminal_source
    assert "'ARENA_REGISTER'" not in terminal_source
    assert "'FIELD_TRADE'" not in command_source
    assert "'ARENA_REGISTER'" not in command_source


def test_frontend_mission_renderer_uses_current_mission_schema():
    ui_source = open("frontend/ui.js", encoding="utf-8").read()

    assert ui_source.count("updateMissionsUI(missions)") == 1
    assert "current_quantity" in ui_source
    assert "required_quantity" in ui_source
    assert "game.api.turnInMission" in ui_source
    assert "submitIntent('TURN_IN'" not in ui_source
