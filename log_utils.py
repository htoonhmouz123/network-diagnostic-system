"""Log helpers for the web pages: reading the log and searching it."""

from core.log_parser import read_log_file


def read_log(log_path):
    """All log entries as a list of dicts (empty list if the log does not exist yet)."""
    return read_log_file(log_path)


def search_log(entries, command=None, hostname=None, client_ip=None):
    """Filter the entries. Any filter left empty is ignored."""
    results = entries

    if command:
        command = command.strip().upper()
        results = [r for r in results if r.get("Command", "").upper() == command]

    if hostname:
        hostname = hostname.strip().lower()
        results = [r for r in results if hostname in r.get("Parameters", "").lower()]

    if client_ip:
        client_ip = client_ip.strip()
        results = [r for r in results if r.get("ClientIP", "") == client_ip]

    return results
