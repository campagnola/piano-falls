import os
import pathlib
import time
import threading
import queue
from .qt import QtCore


class FileStabilityMonitor(QtCore.QObject):
    """
    Background monitoring for file stability.

    Monitors files for size stability and emits file_ready when files
    have been stable for the configured duration.
    """
    # Signal emitted when a file becomes stable and ready for use
    file_ready = QtCore.Signal(str)  # file path that became ready

    # Configuration constants
    stability_duration = 3.0  # seconds - how long size must be unchanged
    check_interval = 0.5      # seconds - how often to check file sizes

    def __init__(self):
        super().__init__()
        self.monitor_queue = queue.Queue()  # Files to monitor
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def monitor_file(self, file_path):
        """Queue a file for monitoring."""
        self.monitor_queue.put(pathlib.Path(file_path))

    def _monitor_loop(self):
        """
        Background thread main loop - monitors file stability.
        """
        monitor_files = {}
        while True:
            # Process any new files to monitor
            while self.monitor_queue.qsize() > 0:
                monitor_files[self.monitor_queue.get()] = [None, None]

            # Check stability of currently monitored files
            for file_path in list(monitor_files.keys()):
                try:
                    current_size = file_path.stat().st_size
                except OSError:
                    # File not accessible, remove from monitoring
                    del monitor_files[file_path]
                    continue

                # check size stability
                now = time.time()
                last_size, last_time = monitor_files[file_path]
                if last_size != current_size:
                    monitor_files[file_path] = (current_size, now)
                elif now - last_time >= self.stability_duration:
                    # File is stable, emit signal
                    self.file_ready.emit(str(file_path))
                    del monitor_files[file_path]

            time.sleep(self.check_interval)


