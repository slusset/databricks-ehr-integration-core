"""SMART on FHIR backend-services auth (generic).

This implements the SMART Backend Services authorization flow (RFC 7523)
which works with any FHIR server that supports SMART on FHIR.

See: https://hl7.org/fhir/smart-app-launch/backend-services.html
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx
import jwt
from cryptography.hazmat.primitives import serialization

from ehr_writeback.core.ports import AuthPort


@dataclass
class SMARTOnFHIRAuth(AuthPort):
    """Generic SMART on FHIR backend-services auth adapter."""

    client_id: str
    private_key_pem: str
    token_endpoint: str
    scope: str = "system/Observation.write"
    _access_token: str | None = field(default=None, repr=False)
    _token_expires_at: float = field(default=0.0, repr=False)

    def _build_jwt(self) -> str:
        now = int(time.time())
        claims = {
            "iss": self.client_id,
            "sub": self.client_id,
            "aud": self.token_endpoint,
            "iat": now,
            "exp": now + 300,
        }
        private_key = serialization.load_pem_private_key(
            self.private_key_pem.encode(), password=None
        )
        return jwt.encode(claims, private_key, algorithm="RS384")

    async def authenticate(self) -> str:
        assertion = self._build_jwt()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    "grant_type": "client_credentials",
                    "scope": self.scope,
                    "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                    "client_assertion": assertion,
                },
            )
            response.raise_for_status()
            data = response.json()

        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 300)
        return self._access_token

    async def refresh(self) -> str:
        return await self.authenticate()

    async def get_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at - 30:
            return self._access_token
        return await self.authenticate()
