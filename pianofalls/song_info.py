"""SongInfo class providing metadata management for individual songs.

This module handles song metadata using individual JSON files stored by SHA hash.
Each SongInfo instance represents metadata for one unique song content (SHA).
"""

import os
import json
import time
import pathlib

from pianofalls.song_repository import SongRepository
from .midi import load_midi
from .musicxml import load_musicxml
from .qt import QtWidgets
from .config import config


# Default song configuration template
default_song_config = {
    "speed": 100.0,
    "zoom": 1.0,
    "transpose": 0,
    "rating": 0,  # 0-10 scale, 0 = unrated
    "loops": [],
    "track_modes": [],  # List of [part_name, staff, mode] tuples
    "tags": [],  # List of tag names applied to this song
}


def _normalize_path(path):
    """Return a fully expanded absolute pathlib.Path for the provided path-like value."""
    if isinstance(path, pathlib.Path):
        result = path
    else:
        result = pathlib.Path(str(path))
    return pathlib.Path(os.path.abspath(os.path.expanduser(str(result))))


class SongInfo:
    """
    Metadata manager for a single song identified by SHA hash.

    Manages:
    - Song settings (speed, zoom, transpose, track_modes, loops, rating)
    - File path tracking for all files with this SHA
    - File verification and cleanup
    - Duplicate detection and handling
    - Persistent storage in individual JSON files

    Each SongInfo instance corresponds to one unique song content (SHA).
    Multiple file paths can map to the same SongInfo if they have identical content.
    """

    def __init__(self, sha):
        """
        Initialize SongInfo for a specific SHA.

        Parameters
        ----------
        sha : str
            SHA-1 hash identifying this song's content
        """
        self.sha = sha
        self.known_files = []  # List of all file paths with this SHA
        self.last_verified = None  # Timestamp of last file verification
        self._song = None  # Cached Song instance
        self._settings = default_song_config.copy()

        # Load existing data or save defaults
        self._json_path = config.songs_dir / f"{self.sha}.json"
        if self._json_path.exists():
            self.load()
        else:
            self.save()

    def save(self):
        """
        Save song metadata to ~/.pianofalls/songs/{sha}.json file.

        Saves all settings, known files, and verification timestamp.
        """
        data = {
            'sha': self.sha,
            'known_files': self.known_files,
            'last_verified': self.last_verified,
            'settings': self._settings
        }

        with open(self._json_path, 'w') as f:
            json.dump(data, f, indent=2)

    def load(self):
        """
        Load song metadata from ~/.pianofalls/songs/{sha}.json file.

        Loads settings, known files, and verification timestamp.
        """
        with open(self._json_path, 'r') as f:
            data = json.load(f)

        self.known_files = data.get('known_files', [])
        self.last_verified = data.get('last_verified')

        # Load settings with defaults for missing values
        loaded_settings = data.get('settings', {})
        self._settings = default_song_config.copy()
        self._settings.update(loaded_settings)

    def verify_files(self):
        """
        Verify all known files still exist and have the correct SHA.

        Removes files from known_files if they no longer exist or have different SHA.
        Updates last_verified timestamp and saves if changes were made.
        """
        files_to_remove = []

        for filepath in self.known_files:
            path = _normalize_path(filepath)

            # Check if file still exists
            if not path.exists() or not path.is_file():
                files_to_remove.append(filepath)
                continue

        # Remove invalid files
        for filepath in files_to_remove:
            self.known_files.remove(filepath)

        # Update timestamp and save if files changed or if we still have files
        if len(files_to_remove) > 0 or len(self.known_files) > 0:
            self.last_verified = time.time()
            self.save()

        if files_to_remove:
            print(f"Removed {len(files_to_remove)} invalid file(s) from {self.sha[:8]}...")

    def check_duplicate(self, filepath):
        """
        Check and handle duplicate files for this SHA.

        Verifies existing files, detects duplicates, and prompts user for resolution
        if duplicates are found.

        Parameters
        ----------
        filepath : str or pathlib.Path
            File path to check for duplicates
        """
        filepath = str(_normalize_path(filepath))

        # First verify existing files
        self.verify_files()

        # Check if this file is already known
        if filepath in self.known_files:
            return  # File already tracked, nothing to do

        # Check if we have other files with this SHA (duplicates)
        if len(self.known_files) > 0:
            self._handle_duplicate_dialog(filepath)
        else:
            # First file with this SHA, just add it
            self.known_files.append(filepath)
            self.last_verified = time.time()
            self.save()

    def _handle_duplicate_dialog(self, new_filepath):
        """
        Show dialog to handle duplicate files and execute user's choice.

        Parameters
        ----------
        new_filepath : str
            Path to the new duplicate file
        """
        # Build list of existing files for display
        existing_files_text = '\n'.join(f'  • {f}' for f in self.known_files)

        # Create message box for duplicate handling
        msg = QtWidgets.QMessageBox()
        msg.setWindowTitle('Duplicate File Detected')
        msg.setText(f'Files with identical content already exist.\n\n'
                   f'New file:\n  • {new_filepath}\n\n'
                   f'Existing files ({len(self.known_files)}):\n{existing_files_text}')

        if len(self.known_files) == 1:
            delete_old_text = 'Delete Existing'
        else:
            delete_old_text = f'Delete All {len(self.known_files)} Existing'

        msg.setInformativeText('What would you like to do?')

        # Add custom buttons
        keep_both_btn = msg.addButton('Keep All', QtWidgets.QMessageBox.ActionRole)
        delete_new_btn = msg.addButton('Delete New', QtWidgets.QMessageBox.DestructiveRole)
        delete_old_btn = msg.addButton(delete_old_text, QtWidgets.QMessageBox.DestructiveRole)
        msg.setDefaultButton(keep_both_btn)

        # Show dialog and get user choice
        msg.exec()
        clicked_btn = msg.clickedButton()

        if clicked_btn == keep_both_btn:
            # Keep both files
            self.known_files.append(new_filepath)
            self.last_verified = time.time()
            self.save()

        elif clicked_btn == delete_new_btn:
            # Delete the new file
            try:
                os.remove(new_filepath)
                print(f"Deleted duplicate file: {new_filepath}")
            except OSError as e:
                print(f"Error deleting duplicate file {new_filepath}: {e}")

        elif clicked_btn == delete_old_btn:
            # Delete old files and keep new one
            files_to_delete = self.known_files.copy()
            self.known_files = [new_filepath]

            for old_file in files_to_delete:
                try:
                    os.remove(old_file)
                    print(f"Deleted old file: {old_file}")
                except OSError as e:
                    print(f"Error deleting old file {old_file}: {e}")

            self.last_verified = time.time()
            self.save()

    def is_stale(self):
        """
        Check if this song metadata is stale and should be cleaned up.

        Returns True if known_files is empty AND last_verified timestamp is older
        than the configured stale threshold.

        Returns
        -------
        bool
            True if metadata is stale and should be removed
        """
        # Not stale if we have files
        if len(self.known_files) > 0:
            return False

        # Not stale if never verified (fresh metadata)
        if self.last_verified is None:
            return False

        # Check if last verification is older than threshold
        threshold_days = config['stale_threshold_days']
        threshold_seconds = threshold_days * 24 * 60 * 60
        age_seconds = time.time() - self.last_verified

        return age_seconds > threshold_seconds

    def get_song(self, force_reload=False):
        """
        Get the Song instance, loading from the first available file if needed.

        Parameters
        ----------
        force_reload : bool, optional
            If True, force reload from file even if cached

        Returns
        -------
        Song
            The loaded Song instance

        Raises
        ------
        ValueError
            If no valid files are available
        """
        # Verify files first
        self.verify_files()

        if not self.known_files:
            raise ValueError(f"No valid files available for song {self.sha[:8]}...")

        # Use first available file
        filepath = self.known_files[0]

        # Check if file has been modified
        try:
            current_mtime = os.path.getmtime(filepath)
        except OSError:
            current_mtime = None

        # Load if not cached, modified, or forced
        if self._song is None or force_reload or getattr(self, '_file_mtime', None) != current_mtime:
            self._load_song(filepath)
            self._file_mtime = current_mtime

        return self._song

    def _load_song(self, filepath):
        """Load the Song instance from file."""
        ext = os.path.splitext(filepath)[1].lower()
        if ext in ['.mid', '.midi']:
            self._song = load_midi(filepath)
        elif ext in ['.xml', '.mxl', '.musicxml']:
            self._song = load_musicxml(filepath)
        else:
            raise ValueError(f'Unsupported file type: {filepath}')

    def reload_song(self):
        """Force reload the Song from file."""
        return self.get_song(force_reload=True)

    # Settings management

    def get_settings(self):
        """Get a copy of all settings."""
        return self._settings.copy()

    def get_setting(self, name):
        """Get a specific setting value."""
        return self._settings[name]

    def update_settings(self, **kwargs):
        """Update settings and save to file."""
        for key in kwargs:
            if key not in default_song_config:
                raise ValueError(f"Unknown setting '{key}'")
        self._settings.update(kwargs)

        self.save()

    @property
    def filename(self):
        """Get the primary file path for this song."""
        return self.known_files[0]

    @property
    def name(self):
        """Get the display name for this song."""
        return os.path.basename(self.known_files[0])

    def __repr__(self):
        return f"SongInfo(sha={self.sha[:8]}..., files={len(self.known_files)})"
