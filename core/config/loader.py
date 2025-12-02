# core/config/loader.py
import yaml
from pathlib import Path

class Config:
    _config = None

    @staticmethod
    def load(path="config/config.yaml"):
        if Config._config is None:
            with open(path, "r") as f:
                Config._config = yaml.safe_load(f)
        return Config._config

    @staticmethod
    def get(path, default=None):
        """
        path example: 'ib.host' -> returns config['ib']['host']
        """
        parts = path.split(".")
        cfg = Config._config
        for p in parts:
            cfg = cfg.get(p, None)
            if cfg is None:
                return default
        return cfg

