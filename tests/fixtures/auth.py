"""Authentication fixtures for tests"""
from typing import Dict, Any


class DummyUser:
    """Mock user for testing"""
    def __init__(self, identity: str = "test-user", display_name: str = "Test User"):
        self.identity = identity
        self.display_name = display_name
        self.is_authenticated = True

    def to_dict(self) -> Dict[str, Any]:
        return {"identity": self.identity, "display_name": self.display_name}
