"""Loads config/config.json, validates it and derives the TCP/HTTP ports."""

import json
from pathlib import Path

# Project root = the folder that contains run_server.py (one level above config/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_FILE = PROJECT_ROOT / "config" / "config.json"

# Used when a key is missing or null in config.json
DEFAULTS = {
    "Server Host": "localhost",
    "Log File": "logs/server.log",
    "Stats File": "data/stats.json",
    "MAX Clients": 10,
    "Default Homepage": "/",
}


class ConfigManager:
    def __init__(self, config_file=DEFAULT_CONFIG_FILE):
        self.config_file = Path(config_file)
        self.config = {}  # empty until load_config() is called

    def load_config(self):
        """Read the JSON file, fill in defaults, validate and compute the ports."""
        with open(self.config_file, "r", encoding="utf-8") as file:
            self.config = json.load(file)

        for key, value in DEFAULTS.items():
            if self.config.get(key) is None:
                self.config[key] = value

        self.validate_student_id()
        self.calculate_ports()
        self.resolve_paths()

    def validate_student_id(self):
        student_id = str(self.config.get("Student ID", ""))
        if not student_id.isdigit():
            raise ValueError("Student ID must contain only digits")
        if len(student_id) < 3:
            raise ValueError("Student ID must contain at least 3 digits")

    def calculate_ports(self):
        """TCP port = last 3 digits + 5000, HTTP port = last 3 digits + 6000."""
        last_three = int(str(self.config["Student ID"])[-3:])
        self.config["TCP Port"] = last_three + 5000
        self.config["HTTP Port"] = last_three + 6000

    def resolve_paths(self):
        """Make relative file paths relative to the project root, not the terminal's folder."""
        for key in ("Log File", "Stats File"):
            path = Path(self.config[key])
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            self.config[key] = str(path)

    def get_config(self):
        return self.config
