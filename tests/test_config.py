"""
Tests for the pianofalls.config module.

These tests verify that configuration parameters can be saved and reloaded correctly.
"""
import json
import pytest
import tempfile
import pathlib

from pianofalls import config


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = pathlib.Path(f.name)
    yield temp_path
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


class TestConfigBasics:
    """Test basic config functionality."""

    def test_config_creation_loads_defaults(self, temp_config_file):
        """Test that a new config creates file with defaults."""
        test_config = config.Config(temp_config_file)

        # Verify it has default values (note: test config is active, so search_paths is test path)
        assert isinstance(test_config['search_paths'], list)
        assert len(test_config['search_paths']) == 1
        assert test_config['autoplay_volume'] == 80
        assert test_config['scroll_mode'] == "wait"
        assert test_config['stale_threshold_days'] == 30
        assert test_config['rpi_display'] is None

        # Verify the file was created
        assert temp_config_file.exists()

    def test_config_parameter_persistence(self, temp_config_file):
        """Test that config parameters are saved and reloaded correctly."""
        # Create config and modify values
        test_config = config.Config(temp_config_file)
        test_config['autoplay_volume'] = 65
        test_config['scroll_mode'] = "tempo"
        test_config['search_paths'] = ["/custom/path", "~/Music"]

        # Create a new config instance to verify persistence
        test_config2 = config.Config(temp_config_file)

        # Verify values were persisted
        assert test_config2['autoplay_volume'] == 65
        assert test_config2['scroll_mode'] == "tempo"
        assert test_config2['search_paths'] == ["/custom/path", "~/Music"]

    def test_missing_defaults_added_on_load(self, temp_config_file):
        """Test that missing default values are added when loading config."""
        # Create a partial config file
        partial_config = {"autoplay_volume": 50}
        with open(temp_config_file, 'w') as f:
            json.dump(partial_config, f)

        # Load the config
        test_config = config.Config(temp_config_file)

        # Verify all default values are present
        assert test_config['autoplay_volume'] == 50  # From file
        assert isinstance(test_config['search_paths'], list)  # From defaults (test config active)
        assert test_config['scroll_mode'] == "wait"  # From defaults
        assert test_config['stale_threshold_days'] == 30  # From defaults

    def test_corrupted_file_fallback_to_defaults(self, temp_config_file):
        """Test that corrupted config files fall back to defaults."""
        # Create a corrupted JSON file
        with open(temp_config_file, 'w') as f:
            f.write("{ invalid json content ")

        # Config should load with defaults despite corruption
        test_config = config.Config(temp_config_file)

        assert test_config['autoplay_volume'] == 80
        assert isinstance(test_config['search_paths'], list)  # Test config active
        assert test_config['scroll_mode'] == "wait"
