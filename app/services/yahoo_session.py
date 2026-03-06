"""
Manages a persistent curl_cffi AsyncSession that handles Yahoo Finance
cookie + crumb authentication with automatic re-auth on expiry or 401.

Yahoo's bot detection works at the TLS layer (JA3/JA4 fingerprinting).  Plain
requests / httpx are blocked with HTTP 401/403.  curl_cffi replays Chrome's
exact TLS ClientHello, which is required to reach the API endpoints.

Auth flow
---------
1. GET https://fc.yahoo.com  — Yahoo sets the A3 session cookie.
2. GET https://query1.finance.yahoo.com/v1/test/getcrumb  — returns a short
   crumb token that must be appended to every subsequent API call.

Both the A3 cookie and the crumb are session-scoped; the crumb is only valid
for the session that fetched it (they are cryptographically bound together).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from curl_cffi.requests import AsyncSession

logger = logging.getLogger(__name__)

_COOKIE_BOOTSTRAP_URL = "https://fc.yahoo.com"
_CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"

# Crumb / cookie TTL – Yahoo sessions last several hours; refresh conservatively.
_SESSION_TTL_SECONDS = 3_600  # 1 hour


class YahooSession:
    """Singleton async session with automatic cookie/crumb lifecycle management."""

    def __init__(self) -> None:
        self._session: Optional[AsyncSession] = None
        self._crumb: Optional[str] = None
        self._session_expires_at: float = 0.0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def crumb(self) -> str:
        """Return a valid crumb, re-authenticating if necessary."""
        await self._ensure_auth()
        assert self._crumb is not None
        return self._crumb

    async def get(self, url: str, **kwargs) -> "curl_cffi.requests.Response":  # type: ignore[name-defined]
        """Perform a GET request on the managed session."""
        await self._ensure_auth()
        assert self._session is not None
        response = await self._session.get(url, **kwargs)
        if response.status_code in (401, 403):
            # Crumb/cookie has been invalidated server-side – re-auth once.
            logger.warning("Received %d from Yahoo; re-authenticating.", response.status_code)
            await self._authenticate(force=True)
            response = await self._session.get(url, **kwargs)
        return response

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # Internal auth management
    # ------------------------------------------------------------------

    async def _ensure_auth(self) -> None:
        if self._crumb and time.monotonic() < self._session_expires_at:
            return
        async with self._lock:
            # Double-checked locking: another coroutine may have refreshed
            # while we were waiting on the lock.
            if self._crumb and time.monotonic() < self._session_expires_at:
                return
            await self._authenticate()

    async def _authenticate(self, force: bool = False) -> None:
        if force or self._session is None:
            if self._session is not None:
                await self._session.close()
            self._session = AsyncSession(impersonate="chrome")

        logger.info("Authenticating with Yahoo Finance (fetching cookie + crumb).")

        # Step 1 – obtain A3 cookie
        try:
            await self._session.get(_COOKIE_BOOTSTRAP_URL, allow_redirects=True, timeout=10)
        except Exception as exc:
            logger.warning("Cookie bootstrap request failed: %s", exc)
            # Non-fatal; the crumb endpoint may still work if cookies are set.

        # Step 2 – obtain crumb
        crumb_response = await self._session.get(_CRUMB_URL, timeout=10)
        if crumb_response.status_code != 200 or not crumb_response.text.strip():
            raise RuntimeError(
                f"Failed to obtain Yahoo Finance crumb "
                f"(HTTP {crumb_response.status_code}): {crumb_response.text!r}"
            )

        self._crumb = crumb_response.text.strip()
        self._session_expires_at = time.monotonic() + _SESSION_TTL_SECONDS
        logger.info("Yahoo Finance session established (crumb obtained).")


# Module-level singleton – shared across all requests in the process.
yahoo_session = YahooSession()
