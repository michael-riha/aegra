"""Global pytest configuration and fixtures

This file contains shared fixtures and configuration that are available
to all tests across the test suite.
"""

import pytest

from tests.fixtures.auth import DummyUser
from tests.fixtures.clients import (
    create_test_app,
    install_dummy_user_middleware,
    make_client,
)
from tests.fixtures.database import DummySessionBase, override_get_session_dep
from tests.fixtures.langgraph import (
    FakeAgent,
    FakeGraph,
    FakeSnapshot,
    make_snapshot,
    patch_langgraph_service,
)

# Export fixtures for use in tests
__all__ = [
    "DummyUser",
    "DummySessionBase",
    "override_get_session_dep",
    "FakeSnapshot",
    "FakeAgent",
    "FakeGraph",
    "make_snapshot",
    "patch_langgraph_service",
    "create_test_app",
    "make_client",
    "install_dummy_user_middleware",
]


# Add any global fixtures here
@pytest.fixture
def dummy_user():
    """Fixture providing a dummy user for tests"""
    return DummyUser()


@pytest.fixture
def test_user_identity():
    """Fixture providing a test user identity"""
    return "test-user"
