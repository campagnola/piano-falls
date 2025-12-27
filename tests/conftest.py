"""
Pytest configuration file.

This file contains session-wide fixtures and configuration for the test suite.
"""
import pytest
from pianofalls import config


@pytest.fixture(scope="session", autouse=True)
def setup_test_config():
    """
    Configure pianofalls to use test configuration before running any tests.

    This fixture runs automatically once per test session before any tests execute,
    ensuring that all tests use the test configuration settings.
    """
    config.use_test_config()