class FileManager(QtCore.QObject):
    """
    Centralized file manager providing file operations and change notifications.

    Manages:
    - File system watching with integrated stability monitoring
    - File operations (move, rename, delete)
    - File type filtering
    - Search path management
    - Change notifications via Qt signals
    - Coordination with background file stability monitoring

    Implements singleton pattern to ensure consistent state across the application.
    """

    # Signal emitted when directories are added/removed, files are removed, or files become ready
    file_changed = QtCore.Signal(str)  # path that changed

    # Supported music file extensions
    supported_extensions = {'.mid', '.midi', '.mxl', '.xml', '.musicxml'}

    _instance = None

    @classmethod
    def get_instance(cls):
        """Get the singleton FileManager instance."""
        if cls._instance is None:
            cls._instance = FileManager()
        return cls._instance

    def __init__(self):
        """Initialize FileManager singleton."""
        if FileManager._instance is not None:
            raise RuntimeError("Use FileManager.get_instance() instead of direct instantiation")

        super().__init__()

        # File system watching
        self.file_watcher = QtCore.QFileSystemWatcher()
        self.file_watcher.directoryChanged.connect(self._on_directory_changed)

        # File stability monitoring
        self.hidden_files = set()  # Files not yet stable/ready for listing
        self.recently_moved_files = set()  # Files recently moved, bypass stability checks
        self.directory_files = {}  # Track all files per directory: {dir_path: set_of_files}
        self.stability_monitor = FileStabilityMonitor()

        # Connect to stability monitor signals
        self.stability_monitor.file_ready.connect(self._on_file_ready)

        # Auto-watch all search paths
        for search_path in self.get_search_paths():
            self._ensure_watching(search_path)

        # Set this instance as the singleton
        FileManager._instance = self

    def get_search_paths(self):
        """
        Get the list of top-level search paths for music files.

        Returns
        -------
        list of str
            List of directory paths to search for music files
        """
        from .config import config
        return config.data.get('search_paths', ['~/Downloads'])

    def _ensure_watching(self, path):
        """
        Ensure a directory is being watched by QFileSystemWatcher.

        Safely adds the directory to the watcher if it exists and isn't already watched.

        Parameters
        ----------
        path : str or pathlib.Path
            Directory path to watch
        """
        path = pathlib.Path(os.path.expanduser(str(path)))
        path_str = str(path)
        if path_str not in self.file_watcher.directories():
            assert path.exists() and path.is_dir(), f"Cannot watch non-existent directory: {path}"
            self.file_watcher.addPath(path_str)

            # Initialize directory state with current files
            self.directory_files[path] = set(self.list_folder_contents(path))

    def list_folder_contents(self, path):
        """
        List files in a folder after applying type filtering.

        Filters to only include supported music file types and directories.
        Excludes new files that are still being written.

        Parameters
        ----------
        path : str or pathlib.Path
            Directory path to list contents for

        Returns
        -------
        list of pathlib.Path
            List of files and directories, with files filtered to supported types
        """
        path = pathlib.Path(os.path.expanduser(path))
        if not path.exists():
            raise FileNotFoundError(f"Directory does not exist: {path}")
        if not path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {path}")

        # Auto-watch this directory for changes
        self._ensure_watching(path)

        contents = []
        try:
            for item in path.iterdir():
                if item.is_dir():
                    # Include all directories
                    contents.append(item)
                elif item.is_file() and self._is_supported_file(item):
                    # Include only supported music files that are not hidden
                    if item not in self.hidden_files:
                        contents.append(item)
        except (OSError, PermissionError):
            # Directory not accessible
            pass

        return sorted(contents, key=lambda p: (not p.is_dir(), p.name.lower()))

    def emit_change_signal(self, path):
        """
        Emit file change signal for the given path.

        This method provides a central point for file change notifications
        that can be used by other components to trigger UI updates.

        Parameters
        ----------
        path : str or pathlib.Path
            Path that changed
        """
        self.file_changed.emit(str(path))

    def move_file(self, old_path, new_path):
        """
        Move a file with immediate notifications.

        Parameters
        ----------
        old_path : str or pathlib.Path
            Source path
        new_path : str or pathlib.Path
            Destination path

        Raises
        ------
        OSError
            If the move operation fails
        FileExistsError
            If destination already exists
        """
        old_path = pathlib.Path(old_path)
        new_path = pathlib.Path(new_path)

        if new_path.exists():
            raise FileExistsError(f"Destination already exists: {new_path}")
        if not new_path.parent.exists():
            raise FileNotFoundError(f"Destination directory does not exist: {new_path.parent}")

        # Auto-watch source and dest directory
        self._ensure_watching(old_path.parent)
        self._ensure_watching(new_path.parent)

        # Track this as a moved file for immediate processing
        self.recently_moved_files.add(new_path)

        # Perform the move
        old_path.rename(new_path)


    def rename_file(self, old_path, new_name):
        """
        Rename a file with immediate notifications.

        Convenience method for renaming a file within the same directory.

        Parameters
        ----------
        old_path : str or pathlib.Path
            Current file path
        new_name : str
            New filename (not full path)

        Raises
        ------
        OSError
            If the rename operation fails
        FileExistsError
            If destination already exists
        """
        old_path = pathlib.Path(old_path)
        new_path = old_path.with_name(new_name)
        self.move_file(old_path, new_path)

    def delete_file(self, path):
        """
        Delete a file or directory with immediate notifications.

        Parameters
        ----------
        path : str or pathlib.Path
            Path to delete

        Raises
        ------
        OSError
            If the delete operation fails
        """
        path = pathlib.Path(path)
        parent_dir = path.parent

        # Auto-watch the parent directory
        self._ensure_watching(parent_dir)

        # Remove from tracking sets if present
        self.hidden_files.discard(path)
        self.recently_moved_files.discard(path)

        # Perform the delete
        path.unlink()

    def add_watch_path(self, path):
        """
        Add a directory to the file watcher.

        Parameters
        ----------
        path : str or pathlib.Path
            Directory path to watch
        """
        path_str = str(pathlib.Path(path).resolve())
        if path_str not in self.file_watcher.directories():
            self.file_watcher.addPath(path_str)

    def remove_watch_path(self, path):
        """
        Remove a directory from the file watcher.

        Parameters
        ----------
        path : str or pathlib.Path
            Directory path to stop watching
        """
        path_str = str(pathlib.Path(path).resolve())
        if path_str in self.file_watcher.directories():
            self.file_watcher.removePath(path_str)

    def _is_supported_file(self, path):
        """
        Check if a file has a supported music file extension.

        Parameters
        ----------
        path : pathlib.Path
            File path to check

        Returns
        -------
        bool
            True if file extension is supported
        """
        return path.suffix.lower() in self.supported_extensions

    def _on_directory_changed(self, dir_path):
        """
        Handle directory change notifications from QFileSystemWatcher.

        Scans the directory for new files and starts monitoring them.
        Emits immediate signals for file removals.

        Parameters
        ----------
        dir_path : str
            Directory path that changed
        """
        dir_path = pathlib.Path(dir_path)
        current_files = set(self.list_folder_contents(dir_path))

        # Get previously known files for this directory
        previous_files = self.directory_files[dir_path]

        # Update tracking with current state
        self.directory_files[dir_path] = current_files

        # Find new files and removed files
        new_files = current_files - previous_files
        removed_files = previous_files - current_files

        # Track whether we should emit a signal for this directory change
        should_emit_signal = False

        # Handle removed files
        if removed_files:
            # Clean up tracking for removed files
            for removed_file in removed_files:
                self.hidden_files.discard(removed_file)
                self.recently_moved_files.discard(removed_file)
            should_emit_signal = True

        # Handle new files
        for new_file in new_files:
            if new_file in self.recently_moved_files:
                # This is a recently moved file, make it immediately available
                self.recently_moved_files.discard(new_file)
                should_emit_signal = True
            else:
                # This is a genuinely new file that needs stability monitoring
                self.hidden_files.add(new_file)
                self.stability_monitor.monitor_file(new_file)

        if should_emit_signal:
            self.file_changed.emit(str(dir_path))

    def _on_file_ready(self, file_path):
        """
        Handle file_ready signals from FileStabilityMonitor.

        Called when a file has become stable and ready for use.
        Unhides the file and emits a change signal.

        Parameters
        ----------
        file_path : str
            File path that became ready
        """
        file_path = pathlib.Path(file_path)

        # Unhide the file
        self.hidden_files.discard(file_path)

        # Emit change signal for the directory
        self.file_changed.emit(str(file_path.parent))

    def force_immediate_update(self, dir_path):
        """
        Force an immediate update for a directory, bypassing stability monitoring.

        This should be called for user-initiated changes or in tests where we want
        immediate visual feedback rather than waiting for stability.

        This method is safe to call from the Qt main thread.

        Parameters
        ----------
        dir_path : str or pathlib.Path
            Path to directory that should be updated immediately
        """
        # Emit signal immediately without waiting for stability
        self.file_changed.emit(str(dir_path))



class FileState:
    """
    Tracks size and stability state for a single file.

    Attributes
    ----------
    path : pathlib.Path
        File being monitored
    current_size : int
        Current file size in bytes
    stable_since : float
        Timestamp (time.time()) when stability period started
    """

    def __init__(self, path, initial_size):
        """
        Initialize file state tracking.

        Parameters
        ----------
        path : pathlib.Path
            File to track
        initial_size : int
            Initial file size in bytes
        """
        self.path = pathlib.Path(path)
        self.current_size = initial_size
        self.stable_since = time.time()

    def update_size(self, new_size):
        """
        Update file size and reset stability timer if changed.

        Parameters
        ----------
        new_size : int
            New file size in bytes
        """
        if new_size != self.current_size:
            # Size changed, reset stability timer
            self.current_size = new_size
            self.stable_since = time.time()
        # If size unchanged, stable_since remains the same

    def is_stable(self, duration):
        """
        Check if file has been stable for at least the specified duration.

        Parameters
        ----------
        duration : float
            Required stability duration in seconds

        Returns
        -------
        bool
            True if file size has been unchanged for at least duration seconds
        """
        return time.time() - self.stable_since >= duration
