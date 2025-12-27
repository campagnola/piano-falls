"""
Tests for the pianofalls.song_repository module.

These tests verify song metadata management and SHA-based caching.
"""
import pytest
import tempfile
import pathlib
import json
import hashlib
from unittest.mock import Mock, patch

from pianofalls import config
from pianofalls.song_repository import SongRepository
from pianofalls.song_info import SongInfo


@pytest.fixture
def isolated_song_repository(tmp_path):
    """Create isolated SongRepository with test config."""
    # Setup isolated test config
    config.use_test_config(path=tmp_path / 'test_config')

    # Reset SongRepository singleton
    SongRepository._instance = None

    # Create test songs directory
    songs_dir = tmp_path / 'test_config' / 'songs'
    songs_dir.mkdir(parents=True, exist_ok=True)

    sr = SongRepository.get_instance()

    yield sr, songs_dir

    # Cleanup
    SongRepository._instance = None


@pytest.fixture
def sample_song_files(tmp_path):
    """Create sample song files with known content."""
    music_dir = tmp_path / 'music'
    music_dir.mkdir()

    # Create files with known content so we can predict SHAs
    files = {
        'song1.mid': b'fake midi content song1',
        'song2.mid': b'fake midi content song2',
        'duplicate.mid': b'fake midi content song1',  # Same content as song1
        'song3.xml': b'<musicxml>fake content</musicxml>',
    }

    created_files = {}
    file_shas = {}

    for filename, content in files.items():
        filepath = music_dir / filename
        filepath.write_bytes(content)
        created_files[filename] = filepath

        # Calculate SHA for testing
        sha = hashlib.sha1(content).hexdigest()
        file_shas[filename] = sha

    return music_dir, created_files, file_shas


@pytest.fixture
def existing_song_metadata(tmp_path):
    """Create existing song metadata files for testing."""
    songs_dir = tmp_path / 'test_config' / 'songs'
    songs_dir.mkdir(parents=True, exist_ok=True)

    # Create sample metadata files
    metadata_files = {
        'abc123def456': {
            'sha': 'abc123def456',
            'known_files': ['/test/song1.mid'],
            'last_verified': 1234567890.0,
            'settings': {
                'speed': 120.0,
                'zoom': 1.5,
                'transpose': 0,
                'rating': 8,
                'loops': [[10, 20]],
                'track_modes': []
            }
        },
        'fedcba654321': {
            'sha': 'fedcba654321',
            'known_files': ['/test/song2.mid', '/test/song2_copy.mid'],
            'last_verified': 1234567890.0,
            'settings': {
                'speed': 80.0,
                'zoom': 2.0,
                'transpose': 2,
                'rating': 0,
                'loops': [],
                'track_modes': []
            }
        }
    }

    for sha, data in metadata_files.items():
        metadata_file = songs_dir / f'{sha}.json'
        with open(metadata_file, 'w') as f:
            json.dump(data, f, indent=2)

    return songs_dir, metadata_files


class TestSongRepositoryBasics:
    """Test basic SongRepository functionality."""

    def test_singleton_pattern(self, isolated_song_repository):
        """Test that SongRepository follows singleton pattern."""
        sr1, _ = isolated_song_repository
        sr2 = SongRepository.get_instance()

        assert sr1 is sr2

    def test_direct_instantiation_raises_error(self, isolated_song_repository):
        """Test that direct instantiation raises RuntimeError."""
        # First call get_instance to set up the singleton
        sr1, _ = isolated_song_repository

        # Now try direct instantiation, which should fail
        with pytest.raises(RuntimeError):
            SongRepository()


