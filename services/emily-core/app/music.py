import re

from app.models import MusicItem, MusicPlayer, ToolResult
from app.music_assistant import MusicAssistantBackend, MusicAssistantError


class PlayerResolver:
    @staticmethod
    def normalize(value: str) -> str:
        value = re.sub(r"[_-]", " ", value.casefold())
        value = re.sub(r"[^a-z0-9\s]", "", value)
        return re.sub(r"\s+", " ", re.sub(r"^the\s+", "", value)).strip()

    def resolve(self, players: list[MusicPlayer], requested: str | None) -> tuple[MusicPlayer | None, str | None]:
        usable = [player for player in players if player.available]
        if not requested:
            if len(usable) == 1: return usable[0], None
            return None, "I found more than one music player. Say where you'd like me to play it."
        needle = self.normalize(requested)
        exact = [p for p in usable if needle in {self.normalize(p.name), self.normalize(p.player_id)}]
        matches = exact or [p for p in usable if needle in self.normalize(p.name) or needle in self.normalize(p.player_id)]
        if len(matches) == 1: return matches[0], None
        if len(matches) > 1:
            return None, f"I found more than one matching player: {' and '.join(p.name for p in matches)}. Which one did you mean?"
        unavailable = [p for p in players if not p.available and (needle in self.normalize(p.name) or needle in self.normalize(p.player_id))]
        if len(unavailable) == 1:
            return None, f"The {unavailable[0].name} player is currently unavailable."
        return None, f"I couldn't find a music player called {requested}."


class MusicResolver:
    @staticmethod
    def resolve(items: list[MusicItem], query: str, media_type: str | None) -> MusicItem | None:
        if media_type:
            items = [item for item in items if item.media_type == media_type]
        normalized = PlayerResolver.normalize(query)
        exact = [item for item in items if PlayerResolver.normalize(item.name) == normalized]
        candidates = exact or items
        return candidates[0] if len(candidates) == 1 else None


class MusicToolExecutor:
    def __init__(self, backend: MusicAssistantBackend, control_enabled: bool, default_player: str) -> None:
        self.backend, self.control_enabled, self.default_player = backend, control_enabled, default_player
        self.players = PlayerResolver()
        self.music = MusicResolver()
        self.active_player: str | None = None

    async def _player(self, requested: str | None) -> tuple[MusicPlayer | None, str | None]:
        all_players = await self.backend.players()
        return self.players.resolve(all_players, requested or self.default_player or self.active_player)

    async def execute(self, action: str, target: str | None = None, value: str | int | None = None, media_type: str | None = None) -> ToolResult:
        try:
            if action == "list_players":
                available = [p.name for p in await self.backend.players() if p.available]
                return ToolResult(reply=f"Available players: {' and '.join(available)}." if available else "No music players are available.", success=True, tool="list_music_players")
            player, error = await self._player(target)
            if error: return ToolResult(reply=error, success=False, tool=f"music_{action}")
            assert player is not None
            if action in {"now_playing", "get_state"}:
                if not player.current_item: reply = f"Nothing is currently playing on {player.name}."
                elif action == "get_state": reply = f"{player.name} is {player.state}."
                else: reply = f"{player.current_item}{' by ' + player.current_artist if player.current_artist else ''} is {player.state} on {player.name}."
                return ToolResult(reply=reply, success=True, tool="music_now_playing", target=player.player_id)
            if not self.control_enabled: return ToolResult(reply="Music Assistant control is disabled.", success=False, tool=f"music_{action}", target=player.player_id)
            if action == "play":
                results = await self.backend.search(value if isinstance(value, str) else "", media_type)
                item = self.music.resolve(results, value if isinstance(value, str) else "", media_type)
                if not item: return ToolResult(reply="I couldn't find one unambiguous music match. Try a more specific song, artist, album, or playlist.", success=False, tool="play_music", target=player.player_id)
                await self.backend.play(player.player_id, item)
                self.active_player = player.player_id
                description = f"{item.name}{' by ' + item.artist if item.artist else ''}"
                return ToolResult(reply=f"Playing {description} on {player.name}.", success=True, tool="play_music", target=player.player_id)
            await self.backend.command(player.player_id, action, value if isinstance(value, int) else None)
            self.active_player = player.player_id
            replies = {"pause": "Paused.", "resume": "Resumed.", "next": "Skipped.", "previous": "Going back.", "stop": "Stopped.", "volume": f"Set {player.name} volume to {max(0, min(100, value or 0))} percent."}
            return ToolResult(reply=replies[action], success=True, tool=f"music_{action}", target=player.player_id)
        except MusicAssistantError as error:
            return ToolResult(reply=error.message, success=False, tool=f"music_{action}")
