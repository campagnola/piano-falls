"""
Tests for the pianofalls.song_info module.

These tests verify song metadata management, file tracking, and duplicate handling.
"""
import pytest
import tempfile
import pathlib
import json
import time
import os
from unittest.mock import Mock, patch, MagicMock

from pianofalls import config
from pianofalls import song_info as song_info_module
from pianofalls.song_info import SongInfo, default_song_config, _normalize_path


@pytest.fixture
def isolated_song_info_env(tmp_path):
    """Create isolated environment for SongInfo testing."""
    # Setup isolated test config
    config.config.load(tmp_path / 'test_config' / 'config.json')

    # Create test songs directory
    songs_dir = tmp_path / 'test_config' / 'songs'
    songs_dir.mkdir(parents=True, exist_ok=True)

    yield songs_dir

    # No cleanup needed - tmp_path handles it


@pytest.fixture
def sample_song_content():
    """Provide sample song content for creating files."""
    return {
        'song1.mid': b'fake midi content song1',
        'song2.mid': b'fake midi content song2',
        'song3.xml': b'<musicxml>fake musicxml content</musicxml>'
    }


@pytest.fixture
def test_duplicate_dialog_config():
    """Add test configuration for duplicate dialog handling."""
    original_config = config.config._data.copy()

    # Add test configuration for duplicate handling
    config.config['test_duplicate_dialog_choice'] = 'keep_all'  # Default choice

    yield

    # Restore original config
    config.config._data = original_config


class TestSongInfoBasics:
    """Test basic SongInfo functionality."""

    def test_songinfo_creation_new_sha(self, isolated_song_info_env):
        """Test creating SongInfo for new SHA."""
        test_sha = 'abc123def456'

        song_info = SongInfo(test_sha)

        assert song_info.sha == test_sha
        assert song_info.known_files == []
        assert song_info.last_verified is None
        assert song_info._song is None

        # Should have default settings
        expected_settings = default_song_config.copy()
        assert song_info._settings == expected_settings

        # Should create metadata file
        metadata_file = song_info._get_json_path()
        assert metadata_file.exists()

    def test_songinfo_creation_existing_sha(self, isolated_song_info_env):
        """Test creating SongInfo for existing SHA loads saved data."""
        test_sha = 'existing123'
        songs_dir = isolated_song_info_env

        # Create existing metadata file
        existing_data = {
            'sha': test_sha,
            'known_files': ['/test/song.mid'],
            'last_verified': 1234567890.0,
            'settings': {
                'speed': 120.0,
                'zoom': 1.5,
                'transpose': 2,
                'rating': 7,
                'loops': [[10, 20]],
                'track_modes': [['Piano', 0, 'notes']]
            }
        }

        metadata_file = songs_dir / f'{test_sha}.json'
        with open(metadata_file, 'w') as f:
            json.dump(existing_data, f)

        # Create SongInfo instance
        song_info = SongInfo(test_sha)

        assert song_info.sha == test_sha
        assert song_info.known_files == ['/test/song.mid']
        assert song_info.last_verified == 1234567890.0
        assert song_info.get_setting('speed') == 120.0
        assert song_info.get_setting('zoom') == 1.5
        assert song_info.get_setting('transpose') == 2
        assert song_info.get_setting('rating') == 7

    def test_normalize_path_function(self):
        """Test path normalization function."""
        # Test string path
        result = _normalize_path('~/test/file.mid')
        assert isinstance(result, pathlib.Path)
        assert result.is_absolute()

        # Test pathlib.Path
        path_obj = pathlib.Path('~/test/file.mid')
        result = _normalize_path(path_obj)
        assert isinstance(result, pathlib.Path)
        assert result.is_absolute()


