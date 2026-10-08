"""Turns log lines (Key=Value | Key=Value ...) back into Python dictionaries."""

import os


def parse_log_line(line):
    entry = {}
    for part in line.strip().split(" | "):
        if "=" in part:
            key, value = part.split("=", 1)
            entry[key.strip()] = value.strip()
    return entry


def read_log_file(log_file):
    """Return a list of dicts, one per log line. A missing file gives an empty list."""
    if not os.path.exists(log_file):
        return []

    entries = []
    with open(log_file, "r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                entry = parse_log_line(line)
                if entry:  # skip lines that could not be parsed
                    entries.append(entry)
    return entries
