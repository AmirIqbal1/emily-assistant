from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(**settings: object) -> TestClient:
    return TestClient(create_app(Settings(music_assistant_mock=True, **settings)))


def test_mock_music_playback_is_stateful() -> None:
    with make_client(music_assistant_default_player="Living Room Speaker") as client:
        play = client.post("/api/chat", json={"message": "play Wonderwall"})
        now_playing = client.post("/api/chat", json={"message": "what song is playing in living room"})
        pause = client.post("/api/chat", json={"message": "pause the music in living room"})

    assert play.json()["provider"] == "music_assistant"
    assert play.json()["success"] is True
    assert "Wonderwall by Oasis" in now_playing.json()["reply"]
    assert pause.json()["success"] is True


def test_music_player_api_is_safe_and_reports_mock_mode() -> None:
    with make_client() as client:
        response = client.get("/api/music/players")
        status = client.get("/api/music/status")

    assert response.status_code == 200
    assert response.json()["count"] == 3
    assert all("token" not in player for player in response.json()["players"])
    assert status.json()["mode"] == "mock"


def test_multiple_players_require_a_choice() -> None:
    with make_client() as client:
        response = client.post("/api/chat", json={"message": "play Wonderwall"})

    assert response.json()["success"] is False
    assert "more than one music player" in response.json()["reply"]


def test_music_control_switch_blocks_mutations() -> None:
    with make_client(music_assistant_control_enabled=False, music_assistant_default_player="Living Room Speaker") as client:
        response = client.post("/api/chat", json={"message": "play Wonderwall"})
        players = client.post("/api/chat", json={"message": "what speakers are available"})

    assert response.json()["reply"] == "Music Assistant control is disabled."
    assert players.json()["success"] is True


def test_unavailable_mock_player_is_rejected_explicitly() -> None:
    with make_client() as client:
        response = client.post("/api/chat", json={"message": "play Wonderwall in the car"})

    assert response.json()["success"] is False
    assert response.json()["reply"] == "The Car player is currently unavailable."
