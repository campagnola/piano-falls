import json, hashlib
import os, sys


if sys.platform == 'win32':
    config_path = os.path.expanduser('~/AppData/Local/pianofalls.json')
else:
    config_path = os.path.expanduser('~/.pianofalls.json')


default_config = {
    "search_paths": ["~/Downloads"],
    "songs": [],
    "rpi_display": None,  
        # {"ip_address": "10.10.10.10", "port": 1337, "udp": False, 
        #  "resolution": [64, 512], "bounds": [10, 501]},
}

default_song_config = {
    "name": "",
    "filename": "",
    "sha": "",
    "speed": 100.0,
    "zoom": 1.0,
    "transpose": 0,
    "loops": [],
    "track_modes": [],  # List of [part_name, staff, mode] tuples
}


class Config:

    singleton = None

    @classmethod
    def get_config(cls):
        if cls.singleton is None:
            cls.singleton = Config(config_path)
        return cls.singleton

    def __init__(self, filename):
        self.config_file = filename
        self.songs_by_sha = {}
        self.load()

    def load(self):
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w') as f:
                f.write(json.dumps(default_config, indent=4))
        try:
            with open(self.config_file) as f:
                self.data = json.load(f)
        except Exception as e:
            print(f"Error loading config file {self.config_file}: {e}")
            self.data = default_config

        # Ensure all song entries have all fields from default_song_config
        for song in self.data.get('songs', []):
            for key, default_value in default_song_config.items():
                if key not in song:
                    song[key] = default_value

        # Rebuild songs_by_sha lookup index
        self.songs_by_sha = {}
        for song in self.data.get('songs', []):
            sha = song.get('sha')
            if sha and sha not in self.songs_by_sha:
                self.songs_by_sha[sha] = song

    def save(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.data, f, indent=4)

    def __getitem__(self, key):
        return self.data[key]
    
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

    def update_song_settings(self, filename, speed=None, zoom=None, loops=None, transpose=None, track_modes=None):
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

        self.save()


config = Config.get_config()
