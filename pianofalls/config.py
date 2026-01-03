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
        self._data[key] = value
        self.save()


config = Config.get_config()
