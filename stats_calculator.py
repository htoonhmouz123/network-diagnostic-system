"""Calculates usage statistics from the parsed log entries."""

from core.log_parser import read_log_file


def empty_statistics():
    return {
        "Total Commands": 0,
        "Most Frequent Command": None,
        "Average Execution Time": 0,
        "Successful Requests": 0,
        "Failed Requests": 0,
        "Last Execution Time": None,
    }


def compute_statistics(entries):
    """Statistics for a list of log entries (dicts)."""
    total = len(entries)
    if total == 0:
        return empty_statistics()

    command_counts = {}
    total_time = 0.0
    timed_entries = 0
    successes = 0
    failures = 0

    for entry in entries:
        command = entry.get("Command")
        command_counts[command] = command_counts.get(command, 0) + 1

        try:
            total_time += float(entry.get("ExecutionTime", ""))
            timed_entries += 1
        except ValueError:
            pass  # damaged row: ignore its time instead of crashing

        status = entry.get("Status")
        if status == "Success":
            successes += 1
        elif status == "Failure":
            failures += 1

    average = total_time / timed_entries if timed_entries else 0.0

    return {
        "Total Commands": total,
        "Most Frequent Command": max(command_counts, key=command_counts.get),
        "Average Execution Time": round(average, 4),
        "Successful Requests": successes,
        "Failed Requests": failures,
        "Last Execution Time": entries[-1].get("Timestamp"),
    }


def calculate_statistics(log_file):
    """Statistics straight from a log file path."""
    return compute_statistics(read_log_file(log_file))
