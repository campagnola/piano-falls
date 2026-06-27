import json
import os
import sys
import pathlib


# Define config directory based on platform
if sys.platform == 'win32':
    default_config_dir = pathlib.Path.home() / 'AppData' / 'Local' / 'pianofalls'
else:
    default_config_dir = pathlib.Path.home() / '.pianofalls'

default_config = {
    "search_paths": ["~/Downloads"],
    "songs": [],
    "tags": [],  # List of all available tag names
    "rpi_display": None,
        # {"ip_address": "10.10.10.10", "port": 1337, "udp": False,
        #  "resolution": [64, 512], "bounds": [10, 501]},
    "autoplay_volume": 80,  # 0-100 percentage
    "autoplay_volume_randomness": 10,  # 0-100 percentage of volume variation
    "scroll_mode": "wait",  # 'wait' or 'tempo'
    "play_line_seconds": 0.0,  # vertical offset of play line from bottom, in seconds at 100% zoom
}

default_song_config = {
    "name": "",
    "filename": "",
    "sha": "",
    "speed": 100.0,
    "zoom": 1.0,
    "transpose": 0,
    "rating": 0,  # 0-10 scale, 0 = unrated
    "loops": [],
    "track_modes": [],  # List of [part_name, staff, mode] tuples
    "stale_threshold_days": 30,  # Days after which unused song metadata is considered stale
}


class Config:

    singleton = None

    @classmethod
    def get_config(cls):
        if cls.singleton is None:
            cls.singleton = Config(default_config_dir / 'config.json')
        return cls.singleton

    def __init__(self, config_file):
        self.load(config_file)


    def load(self, config_file):
        config_file = pathlib.Path(config_file)
        self.config_file = config_file
        self.config_dir = config_file.parent
        self.songs_dir = config_file.parent / 'songs'

        # Ensure config and songs directories exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.songs_dir.mkdir(parents=True, exist_ok=True)

        if not config_file.exists():
            self._data = default_config.copy()
            with open(config_file, 'w') as f:
                f.write(json.dumps(self._data, indent=4))
        try:
            with open(config_file) as f:
                self._data = json.load(f)
        except Exception as e:
            print(f"Error loading config file {config_file}: {e}")
            self._data = default_config.copy()

        # Ensure all default config fields are present
        for key, default_value in default_config.items():
            if key not in self._data:
                self._data[key] = default_value

    def save(self):
        with open(self.config_file, 'w') as f:
            json.dump(self._data, f, indent=4)

    def __getitem__(self, key):
        return self._data[key]
    
    def __setitem__(self, key, value):
        self.data[key] = value
        self.save()

    def get_sha(self, filename):
        data = open(filename, 'rb').read()
        sha = hashlib.sha1()
        sha.update(data)
        return sha.hexdigest()

    def get_song_settings(self, filename):
        """Get song settings by filename. Returns default values merged with stored values."""
        sha = self.get_sha(filename)
        song_data = self.songs_by_sha.get(sha, {})

        # Return default values merged with any stored values
        settings = default_song_config.copy()
        settings.update(song_data)

        return settings

    def get_all_tags(self):
        """Return the sorted list of all available tag names."""
        return self.data.get('tags', [])

    def add_tag(self, tag_name):
        """Add a tag to the global list if not already present, then save."""
        tags = self.data.setdefault('tags', [])
        if tag_name not in tags:
            tags.append(tag_name)
            tags.sort()
            self.save()

    def update_song_settings(self, filename, speed=None, zoom=None, loops=None, transpose=None, track_modes=None, rating=None, tags=None):
        """Update song settings by filename. Creates new entry if not found."""
        sha = self.get_sha(filename)

        # Use the existing songs_by_sha lookup instead of searching
        existing_song = self.songs_by_sha.get(sha)

        if existing_song is None:
            # Create new entry
            existing_song = default_song_config.copy()
            existing_song['sha'] = sha
            self.data.setdefault('songs', []).append(existing_song)
            # Add to the lookup dictionary
            self.songs_by_sha[sha] = existing_song

        # Update filename and other specified fields
        existing_song['filename'] = filename
        if speed is not None:
            existing_song['speed'] = speed
        if zoom is not None:
            existing_song['zoom'] = zoom
        if loops is not None:
            existing_song['loops'] = loops
        if transpose is not None:
            existing_song['transpose'] = transpose
        if track_modes is not None:
            existing_song['track_modes'] = track_modes
        if rating is not None:
            existing_song['rating'] = rating
        if tags is not None:
            existing_song['tags'] = tags

        self.save()


config = Config.get_config()
