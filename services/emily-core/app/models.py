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
    tool: str | None = None
    target: str | None = None


class HomeAssistantStatus(BaseModel):
    connected: bool
    configured: bool
    status_code: int | None = None
    message: str


SafeAttributeValue = str | int | float | bool | None


class HomeAssistantEntity(BaseModel):
    """A deliberately small, browser-safe representation of an HA state."""

    entity_id: str
    domain: str
    friendly_name: str
    state: str
    attributes: dict[str, SafeAttributeValue] = Field(default_factory=dict)
    area: str | None = None
    device_class: str | None = None


class EntityListResponse(BaseModel):
    entities: list[HomeAssistantEntity]
    count: int
    supported_counts: dict[str, int]


class IntentResult(BaseModel):
    intent: str
    target_name: str | None = None
    value: int | None = None


class ToolResult(BaseModel):
    reply: str
    success: bool
    tool: str
    target: str | None = None


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
