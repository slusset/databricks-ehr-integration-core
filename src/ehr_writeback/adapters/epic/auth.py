"""Epic backend-system OAuth2 authentication via JWT assertion.

Epic's backend auth flow:
1. Build a JWT signed with your private key
2. POST to Epic's token endpoint with grant_type=client_credentials
3. Receive an access token (typically 5-minute TTL)

See: https://fhir.epic.com/Documentation?docId=oauth2&section=BackendOAuth2Guide
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx
import jwt
from cryptography.hazmat.primitives import serialization

from ehr_writeback.core.ports import AuthPort


@dataclass
class EpicBackendJWTAuth(AuthPort):
    """Adapter for Epic's backend OAuth2 JWT flow."""

    client_id: str
    private_key_pem: str  # PEM-encoded RSA private key
    token_endpoint: str  # e.g. https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token
    _access_token: str | None = field(default=None, repr=False)
    _token_expires_at: float = field(default=0.0, repr=False)

    def _build_jwt(self) -> str:
        now = int(time.time())
        claims = {
            "iss": self.client_id,
            "sub": self.client_id,
            "aud": self.token_endpoint,
            "jti": f"{self.client_id}-{now}",
            "iat": now,
            "exp": now + 300,  # 5 minutes
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
        # Epic backend tokens aren't refreshable — just re-authenticate
        return await self.authenticate()

    async def get_token(self) -> str:
        """Get a valid token, authenticating if needed."""
        if self._access_token and time.time() < self._token_expires_at - 30:
            return self._access_token
        return await self.authenticate()
