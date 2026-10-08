"""A small HTTP/1.1 web server built directly on sockets (no http.server, no frameworks).

Flow: accept connection -> read the raw request text -> work out which page was asked for
-> send back raw HTTP response text -> close the connection.
"""

import os
import socket
import threading

from core.console import log_message
from web import log_utils
from web import pages
from web import stats_utils
from core.stats_calculator import compute_statistics


def percent_decode(text):
    """Decode URL escapes: 'a%20b+c' -> 'a b c', also handles UTF-8 like '%D8%AA'."""
    text = text.replace("+", " ")  # browsers send spaces in forms as '+'
    raw = bytearray()
    i = 0
    while i < len(text):
        if text[i] == "%" and _is_hex(text[i + 1:i + 3]):
            raw.append(int(text[i + 1:i + 3], 16))
            i += 3
        else:
            raw.extend(text[i].encode("utf-8"))
            i += 1
    return raw.decode("utf-8", errors="replace")


def _is_hex(two_chars):
    return len(two_chars) == 2 and all(c in "0123456789abcdefABCDEF" for c in two_chars)


def parse_query_string(query_string):
    """'command=PING&hostname=google.com' -> {'command': 'PING', 'hostname': 'google.com'}"""
    params = {}
    if not query_string:
        return params

    for pair in query_string.split("&"):
        key, _, value = pair.partition("=")
        params[percent_decode(key)] = percent_decode(value)
    return params


def parse_request_line(request_text):
    """First line looks like 'GET /search?command=PING HTTP/1.1' -> (method, path, params)."""
    first_line = request_text.split("\r\n", 1)[0]
    parts = first_line.split(" ")

    if len(parts) != 3:
        raise ValueError("Malformed request line")  # the caller turns this into a 400

    method, full_path, _http_version = parts
    path, _, query_string = full_path.partition("?")
    return method, path, parse_query_string(query_string)


def build_response(status_code, status_text, body_bytes, content_type="text/html", extra_headers=None):
    """Build the raw bytes of an HTTP response (status line + headers + blank line + body)."""
    headers = [
        f"HTTP/1.1 {status_code} {status_text}",
        f"Content-Type: {content_type}; charset=utf-8",
        f"Content-Length: {len(body_bytes)}",
        "Connection: close",
    ]
    if extra_headers:
        for key, value in extra_headers.items():
            headers.append(f"{key}: {value}")

    header_text = "\r\n".join(headers) + "\r\n\r\n"
    return header_text.encode("utf-8") + body_bytes


def html_response(status_code, status_text, html):
    return build_response(status_code, status_text, html.encode("utf-8"))


class HTTPServer:
    def __init__(self, config):
        self.config = config
        self.host = "0.0.0.0"
        self.port = config["http_port"]

    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(self.config.get("max_clients", 10))
        log_message(f"[HTTP] Web server listening on port {self.port} ...")

        try:
            while True:
                client_socket, client_address = server_socket.accept()
                # one thread per connection, so several browser tabs work at the same time
                threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, client_address),
                    daemon=True,
                ).start()
        except KeyboardInterrupt:
            log_message("[HTTP] Shutting down.")
        finally:
            server_socket.close()

    def handle_client(self, client_socket, client_address):
        try:
            request_bytes = client_socket.recv(4096)
            if not request_bytes:
                return
            request_text = request_bytes.decode("utf-8", errors="replace")

            try:
                method, path, query_params = parse_request_line(request_text)
            except ValueError:
                # garbage request: we cannot even tell which page was wanted
                response = html_response(
                    400, "Bad Request",
                    pages.render_error(400, "Bad Request", "Could not parse your request."),
                )
            else:
                response = self.route(method, path, query_params)

            client_socket.sendall(response)

        except Exception as error:
            # one bad request must never kill the whole server
            log_message(f"[HTTP] Error handling {client_address}: {error}")
        finally:
            client_socket.close()

    def route(self, method, path, query_params):
        """Decide which page to build for this URL. Returns the full response bytes."""

        # 403: block path traversal tricks like /../secret and the /private area
        if ".." in path or path.startswith("/private"):
            return html_response(403, "Forbidden",
                                 pages.render_error(403, "Forbidden", "Access to this resource is not allowed."))

        # 400: only GET is supported
        if method != "GET":
            return html_response(400, "Bad Request",
                                 pages.render_error(400, "Bad Request", "Only GET requests are supported."))

        # "/" shows the default homepage from config.json
        if path == "/":
            default_page = self.config.get("default_homepage", "home").strip("/")
            path = "/" + default_page if default_page else "/home"

        if path == "/home":
            return html_response(200, "OK", pages.render_home(self.config))

        if path == "/dashboard":
            live_stats = stats_utils.read_live_stats(self.config["stats_file"])
            uptime = stats_utils.format_uptime(live_stats.get("server_start_time"))
            return html_response(200, "OK", pages.render_dashboard(live_stats, uptime))

        if path == "/history":
            entries = log_utils.read_log(self.config["log_file"])
            return html_response(200, "OK", pages.render_history(entries))

        if path == "/statistics":
            entries = log_utils.read_log(self.config["log_file"])
            return html_response(200, "OK", pages.render_statistics(compute_statistics(entries)))

        if path == "/search":
            if not query_params:
                return html_response(200, "OK", pages.render_search(results=None))  # empty form

            entries = log_utils.read_log(self.config["log_file"])
            results = log_utils.search_log(
                entries,
                command=query_params.get("command"),
                hostname=query_params.get("hostname"),
                client_ip=query_params.get("client_ip"),
            )
            return html_response(200, "OK", pages.render_search(results=results, query=query_params))

        if path == "/download":
            log_filename = os.path.basename(self.config["log_file"])
            return html_response(200, "OK", pages.render_download_page(log_filename))

        if path == "/download/log":
            # this one really sends the file, not just a page about it
            log_path = self.config["log_file"]
            if not os.path.exists(log_path):
                return html_response(404, "Not Found",
                                     pages.render_error(404, "Not Found", "Log file does not exist yet."))

            with open(log_path, "rb") as file:
                file_bytes = file.read()

            return build_response(
                200, "OK", file_bytes,
                content_type="application/octet-stream",
                extra_headers={"Content-Disposition": f'attachment; filename="{os.path.basename(log_path)}"'},
            )

        # anything else: custom 404 page
        return html_response(404, "Not Found",
                             pages.render_error(404, "Not Found", "The page you requested does not exist."))
