"""SongRepository class providing centralized song metadata management for Piano Falls.

This module manages song metadata using individual JSON files for each unique song SHA.
Replaces the song-related functionality that was previously handled by the Config class.
"""

import functools
import os
import hashlib
import pathlib
import json
import glob
from .config import config


class SongRepository:
    """
    Centralized repository for managing song metadata.

    Manages song metadata using individual JSON files stored in ~/.pianofalls/songs/.
    Each file is named by the SHA hash of the song content and contains all metadata
    for songs with that SHA.

    Implements singleton pattern to ensure consistent state across the application.
    """

    _instance = None

    @classmethod
    def get_instance(cls):
        """Get the singleton SongRepository instance."""
        if cls._instance is None:
            cls._instance = SongRepository()
        return cls._instance

    def __init__(self):
        """Initialize SongRepository singleton."""
        if SongRepository._instance is not None:
            raise RuntimeError("Use SongRepository.get_instance() instead of direct instantiation")

        # Cache for loaded SongInfo instances: SHA -> SongInfo
        self._song_cache = {}

        # Set this instance as the singleton
        SongRepository._instance = self

    def load_all_songs(self):
        """
        Load all song metadata from ~/.pianofalls/songs/*.json files.

        Scans the songs directory for JSON files and loads them into the cache.
        Also removes any stale entries based on the configured threshold.

        Returns
        -------
        dict
            Dictionary mapping SHA to SongInfo for all loaded songs
        """
        from .song_info import SongInfo

        # Clear existing cache
        self._song_cache = {}

        # Scan for JSON files in songs directory
        songs_dir = config.config.songs_dir
        if not songs_dir.exists():
            return self._song_cache

        pattern = str(songs_dir / "*.json")
        for json_path in glob.glob(pattern):
            try:
                # Extract SHA from filename
                sha = pathlib.Path(json_path).stem

                # Create SongInfo instance and let it load from the file
                song_info = SongInfo(sha)

                # Check if stale and remove if needed
                if song_info.is_stale():
                    self._remove_stale_song(sha, json_path)
                    continue

                # Add to cache
                self._song_cache[sha] = song_info

            except Exception as e:
                print(f"Warning: Could not load song metadata from {json_path}: {e}")

        return self._song_cache

    def get_song_info(self, filepath):
        """
        Get or create SongInfo for a file path.

        Performs SHA calculation, cache lookup, SongInfo creation if needed,
        and duplicate detection. This is the main entry point for getting
        song metadata.

        Parameters
        ----------
        filepath : str or pathlib.Path
            Path to the song file

        Returns
        -------
        SongInfo
            SongInfo instance for this file
        """
        from .song_info import SongInfo

        filepath = str(pathlib.Path(filepath).resolve())

        # Calculate SHA
        sha = self._compute_sha(filepath)

        # Check cache first
        if sha in self._song_cache:
            song_info = self._song_cache[sha]
            # Check for duplicate files (and add this filepath)
            song_info.check_duplicate(filepath)
            return song_info

        # Create new SongInfo instance
        song_info = SongInfo(sha)

        # Add to cache
        self._song_cache[sha] = song_info

        # Check for duplicate files (and add this filepath)
        song_info.check_duplicate(filepath)

        return song_info

    @functools.lru_cache(maxsize=1024)
    def _compute_sha(self, filepath):
        """
        Compute SHA-1 hash of a file.

        Parameters
        ----------
        filepath : str
            Path to file

        Returns
        -------
        str
            SHA-1 hash as hexadecimal string
        """
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
        except OSError as e:
            raise ValueError(f"Could not read file for SHA calculation: {filepath}") from e
        sha = hashlib.sha1()
        sha.update(data)
        return sha.hexdigest()

    def _remove_stale_song(self, sha, json_path):
        """
        Remove a stale song metadata file.

        Parameters
        ----------
        sha : str
            SHA hash of the song
        json_path : str
            Path to the JSON metadata file to remove
        """
        try:
            os.remove(json_path)
            print(f"Removed stale song metadata: {sha}")
        except OSError as e:
            print(f"Warning: Could not remove stale metadata file {json_path}: {e}")

        # Also remove from cache if present
        if sha in self._song_cache:
            del self._song_cache[sha]
