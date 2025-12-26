import json
import os
import sys
import pathlib


# Define config directory based on platform
if sys.platform == 'win32':
    config_dir = pathlib.Path.home() / 'AppData' / 'Local' / 'pianofalls'
else:
    config_dir = pathlib.Path.home() / '.pianofalls'

config_path = config_dir / 'config.json'
songs_dir = config_dir / 'songs'


default_config = {
    "search_paths": ["~/Downloads"],
    "rpi_display": None,
        # {"ip_address": "10.10.10.10", "port": 1337, "udp": False,
        #  "resolution": [64, 512], "bounds": [10, 501]},
    "autoplay_volume": 80,  # 0-100 percentage
    "autoplay_volume_randomness": 10,  # 0-100 percentage of volume variation
    "scroll_mode": "wait",  # 'wait' or 'tempo'
    "stale_threshold_days": 30,  # Days after which unused song metadata is considered stale
}



class Config:

    singleton = None

    @classmethod
    def get_config(cls):
        if cls.singleton is None:
            cls.singleton = Config(config_path)
        return cls.singleton

    def __init__(self, filename):
        self.config_file = pathlib.Path(filename)
        self._ensure_directories()
        self.load()

    def _ensure_directories(self):
        """Create config directory structure if it doesn't exist."""
        # Create main config directory
        config_dir.mkdir(parents=True, exist_ok=True)

        # Create songs directory
        songs_dir.mkdir(parents=True, exist_ok=True)

    def load(self):
        if not self.config_file.exists():
            with open(self.config_file, 'w') as f:
                f.write(json.dumps(default_config, indent=4))
        try:
            with open(self.config_file) as f:
                self.data = json.load(f)
        except Exception as e:
            print(f"Error loading config file {self.config_file}: {e}")
            self.data = default_config.copy()

        # Ensure all default config fields are present
        for key, default_value in default_config.items():
            if key not in self.data:
                self.data[key] = default_value

    def save(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.data, f, indent=4)

    def __getitem__(self, key):
        return self.data[key]
    
    def __setitem__(self, key, value):
        self.data[key] = value
        self.save()



config = Config.get_config()
