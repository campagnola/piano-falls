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


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for Qt-dependent tests."""
    import sys
    from pianofalls.qt import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    yield app

    # Note: Don't quit here as it may be needed by other tests