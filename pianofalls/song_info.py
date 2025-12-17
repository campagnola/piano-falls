import os
import pathlib
import hashlib
from .config import config, default_song_config
from .qt import QtWidgets


def _normalize_path(path):
    """Return a fully expanded absolute pathlib.Path for the provided path-like value."""
    if isinstance(path, pathlib.Path):
        result = path
    else:
        result = pathlib.Path(str(path))
    return pathlib.Path(os.path.abspath(os.path.expanduser(str(result))))


class SongInfo:
    """
    Central source of truth about a song file.

    Manages:
    - File identification (filename, SHA)
    - Settings (speed, zoom, transpose, track_modes, loops)
    - Song instance loading and caching
    - File registration and duplicate handling

    Implements singleton pattern per SHA - the same file always returns the same SongInfo.
    """

    _instances = {}  # SHA -> SongInfo mapping

    @classmethod
    def load(cls, filename, parent=None):
        """
        Load a SongInfo by filename.

        Computes the file's SHA and returns the singleton SongInfo for that SHA.
        Handles file registration and duplicate detection.

        Parameters
        ----------
        filename : str or pathlib.Path
            Path to the song file
        parent : QtWidgets.QWidget, optional
            Parent widget for dialog boxes

        Returns
        -------
        SongInfo
            The singleton SongInfo instance for this file
        """
        filename = str(_normalize_path(filename))

        # Compute SHA
        try:
            sha = cls._compute_sha(filename)
        except OSError:
            raise ValueError(f"Could not read file: {filename}")

        # Get or create singleton
        if sha in cls._instances:
            song_info = cls._instances[sha]
            # Update filename if it changed
            if song_info.filename != filename:
                song_info._handle_filename_change(filename, parent)
            return song_info

        # Create new instance
        song_info = cls(sha, filename)
        song_info._register(parent)
        return song_info

    @classmethod
    def load_from_sha(cls, sha):
        """
        Load a SongInfo by SHA.

        Returns the singleton SongInfo for this SHA if it exists,
        otherwise looks up the filename in config and loads it.

        Parameters
        ----------
        sha : str
            SHA-1 hash of the song file

        Returns
        -------
        SongInfo or None
            The SongInfo instance, or None if not found
        """
        # Check if already loaded
        if sha in cls._instances:
            return cls._instances[sha]

        # Look up in config
        song_data = config.songs_by_sha.get(sha)
        if song_data is None:
            return None

        filename = song_data.get('filename')
        if not filename:
            return None

        # Create instance (don't re-register since it's already in config)
        song_info = cls(sha, filename)
        song_info._ensure_registered()
        return song_info

    @staticmethod
    def _compute_sha(filename):
        """Compute SHA-1 hash of a file."""
        with open(filename, 'rb') as f:
            data = f.read()
        sha = hashlib.sha1()
        sha.update(data)
        return sha.hexdigest()

    def __init__(self, sha, filename):
        """
        Private constructor - use load() or load_from_sha() instead.

        Parameters
        ----------
        sha : str
            SHA-1 hash of the file
        filename : str
            Path to the file
        """
        self.sha = sha
        self.filename = filename
        self._song = None  # Cached Song instance
        self._file_mtime = None  # Track file modification time

        # Register in singleton dict
        SongInfo._instances[sha] = self

    def _register(self, parent=None):
        """Register this file in the config, handling duplicates."""
        from .file_registry import register_file
        register_file(self.filename, parent)

    def _ensure_registered(self):
        """Ensure this file is registered in config without duplicate prompts."""
        path = _normalize_path(self.filename)
        if not path.exists() or not path.is_file():
            return

        entry = config.songs_by_sha.get(self.sha)
        if entry is None:
            # Create new entry
            new_entry = default_song_config.copy()
            new_entry.update({
                'sha': self.sha,
                'filename': self.filename,
                'name': path.stem,
            })
            config.data.setdefault('songs', []).append(new_entry)
            config.songs_by_sha[self.sha] = new_entry
            config.save()

    def _handle_filename_change(self, new_filename, parent=None):
        """Handle updating to a new filename for the same SHA."""
        old_path = _normalize_path(self.filename)
        new_path = _normalize_path(new_filename)

        if old_path == new_path:
            # Just a normalization difference, update silently
            if self.filename != new_filename:
                self.filename = new_filename
                entry = config.songs_by_sha.get(self.sha)
                if entry:
                    entry['filename'] = new_filename
                    config.save()
            return

        # Different paths with same SHA - handle via register_file
        self.filename = new_filename
        self._register(parent)

    def get_song(self, force_reload=False):
        """
        Get the Song instance, loading from file if needed.

        Caches the Song instance and only reloads if the file has been modified
        or force_reload is True.

        Parameters
        ----------
        force_reload : bool, optional
            If True, force reload from file even if cached

        Returns
        -------
        Song
            The loaded Song instance
        """
        # Check if file has been modified
        try:
            current_mtime = os.path.getmtime(self.filename)
        except OSError:
            current_mtime = None

        # Load if not cached, modified, or forced
        if self._song is None or force_reload or current_mtime != self._file_mtime:
            self._load_song()
            self._file_mtime = current_mtime

        return self._song

    def _load_song(self):
        """Load the Song instance from file."""
        from .midi import load_midi
        from .musicxml import load_musicxml

        ext = os.path.splitext(self.filename)[1].lower()
        if ext in ['.mid', '.midi']:
            self._song = load_midi(self.filename)
        elif ext in ['.xml', '.mxl', '.musicxml']:
            self._song = load_musicxml(self.filename)
        else:
            raise ValueError(f'Unsupported file type: {self.filename}')

    def reload_song(self):
        """Force reload the Song from file."""
        return self.get_song(force_reload=True)

    # Settings management

    def get_settings(self):
        """
        Get all settings for this song.

        Returns
        -------
        dict
            Dictionary of settings including speed, zoom, transpose, loops, track_modes
        """
        return config.get_song_settings(self.filename)

    def get_setting(self, name):
        """
        Get a specific setting for this song.

        Parameters
        ----------
        name : str
            Setting name (e.g., 'speed', 'zoom', 'transpose', 'loops', 'track_modes')

        Returns
        -------
        The setting value
        """
        return self.get_settings()[name]

    def update_settings(self, **kwargs):
        """
        Update settings for this song.

        Parameters
        ----------
        **kwargs
            Any of: speed, zoom, transpose, loops, track_modes
        """
        config.update_song_settings(self.filename, **kwargs)

    @property
    def name(self):
        """Get the display name for this song."""
        return os.path.basename(self.filename)

    def __repr__(self):
        return f"SongInfo(sha={self.sha[:8]}..., filename={self.filename})"
