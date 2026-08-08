from abc import ABC, abstractmethod
import time
from typing import Any

from app.models import MusicAssistantStatus, MusicItem, MusicPlayer


class MusicAssistantError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class MusicAssistantBackend(ABC):
    is_mock = False
    @property
    @abstractmethod
    def token_configured(self) -> bool: ...
    @abstractmethod
    async def check_connection(self) -> MusicAssistantStatus: ...
    @abstractmethod
    async def players(self) -> list[MusicPlayer]: ...
    @abstractmethod
    async def search(self, query: str, media_type: str | None = None) -> list[MusicItem]: ...
    @abstractmethod
    async def play(self, player_id: str, item: MusicItem) -> None: ...
    @abstractmethod
    async def command(self, player_id: str, command: str, value: int | None = None) -> None: ...
    async def close(self) -> None: pass


class RealMusicAssistantBackend(MusicAssistantBackend):
    """Optional adapter for the official music-assistant-client package.

    It intentionally exposes only Emily's fixed operations; no user text reaches
    the client command layer directly.
    """
    def __init__(self, url: str, token: str, cache_seconds: int = 30) -> None:
        self.url, self._token = url.rstrip("/"), token.strip()
        self._client: Any = None
        self._cache_seconds, self._search_cache = cache_seconds, {}
    @property
    def token_configured(self) -> bool: return bool(self._token)
    async def _client_or_error(self) -> Any:
        if not self._token: raise MusicAssistantError("Music Assistant requires authentication.")
        try:
            from music_assistant_client import MusicAssistantClient
            if self._client is None:
                self._client = MusicAssistantClient(self.url, None, token=self._token)
                await self._client.connect()
            return self._client
        except Exception:
            self._client = None
            raise MusicAssistantError("I can't reach Music Assistant right now.") from None
    async def check_connection(self) -> MusicAssistantStatus:
        if not self._token: return MusicAssistantStatus(connected=False, configured=False, message="Music Assistant requires authentication.")
        try:
            await self._client_or_error()
            return MusicAssistantStatus(connected=True, configured=True, message="Music Assistant is online.")
        except MusicAssistantError as error: return MusicAssistantStatus(connected=False, configured=True, message=error.message)
    async def players(self) -> list[MusicPlayer]:
        client = await self._client_or_error()
        try:
            return [MusicPlayer(player_id=p.player_id, name=p.name, available=bool(getattr(p, "available", True)), powered=bool(getattr(p, "powered", True)), state=str(getattr(p, "state", "idle")).lower(), volume_percent=int(getattr(p, "volume_level", 0)), current_item=getattr(getattr(p, "current_item", None), "name", None), current_artist=getattr(getattr(p, "current_item", None), "artist", None)) for p in client.players]
        except Exception: raise MusicAssistantError("I can't reach Music Assistant right now.") from None
    async def search(self, query: str, media_type: str | None = None) -> list[MusicItem]:
        cache_key = (query.casefold(), media_type)
        cached = self._search_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < self._cache_seconds:
            return cached[1]
        client = await self._client_or_error()
        try:
            results = await client.music.search(query, limit=8)
            items = [item for group in (results.tracks, results.artists, results.albums, results.playlists) for item in group]
            mapped = [MusicItem(item_id=str(x.item_id), name=x.name, media_type=str(x.media_type).lower(), artist=getattr(getattr(x, "artists", [None])[0], "name", None), album=getattr(getattr(x, "album", None), "name", None), provider="music_assistant", uri=getattr(x, "uri", None)) for x in items if str(x.media_type).lower() in {"track", "artist", "album", "playlist"} and (not media_type or str(x.media_type).lower() == media_type)]
            self._search_cache[cache_key] = (time.monotonic(), mapped)
            return mapped
        except Exception: raise MusicAssistantError("I can't reach Music Assistant right now.") from None
    async def play(self, player_id: str, item: MusicItem) -> None:
        client = await self._client_or_error()
        try:
            await client.player_queues.play_media(player_id, item.uri or item.item_id)
        except Exception: raise MusicAssistantError("Music Assistant could not start playback.") from None
    async def command(self, player_id: str, command: str, value: int | None = None) -> None:
        client = await self._client_or_error()
        try:
            commands = {
                "pause": lambda: client.players.pause(player_id),
                "resume": lambda: client.players.play(player_id),
                "stop": lambda: client.players.stop(player_id),
                "next": lambda: client.players.next_track(player_id),
                "previous": lambda: client.players.previous_track(player_id),
                "volume": lambda: client.players.volume_set(player_id, max(0, min(100, value or 0))),
            }
            await commands[command]()
        except Exception:
            raise MusicAssistantError("Music Assistant could not complete that command.") from None
    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
