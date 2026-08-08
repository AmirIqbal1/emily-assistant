import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.models import HomeAssistantStatus

logger = logging.getLogger(__name__)


class HomeAssistantError(Exception):
    """Safe error suitable for display to a local Emily user."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class HomeAssistantBackend(ABC):
    """Small backend contract shared by real and development mock Home Assistant."""

    is_mock = False

    @property
    @abstractmethod
    def token_configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def check_connection(self) -> HomeAssistantStatus:
        raise NotImplementedError

    @abstractmethod
    async def get_states(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def get_state(self, entity_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def call_service(
        self, domain: str, service: str, service_data: dict[str, Any]
    ) -> None:
        raise NotImplementedError


class HomeAssistantClient(HomeAssistantBackend):
    """Server-side, allow-listed Home Assistant REST client.

    The long-lived token remains private to this object.  Callers get only
    sanitized status messages and parsed JSON, never upstream response bodies.
    """

    def __init__(
        self,
        base_url: str,
        token: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token.strip()
        self._transport = transport
        self._timeout = httpx.Timeout(connect=3.0, read=5.0, write=5.0, pool=3.0)

    @property
    def token_configured(self) -> bool:
        return bool(self._token)

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        if not self._token:
            raise HomeAssistantError("Home Assistant token is not configured.")

        try:
            async with httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = await client.request(method, f"{self.base_url}{path}", json=json)
        except (httpx.TimeoutException, httpx.NetworkError):
            logger.info("Home Assistant request could not be completed")
            raise HomeAssistantError("Home Assistant could not be reached.") from None
        except httpx.HTTPError:
            logger.warning("Home Assistant HTTP client failure")
            raise HomeAssistantError("Home Assistant request failed.") from None

        if response.status_code in {401, 403}:
            raise HomeAssistantError(
                "Home Assistant rejected the configured token.", response.status_code
            )
        if response.status_code == 404:
            raise HomeAssistantError("Home Assistant could not find that entity.", 404)
        if not response.is_success:
            raise HomeAssistantError(
                "Home Assistant could not complete that request.", response.status_code
            )
        return response

    async def check_connection(self) -> HomeAssistantStatus:
        if not self._token:
            return HomeAssistantStatus(
                connected=False,
                configured=False,
                message="Home Assistant token is not configured.",
            )
        try:
            response = await self._request("GET", "/api/")
            self._json_object(response)
        except HomeAssistantError as error:
            return HomeAssistantStatus(
                connected=False,
                configured=True,
                status_code=error.status_code,
                message=error.message,
            )
        return HomeAssistantStatus(
            connected=True,
            configured=True,
            status_code=response.status_code,
            message="Home Assistant is online.",
        )

    async def get_api(self) -> dict[str, Any]:
        return self._json_object(await self._request("GET", "/api/"))

    async def get_states(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "/api/states")
        try:
            data = response.json()
        except ValueError:
            raise HomeAssistantError("Home Assistant returned malformed entity data.") from None
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise HomeAssistantError("Home Assistant returned malformed entity data.")
        return data

    async def get_state(self, entity_id: str) -> dict[str, Any]:
        return self._json_object(await self._request("GET", f"/api/states/{entity_id}"))

    async def call_service(
        self, domain: str, service: str, service_data: dict[str, Any]
    ) -> None:
        """Invoke a service only after a tool selected a fixed allow-listed mapping."""
        await self._request("POST", f"/api/services/{domain}/{service}", service_data)

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            raise HomeAssistantError("Home Assistant returned malformed data.") from None
        if not isinstance(data, dict):
            raise HomeAssistantError("Home Assistant returned malformed data.")
        return data


class RealHomeAssistantBackend(HomeAssistantClient):
    """Named production backend; retains the existing client implementation."""
