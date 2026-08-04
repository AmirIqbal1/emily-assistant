from typing import Any

from pydantic import BaseModel, Field, field_validator


MAX_CHAT_MESSAGE_LENGTH = 1_000


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_CHAT_MESSAGE_LENGTH)

    @field_validator("message")
    @classmethod
    def message_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be empty")
        return value


class ChatResponse(BaseModel):
    reply: str
    intent: str
    provider: str
    success: bool


class HomeAssistantStatus(BaseModel):
    connected: bool
    configured: bool
    status_code: int | None = None
    message: str


class StatusResponse(BaseModel):
    version: str
    name: str
    home_assistant: HomeAssistantStatus
    home_assistant_token_configured: bool
    uptime_seconds: float
    server_time: str
    enabled_providers: list[str]


class ProviderContext(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)

