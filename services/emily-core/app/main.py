import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import __version__
from app.assistant import Assistant
from app.config import Settings, get_settings
from app.entities import EntityRegistry, EntityResolver, SUPPORTED_DOMAINS
from app.home_assistant import HomeAssistantBackend, HomeAssistantError, RealHomeAssistantBackend
from app.intent_router import LocalIntentRouter
from app.models import ChatRequest, ChatResponse, EntityListResponse, HomeAssistantEntity, StatusResponse
from app.mock_home_assistant import MockHomeAssistantBackend
from app.mock_music_assistant import MockMusicAssistantBackend
from app.music import MusicToolExecutor
from app.music_assistant import MusicAssistantBackend, MusicAssistantError, RealMusicAssistantBackend
from app.models import MusicAssistantStatus, MusicNowPlayingResponse, MusicPlayersResponse
from app.providers.local import LocalProvider
from app.tools import ToolExecutor

STATIC_DIR = Path(__file__).parent / "static"


class RequestSizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    response = JSONResponse({"detail": "Request body too large"}, status_code=413)
                    await response(scope, receive, send)
                    return
            except ValueError:
                response = JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
                await response(scope, receive, send)
                return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLarge:
            response = JSONResponse({"detail": "Request body too large"}, status_code=413)
            await response(scope, receive, send)


class RequestBodyTooLarge(Exception):
    pass


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
    )


