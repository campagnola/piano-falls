"""
Pytest configuration file.

This file contains session-wide fixtures and configuration for the test suite.
"""
import pathlib
import pytest
from pianofalls import config
from pianofalls.file_manager import FileManager


@pytest.fixture(scope="session", autouse=True)
def setup_test_config(tmp_path_factory):
    """
    Configure pianofalls to use test configuration before running any tests.

    This fixture runs automatically once per test session before any tests execute,
    ensuring that all tests use the test configuration settings.
    """
    base_dir = tmp_path_factory.mktemp('pianofalls_config')
    config_file = base_dir / 'config.json'
    config.config.load(config_file)
    test_songs_dir = base_dir / 'test_songs'
    test_songs_dir.mkdir(parents=True, exist_ok=True)
    config.config['search_paths'] = [str(test_songs_dir)]



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


@pytest.fixture
def isolated_file_manager(tmp_path, qapp):
    """Create an isolated FileManager instance with test config."""
    # Setup isolated test config
    config.config.load(tmp_path / 'test_config' / 'config.json')

    # Reset FileManager singleton
    FileManager._instance = None

    # Create test directories
    test_search_path = tmp_path / 'music'
    test_search_path.mkdir(exist_ok=True)

    # Update config to use test search path
    config.config['search_paths'] = [str(test_search_path)]

    fm = FileManager.get_instance()

    yield fm, test_search_path

    # Cleanup
    FileManager._instance = None


@pytest.fixture
def sample_music_files(tmp_path):
    """Create sample music files for testing."""
    music_dir = tmp_path / 'music'
    music_dir.mkdir(exist_ok=True)

    # Create various file types
    files = {
        'song1.mid': b'fake midi content for song1',
        'song2.midi': b'fake midi content for song2',
        'song3.xml': b'<musicxml>fake musicxml content</musicxml>',
        'song4.mxl': b'fake compressed musicxml',
        'song5.musicxml': b'<score>more fake content</score>',
        'readme.txt': b'not a music file',
        'song6.mp3': b'fake mp3 content'  # Not supported
    }

    created_files = {}
    for filename, content in files.items():
        filepath = music_dir / filename
        filepath.write_bytes(content)
        created_files[filename] = filepath

    # Create a subdirectory
    subdir = music_dir / 'classical'
    subdir.mkdir(exist_ok=True)
    subdir_file = subdir / 'bach.mid'
    subdir_file.write_bytes(b'fake bach midi')
    created_files['classical/bach.mid'] = subdir_file

    return music_dir, created_files


@pytest.fixture
def isolated_config():
    """Isolate config data mutations within a test."""
    original_config = config.config._data.copy()

    yield

    config.config._data = original_config
