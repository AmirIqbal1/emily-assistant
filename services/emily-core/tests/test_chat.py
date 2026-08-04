from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import MAX_CHAT_MESSAGE_LENGTH


def make_client() -> TestClient:
    return TestClient(create_app(Settings(emily_name="Emily")))


def test_greeting_intent() -> None:
    with make_client() as client:
        response = client.post("/api/chat", json={"message": "Hello Emily"})

    assert response.status_code == 200
    assert response.json() == {
        "reply": "Hello. I’m Emily.",
        "intent": "greeting",
        "provider": "local",
        "success": True,
    }


def test_name_question() -> None:
    with make_client() as client:
        response = client.post("/api/chat", json={"message": "What is your name?"})

    assert response.status_code == 200
    assert response.json()["intent"] == "name"
    assert response.json()["reply"] == "My name is Emily."


def test_empty_message_is_rejected() -> None:
    with make_client() as client:
        response = client.post("/api/chat", json={"message": "   "})

    assert response.status_code == 422


def test_overly_long_message_is_rejected() -> None:
    with make_client() as client:
        response = client.post(
            "/api/chat",
            json={"message": "x" * (MAX_CHAT_MESSAGE_LENGTH + 1)},
        )

    assert response.status_code == 422

