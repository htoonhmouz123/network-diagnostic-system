"""Unit tests for the parts that do not need a running server. Run: python -m unittest discover tests"""

import tempfile
import unittest
from pathlib import Path

from config.config_manager import ConfigManager
from core.log_parser import parse_log_line, read_log_file
from core.logger import Logger
from core.stats_calculator import compute_statistics
from server.tcp_server import execute_command, is_valid_hostname
from web import pages
from web.http_server import build_response, parse_request_line, percent_decode
from web.log_utils import search_log
from web.stats_utils import format_uptime

SAMPLE = [
    {"Timestamp": "2026-01-01 10:00:00", "ClientIP": "127.0.0.1", "Command": "PING",
     "Parameters": "google.com", "ExecutionTime": "3.0", "Status": "Success"},
    {"Timestamp": "2026-01-01 10:01:00", "ClientIP": "10.0.0.5", "Command": "PING",
     "Parameters": "invalid-host", "ExecutionTime": "1.0", "Status": "Failure"},
    {"Timestamp": "2026-01-01 10:02:00", "ClientIP": "127.0.0.1", "Command": "DNS",
     "Parameters": "birzeit.edu", "ExecutionTime": "2.0", "Status": "Success"},
]


class ConfigTests(unittest.TestCase):
    def test_ports_come_from_last_three_digits(self):
        manager = ConfigManager()
        manager.load_config()
        config = manager.get_config()
        last_three = int(str(config["Student ID"])[-3:])
        self.assertEqual(config["TCP Port"], last_three + 5000)
        self.assertEqual(config["HTTP Port"], last_three + 6000)

    def test_bad_student_id_is_rejected(self):
        manager = ConfigManager()
        manager.config = {"Student ID": "12ab"}
        with self.assertRaises(ValueError):
            manager.validate_student_id()


class LogTests(unittest.TestCase):
    def test_logger_and_parser_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            log_file = Path(folder) / "nested" / "server.log"
            Logger(log_file).log_request("127.0.0.1", 5000, "PING", "google.com", 0.5, "Success")
            entries = read_log_file(log_file)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["Command"], "PING")
            self.assertEqual(entries[0]["ExecutionTime"], "0.5000")

    def test_missing_log_is_empty_list(self):
        self.assertEqual(read_log_file("does/not/exist.log"), [])

    def test_parse_line(self):
        self.assertEqual(parse_log_line("A=1 | B=two=2"), {"A": "1", "B": "two=2"})


class StatisticsTests(unittest.TestCase):
    def test_statistics_values(self):
        stats = compute_statistics(SAMPLE)
        self.assertEqual(stats["Total Commands"], 3)
        self.assertEqual(stats["Most Frequent Command"], "PING")
        self.assertEqual(stats["Average Execution Time"], 2.0)
        self.assertEqual(stats["Successful Requests"], 2)
        self.assertEqual(stats["Failed Requests"], 1)
        self.assertEqual(stats["Last Execution Time"], "2026-01-01 10:02:00")

    def test_empty_log(self):
        self.assertEqual(compute_statistics([])["Total Commands"], 0)


class SearchTests(unittest.TestCase):
    def test_filters(self):
        self.assertEqual(len(search_log(SAMPLE, command="ping")), 2)
        self.assertEqual(len(search_log(SAMPLE, hostname="BIRZEIT")), 1)
        self.assertEqual(len(search_log(SAMPLE, client_ip="10.0.0.5")), 1)
        self.assertEqual(len(search_log(SAMPLE, command="PING", client_ip="127.0.0.1")), 1)
        self.assertEqual(len(search_log(SAMPLE)), 3)


class ServerValidationTests(unittest.TestCase):
    def test_hostname_rules(self):
        for good in ("google.com", "birzeit.edu", "192.168.1.1", "my-host_1", "::1"):
            self.assertTrue(is_valid_hostname(good), good)
        for bad in ("", "-t", "a b", "a;b", "a&b", "$(x)", "x" * 300, None):
            self.assertFalse(is_valid_hostname(bad), bad)

    def test_unknown_command_and_missing_hostname(self):
        self.assertEqual(execute_command("HACK", None)[0], "Failure")
        status, output, _ = execute_command("PING", "")
        self.assertEqual(status, "Failure")
        self.assertIn("hostname", output.lower())


class HttpTests(unittest.TestCase):
    def test_percent_decode(self):
        self.assertEqual(percent_decode("a%20b+c"), "a b c")
        self.assertEqual(percent_decode("%D8%AA"), "\u062a")
        self.assertEqual(percent_decode("100%"), "100%")

    def test_parse_request_line(self):
        method, path, params = parse_request_line("GET /search?command=PING&hostname=a.com HTTP/1.1\r\nHost: x\r\n\r\n")
        self.assertEqual((method, path), ("GET", "/search"))
        self.assertEqual(params, {"command": "PING", "hostname": "a.com"})
        with self.assertRaises(ValueError):
            parse_request_line("garbage")

    def test_response_format(self):
        raw = build_response(404, "Not Found", b"hi")
        head, _, body = raw.partition(b"\r\n\r\n")
        self.assertTrue(head.startswith(b"HTTP/1.1 404 Not Found"))
        self.assertIn(b"Content-Length: 2", head)
        self.assertEqual(body, b"hi")

    def test_html_is_escaped(self):
        page = pages.render_history([{"Parameters": "<script>alert(1)</script>"}])
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)

    def test_uptime_format(self):
        self.assertEqual(format_uptime(None), "N/A")
        self.assertEqual(format_uptime("not a date"), "N/A")


if __name__ == "__main__":
    unittest.main()
