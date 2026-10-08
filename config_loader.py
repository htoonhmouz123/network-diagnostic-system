"""Gives the web server the settings it needs, using the same ConfigManager as the TCP side.

Using one loader means the HTTP port is always derived from the Student ID in config.json.
"""

from config.config_manager import ConfigManager


def load_config():
    manager = ConfigManager()
    manager.load_config()
    raw = manager.get_config()

    return {
        "tcp_port": raw["TCP Port"],
        "http_port": raw["HTTP Port"],
        "log_file": raw["Log File"],
        "stats_file": raw["Stats File"],
        "max_clients": raw["MAX Clients"],
        "default_homepage": raw["Default Homepage"],
        "team": raw["Team"],
    }
