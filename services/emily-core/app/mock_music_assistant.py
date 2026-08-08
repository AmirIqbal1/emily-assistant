from copy import deepcopy

from app.models import MusicAssistantStatus, MusicItem, MusicPlayer
from app.music_assistant import MusicAssistantBackend, MusicAssistantError


class MockMusicAssistantBackend(MusicAssistantBackend):
    """Deterministic, stateful local Music Assistant substitute for development."""

    is_mock = True

    def __init__(self) -> None:
        self._players = {
            "player.living_room": MusicPlayer(player_id="player.living_room", name="Living Room Speaker", available=True, state="idle", volume_percent=30),
            "player.bedroom": MusicPlayer(player_id="player.bedroom", name="Bedroom Speaker", available=True, state="idle", volume_percent=20),
            "player.car": MusicPlayer(player_id="player.car", name="Car", available=False, powered=False, state="unavailable", volume_percent=50),
        }
        self._catalogue = [
            MusicItem(item_id="artist.oasis", name="Oasis", media_type="artist"),
            MusicItem(item_id="artist.fleetwood_mac", name="Fleetwood Mac", media_type="artist"),
            MusicItem(item_id="artist.arctic_monkeys", name="Arctic Monkeys", media_type="artist"),
            MusicItem(item_id="artist.queen", name="Queen", media_type="artist"),
            MusicItem(item_id="artist.daft_punk", name="Daft Punk", media_type="artist"),
            MusicItem(item_id="track.wonderwall", name="Wonderwall", media_type="track", artist="Oasis", album="(What's the Story) Morning Glory?"),
            MusicItem(item_id="track.dont_look_back", name="Don't Look Back in Anger", media_type="track", artist="Oasis", album="(What's the Story) Morning Glory?"),
            MusicItem(item_id="track.dreams", name="Dreams", media_type="track", artist="Fleetwood Mac", album="Rumours"),
            MusicItem(item_id="track.go_your_own_way", name="Go Your Own Way", media_type="track", artist="Fleetwood Mac", album="Rumours"),
            MusicItem(item_id="track.do_i_wanna_know", name="Do I Wanna Know?", media_type="track", artist="Arctic Monkeys", album="AM"),
            MusicItem(item_id="track.bohemian_rhapsody", name="Bohemian Rhapsody", media_type="track", artist="Queen"),
            MusicItem(item_id="track.get_lucky", name="Get Lucky", media_type="track", artist="Daft Punk", album="Random Access Memories"),
            MusicItem(item_id="album.morning_glory", name="(What's the Story) Morning Glory?", media_type="album", artist="Oasis"),
            MusicItem(item_id="album.rumours", name="Rumours", media_type="album", artist="Fleetwood Mac"),
            MusicItem(item_id="album.am", name="AM", media_type="album", artist="Arctic Monkeys"),
            MusicItem(item_id="album.random_access_memories", name="Random Access Memories", media_type="album", artist="Daft Punk"),
            MusicItem(item_id="playlist.driving", name="Driving", media_type="playlist"),
            MusicItem(item_id="playlist.chill", name="Chill", media_type="playlist"),
            MusicItem(item_id="playlist.favourites", name="Favourites", media_type="playlist"),
            MusicItem(item_id="playlist.workout", name="Workout", media_type="playlist"),
        ]
        self._queues: dict[str, list[MusicItem]] = {}
        self._positions: dict[str, int] = {}

    @property
    def token_configured(self) -> bool:
        return False

    async def check_connection(self) -> MusicAssistantStatus:
        return MusicAssistantStatus(connected=True, configured=True, message="Music Assistant mock is online.", mode="mock")

    async def players(self) -> list[MusicPlayer]:
        return deepcopy(list(self._players.values()))

    async def search(self, query: str, media_type: str | None = None) -> list[MusicItem]:
        needle = " ".join(query.casefold().replace("-", " ").split())
        results = [item for item in self._catalogue if needle in f"{item.name} {item.artist or ''} {item.album or ''}".casefold()]
        if media_type:
            results = [item for item in results if item.media_type == media_type]
        return deepcopy(results)

    def _require_player(self, player_id: str) -> MusicPlayer:
        player = self._players.get(player_id)
        if not player or not player.available:
            raise MusicAssistantError("That music player is unavailable.")
        return player

    def _tracks_for(self, item: MusicItem) -> list[MusicItem]:
        tracks = [x for x in self._catalogue if x.media_type == "track"]
        if item.media_type == "track": return [item]
        if item.media_type == "artist": return [x for x in tracks if x.artist == item.name]
        if item.media_type == "album": return [x for x in tracks if x.album == item.name]
        playlist_tracks = {"Driving": ["Dreams", "Get Lucky", "Wonderwall"], "Chill": ["Dreams", "Do I Wanna Know?"], "Favourites": ["Wonderwall", "Bohemian Rhapsody"], "Workout": ["Get Lucky", "Go Your Own Way"]}
        names = playlist_tracks.get(item.name, [])
        return [x for x in tracks if x.name in names]

    def _set_current(self, player_id: str) -> None:
        player = self._players[player_id]
        queue = self._queues.get(player_id, [])
        if not queue:
            player.current_item = player.current_artist = None
            return
        item = queue[self._positions[player_id]]
        player.current_item, player.current_artist = item.name, item.artist

    async def play(self, player_id: str, item: MusicItem) -> None:
        player = self._require_player(player_id)
        tracks = self._tracks_for(item)
        if not tracks: raise MusicAssistantError("I couldn't find playable music for that request.")
        self._queues[player_id], self._positions[player_id] = tracks, 0
        self._set_current(player_id)
        player.state, player.powered = "playing", True

    async def command(self, player_id: str, command: str, value: int | None = None) -> None:
        player = self._require_player(player_id)
        if command == "volume":
            player.volume_percent = max(0, min(100, value or 0)); return
        if command == "pause": player.state = "paused"; return
        if command == "resume":
            if player.current_item: player.state = "playing"
            return
        if command == "stop":
            player.state = "idle"; player.current_item = player.current_artist = None; self._queues.pop(player_id, None); return
        if command in {"next", "previous"}:
            queue = self._queues.get(player_id, [])
            if not queue: raise MusicAssistantError("Nothing is currently queued on that player.")
            shift = 1 if command == "next" else -1
            self._positions[player_id] = (self._positions[player_id] + shift) % len(queue)
            self._set_current(player_id); player.state = "playing"; return
        raise MusicAssistantError("That music command is not supported.")
