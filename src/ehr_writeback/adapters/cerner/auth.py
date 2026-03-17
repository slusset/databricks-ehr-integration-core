"""Cerner/Oracle Health OAuth2 authentication.

Cerner supports both SMART on FHIR and system-level OAuth2.
This adapter implements the system-account (backend service) flow.

See: https://fhir.cerner.com/authorization/
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from ehr_writeback.core.ports import AuthPort


@dataclass
class CernerOAuth2Auth(AuthPort):
    """Adapter for Cerner's system-level OAuth2 flow."""

    client_id: str
    client_secret: str
    token_endpoint: str  # e.g. https://authorization.cerner.com/tenants/{tenant}/protocols/oauth2/profiles/smart-v1/token
    scope: str = "system/Observation.write"
    _access_token: str | None = field(default=None, repr=False)
    _token_expires_at: float = field(default=0.0, repr=False)

    async def authenticate(self) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    "grant_type": "client_credentials",
                    "scope": self.scope,
                },
                auth=(self.client_id, self.client_secret),
            )
            response.raise_for_status()
            data = response.json()

        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 600)
        return self._access_token

    async def refresh(self) -> str:
        return await self.authenticate()

    async def get_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at - 30:
            return self._access_token
        return await self.authenticate()