class TestSettingsManagement:
    """Test song settings management."""

    def test_get_settings_returns_copy(self, isolated_song_info_env):
        """Test that get_settings returns a copy of settings."""
        song_info = SongInfo('test123')

        settings1 = song_info.get_settings()
        settings2 = song_info.get_settings()

        # Should be equal but not the same object
        assert settings1 == settings2
        assert settings1 is not settings2

        # Modifying returned dict shouldn't affect internal settings
        settings1['speed'] = 999.0
        assert song_info.get_setting('speed') != 999.0

    def test_get_setting_existing_key(self, isolated_song_info_env):
        """Test getting existing setting value."""
        song_info = SongInfo('test123')

        # Default values
        assert song_info.get_setting('speed') == 100.0
        assert song_info.get_setting('zoom') == 1.0
        assert song_info.get_setting('rating') == 0

    def test_get_setting_nonexistent_key(self, isolated_song_info_env):
        """Test getting nonexistent setting returns default."""
        song_info = SongInfo('test123')

        # Should return default value for unknown key
        result = song_info.get_setting('nonexistent_key')
        assert result is None  # Not in default_song_config

    def test_update_settings_valid_keys(self, isolated_song_info_env):
        """Test updating settings with valid keys."""
        song_info = SongInfo('test123')

        song_info.update_settings(
            speed=150.0,
            zoom=2.0,
            transpose=3,
            rating=8
        )

        assert song_info.get_setting('speed') == 150.0
        assert song_info.get_setting('zoom') == 2.0
        assert song_info.get_setting('transpose') == 3
        assert song_info.get_setting('rating') == 8

        # Should persist to file
        metadata_file = song_info._get_json_path()
        with open(metadata_file, 'r') as f:
            data = json.load(f)

        assert data['settings']['speed'] == 150.0
        assert data['settings']['zoom'] == 2.0

    def test_update_settings_invalid_keys(self, isolated_song_info_env):
        """Test that invalid setting keys are ignored."""
        song_info = SongInfo('test123')

        # Should ignore invalid key but process valid ones
        song_info.update_settings(
            speed=150.0,
            invalid_key='invalid_value'
        )

        assert song_info.get_setting('speed') == 150.0
        assert 'invalid_key' not in song_info._settings


class TestFileVerification:
    """Test file verification and cleanup."""

    def test_verify_files_removes_nonexistent(self, isolated_song_info_env, tmp_path):
        """Test that verify_files removes nonexistent files."""
        song_info = SongInfo('test123')

        # Add some fake file paths
        real_file = tmp_path / 'real_file.mid'
        real_file.write_bytes(b'content')
        fake_file = tmp_path / 'fake_file.mid'  # Don't create this

        song_info.known_files = [str(real_file), str(fake_file)]
        song_info.save()

        # Verify files
        song_info.verify_files()

        # Only real file should remain
        assert song_info.known_files == [str(real_file)]
        assert song_info.last_verified is not None

    def test_verify_files_updates_timestamp(self, isolated_song_info_env, tmp_path):
        """Test that verify_files updates last_verified timestamp."""
        song_info = SongInfo('test123')

        # Create real file
        real_file = tmp_path / 'real_file.mid'
        real_file.write_bytes(b'content')
        song_info.known_files = [str(real_file)]

        initial_time = song_info.last_verified

        # Verify files
        time.sleep(0.01)  # Ensure timestamp changes
        song_info.verify_files()

        # Timestamp should be updated
        assert song_info.last_verified != initial_time
        assert song_info.last_verified is not None

    def test_verify_files_empty_list(self, isolated_song_info_env):
        """Test verify_files with empty file list."""
        song_info = SongInfo('test123')

        assert song_info.known_files == []
        initial_time = song_info.last_verified

        song_info.verify_files()

        # Timestamp should remain unchanged when no files are tracked
        assert song_info.last_verified == initial_time


