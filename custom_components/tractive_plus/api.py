"""Client minimal pour l'API cloud Tractive, propre a Tractive Plus."""

from __future__ import annotations

import asyncio
import logging
import time
from http import HTTPStatus
from typing import Any

import aiohttp
from yarl import URL

_LOGGER = logging.getLogger(__name__)

API_URL = URL("https://graph.tractive.com/4/")
APS_API_URL = URL("https://aps-api.tractive.com/api/1/")
CLIENT_ID = "625e533dc3c3b41c28a669f0"
TIMEOUT = aiohttp.ClientTimeout(total=15)
TOKEN_REFRESH_MARGIN = 3600
MAX_RETRIES = 2


class TractivePlusError(Exception):
    """Erreur generique de l'API Tractive."""


class TractivePlusAuthError(TractivePlusError):
    """Identifiants refuses ou jeton invalide."""


class TractivePlusApi:
    """Client Tractive base sur la session HTTP de Home Assistant."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        """Initialise le client."""
        self._session = session
        self._email = email
        self._password = password
        self._credentials: dict[str, Any] | None = None
        self._lock = asyncio.Lock()

    @staticmethod
    def _base_headers() -> dict[str, str]:
        return {
            "x-tractive-client": CLIENT_ID,
            "content-type": "application/json;charset=UTF-8",
            "accept": "application/json, text/plain, */*",
        }

    async def authenticate(self) -> dict[str, Any]:
        """Obtient (ou reutilise) un jeton d'acces."""
        async with self._lock:
            creds = self._credentials
            if creds and creds.get("expires_at", 0) - time.time() > TOKEN_REFRESH_MARGIN:
                return creds
            self._credentials = None
            try:
                async with self._session.post(
                    API_URL.join(URL("auth/token")),
                    json={
                        "platform_email": self._email,
                        "platform_token": self._password,
                        "grant_type": "tractive",
                    },
                    headers=self._base_headers(),
                    timeout=TIMEOUT,
                ) as resp:
                    if resp.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                        raise TractivePlusAuthError("Identifiants Tractive refusés")
                    resp.raise_for_status()
                    creds = await resp.json(content_type=None)
            except TractivePlusError:
                raise
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                raise TractivePlusError(f"Authentification impossible : {err}") from err
            if not isinstance(creds, dict) or "access_token" not in creds:
                raise TractivePlusAuthError("Réponse d'authentification inattendue")
            self._credentials = creds
            return creds

    async def user_id(self) -> str:
        """Identifiant du compte Tractive."""
        return str((await self.authenticate())["user_id"])

    async def request(self, uri: str, aps: bool = False) -> Any:
        """Requete GET authentifiee sur l'API Tractive."""
        base = APS_API_URL if aps else API_URL
        for attempt in range(MAX_RETRIES + 1):
            creds = await self.authenticate()
            headers = {
                **self._base_headers(),
                "x-tractive-user": str(creds["user_id"]),
                "authorization": f"Bearer {creds['access_token']}",
            }
            try:
                async with self._session.get(
                    base.join(URL(uri)), headers=headers, timeout=TIMEOUT
                ) as resp:
                    if resp.status == HTTPStatus.UNAUTHORIZED:
                        # Jeton expire cote serveur : on en redemande un une fois.
                        self._credentials = None
                        if attempt < MAX_RETRIES:
                            continue
                        raise TractivePlusAuthError("Jeton Tractive refusé")
                    if resp.status == HTTPStatus.TOO_MANY_REQUESTS and attempt < MAX_RETRIES:
                        await asyncio.sleep(10 * (attempt + 1))
                        continue
                    resp.raise_for_status()
                    if "application/json" in resp.headers.get("Content-Type", ""):
                        return await resp.json()
                    return await resp.read()
            except TractivePlusError:
                raise
            except (aiohttp.ClientError, TimeoutError) as err:
                raise TractivePlusError(f"Requête {uri} impossible : {err}") from err
        raise TractivePlusError(f"Requête {uri} impossible après plusieurs essais")
