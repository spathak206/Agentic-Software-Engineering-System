"""Runnable SQLite-backed URL shortener HTTP service."""

import argparse
import json
import re
import secrets
import sqlite3
import sys
import threading
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import urlsplit


CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
MAX_REQUEST_BYTES = 16 * 1024
MAX_TARGET_LENGTH = 2048


class InvalidTargetUrl(ValueError):
    pass


class UrlShortenerStore:
    def __init__(self, database: str) -> None:
        self.database = database
        self._initialize_lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._initialize_lock:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute("PRAGMA journal_mode=WAL")
                    connection.execute(
                        """
                        CREATE TABLE IF NOT EXISTS urls (
                            code TEXT PRIMARY KEY,
                            target_url TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            click_count INTEGER NOT NULL DEFAULT 0
                        )
                        """
                    )
                    connection.execute(
                        """
                        CREATE TABLE IF NOT EXISTS click_events (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            code TEXT NOT NULL REFERENCES urls(code),
                            clicked_at TEXT NOT NULL
                        )
                        """
                    )
                    connection.execute(
                        "CREATE INDEX IF NOT EXISTS click_events_code_time ON click_events(code, clicked_at)"
                    )

    def create(self, target_url: str) -> Dict[str, Any]:
        validate_target_url(target_url)
        for _ in range(5):
            code = secrets.token_urlsafe(6)
            created_at = datetime.now(timezone.utc).isoformat()
            try:
                with closing(self._connect()) as connection:
                    with connection:
                        connection.execute(
                            "INSERT INTO urls (code, target_url, created_at) VALUES (?, ?, ?)",
                            (code, target_url, created_at),
                        )
                return {"code": code, "target_url": target_url, "created_at": created_at}
            except sqlite3.IntegrityError:
                continue
        raise RuntimeError("Unable to allocate a unique short code after five attempts")

    def record_click(self, code: str) -> Optional[str]:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT target_url FROM urls WHERE code = ?", (code,)
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            connection.execute(
                "UPDATE urls SET click_count = click_count + 1 WHERE code = ?", (code,)
            )
            connection.execute(
                "INSERT INTO click_events (code, clicked_at) VALUES (?, ?)",
                (code, datetime.now(timezone.utc).isoformat()),
            )
            connection.commit()
            return str(row["target_url"])

    def analytics(self, code: str) -> Optional[Dict[str, Any]]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT code, target_url, created_at, click_count FROM urls WHERE code = ?",
                (code,),
            ).fetchone()
            if row is None:
                return None
            daily_rows = connection.execute(
                """
                SELECT substr(clicked_at, 1, 10) AS day, COUNT(*) AS clicks
                FROM click_events WHERE code = ?
                GROUP BY day ORDER BY day DESC
                """,
                (code,),
            ).fetchall()
        return {
            "code": str(row["code"]),
            "target_url": str(row["target_url"]),
            "created_at": str(row["created_at"]),
            "click_count": int(row["click_count"]),
            "daily_clicks": [
                {"date": str(item["day"]), "clicks": int(item["clicks"])}
                for item in daily_rows
            ],
        }


def validate_target_url(target_url: Any) -> None:
    if not isinstance(target_url, str) or not target_url or len(target_url) > MAX_TARGET_LENGTH:
        raise InvalidTargetUrl("target_url must be a non-empty string of at most 2048 characters")
    if any(character.isspace() for character in target_url):
        raise InvalidTargetUrl("target_url must not contain whitespace")
    try:
        parsed = urlsplit(target_url)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as error:
        raise InvalidTargetUrl("target_url is malformed: {}".format(error))
    if parsed.scheme not in ("http", "https") or not hostname:
        raise InvalidTargetUrl("target_url must be an absolute HTTP or HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise InvalidTargetUrl("target_url must not contain embedded credentials")


def create_handler(store: UrlShortenerStore, public_base_url: str):
    class UrlShortenerHandler(BaseHTTPRequestHandler):
        def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> Any:
            raw_length = self.headers.get("Content-Length")
            try:
                length = int(raw_length or "")
            except ValueError:
                raise ValueError("Content-Length must be a valid integer")
            if length < 0 or length > MAX_REQUEST_BYTES:
                raise OverflowError("Request body exceeds the 16 KiB limit")
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("Request body ended before Content-Length bytes were read")
            try:
                return json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("Request body must be valid UTF-8 JSON: {}".format(error))

        def do_POST(self) -> None:
            if self.path != "/api/urls":
                self._send_json(404, {"error": "not_found"})
                return
            try:
                payload = self._read_json()
            except OverflowError as error:
                self._send_json(413, {"error": str(error)})
                return
            except ValueError as error:
                self._send_json(400, {"error": str(error)})
                return
            if not isinstance(payload, dict):
                self._send_json(400, {"error": "JSON body must be an object"})
                return
            try:
                created = store.create(payload.get("target_url"))
            except InvalidTargetUrl as error:
                self._send_json(400, {"error": str(error)})
                return
            created["short_url"] = "{}/{}".format(public_base_url, created["code"])
            self._send_json(201, created)

        def do_GET(self) -> None:
            parts = urlsplit(self.path).path.split("/")
            if len(parts) == 5 and parts[:3] == ["", "api", "urls"] and parts[4] == "analytics":
                code = parts[3]
                if not CODE_PATTERN.fullmatch(code):
                    self._send_json(404, {"error": "not_found"})
                    return
                result = store.analytics(code)
                if result is None:
                    self._send_json(404, {"error": "not_found"})
                    return
                self._send_json(200, result)
                return
            if len(parts) != 2 or not CODE_PATTERN.fullmatch(parts[1]):
                self._send_json(404, {"error": "not_found"})
                return
            target_url = store.record_click(parts[1])
            if target_url is None:
                self._send_json(404, {"error": "not_found"})
                return
            self.send_response(302)
            self.send_header("Location", target_url)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            sys.stderr.write(
                "%s - %s\n" % (self.address_string(), format % args)
            )

    return UrlShortenerHandler


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local SQLite URL shortener service.")
    parser.add_argument("--database", default="url_shortener.db", help="SQLite database path")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: loopback only)")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (default: 8000)")
    arguments = parser.parse_args()
    if not 0 < arguments.port < 65536:
        parser.error("--port must be between 1 and 65535")
    store = UrlShortenerStore(arguments.database)
    base_url = "http://{}:{}".format(arguments.host, arguments.port)
    server = ThreadingHTTPServer(
        (arguments.host, arguments.port), create_handler(store, base_url)
    )
    print("URL shortener listening on {}".format(base_url), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping URL shortener.", file=sys.stderr)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
