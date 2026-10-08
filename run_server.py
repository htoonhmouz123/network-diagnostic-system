"""Starts BOTH servers: the HTTP web server (background thread) and the TCP server (main thread)."""

import threading

from server.tcp_server import run_server
from web.config_loader import load_config
from web.http_server import HTTPServer


def run_http_server():
    HTTPServer(load_config()).start()


if __name__ == "__main__":
    # daemon=True: the web server stops automatically when the TCP server stops
    threading.Thread(target=run_http_server, daemon=True).start()
    run_server()