class TestSongLoading:
    """Test song metadata loading functionality."""

    def test_load_all_songs_empty_directory(self, isolated_song_repository):
        """Test loading songs from empty directory."""
        sr, songs_dir = isolated_song_repository

        loaded_songs = sr.load_all_songs()

        assert loaded_songs == {}
        assert sr._song_cache == {}

    def test_load_all_songs_with_existing_metadata(self, isolated_song_repository, existing_song_metadata):
        """Test loading existing song metadata files."""
        sr, _ = isolated_song_repository
        songs_dir, metadata_files = existing_song_metadata

        loaded_songs = sr.load_all_songs()

        # Should have loaded both songs
        assert len(loaded_songs) == 2
        assert 'abc123def456' in loaded_songs
        assert 'fedcba654321' in loaded_songs

        # Verify the loaded SongInfo instances have correct data
        song1 = loaded_songs['abc123def456']
        assert isinstance(song1, SongInfo)
        assert song1.sha == 'abc123def456'
        assert song1.known_files == ['/test/song1.mid']
        assert song1.get_setting('speed') == 120.0

        song2 = loaded_songs['fedcba654321']
        assert song2.sha == 'fedcba654321'
        assert song2.known_files == ['/test/song2.mid', '/test/song2_copy.mid']
        assert song2.get_setting('speed') == 80.0

    def test_load_corrupted_metadata_file(self, isolated_song_repository):
        """Test that corrupted metadata files are skipped with warning."""
        sr, songs_dir = isolated_song_repository

        # Create corrupted JSON file
        corrupted_file = songs_dir / 'corrupted.json'
        corrupted_file.write_text('{ invalid json content')

        # Should load without crashing, but skip corrupted file
        loaded_songs = sr.load_all_songs()

        assert loaded_songs == {}


class TestSongInfoRetrieval:
    """Test song info retrieval and caching."""

    def test_get_song_info_new_file(self, isolated_song_repository, sample_song_files):
        """Test getting SongInfo for new file creates and caches it."""
        sr, _ = isolated_song_repository
        music_dir, created_files, file_shas = sample_song_files

        filepath = created_files['song1.mid']
        expected_sha = file_shas['song1.mid']

        song_info = sr.get_song_info(filepath)

        # Should return SongInfo instance
        assert isinstance(song_info, SongInfo)
        assert song_info.sha == expected_sha

        # Should be cached
        assert expected_sha in sr._song_cache
        assert sr._song_cache[expected_sha] is song_info

        # Should track the file
        assert str(filepath) in song_info.known_files

    def test_get_song_info_cached_file(self, isolated_song_repository, sample_song_files):
        """Test that subsequent calls return cached SongInfo."""
        sr, _ = isolated_song_repository
        music_dir, created_files, file_shas = sample_song_files

        filepath = created_files['song1.mid']

        # First call
        song_info1 = sr.get_song_info(filepath)

        # Second call should return same instance
        song_info2 = sr.get_song_info(filepath)

        assert song_info1 is song_info2

    @patch('pianofalls.song_info.SongInfo.check_duplicate')
    def test_get_song_info_calls_duplicate_check(self, mock_check_duplicate, isolated_song_repository, sample_song_files):
        """Test that get_song_info calls duplicate checking."""
        sr, _ = isolated_song_repository
        music_dir, created_files, file_shas = sample_song_files

        filepath = created_files['song1.mid']

        sr.get_song_info(filepath)

        # Should have called check_duplicate with the filepath
        mock_check_duplicate.assert_called_once_with(str(filepath.resolve()))

    def test_sha_computation_cached(self, isolated_song_repository, sample_song_files):
        """Test that SHA computation is cached via LRU cache."""
        sr, _ = isolated_song_repository
        music_dir, created_files, file_shas = sample_song_files

        filepath = str(created_files['song1.mid'])

        # Compute SHA twice
        sha1 = sr._compute_sha(filepath)
        sha2 = sr._compute_sha(filepath)

        assert sha1 == sha2
        assert sha1 == file_shas['song1.mid']

        # Verify cache info (should have 1 hit after second call)
        cache_info = sr._compute_sha.cache_info()
        assert cache_info.hits >= 1


class TestDuplicateDetection:
    """Test duplicate file detection scenarios."""

    @patch('pianofalls.song_info.SongInfo.check_duplicate')
    def test_duplicate_files_same_sha(self, mock_check_duplicate, isolated_song_repository, sample_song_files):
        """Test that files with same content get same SHA and SongInfo."""
        sr, _ = isolated_song_repository
        music_dir, created_files, file_shas = sample_song_files

        # song1.mid and duplicate.mid have same content
        filepath1 = created_files['song1.mid']
        filepath_dup = created_files['duplicate.mid']

        # Mock the check_duplicate method to avoid GUI dialog
        mock_check_duplicate.side_effect = lambda fp: None

        # Get SongInfo for both
        song_info1 = sr.get_song_info(filepath1)
        song_info_dup = sr.get_song_info(filepath_dup)

        # Should be same instance since same SHA
        assert song_info1 is song_info_dup

        # Both files should have been processed
        assert mock_check_duplicate.call_count == 2

    @patch('pianofalls.song_info.SongInfo.check_duplicate')
    def test_different_files_different_sha(self, mock_check_duplicate, isolated_song_repository, sample_song_files):
        """Test that files with different content get different SHAs."""
        sr, _ = isolated_song_repository
        music_dir, created_files, file_shas = sample_song_files

        filepath1 = created_files['song1.mid']
        filepath2 = created_files['song2.mid']

        # Mock check_duplicate to just add files without GUI dialog
        def mock_check_dup_func(filepath):
            pass  # Do nothing, just avoid the dialog

        mock_check_duplicate.side_effect = mock_check_dup_func

        song_info1 = sr.get_song_info(filepath1)
        song_info2 = sr.get_song_info(filepath2)

        # Should be different instances
        assert song_info1 is not song_info2
        assert song_info1.sha != song_info2.sha


