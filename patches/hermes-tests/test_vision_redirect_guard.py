"""A public image URL must not reach an internal address, by redirect or by DNS rebinding."""

import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import tools.url_safety
from tools.vision_tools import _download_image


@pytest.fixture()
def server(monkeypatch):
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            if self.path.startswith("/redirect/"):
                self.send_response(302)
                self.send_header("Location", "/" + self.path.split("/", 2)[2])
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = b"image-bytes"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    async def treat_internal_path_as_private(url):
        return "/internal" not in url

    monkeypatch.setattr(tools.url_safety, "async_is_safe_url", treat_internal_path_as_private)
    # The connect-time guard would refuse this loopback server before any redirect is seen.
    monkeypatch.setattr(tools.url_safety, "_global_allow_private_urls", lambda: True)
    monkeypatch.setenv("NO_PROXY", "*")
    yield f"http://127.0.0.1:{httpd.server_port}", hits
    httpd.shutdown()
    httpd.server_close()


def test_redirect_to_internal_address_is_never_requested(server, tmp_path):
    base, hits = server
    with pytest.raises(ValueError, match="Blocked redirect"):
        asyncio.run(_download_image(f"{base}/redirect/internal", tmp_path / "x", max_retries=1))
    assert hits == ["/redirect/internal"]
    assert not (tmp_path / "x").exists()


def test_redirect_to_public_address_still_works(server, tmp_path):
    base, hits = server
    asyncio.run(_download_image(f"{base}/redirect/picture.png", tmp_path / "x", max_retries=1))
    assert hits == ["/redirect/picture.png", "/picture.png"]
    assert (tmp_path / "x").read_bytes() == b"image-bytes"


def test_private_address_at_connect_time_is_refused(server, tmp_path, monkeypatch):
    """Preflight can pass and DNS can then answer with an internal address (upstream 42626da1ce)."""
    base, hits = server
    monkeypatch.setattr(tools.url_safety, "_global_allow_private_urls", lambda: False)

    with pytest.raises(Exception, match="during connect"):
        asyncio.run(_download_image(f"{base}/picture.png", tmp_path / "x", max_retries=1))

    assert hits == []
    assert not (tmp_path / "x").exists()