def create_app(
    settings: Settings | None = None,
    home_assistant: HomeAssistantBackend | None = None,
    music_assistant: MusicAssistantBackend | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.emily_log_level)
    home_assistant = home_assistant or (
        MockHomeAssistantBackend()
        if settings.home_assistant_mock
        else RealHomeAssistantBackend(settings.home_assistant_url, settings.home_assistant_token)
    )
    entity_registry = EntityRegistry(home_assistant, settings.entity_cache_seconds)
    tools = ToolExecutor(entity_registry, EntityResolver(), settings.home_assistant_control_enabled)
    music_assistant = music_assistant or (
        MockMusicAssistantBackend() if settings.music_assistant_mock
        else RealMusicAssistantBackend(settings.music_assistant_url, settings.music_assistant_token, settings.music_assistant_cache_seconds)
    )
    music_tools = MusicToolExecutor(music_assistant, settings.music_assistant_control_enabled, settings.music_assistant_default_player)
    local_provider = LocalProvider(settings.emily_name, LocalIntentRouter(), home_assistant, tools, music_tools)
    assistant = Assistant([local_provider])

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.started_at = time.monotonic()
        try:
            yield
        finally:
            await app.state.music_assistant.close()

    app = FastAPI(
        title="Emily Core",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.home_assistant = home_assistant
    app.state.entity_registry = entity_registry
    app.state.assistant = assistant
    app.state.music_assistant = music_assistant
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.max_request_bytes)

    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    @app.middleware("http")
    async def security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[JSONResponse]],
    ):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self'; frame-ancestors 'none'"
        )
        return response

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy", "service": "emily-core", "version": __version__}

    @app.get("/api/status", response_model=StatusResponse)
    async def status(request: Request) -> StatusResponse:
        ha_status = await request.app.state.home_assistant.check_connection()
        music_status = await request.app.state.music_assistant.check_connection()
        try:
            music_player_count = len(await request.app.state.music_assistant.players()) if music_status.connected else 0
        except MusicAssistantError:
            music_player_count = 0
        started_at = getattr(request.app.state, "started_at", time.monotonic())
        return StatusResponse(
            version=__version__,
            name=settings.emily_name,
            home_assistant=ha_status,
            home_assistant_token_configured=home_assistant.token_configured,
            home_assistant_mock=home_assistant.is_mock,
            home_assistant_control_enabled=settings.home_assistant_control_enabled,
            entity_count=entity_registry.cached_count or getattr(home_assistant, "entity_count", 0),
            uptime_seconds=round(time.monotonic() - started_at, 3),
            server_time=datetime.now(timezone.utc).isoformat(),
            enabled_providers=assistant.enabled_provider_names,
            music_assistant=music_status,
            music_assistant_control_enabled=settings.music_assistant_control_enabled,
            music_player_count=music_player_count,
            music_default_player=settings.music_assistant_default_player or None,
        )

    @app.get("/api/music/status", response_model=MusicAssistantStatus)
    async def music_status(request: Request) -> MusicAssistantStatus:
        return await request.app.state.music_assistant.check_connection()

    @app.get("/api/music/players", response_model=MusicPlayersResponse)
    async def music_players(request: Request) -> MusicPlayersResponse:
        try:
            players = await request.app.state.music_assistant.players()
        except MusicAssistantError as error:
            raise HTTPException(status_code=503, detail=error.message) from None
        return MusicPlayersResponse(players=players, count=len(players))

    @app.get("/api/music/now-playing", response_model=MusicNowPlayingResponse)
    async def music_now_playing(request: Request, player: str | None = Query(default=None, max_length=100)) -> MusicNowPlayingResponse:
        try:
            players = await request.app.state.music_assistant.players()
        except MusicAssistantError as error:
            raise HTTPException(status_code=503, detail=error.message) from None
        selected, error = music_tools.players.resolve(players, player or settings.music_assistant_default_player or None)
        if error:
            return MusicNowPlayingResponse(player=None)
        return MusicNowPlayingResponse(player=selected)

    @app.get("/api/music/search")
    async def music_search(
        request: Request,
        q: str = Query(min_length=1, max_length=100),
        media_type: str | None = Query(default=None, pattern="^(track|artist|album|playlist)$"),
    ) -> list:
        try:
            return await request.app.state.music_assistant.search(q, media_type)
        except MusicAssistantError as error:
            raise HTTPException(status_code=503, detail=error.message) from None

    @app.post("/api/chat", response_model=ChatResponse, response_model_exclude_none=True)
    async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
        return await request.app.state.assistant.process(payload.message)

    @app.get("/api/entities", response_model=EntityListResponse)
    async def entities(
        request: Request,
        domain: str | None = Query(default=None, max_length=32),
        search: str | None = Query(default=None, max_length=100),
    ) -> EntityListResponse:
        if domain and domain not in SUPPORTED_DOMAINS:
            raise HTTPException(status_code=422, detail="Unsupported entity domain.")
        try:
            discovered = await request.app.state.entity_registry.discover()
        except HomeAssistantError as error:
            raise HTTPException(status_code=503, detail=error.message) from None
        filtered = discovered
        if domain:
            filtered = [entity for entity in filtered if entity.domain == domain]
        if search:
            needle = EntityResolver.normalize(search)
            filtered = [
                entity for entity in filtered
                if needle in EntityResolver.normalize(f"{entity.friendly_name} {entity.entity_id}")
            ]
        return EntityListResponse(
            entities=filtered,
            count=len(filtered),
            supported_counts=EntityRegistry.counts(discovered),
        )

    @app.post("/api/entities/refresh", response_model=EntityListResponse)
    async def refresh_entities(request: Request) -> EntityListResponse:
        try:
            discovered = await request.app.state.entity_registry.discover(refresh=True)
        except HomeAssistantError as error:
            raise HTTPException(status_code=503, detail=error.message) from None
        return EntityListResponse(
            entities=discovered,
            count=len(discovered),
            supported_counts=EntityRegistry.counts(discovered),
        )

    @app.get("/api/entities/{entity_id}", response_model=HomeAssistantEntity)
    async def entity(entity_id: str, request: Request) -> HomeAssistantEntity:
        try:
            return await request.app.state.entity_registry.find_by_id(entity_id)
        except HomeAssistantError as error:
            status_code = 404 if error.status_code == 404 else 503
            raise HTTPException(status_code=status_code, detail=error.message) from None

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
