import gzip
import socket
from email.message import Message


class _Response:
    def __init__(self, body: bytes, *, content_type="text/html", encoding=""):
        self.body = body
        self.status = 200
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if encoding:
            self.headers["Content-Encoding"] = encoding

    def getcode(self):
        return self.status

    def read(self, size=-1):
        return self.body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_static_html_extraction_preserves_table_text(monkeypatch):
    from plugins.web.simple_http import provider

    html = b"<html><title>Tier list</title><script>bad()</script><table><tr><th>Hero</th><th>Win</th></tr><tr><td>Lee Sin</td><td>40.41%</td></tr></table></html>"
    monkeypatch.setattr(provider, "is_safe_url", lambda url: True)
    monkeypatch.setattr(provider.urllib.request.OpenerDirector, "open", lambda *a, **k: _Response(html))

    result = provider.SimpleHTTPExtractProvider().extract(["https://example.test/tier"])[0]
    assert result["title"] == "Tier list"
    assert "Lee Sin" in result["content"]
    assert "40.41%" in result["content"]
    assert "bad()" not in result["content"]


def test_redirect_to_private_address_is_blocked(monkeypatch):
    from plugins.web.simple_http import provider

    redirect = _Response(b"")
    redirect.status = 302
    redirect.headers["Location"] = "http://127.0.0.1/private"
    monkeypatch.setattr(provider, "is_safe_url", lambda url: "127.0.0.1" not in url)
    monkeypatch.setattr(provider.urllib.request.OpenerDirector, "open", lambda *a, **k: redirect)

    result = provider.SimpleHTTPExtractProvider().extract(["https://example.test/start"])[0]
    assert "private or internal" in result["error"]


def test_decompression_limit_is_enforced():
    from plugins.web.simple_http import provider

    compressed = gzip.compress(b"x" * (provider._MAX_DECOMPRESSED_BYTES + 1))
    try:
        provider._decode_body(compressed, "gzip")
    except ValueError as exc:
        assert "8 MiB" in str(exc)
    else:
        raise AssertionError("oversized decompressed content was accepted")


def test_connection_rejects_dns_rebinding_to_private_address(monkeypatch):
    from plugins.web.simple_http import provider

    monkeypatch.setattr(
        provider.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ],
    )
    try:
        provider._connect_public_address(("example.test", 443), 1)
    except ValueError as exc:
        assert "private or internal" in str(exc)
    else:
        raise AssertionError("private DNS answer was accepted")


def test_production_web_selection_resolves_both_tools(monkeypatch):
    import tools.web_tools as web_tools
    from tools.web_tools_extract import _resolve_extract_provider

    monkeypatch.setattr(
        web_tools, "_load_web_config",
        lambda: {"search_backend": "ddgs", "extract_backend": "simple-http"},
    )
    web_tools._ensure_web_plugins_loaded()

    assert web_tools.check_web_api_key() is True
    assert web_tools._get_search_backend() == "ddgs"
    provider, error = _resolve_extract_provider(web_tools._get_extract_backend())
    assert error is None
    assert provider.name == "simple-http"
