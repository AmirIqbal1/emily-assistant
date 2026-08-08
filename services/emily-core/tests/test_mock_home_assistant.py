from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.mock_home_assistant import MockHomeAssistantBackend


def make_mock_client(control_enabled: bool = True) -> TestClient:
    return TestClient(
        create_app(
            Settings(
                home_assistant_mock=True,
                home_assistant_control_enabled=control_enabled,
            )
        )
    )


def test_status_is_healthy_without_real_home_assistant() -> None:
    with TestClient(create_app(Settings(home_assistant_token=""))) as client:
        response = client.get("/api/status")
    assert response.status_code == 200
    assert response.json()["home_assistant"]["connected"] is False
    assert response.json()["home_assistant_token_configured"] is False


def test_mock_status_and_entities_are_explicit_and_safe() -> None:
    with make_mock_client() as client:
        status = client.get("/api/status")
        entities = client.get("/api/entities?search=office")
    assert status.json()["home_assistant_mock"] is True
    assert status.json()["home_assistant"]["mode"] == "mock"
    assert status.json()["home_assistant_control_enabled"] is True
    assert status.json()["entity_count"] == 6
    assert entities.json()["count"] == 2
    assert {entity["entity_id"] for entity in entities.json()["entities"]} == {
        "switch.office_fan", "sensor.office_temperature"
    }


def test_mock_state_changes_persist_for_chat_and_refresh() -> None:
    with make_mock_client() as client:
        assert client.get("/api/entities").json()["count"] == 6
        turn_on = client.post("/api/chat", json={"message": "turn on kitchen ceiling"})
        state = client.post("/api/chat", json={"message": "is kitchen ceiling on?"})
        brightness = client.post(
            "/api/chat", json={"message": "set bedroom lamp brightness to 50 percent"}
        )
        volume = client.post("/api/chat", json={"message": "volume living room tv to 30%"})
        pause = client.post("/api/chat", json={"message": "pause living room tv"})
        refreshed = client.post("/api/entities/refresh")
    assert turn_on.json()["success"] is True
    assert turn_on.json()["target"] == "light.kitchen_ceiling"
    assert state.json()["reply"] == "Kitchen Ceiling is on."
    assert brightness.json()["reply"] == "Bedroom Lamp brightness set to 50%."
    assert volume.json()["reply"] == "Living Room TV volume set to 30%."
    assert pause.json()["reply"] == "Living Room TV paused."
    bedroom_lamp = next(entity for entity in refreshed.json()["entities"] if entity["entity_id"] == "light.bedroom_lamp")
    assert bedroom_lamp["attributes"]["brightness"] == 128


def test_mock_toggle_off_and_media_play_work() -> None:
    with make_mock_client() as client:
        toggle = client.post("/api/chat", json={"message": "toggle bedroom lamp"})
        off = client.post("/api/chat", json={"message": "turn bedroom lamp off"})
        play = client.post("/api/chat", json={"message": "resume living room tv"})
    assert toggle.json()["success"] is True
    assert off.json()["success"] is True
    assert play.json()["reply"] == "Living Room TV playing."


def test_mock_respects_control_disabled_and_blocks_lock_commands() -> None:
    with make_mock_client(control_enabled=False) as client:
        disabled = client.post("/api/chat", json={"message": "turn on kitchen ceiling"})
        query = client.post("/api/chat", json={"message": "is front door locked?"})
    assert disabled.json()["success"] is False
    assert "control is disabled" in disabled.json()["reply"]
    assert query.json()["reply"] == "Front Door is locked."

    with make_mock_client() as client:
        blocked = client.post("/api/chat", json={"message": "unlock front door"})
        arbitrary = client.post("/api/chat", json={"message": "call service light turn_on kitchen ceiling"})
    assert blocked.json()["success"] is False
    assert "security-sensitive lock control" in blocked.json()["reply"]
    assert arbitrary.json()["intent"] == "unknown"


async def test_mock_backend_rejects_unallowlisted_service() -> None:
    backend = MockHomeAssistantBackend()
    from app.home_assistant import HomeAssistantError
    import pytest

    with pytest.raises(HomeAssistantError):
        await backend.call_service("lock", "unlock", {"entity_id": "lock.front_door"})
