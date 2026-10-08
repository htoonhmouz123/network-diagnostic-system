"""TCP client: shows a menu, sends the chosen command to the server and prints the answer."""

import json
from socket import socket, AF_INET, SOCK_STREAM

from config.config_manager import ConfigManager

# menu choice -> (command name, needs a hostname?)
MENU_OPTIONS = {
    "1": ("PING", True),
    "2": ("TRACEROUTE", True),
    "3": ("DNS", True),
    "4": ("IP_CONFIG", False),
    "5": ("ROUTING_TABLE", False),
    "6": ("ARP_TABLE", False),
    "7": ("TCP_CONNECTIONS", False),
}


def show_menu():
    print("=================================")
    print("   Network Diagnostic System  ")
    print("=================================")
    print("1. Ping Host")
    print("2. Trace Route")
    print("3. DNS Lookup")
    print("4. IP Configuration")
    print("5. Routing Table")
    print("6. ARP Table")
    print("7. Active TCP Connections")
    print("8. Exit")
    return input("Select: ").strip()


def ask_hostname():
    """Keep asking until the user types something (the server needs a hostname)."""
    while True:
        hostname = input("Enter HostName: ").strip()
        if hostname:
            return hostname
        print("Hostname cannot be empty.")


def receive_response(client_socket):
    """Read until '\n' (end of the server's message). Returns a dict, None or 'Invalid'."""
    response = ""
    while "\n" not in response:
        received = client_socket.recv(1024)
        if not received:  # empty bytes = the server closed the connection
            return None
        response += received.decode()

    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        return "Invalid"


def run_client():
    config_manager = ConfigManager()
    config_manager.load_config()
    config = config_manager.get_config()

    client_socket = socket(AF_INET, SOCK_STREAM)
    try:
        client_socket.connect((config["Server Host"], config["TCP Port"]))
    except ConnectionRefusedError:
        print(f"Could not connect to {config['Server Host']}:{config['TCP Port']}. Is run_server.py running?")
        return

    # The server greets every new client
    confirmation = client_socket.recv(1024)
    if confirmation:
        print(confirmation.decode().strip())

    while True:
        choice = show_menu()

        if choice == "8":
            print("Exiting.. :)")
            break

        if choice not in MENU_OPTIONS:
            print("Invalid Choice, Select a Valid Option")
            continue

        command, needs_hostname = MENU_OPTIONS[choice]
        parameter = ask_hostname() if needs_hostname else None

        request = {"command": command, "parameter": parameter}
        client_socket.sendall((json.dumps(request) + "\n").encode())  # '\n' marks the end of the request

        response = receive_response(client_socket)

        if response is None:
            print("Server Disconnected")
            break

        if response == "Invalid":
            print("Invalid Response")
            continue

        print("Command:", response["command"])
        print("Status:", response["status"])
        print("Execution Time:", response["execution_time"])
        print("Time Stamp:", response["timestamp"])
        print("Output:", response["output"])

    client_socket.close()
