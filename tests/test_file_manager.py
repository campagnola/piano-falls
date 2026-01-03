"""
Tests for the pianofalls.file_manager module.

These tests verify file management operations and notifications.
"""
import pytest
import time
import threading
from unittest.mock import patch

from pianofalls import config
from pianofalls.file_manager import FileManager
from pianofalls.qt import QtCore, QtTest

# Note: Simplified event processing without QtTest dependency


@pytest.fixture
def isolated_file_manager(tmp_path):
    """Create an isolated FileManager instance with test config."""
    # Setup isolated test config
    config.use_test_config(path=tmp_path / 'test_config')

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


class TestFileManagerBasics:
    """Test basic FileManager functionality."""

    def test_singleton_pattern(self, isolated_file_manager):
        """Test that FileManager follows singleton pattern."""
        fm1, _ = isolated_file_manager
        fm2 = FileManager.get_instance()

        assert fm1 is fm2

    def test_get_search_paths(self, isolated_file_manager):
        """Test getting search paths from config."""
        fm, test_search_path = isolated_file_manager

        search_paths = fm.get_search_paths()
        assert search_paths == [str(test_search_path)]


class TestFileListingAndFiltering:
    """Test file listing and filtering functionality."""

    def test_list_folder_contents_filters_correctly(self, isolated_file_manager, sample_music_files):
        """Test that folder listing filters to only supported files."""
        fm, _ = isolated_file_manager
        music_dir, _ = sample_music_files

        contents = fm.list_folder_contents(music_dir)

        # Should include supported music files and directories
        expected_files = {
            'song1.mid', 'song2.midi', 'song3.xml',
            'song4.mxl', 'song5.musicxml', 'classical'
        }

        actual_files = {p.name for p in contents}

        assert expected_files == actual_files

        # Should NOT include unsupported files
        assert 'readme.txt' not in actual_files
        assert 'song6.mp3' not in actual_files

    def test_list_folder_contents_sorts_correctly(self, isolated_file_manager, sample_music_files):
        """Test that directories come before files, then alphabetically."""
        fm, _ = isolated_file_manager
        music_dir, _ = sample_music_files

        contents = fm.list_folder_contents(music_dir)

        # First item should be the directory
        assert contents[0].name == 'classical'
        assert contents[0].is_dir()

        # Remaining items should be files in alphabetical order
        file_names = [p.name for p in contents[1:] if p.is_file()]
        assert file_names == sorted(file_names)

    def test_list_invalid(self, isolated_file_manager, sample_music_files):
        """Test listing invalid paths raises appropriate errors."""
        fm, _ = isolated_file_manager
        _, created_files = sample_music_files

        # Test listing a nonexistent directory raises FileNotFoundError.
        with pytest.raises(FileNotFoundError):
            fm.list_folder_contents('/nonexistent/path')

        # Test listing a file instead of directory raises NotADirectoryError
        with pytest.raises(NotADirectoryError):
            fm.list_folder_contents(created_files['song1.mid'])


class TestFileOperations:
    """Test file operations like move, rename, delete."""

    def test_move_file_success(self, isolated_file_manager, sample_music_files):
        """Test successful file move operation."""
        fm, _ = isolated_file_manager
        music_dir, created_files = sample_music_files

        # Create destination directory
        dest_dir = music_dir / 'moved'
        dest_dir.mkdir()

        old_path = created_files['song1.mid']
        new_path = dest_dir / 'moved_song1.mid'

        # Capture signals
        signal_received = []
        fm.file_changed.connect(lambda path: signal_received.append(path))

        # Perform move
        fm.move_file(old_path, new_path)

        # Verify file was moved
        assert not old_path.exists()
        assert new_path.exists()
        assert new_path.read_bytes() == b'fake midi content for song1'

        # Verify signals were emitted for both directories
        assert len(signal_received) == 2
        assert str(old_path.parent) in signal_received
        assert str(new_path.parent) in signal_received

    def test_move_file_destination_exists(self, isolated_file_manager, sample_music_files):
        """Test move operation fails when destination exists."""
        fm, _ = isolated_file_manager
        music_dir, created_files = sample_music_files

        old_path = created_files['song1.mid']
        new_path = created_files['song2.midi']  # Already exists

        with pytest.raises(FileExistsError):
            fm.move_file(old_path, new_path)

    def test_rename_file_success(self, isolated_file_manager, sample_music_files):
        """Test successful file rename operation."""
        fm, _ = isolated_file_manager
        music_dir, created_files = sample_music_files

        old_path = created_files['song1.mid']
        original_content = old_path.read_bytes()

        # Capture signals
        signal_received = []
        fm.file_changed.connect(lambda path: signal_received.append(path))

        # Perform rename
        fm.rename_file(old_path, 'renamed_song.mid')

        new_path = music_dir / 'renamed_song.mid'

        # Verify file was renamed
        assert not old_path.exists()
        assert new_path.exists()
        assert new_path.read_bytes() == original_content

        # Verify signal was emitted
        assert signal_received == [str(music_dir)]

    def test_delete_file_success(self, isolated_file_manager, sample_music_files):
        """Test successful file deletion."""
        fm, _ = isolated_file_manager
        music_dir, created_files = sample_music_files

        target_path = created_files['song1.mid']

        # Capture signals
        signal_received = []
        fm.file_changed.connect(lambda path: signal_received.append(path))

        # Perform delete
        fm.delete_file(target_path)

        # Verify file was deleted
        assert not target_path.exists()

        # Verify signal was emitted
        assert signal_received == [str(music_dir)]