class TestStaleMetadataCleanup:
    """Test cleanup of stale metadata files."""

    def test_stale_songs_removed_on_load(self, isolated_song_repository):
        """Test that stale songs are removed during loading."""
        sr, songs_dir = isolated_song_repository

        # Create metadata for a stale song (no files, old timestamp)
        stale_sha = 'stale123456'
        stale_metadata = {
            'sha': stale_sha,
            'known_files': [],  # No files
            'last_verified': 1000000.0,  # Very old timestamp
            'settings': {'speed': 100.0, 'zoom': 1.0, 'transpose': 0, 'rating': 0, 'loops': [], 'track_modes': []}
        }

        stale_file = songs_dir / f'{stale_sha}.json'
        with open(stale_file, 'w') as f:
            json.dump(stale_metadata, f)

        assert stale_file.exists()

        # Load songs - should remove stale entry
        loaded_songs = sr.load_all_songs()

        # Stale song should not be in loaded songs
        assert stale_sha not in loaded_songs

        # Stale file should have been deleted
        assert not stale_file.exists()

    def test_non_stale_songs_preserved(self, isolated_song_repository):
        """Test that non-stale songs are preserved."""
        sr, songs_dir = isolated_song_repository

        # Create metadata for a non-stale song (has files)
        non_stale_sha = 'notstale123'
        non_stale_metadata = {
            'sha': non_stale_sha,
            'known_files': ['/some/existing/file.mid'],  # Has files
            'last_verified': 1000000.0,  # Old timestamp but has files
            'settings': {'speed': 100.0, 'zoom': 1.0, 'transpose': 0, 'rating': 0, 'loops': [], 'track_modes': []}
        }

        non_stale_file = songs_dir / f'{non_stale_sha}.json'
        with open(non_stale_file, 'w') as f:
            json.dump(non_stale_metadata, f)

        # Load songs
        loaded_songs = sr.load_all_songs()

        # Non-stale song should be preserved
        assert non_stale_sha in loaded_songs
        assert non_stale_file.exists()


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_compute_sha_nonexistent_file(self, isolated_song_repository):
        """Test SHA computation for nonexistent file raises ValueError."""
        sr, _ = isolated_song_repository

        with pytest.raises(ValueError, match="Could not read file for SHA calculation"):
            sr._compute_sha('/nonexistent/file.mid')

    def test_load_songs_nonexistent_directory(self, isolated_song_repository):
        """Test loading songs when songs directory doesn't exist."""
        sr, songs_dir = isolated_song_repository

        # Remove songs directory
        songs_dir.rmdir()

        # Should handle gracefully
        loaded_songs = sr.load_all_songs()
        assert loaded_songs == {}


class TestIntegrationScenarios:
    """Test complex integration scenarios."""

    @patch('pianofalls.song_info.SongInfo.check_duplicate')
    def test_full_workflow_new_song(self, mock_check_duplicate, isolated_song_repository, sample_song_files):
        """Test complete workflow for a new song."""
        sr, _ = isolated_song_repository
        music_dir, created_files, file_shas = sample_song_files

        filepath = created_files['song1.mid']
        expected_sha = file_shas['song1.mid']

        # Mock check_duplicate to avoid GUI dialog
        mock_check_duplicate.side_effect = lambda fp: None

        # 1. Get song info (should create new)
        song_info = sr.get_song_info(filepath)

        # 2. Verify it's cached
        assert sr._song_cache[expected_sha] is song_info

        # 3. Verify metadata file was created
        metadata_file = song_info._get_json_path()
        assert metadata_file.exists()

        # 4. Reload all songs and verify persistence
        sr.load_all_songs()
        assert expected_sha in sr._song_cache

        # 5. Get same song again, should return cached instance
        song_info2 = sr.get_song_info(filepath)
        assert song_info is song_info2