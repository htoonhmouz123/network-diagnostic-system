"""Live statistics for the Dashboard page (written by the TCP server into data/stats.json)."""

import datetime
import json
import os


def read_live_stats(stats_path):
    default = {
        "executed_commands": 0,
        "connected_clients": 0,
        "last_execution_time": "N/A",
        "server_start_time": None,
    }

    if not os.path.exists(stats_path):
        return default  # the server has not created the file yet

    try:
        with open(stats_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (ValueError, OSError):
        return default  # file was unreadable at this moment: show defaults instead of crashing

    for key, value in data.items():
        if value is not None:
            default[key] = value
    return default


def format_uptime(server_start_time):
    """'2026-08-20 10:00:00' -> '2h 15m 03s' (time since then)."""
    if not server_start_time:
        return "N/A"

    try:
        start = datetime.datetime.strptime(server_start_time, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return "N/A"

    total_seconds = max(0, int((datetime.datetime.now() - start).total_seconds()))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes:02d}m {seconds:02d}s"