class TestFileWatching:
    """Test file system watching functionality."""

    def test_file_watching_integration(self, isolated_file_manager):
        """Test complete file watching workflow: watch, modify, signal, unwatch."""
        fm, test_search_path = isolated_file_manager

        # Create a directory to watch
        watch_path = test_search_path / 'watched'
        watch_path.mkdir()

        # Set up signal capture
        signals_received = []
        fm.file_changed.connect(lambda path: signals_received.append(path))

        # Start watching the directory
        fm.add_watch_path(watch_path)

        assert len(signals_received) == 0, 'No signals should be emitted on adding watch'

        # Create a file in the watched directory
        test_file = watch_path / 'test_song.mid'
        test_file.write_bytes(b'fake midi content')

        # Give the file system watcher time to notice the change
        QtTest.QTest.qWait(200)

        # Force immediate update to trigger signal so we don't have to wait
        fm.force_immediate_update(watch_path)

        # Should have received a change signal for the directory
        assert len(signals_received) > 0
        assert str(watch_path) in signals_received

        # Clear signals for next test
        signals_received.clear()

        # Remove the watch
        fm.remove_watch_path(watch_path)

        # Modify the directory again (create another file)
        test_file2 = watch_path / 'another_song.mid'
        test_file2.write_bytes(b'more fake midi content')

        # Give time for any potential signals (but don't force update)
        QtTest.QTest.qWait(200)

        # Force immediate update to trigger signal so we don't have to wait
        fm.force_immediate_update(watch_path)

        # Should NOT have received any signals since path is no longer watched
        assert len(signals_received) == 0


class TestSimulatedDownload:
    """Test simulated file download using background threads and Qt event processing."""

    def test_background_download_with_stability_monitoring(self, isolated_file_manager):
        """Test simulation of background file download with proper Qt event processing."""
        fm, test_search_path = isolated_file_manager

        # Set up signal capture
        signals_received = []
        fm.file_changed.connect(lambda path: signals_received.append(path))

        # Add watch on the directory
        fm.add_watch_path(test_search_path)

        download_path = test_search_path / 'downloading.mid'
        chunk_data = b'fake midi chunk data' * 50  # Reasonable chunk size
        total_chunks = 8

        def download_worker():
            """Simulate a file download."""
            with open(download_path, 'wb') as f:
                for _ in range(total_chunks):
                    time.sleep(0.1)
                    f.write(chunk_data)
                    f.flush()

        # Clear any initial signals
        signals_received.clear()

        # Start background download
        download_thread = threading.Thread(target=download_worker, daemon=True)
        download_thread.start()

        start_time = time.time()
        while download_thread.is_alive() and (time.time() - start_time) < 2.0:
            QtTest.QTest.qWait(200)
        assert not download_thread.is_alive(), "Download thread did not finish in time"

        assert len(signals_received) == 0, 'No file change signals should be emitted during download'

        # Verify file exists on disk but is hidden from listing during instability
        assert download_path.exists(), 'Downloaded file should exist on disk'
        folder_contents = fm.list_folder_contents(test_search_path)
        file_names = {p.name for p in folder_contents}
        assert 'downloading.mid' not in file_names, 'Downloaded file should be hidden from listing during instability'

        start_time = time.time()
        while len(signals_received) == 0 and (time.time() - start_time) < 4.0:
            QtTest.QTest.qWait(200)

        assert signals_received == [str(test_search_path)], 'File change signal should be emitted after download completes'

        # Verify file is now visible in listing after stability is achieved
        folder_contents_after = fm.list_folder_contents(test_search_path)
        file_names_after = {p.name for p in folder_contents_after}
        assert 'downloading.mid' in file_names_after, 'Downloaded file should be visible in listing after stability'
