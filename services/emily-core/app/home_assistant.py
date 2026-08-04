import logging

import httpx

from app.models import HomeAssistantStatus

logger = logging.getLogger(__name__)


class HomeAssistantClient:
    """Read-only Home Assistant connectivity client for Emily v0.1."""

    def __init__(
        self,
        base_url: str,
        token: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token.strip()
        self._transport = transport

    @property
    def token_configured(self) -> bool:
        return bool(self._token)

    async def check_connection(self) -> HomeAssistantStatus:
        if not self._token:
            return HomeAssistantStatus(
                connected=False,
                configured=False,
                message="Home Assistant token is not configured.",
            )

        headers = {"Authorization": f"Bearer {self._token}"}
        timeout = httpx.Timeout(connect=3.0, read=5.0, write=5.0, pool=3.0)
        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=timeout,
                transport=self._transport,
            ) as client:
                response = await client.get(f"{self.base_url}/api/")
        except (httpx.TimeoutException, httpx.NetworkError):
            logger.info("Home Assistant connection check failed")
            return HomeAssistantStatus(
                connected=False,
                configured=True,
                message="Home Assistant could not be reached.",
            )
        except httpx.HTTPError:
            logger.warning("Home Assistant returned an HTTP client error")
            return HomeAssistantStatus(
                connected=False,
                configured=True,
                message="Home Assistant connectivity check failed.",
            )

        if response.is_success:
            return HomeAssistantStatus(
                connected=True,
                configured=True,
                status_code=response.status_code,
                message="Home Assistant is online.",
            )

        message = (
            "Home Assistant rejected the configured token."
            if response.status_code in {401, 403}
            else "Home Assistant returned an unexpected response."
        )
        return HomeAssistantStatus(
            connected=False,
            configured=True,
            status_code=response.status_code,
            message=message,
        )

