import os
import pathlib
import shutil
from .qt import QtCore
from .file_stability_monitor import FileStabilityMonitor
from .song_repository import SongRepository


class FileManager(QtCore.QObject):
    """
    Centralized file manager providing file operations and change notifications.

    Manages:
    - File system watching with stability monitoring
    - File operations (move, rename, delete)
    - File type filtering
    - Search path management
    - Change notifications via Qt signals

    Implements singleton pattern to ensure consistent state across the application.
    """

    # Signal emitted when file operations cause changes that should update UI
    file_changed = QtCore.Signal(str)  # path that changed

    # Supported music file extensions
    SUPPORTED_EXTENSIONS = {'.mid', '.midi', '.mxl', '.xml', '.musicxml'}

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
        self.stability_monitor = FileStabilityMonitor()

        # Connect file watching signals
        self.file_watcher.directoryChanged.connect(self.stability_monitor.notify_directory_changed)
        self.stability_monitor.directory_stable.connect(self._on_directory_stable)

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

    def list_folder_contents(self, path):
        """
        List files in a folder after applying type filtering.

        Filters to only include supported music file types and directories.

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

        contents = []
        try:
            for item in path.iterdir():
                if item.is_dir():
                    # Include all directories
                    contents.append(item)
                elif item.is_file() and self._is_supported_file(item):
                    # Include only supported music files
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

        Performs the move operation and emits immediate change notifications
        for UI update. Does not wait for file stability.

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

        # Ensure destination directory exists
        new_path.parent.mkdir(parents=True, exist_ok=True)

        # Perform the move
        old_path.rename(new_path)

        # Force immediate UI update for both directories
        self.stability_monitor.force_immediate_update(old_path.parent)
        if new_path.parent != old_path.parent:
            self.stability_monitor.force_immediate_update(new_path.parent)

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
        Delete a file or directory with SongInfo verification and immediate notifications.

        For files that are tracked by SongInfo, this will trigger verification
        to clean up metadata. Emits immediate change notifications.

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

        path.unlink()

        # Force immediate UI update
        self.stability_monitor.force_immediate_update(parent_dir)
        self.emit_change_signal(parent_dir)

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
        return path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def _on_directory_stable(self, dir_path):
        """
        Handle directory stability notifications from FileStabilityMonitor.

        Called when files in a directory have been stable for the configured
        duration. Emits change signal for UI updates.

        Parameters
        ----------
        dir_path : str
            Directory path that became stable
        """
        self.emit_change_signal(dir_path)
