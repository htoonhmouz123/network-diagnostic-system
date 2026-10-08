"""Builds the HTML of every page of the web interface."""

NAV_BAR = """
<nav>
  <a href="/home">Home</a>
  <a href="/dashboard">Dashboard</a>
  <a href="/history">Command History</a>
  <a href="/statistics">Statistics</a>
  <a href="/search">Search</a>
  <a href="/download">Download Log</a>
</nav>
"""

STYLE = """
<style>
  body { font-family: Arial, sans-serif; margin: 40px; background: #f7f7f9; color: #222; }
  nav a { margin-right: 15px; text-decoration: none; color: #2b5fad; font-weight: bold; }
  table { border-collapse: collapse; width: 100%; margin-top: 15px; background: white; }
  th, td { border: 1px solid #ccc; padding: 8px 10px; text-align: left; }
  th { background: #2b5fad; color: white; }
  tr:nth-child(even) { background: #f0f0f0; }
  h1 { color: #2b5fad; }
  form input, form select { padding: 6px; margin: 4px 0; }
  .card { display: inline-block; background: white; border-radius: 8px; padding: 15px 25px;
          margin: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.15); }
  .card h2 { margin: 0; font-size: 28px; }
  .card p { margin: 4px 0 0 0; color: #555; }
</style>
"""

TABLE_HEADER = (
    "<tr><th>Time</th><th>Client IP</th><th>Command</th>"
    "<th>Parameter</th><th>Exec Time (s)</th><th>Status</th></tr>"
)


def esc(value):
    """Make a value safe to place inside HTML (so log data can never inject tags or scripts)."""
    text = "" if value is None else str(value)
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace('"', "&quot;").replace("'", "&#x27;"))


def _wrap(title, body_html):
    # every page reuses the same nav bar + style, only the body changes
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{esc(title)}</title>
  {STYLE}
</head>
<body>
  {NAV_BAR}
  <hr>
  {body_html}
</body>
</html>"""


def _log_rows(entries):
    return "".join(
        f"""<tr>
            <td>{esc(e.get('Timestamp', ''))}</td>
            <td>{esc(e.get('ClientIP', ''))}</td>
            <td>{esc(e.get('Command', ''))}</td>
            <td>{esc(e.get('Parameters', ''))}</td>
            <td>{esc(e.get('ExecutionTime', ''))}</td>
            <td>{esc(e.get('Status', ''))}</td>
        </tr>"""
        for e in entries
    )


def _card(value, label):
    return f'<div class="card"><h2>{esc(value)}</h2><p>{esc(label)}</p></div>'


def render_home(config):
    team = config["team"]
    members = team["members"]
    show_ids = any(m.get("id") for m in members)  # the ID column only appears if IDs are configured

    id_header = "<th>Student ID</th>" if show_ids else ""
    rows = "".join(
        f"<tr><td>{esc(m['name'])}</td>"
        + (f"<td>{esc(m.get('id', ''))}</td>" if show_ids else "")
        + f"<td>{esc(m['section'])}</td></tr>"
        for m in members
    )
    body = f"""
    <h1>Network Diagnostic System - Team {esc(team['team_number'])}</h1>
    <p><strong>Course:</strong> {esc(team['course'])}</p>
    <table>
      <tr><th>Name</th>{id_header}<th>Section</th></tr>
      {rows}
    </table>
    <p>
      This project implements a client-server network diagnostic system.
      A TCP client requests networking operations (ping, traceroute, DNS
      lookup, etc.) from a multi-threaded TCP server, which executes the
      command, logs the result, and exposes it here through a hand-built
      HTTP web server using raw sockets.
    </p>
    """
    return _wrap("Home", body)


def render_dashboard(live_stats, uptime_str):
    last_run = live_stats.get("last_execution_time") or "N/A"
    body = "<h1>Dashboard</h1>" + "".join([
        _card(live_stats["executed_commands"], "Executed commands"),
        _card(live_stats["connected_clients"], "Connected clients"),
        _card(last_run, "Last execution time"),
        _card(uptime_str, "Server uptime"),
    ])
    return _wrap("Dashboard", body)


def render_history(entries):
    if not entries:
        rows_html = "<tr><td colspan='6'>No commands executed yet.</td></tr>"
    else:
        rows_html = _log_rows(entries)
    body = f"""
    <h1>Command History</h1>
    <table>
      {TABLE_HEADER}
      {rows_html}
    </table>
    """
    return _wrap("Command History", body)


def render_statistics(stats):
    average = f"{stats['Average Execution Time']}s"
    body = "<h1>Statistics</h1>" + "".join([
        _card(stats["Total Commands"], "Total commands executed"),
        _card(stats["Most Frequent Command"] or "N/A", "Most used command"),
        _card(average, "Average execution time"),
        _card(stats["Successful Requests"], "Successful requests"),
        _card(stats["Failed Requests"], "Failed requests"),
        _card(stats["Last Execution Time"] or "N/A", "Last execution time"),
    ])
    return _wrap("Statistics", body)


def render_search(results=None, query=None):
    """results is None on the first visit (no search yet) or a list of matching entries."""
    form = """
    <form method="GET" action="/search">
      <label>Command: <input type="text" name="command" placeholder="e.g. PING"></label><br>
      <label>Hostname: <input type="text" name="hostname" placeholder="e.g. google.com"></label><br>
      <label>Client IP: <input type="text" name="client_ip" placeholder="e.g. 192.168.1.10"></label><br>
      <button type="submit">Search</button>
    </form>
    """

    results_html = ""
    if results is not None:
        if not results:
            results_html = "<p>No matching results.</p>"
        else:
            results_html = f"""
            <table>
              {TABLE_HEADER}
              {_log_rows(results)}
            </table>
            """

    body = f"""
    <h1>Search Command History</h1>
    {form}
    {results_html}
    """
    return _wrap("Search", body)


def render_download_page(log_filename):
    body = f"""
    <h1>Download Log File</h1>
    <p>Click below to download the full request log.</p>
    <a href="/download/log"><button>Download {esc(log_filename)}</button></a>
    """
    return _wrap("Download", body)


def render_error(status_code, status_text, message):
    body = f"""
    <h1>{esc(status_code)} {esc(status_text)}</h1>
    <p>{esc(message)}</p>
    <p><a href="/home">Back to Home</a></p>
    """
    return _wrap(f"{status_code} {status_text}", body)
