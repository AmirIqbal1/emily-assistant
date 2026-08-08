from typing import Any, Literal

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
    mode: Literal["real", "mock"] = "real"


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
    player_name: str | None = None
    media_type: Literal["track", "artist", "album", "playlist"] | None = None


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
    home_assistant_mock: bool
    home_assistant_control_enabled: bool
    entity_count: int
    uptime_seconds: float
    server_time: str
    enabled_providers: list[str]
    music_assistant: "MusicAssistantStatus"
    music_assistant_control_enabled: bool
    music_player_count: int
    music_default_player: str | None = None


class MusicAssistantStatus(BaseModel):
    connected: bool
    configured: bool
    message: str
    mode: Literal["real", "mock"] = "real"


class MusicPlayer(BaseModel):
    player_id: str
    name: str
    available: bool
    powered: bool = True
    state: str
    volume_percent: int
    current_item: str | None = None
    current_artist: str | None = None


class MusicItem(BaseModel):
    item_id: str
    name: str
    media_type: Literal["track", "artist", "album", "playlist"]
    artist: str | None = None
    album: str | None = None
    provider: str = "mock"
    uri: str | None = None


class MusicPlayersResponse(BaseModel):
    players: list[MusicPlayer]
    count: int


class MusicNowPlayingResponse(BaseModel):
    player: MusicPlayer | None = None


StatusResponse.model_rebuild()


class ProviderContext(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
