"""Shared test fixtures for hermes-lite."""
import pytest
from registry import registry


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset the module-level registry singleton after every test."""
    before = set(registry.list_tools())
    yield
    after = set(registry.list_tools())
    for name in after - before:
        registry.deregister(name)
