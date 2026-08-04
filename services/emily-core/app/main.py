import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import __version__
from app.assistant import Assistant
from app.config import Settings, get_settings
from app.home_assistant import HomeAssistantClient
from app.intent_router import LocalIntentRouter
from app.models import ChatRequest, ChatResponse, StatusResponse
from app.providers.local import LocalProvider

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


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.emily_log_level)
    home_assistant = HomeAssistantClient(
        settings.home_assistant_url,
        settings.home_assistant_token,
    )
    local_provider = LocalProvider(settings.emily_name, LocalIntentRouter(), home_assistant)
    assistant = Assistant([local_provider])

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.started_at = time.monotonic()
        yield

    app = FastAPI(
        title="Emily Core",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.home_assistant = home_assistant
    app.state.assistant = assistant
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
        started_at = getattr(request.app.state, "started_at", time.monotonic())
        return StatusResponse(
            version=__version__,
            name=settings.emily_name,
            home_assistant=ha_status,
            home_assistant_token_configured=home_assistant.token_configured,
            uptime_seconds=round(time.monotonic() - started_at, 3),
            server_time=datetime.now(timezone.utc).isoformat(),
            enabled_providers=assistant.enabled_provider_names,
        )

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
        return await request.app.state.assistant.process(payload.message)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()

