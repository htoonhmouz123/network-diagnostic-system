"""Thread-safe request logger. Every request becomes one line in the log file."""

import threading
from datetime import datetime
from pathlib import Path


class Logger:
    def __init__(self, log_file):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()  # only one thread may write at a time

    def log_request(self, client_ip, client_port, command, parameters, execution_time, status):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"Timestamp={timestamp} | ClientIP={client_ip} | ClientPort={client_port} | "
            f"Command={command} | Parameters={parameters} | "
            f"ExecutionTime={execution_time:.4f} | Status={status}\n"
        )
        # Thread wants to log -> takes the lock -> appends one line -> releases the lock
        with self.lock:
            with open(self.log_file, "a", encoding="utf-8") as file:
                file.write(entry)