class TestStaleDetection:
    """Test stale metadata detection."""

    def test_is_stale_with_files(self, isolated_song_info_env):
        """Test that songs with files are never stale."""
        song_info = SongInfo('test123')
        song_info.known_files = ['/some/file.mid']
        song_info.last_verified = 1.0  # Very old timestamp

        assert not song_info.is_stale()

    def test_is_stale_never_verified(self, isolated_song_info_env):
        """Test that never-verified songs are not stale."""
        song_info = SongInfo('test123')
        song_info.known_files = []
        song_info.last_verified = None

        assert not song_info.is_stale()

    def test_is_stale_recent_verification(self, isolated_song_info_env):
        """Test that recently verified empty songs are not stale."""
        song_info = SongInfo('test123')
        song_info.known_files = []
        song_info.last_verified = time.time()  # Very recent

        assert not song_info.is_stale()

    def test_is_stale_old_verification(self, isolated_song_info_env):
        """Test that old empty songs are stale."""
        song_info = SongInfo('test123')
        song_info.known_files = []

        # Set very old timestamp (more than 30 days ago)
        thirty_one_days_ago = time.time() - (31 * 24 * 60 * 60)
        song_info.last_verified = thirty_one_days_ago

        assert song_info.is_stale()

    def test_is_stale_after_file_removed(self, isolated_song_info_env, isolated_config, tmp_path):
        """Test staleness after a tracked file is removed."""
        config.config['stale_threshold_days'] = 1 / 86400

        song_path = tmp_path / 'song1.mid'
        song_path.write_bytes(b'fake midi content for song1')

        song_info = SongInfo('test123')
        song_info.check_duplicate(song_path)

        assert not song_info.is_stale()

        song_path.unlink()
        song_info.verify_files()

        assert not song_info.is_stale()

        time.sleep(1.1)

        assert song_info.is_stale()


class TestDuplicateDetection:
    """Test duplicate file detection and handling."""

    def test_check_duplicate_first_file(self, isolated_song_info_env, tmp_path):
        """Test that first file with SHA is simply added."""
        song_info = SongInfo('test123')

        test_file = tmp_path / 'test_song.mid'
        test_file.write_bytes(b'content')

        song_info.check_duplicate(str(test_file))

        assert str(test_file) in song_info.known_files
        assert song_info.last_verified is not None

    def test_check_duplicate_same_file_twice(self, isolated_song_info_env, tmp_path):
        """Test that checking same file twice doesn't duplicate it."""
        song_info = SongInfo('test123')

        test_file = tmp_path / 'test_song.mid'
        test_file.write_bytes(b'content')

        # Add file twice
        song_info.check_duplicate(str(test_file))
        initial_count = len(song_info.known_files)

        song_info.check_duplicate(str(test_file))
        final_count = len(song_info.known_files)

        assert initial_count == final_count
        assert song_info.known_files.count(str(test_file)) == 1

    @patch('pianofalls.song_info.QtWidgets.QMessageBox')
    def test_duplicate_dialog_keep_all(self, mock_msgbox, isolated_song_info_env, tmp_path):
        """Test duplicate handling when user chooses 'Keep All'."""
        song_info = SongInfo('test123')

        # Add first file
        file1 = tmp_path / 'song1.mid'
        file1.write_bytes(b'content')
        song_info.known_files = [str(file1)]

        # Mock dialog to return "Keep All" choice
        mock_msg_instance = Mock()
        mock_msgbox.return_value = mock_msg_instance

        keep_all_button = Mock()
        mock_msg_instance.addButton.return_value = keep_all_button
        mock_msg_instance.clickedButton.return_value = keep_all_button

        # Add duplicate file
        file2 = tmp_path / 'song2.mid'
        file2.write_bytes(b'content')

        song_info.check_duplicate(str(file2))

        # Both files should be kept
        assert str(file1) in song_info.known_files
        assert str(file2) in song_info.known_files
        assert len(song_info.known_files) == 2

    @patch('pianofalls.song_info.QtWidgets.QMessageBox')
    def test_duplicate_dialog_delete_new(self, mock_msgbox, isolated_song_info_env, tmp_path):
        """Test duplicate handling when user chooses 'Delete New'."""
        song_info = SongInfo('test123')

        # Add first file
        file1 = tmp_path / 'song1.mid'
        file1.write_bytes(b'content')
        song_info.known_files = [str(file1)]

        # Mock dialog to return "Delete New" choice
        mock_msg_instance = Mock()
        mock_msgbox.return_value = mock_msg_instance

        keep_all_button = Mock()
        delete_new_button = Mock()
        mock_msg_instance.addButton.side_effect = [keep_all_button, delete_new_button, Mock()]
        mock_msg_instance.clickedButton.return_value = delete_new_button

        # Add duplicate file
        file2 = tmp_path / 'song2.mid'
        file2.write_bytes(b'content')

        song_info.check_duplicate(str(file2))

        # Only first file should remain, second should be deleted
        assert str(file1) in song_info.known_files
        assert str(file2) not in song_info.known_files
        assert len(song_info.known_files) == 1
        assert not file2.exists()  # File should be deleted

    @patch('pianofalls.song_info.QtWidgets.QMessageBox')
    def test_duplicate_dialog_delete_old(self, mock_msgbox, isolated_song_info_env, tmp_path):
        """Test duplicate handling when user chooses 'Delete Old'."""
        song_info = SongInfo('test123')

        # Add first file
        file1 = tmp_path / 'song1.mid'
        file1.write_bytes(b'content')
        song_info.known_files = [str(file1)]

        # Mock dialog to return "Delete Old" choice
        mock_msg_instance = Mock()
        mock_msgbox.return_value = mock_msg_instance

        keep_all_button = Mock()
        delete_new_button = Mock()
        delete_old_button = Mock()
        mock_msg_instance.addButton.side_effect = [keep_all_button, delete_new_button, delete_old_button]
        mock_msg_instance.clickedButton.return_value = delete_old_button

        # Add duplicate file
        file2 = tmp_path / 'song2.mid'
        file2.write_bytes(b'content')

        song_info.check_duplicate(str(file2))

        # Only new file should remain, old should be deleted
        assert str(file1) not in song_info.known_files
        assert str(file2) in song_info.known_files
        assert len(song_info.known_files) == 1
        assert not file1.exists()  # Old file should be deleted

    def test_duplicate_dialog_multiple_existing_files(self, isolated_song_info_env, tmp_path):
        """Test duplicate dialog text with multiple existing files."""
        with patch('pianofalls.song_info.QtWidgets.QMessageBox') as mock_msgbox:
            song_info = SongInfo('test123')

            # Add multiple existing files
            file1 = tmp_path / 'song1.mid'
            file2 = tmp_path / 'song2.mid'
            file1.write_bytes(b'content')
            file2.write_bytes(b'content')
            song_info.known_files = [str(file1), str(file2)]

            # Mock dialog
            mock_msg_instance = Mock()
            mock_msgbox.return_value = mock_msg_instance

            keep_all_button = Mock()
            mock_msg_instance.addButton.return_value = keep_all_button
            mock_msg_instance.clickedButton.return_value = keep_all_button

            # Add duplicate file
            file3 = tmp_path / 'song3.mid'
            file3.write_bytes(b'content')

            song_info.check_duplicate(str(file3))

            # Verify button text mentions multiple files
            call_args = mock_msg_instance.addButton.call_args_list
            delete_old_button_text = call_args[2][0][0]
            assert 'Delete All 2 Existing' in delete_old_button_text


