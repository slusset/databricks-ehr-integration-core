"""No-op authentication adapter.

For FHIR servers that require no authentication, such as
HAPI FHIR's public test server (https://hapi.fhir.org/baseR4).
"""

from __future__ import annotations

from ehr_writeback.core.ports import AuthPort


class NoAuth(AuthPort):
    """Auth adapter that produces no credentials."""

    async def authenticate(self) -> str:
        return ""

    async def refresh(self) -> str:
        return ""
