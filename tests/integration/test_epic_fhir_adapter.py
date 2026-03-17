"""Integration tests for Epic FHIR adapter.

These tests require a running FHIR server (e.g., HAPI FHIR test server
or Epic's sandbox). Skip in CI unless FHIR_TEST_BASE_URL is set.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("FHIR_TEST_BASE_URL"),
    reason="Set FHIR_TEST_BASE_URL to run integration tests",
)


@pytest.fixture
def fhir_base_url() -> str:
    return os.environ["FHIR_TEST_BASE_URL"]


async def test_check_connection_to_sandbox(fhir_base_url: str):
    """Verify we can reach the FHIR capability statement."""
    # TODO: Wire up with real or mock auth for sandbox testing
    pass
