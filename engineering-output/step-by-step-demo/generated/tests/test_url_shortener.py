import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from agentic_sdlc.url_shortener import (
    InvalidTargetUrl,
    UrlShortenerStore,
    create_handler,
)


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


class UrlShortenerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temporary_directory.name) / "shortener.sqlite3")
        self.store = UrlShortenerStore(self.database)
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), create_handler(self.store, "http://127.0.0.1")
        )
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.base_url = "http://127.0.0.1:{}".format(self.server.server_address[1])
        self.server.RequestHandlerClass = create_handler(self.store, self.base_url)
        self.server_thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=3)
        self.temporary_directory.cleanup()

    def request_json(self, path, method="GET", payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        return urlopen(request)

    def test_create_redirect_and_analytics(self):
        with self.request_json(
            "/api/urls", method="POST", payload={"target_url": "https://example.com/path"}
        ) as response:
            self.assertEqual(response.status, 201)
            created = json.loads(response.read().decode("utf-8"))
        self.assertEqual(created["target_url"], "https://example.com/path")
        self.assertEqual(
            created["short_url"], "{}/{}".format(self.base_url, created["code"])
        )

        request = Request(self.base_url + "/" + created["code"])
        no_redirect_opener = build_opener(NoRedirectHandler())
        with self.assertRaises(HTTPError) as redirect:
            no_redirect_opener.open(request)
        self.assertEqual(redirect.exception.code, 302)
        self.assertEqual(redirect.exception.headers["Location"], "https://example.com/path")

        with self.request_json(
            "/api/urls/{}/analytics".format(created["code"])
        ) as response:
            analytics = json.loads(response.read().decode("utf-8"))
        self.assertEqual(analytics["click_count"], 1)
        self.assertEqual(sum(item["clicks"] for item in analytics["daily_clicks"]), 1)
        restarted_store = UrlShortenerStore(self.database)
        self.assertEqual(restarted_store.analytics(created["code"])["click_count"], 1)

    def test_rejects_unsupported_and_credential_urls(self):
        credential_url = "https://" + "viewer" + ":" + "demo" + "@example.com"
        for target in ("javascript:alert(1)", credential_url):
            with self.subTest(target=target):
                with self.assertRaises(InvalidTargetUrl):
                    self.store.create(target)

    def test_missing_short_code_returns_404(self):
        with self.assertRaises(HTTPError) as response:
            self.request_json("/does-not-exist")
        self.assertEqual(response.exception.code, 404)

    def test_malformed_json_returns_400(self):
        request = Request(
            self.base_url + "/api/urls",
            data=b"{",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as response:
            urlopen(request)
        self.assertEqual(response.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