class TestSongLoading:
    """Test song loading functionality."""

    @patch('pianofalls.song_info.load_midi')
    def test_get_song_midi_file(self, mock_load_midi, isolated_song_info_env, tmp_path):
        """Test loading MIDI song."""
        song_info = SongInfo('test123')

        midi_file = tmp_path / 'test.mid'
        midi_file.write_bytes(b'fake midi content')
        song_info.known_files = [str(midi_file)]

        mock_song = Mock()
        mock_load_midi.return_value = mock_song

        result = song_info.get_song()

        assert result is mock_song
        assert song_info._song is mock_song
        mock_load_midi.assert_called_once_with(str(midi_file))

    @patch('pianofalls.song_info.load_musicxml')
    def test_get_song_musicxml_file(self, mock_load_musicxml, isolated_song_info_env, tmp_path):
        """Test loading MusicXML song."""
        song_info = SongInfo('test123')

        xml_file = tmp_path / 'test.xml'
        xml_file.write_bytes(b'fake musicxml content')
        song_info.known_files = [str(xml_file)]

        mock_song = Mock()
        mock_load_musicxml.return_value = mock_song

        result = song_info.get_song()

        assert result is mock_song
        assert song_info._song is mock_song
        mock_load_musicxml.assert_called_once_with(str(xml_file))

    def test_get_song_no_files(self, isolated_song_info_env):
        """Test getting song with no files raises ValueError."""
        song_info = SongInfo('test123')

        with pytest.raises(ValueError, match="No valid files available"):
            song_info.get_song()

    def test_get_song_uses_cache(self, isolated_song_info_env, tmp_path):
        """Test that subsequent calls use cached song."""
        with patch('pianofalls.song_info.load_midi') as mock_load_midi:
            song_info = SongInfo('test123')

            midi_file = tmp_path / 'test.mid'
            midi_file.write_bytes(b'fake midi content')
            song_info.known_files = [str(midi_file)]

            mock_song = Mock()
            mock_load_midi.return_value = mock_song

            # First call
            result1 = song_info.get_song()

            # Second call
            result2 = song_info.get_song()

            assert result1 is result2
            # Should only load once
            mock_load_midi.assert_called_once()

    def test_reload_song_forces_reload(self, isolated_song_info_env, tmp_path):
        """Test that reload_song forces reload from file."""
        with patch('pianofalls.song_info.load_midi') as mock_load_midi:
            song_info = SongInfo('test123')

            midi_file = tmp_path / 'test.mid'
            midi_file.write_bytes(b'fake midi content')
            song_info.known_files = [str(midi_file)]

            mock_song = Mock()
            mock_load_midi.return_value = mock_song

            # Load once
            song_info.get_song()

            # Force reload
            result = song_info.reload_song()

            assert result is mock_song
            # Should have loaded twice
            assert mock_load_midi.call_count == 2


