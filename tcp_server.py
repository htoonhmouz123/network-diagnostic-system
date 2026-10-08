"""Multi-threaded TCP server.

The main thread only listens and accepts. Every accepted client gets its own thread
that receives requests, runs the matching OS command, logs it and sends the answer.

Protocol: one JSON object per line ("\n" marks the end of a message).
  request : {"command": "PING", "parameter": "google.com"}
  response: {"command", "parameter", "status", "output", "execution_time", "timestamp"}
"""

import json
import os
import subprocess
import threading
import time
from datetime import datetime
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR

from config.config_manager import ConfigManager
from core.console import log_message
from core.logger import Logger

# Each command name maps to the OS command (and its fixed arguments).
if os.name == "nt":  # Windows
    COMMANDS = {
        "PING": ["ping", "-n", "4"],
        "TRACEROUTE": ["tracert", "-d", "-h", "15", "-w", "1000"],
        "DNS": ["nslookup"],
        "IP_CONFIG": ["ipconfig"],
        "ROUTING_TABLE": ["route", "print"],
        "ARP_TABLE": ["arp", "-a"],
        "TCP_CONNECTIONS": ["netstat", "-ano"],
    }
else:  # Linux
    COMMANDS = {
        "PING": ["ping", "-c", "4"],
        "TRACEROUTE": ["traceroute", "-n", "-m", "15"],
        "DNS": ["nslookup"],
        "IP_CONFIG": ["ip", "addr"],
        "ROUTING_TABLE": ["ip", "route"],
        "ARP_TABLE": ["arp", "-a"],
        "TCP_CONNECTIONS": ["ss", "-tun"],
    }

COMMANDS_WITH_HOSTNAME = {"PING", "TRACEROUTE", "DNS"}  # these need a hostname parameter
DEFAULT_TIMEOUT = 15      # seconds a command may run before it is stopped
TIMEOUTS = {"TRACEROUTE": 30}

stats_lock = threading.Lock()
stats = {
    "executed_commands": 0,
    "connected_clients": 0,
    "last_execution_time": None,
    "server_start_time": None,
}


def save_statistics(stats_file):
    """Write the live statistics to disk (the web dashboard reads this file)."""
    with stats_lock:
        os.makedirs(os.path.dirname(stats_file), exist_ok=True)
        temp_file = stats_file + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as file:
            json.dump(stats, file)
        os.replace(temp_file, stats_file)  # atomic: the web server never reads a half-written file


def is_valid_hostname(hostname):
    """Only letters, digits and . - _ : are allowed, and it must not start with '-'.

    This stops a client from sneaking extra options (like '-t') into the OS command.
    """
    if not hostname or len(hostname) > 253 or hostname.startswith("-"):
        return False
    return all(char.isalnum() or char in ".-_:" for char in hostname)


def execute_command(selected_command, hostname):
    """Run the OS command. Returns (status, output, execution_time_in_seconds)."""
    if selected_command not in COMMANDS:
        return "Failure", f"Unknown command: {selected_command}", 0.0

    args = COMMANDS[selected_command].copy()

    if selected_command in COMMANDS_WITH_HOSTNAME:
        if not is_valid_hostname(hostname):
            return "Failure", "A valid hostname is required (letters, digits, '.', '-', '_', ':').", 0.0
        args.append(hostname)

    start_time = time.time()
    try:
        result = subprocess.run(
            args, capture_output=True, text=True,
            timeout=TIMEOUTS.get(selected_command, DEFAULT_TIMEOUT),
        )
        execution_time = time.time() - start_time

        if result.returncode == 0:
            return "Success", result.stdout, execution_time

        # Some tools (e.g. Windows ping) print their error message on stdout, others on stderr
        output = (result.stdout + result.stderr).strip()
        if not output:
            output = f"Command failed with exit code {result.returncode}"
        return "Failure", output, execution_time

    except subprocess.TimeoutExpired:
        return "Failure", "Command timed out", time.time() - start_time

    except FileNotFoundError:
        return "Failure", f"Command not available on this system: {selected_command}", time.time() - start_time


def receive_request(connection_socket):
    """Read bytes until a newline arrives. Returns the text, or '' if the client disconnected."""
    data = ""
    while "\n" not in data:
        received = connection_socket.recv(1024)
        if not received:
            break
        data += received.decode()
    return data.strip()


def serve_client(connection_socket, addr, logger, stats_file):
    """Runs in its own thread: handles every request of ONE client until it disconnects."""
    try:
        while True:
            data = receive_request(connection_socket)
            if not data:
                break  # client disconnected

            try:
                request = json.loads(data)
                selected_command = request["command"]
                hostname = request.get("parameter")
            except (json.JSONDecodeError, KeyError, TypeError):
                log_message(f"Invalid request from {addr[0]}:{addr[1]}")
                connection_socket.sendall((json.dumps({
                    "command": None, "parameter": None, "status": "Failure",
                    "output": "Invalid request", "execution_time": 0.0,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }) + "\n").encode())
                continue

            log_message(f"Received request from {addr[0]}:{addr[1]}: {request}")

            status, output, execution_time = execute_command(selected_command, hostname)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # The logger has its own lock, so threads never write to the log at the same time
            logger.log_request(addr[0], addr[1], selected_command, hostname, execution_time, status)

            with stats_lock:
                stats["executed_commands"] += 1
                stats["last_execution_time"] = timestamp
            save_statistics(stats_file)

            response = {
                "command": selected_command,
                "parameter": hostname,
                "status": status,
                "output": output,
                "execution_time": execution_time,
                "timestamp": timestamp,
            }
            connection_socket.sendall((json.dumps(response) + "\n").encode())

    except ConnectionError:
        log_message(f"Client disconnected: {addr[0]}:{addr[1]}")
    except Exception as error:
        log_message(f"Server error ({addr[0]}:{addr[1]}): {error}")
    finally:
        with stats_lock:
            stats["connected_clients"] -= 1
        save_statistics(stats_file)
        connection_socket.close()
        log_message(f"Connection closed: {addr[0]}:{addr[1]}")


def run_server():
    config_manager = ConfigManager()
    config_manager.load_config()
    config = config_manager.get_config()

    server_port = config["TCP Port"]
    stats_file = config["Stats File"]
    logger = Logger(config["Log File"])

    server_socket = socket(AF_INET, SOCK_STREAM)
    server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)  # restart quickly without "port in use"
    server_socket.bind(("", server_port))
    server_socket.listen(config["MAX Clients"])

    log_message(f"[TCP] The Server is Ready to Receive on port {server_port}")

    # Remember when the server started (the dashboard shows the uptime)
    stats["server_start_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_statistics(stats_file)

    try:
        # The main thread only accepts clients and hands each one to a new thread
        while True:
            connection_socket, addr = server_socket.accept()

            with stats_lock:
                stats["connected_clients"] += 1
            save_statistics(stats_file)

            connection_socket.sendall("Connected to Network Diagnostic System\n".encode())

            client_thread = threading.Thread(
                target=serve_client,
                args=(connection_socket, addr, logger, stats_file),
                daemon=True,
            )
            client_thread.start()
            log_message(f"Client connected: {addr[0]}:{addr[1]} -> {client_thread.name} created")
    except KeyboardInterrupt:
        log_message("\n[TCP] Shutting down.")
    finally:
        server_socket.close()
