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
}

default_song_config = {
    "name": "",
    "filename": "",
    "sha": "",
    "speed": 100.0,
    "zoom": 1.0,
    "loops": [],
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

    def save(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.data, f, indent=4)

    def __getitem__(self, key):
        return self.data[key]
    
    def __setitem__(self, key, value):
        self.data[key] = value
        self.save()

    def get_song_info(self, filename):
        sha = self.get_sha(filename)
        return self.songs_by_sha.get(sha, {})
    
    def get_sha(self, filename):
        data = open(filename, 'rb').read()
        sha = hashlib.sha1()
        sha.update(data)
        return sha.hexdigest()


config = Config.get_config()