class TestNameProperty:
    """Test song name property."""

    def test_name_property_single_file(self, isolated_song_info_env, tmp_path):
        """Test name property with single file."""
        song_info = SongInfo('test123')

        test_file = tmp_path / 'my_song.mid'
        test_file.write_bytes(b'content')
        song_info.known_files = [str(test_file)]

        assert song_info.name == 'my_song.mid'

    def test_name_property_multiple_files(self, isolated_song_info_env, tmp_path):
        """Test name property uses first file."""
        song_info = SongInfo('test123')

        file1 = tmp_path / 'first_song.mid'
        file2 = tmp_path / 'second_song.mid'
        file1.write_bytes(b'content')
        file2.write_bytes(b'content')

        song_info.known_files = [str(file1), str(file2)]

        assert song_info.name == 'first_song.mid'


class TestPersistence:
    """Test data persistence to JSON files."""

    def test_save_and_load_cycle(self, isolated_song_info_env):
        """Test complete save and load cycle."""
        test_sha = 'persist123'

        # Create and modify song info
        song_info1 = SongInfo(test_sha)
        song_info1.known_files = ['/test/file1.mid', '/test/file2.mid']
        song_info1.last_verified = 1234567890.0
        song_info1.update_settings(speed=150.0, zoom=2.5, rating=9)

        # Create new instance (should load from file)
        song_info2 = SongInfo(test_sha)

        # Should have loaded all data correctly
        assert song_info2.sha == test_sha
        assert song_info2.known_files == ['/test/file1.mid', '/test/file2.mid']
        assert song_info2.last_verified == 1234567890.0
        assert song_info2.get_setting('speed') == 150.0
        assert song_info2.get_setting('zoom') == 2.5
        assert song_info2.get_setting('rating') == 9

    def test_settings_backward_compatibility(self, isolated_song_info_env):
        """Test loading data with missing settings fields."""
        test_sha = 'compat123'
        songs_dir = isolated_song_info_env

        # Create metadata with partial settings
        partial_data = {
            'sha': test_sha,
            'known_files': ['/test/song.mid'],
            'last_verified': 1234567890.0,
            'settings': {
                'speed': 120.0,
                'zoom': 1.5
                # Missing transpose, rating, loops, track_modes
            }
        }

        metadata_file = songs_dir / f'{test_sha}.json'
        with open(metadata_file, 'w') as f:
            json.dump(partial_data, f)

        # Load song info
        song_info = SongInfo(test_sha)

        # Should have loaded existing settings and filled in defaults
        assert song_info.get_setting('speed') == 120.0
        assert song_info.get_setting('zoom') == 1.5
        assert song_info.get_setting('transpose') == 0  # Default
        assert song_info.get_setting('rating') == 0  # Default
        assert song_info.get_setting('loops') == []  # Default
        assert song_info.get_setting('track_modes') == []  # Default
