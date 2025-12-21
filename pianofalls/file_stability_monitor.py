"""File stability monitoring for detecting when downloads/writes are complete.

This module provides a background thread that monitors filesystem changes and only
signals when files have been stable (size unchanged) for a specified duration.
This prevents false duplicate detection when users click on partially-downloaded files.
"""

import time
import threading
import queue
import pathlib
import atexit

from .qt import QtCore


class FileStabilityMonitor(QtCore.QObject):
    """
    Monitors filesystem changes and delays notifications until files are stable.

    A file is considered "stable" when its size hasn't changed for STABILITY_DURATION seconds.
    This prevents SHA computation on partially-downloaded files that would cause false
    duplicate detection alerts.

    Signals
    -------
    directory_stable : QtCore.Signal(str)
        Emitted when all files in a directory have been stable for STABILITY_DURATION.
        The signal parameter is the directory path as a string.
    """

    # Signal emitted when a directory's files have stabilized
    directory_stable = QtCore.Signal(str)

    # Configuration constants
    STABILITY_DURATION = 3.0  # seconds - how long size must be unchanged
    CHECK_INTERVAL = 0.5      # seconds - how often to check file sizes

    # Supported music file extensions
    MUSIC_EXTENSIONS = {'.mid', '.midi', '.mxl', '.xml', '.musicxml'}

    def __init__(self):
        """Initialize the file stability monitor and start worker thread."""
        super().__init__()

        # Queue for passing directory paths from Qt main thread to worker thread
        self.pending_dirs = queue.Queue()

        # Track monitored directories: {dir_path: DirectoryMonitor}
        self.monitoring = {}

        # Thread control flag
        self.stop_thread = False

        # Start worker thread
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

        # Register cleanup on exit
        atexit.register(self.shutdown)

    def notify_directory_changed(self, dir_path):
        """
        Called from Qt main thread when QFileSystemWatcher detects a change.

        This method is thread-safe and simply queues the directory for monitoring.

        Parameters
        ----------
        dir_path : str
            Path to directory that changed
        """
        self.pending_dirs.put(dir_path)

    def _monitor_loop(self):
        """
        Worker thread main loop - monitors file stability.

        This runs continuously until shutdown, checking files for size stability
        and emitting signals when all files in a directory are stable.
        """
        while not self.stop_thread:
            # Process any new directory change notifications
            self._process_pending_directories()

            # Check stability of currently monitored files
            self._check_monitored_files()

            # Sleep before next check cycle
            time.sleep(self.CHECK_INTERVAL)

    def _process_pending_directories(self):
        """
        Drain the queue of pending directory notifications.

        For each pending directory, scan it and start monitoring new/changed files.
        This is called from the worker thread.
        """
        while True:
            try:
                dir_path = self.pending_dirs.get_nowait()
            except queue.Empty:
                break

            self._scan_directory(dir_path)

    def _scan_directory(self, dir_path):
        """
        Scan directory for music files and update monitoring state.

        Strategy:
        - Find all music files in directory
        - Track new files or files whose size has changed
        - If no changes detected and no files being monitored, emit signal immediately

        Parameters
        ----------
        dir_path : str
            Directory path to scan
        """
        dir_path = pathlib.Path(dir_path)

        # Get or create directory monitor
        if dir_path not in self.monitoring:
            self.monitoring[dir_path] = DirectoryMonitor(dir_path)
        dir_monitor = self.monitoring[dir_path]

        # Scan current files in directory
        current_files = {}
        try:
            for child_path in dir_path.iterdir():
                if self._is_music_file(child_path) and child_path.is_file():
                    try:
                        size = child_path.stat().st_size
                        current_files[child_path] = size
                    except OSError:
                        # File might have been deleted/moved during iteration
                        continue
        except OSError:
            # Directory might not exist or no permission
            return

        # Update monitoring state for each file
        has_changes = False
        for file_path, size in current_files.items():
            if file_path not in dir_monitor.files:
                # New file detected - start monitoring it
                dir_monitor.files[file_path] = FileState(file_path, size)
                has_changes = True
            else:
                # Existing file - update size
                file_state = dir_monitor.files[file_path]
                old_size = file_state.current_size
                file_state.update_size(size)
                if size != old_size:
                    has_changes = True

        # Remove files that no longer exist
        for file_path in list(dir_monitor.files.keys()):
            if file_path not in current_files:
                del dir_monitor.files[file_path]

        # If no changes and no files being monitored, emit signal immediately
        if not has_changes and not dir_monitor.files:
            self.directory_stable.emit(str(dir_path))
            if dir_path in self.monitoring:
                del self.monitoring[dir_path]

    def _check_monitored_files(self):
        """
        Check all monitored files for stability and emit signals.

        For each directory being monitored:
        1. Update file sizes
        2. Check if all files are stable
        3. Emit signal if all stable
        4. Clean up monitoring state

        This is called from the worker thread every CHECK_INTERVAL seconds.
        """
        dirs_to_emit = []

        for dir_path, dir_monitor in list(self.monitoring.items()):
            if not dir_monitor.files:
                # No files to monitor, clean up
                dirs_to_emit.append(dir_path)
                continue

            # Update file sizes and check for deletions
            for file_path, file_state in list(dir_monitor.files.items()):
                if not file_path.exists():
                    # File was deleted during monitoring
                    del dir_monitor.files[file_path]
                    continue

                try:
                    new_size = file_path.stat().st_size
                    file_state.update_size(new_size)
                except OSError:
                    # File became inaccessible, remove from monitoring
                    del dir_monitor.files[file_path]

            # Check if ALL files in directory are stable
            if dir_monitor.files:  # Only check if we still have files
                all_stable = True
                for file_state in dir_monitor.files.values():
                    if not file_state.is_stable(self.STABILITY_DURATION):
                        all_stable = False
                        break

                if all_stable:
                    # All files stable, emit signal
                    dirs_to_emit.append(dir_path)

        # Emit signals and clean up monitoring
        for dir_path in dirs_to_emit:
            self.directory_stable.emit(str(dir_path))
            if dir_path in self.monitoring:
                del self.monitoring[dir_path]

    def _is_music_file(self, path):
        """
        Check if file is a supported music file based on extension.

        Parameters
        ----------
        path : pathlib.Path
            File path to check

        Returns
        -------
        bool
            True if file extension is in MUSIC_EXTENSIONS
        """
        return path.suffix.lower() in self.MUSIC_EXTENSIONS

    def shutdown(self):
        """
        Clean shutdown of worker thread.

        Sets the stop flag and waits for thread to terminate.
        Called automatically via atexit handler.
        """
        self.stop_thread = True
        if self.thread.is_alive():
            self.thread.join(timeout=2.0)


class DirectoryMonitor:
    """
    Tracks monitoring state for a single directory.

    Attributes
    ----------
    path : pathlib.Path
        Directory being monitored
    files : dict
        Map of file_path -> FileState for all files being monitored
    """

    def __init__(self, path):
        """
        Initialize directory monitor.

        Parameters
        ----------
        path : pathlib.Path
            Directory to monitor
        """
        self.path = pathlib.Path(path)
        self.files = {}  # file_path -> FileState


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
