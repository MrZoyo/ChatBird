import json


def _enabled_config(**overrides):
    config = {
        "enabled": True,
        "search": True,
        "extract": True,
        "require_cloud": True,
        "settle_seconds": 0,
        "min_content_chars": 20,
        "max_pages": 2,
    }
    config.update(overrides)
    return config


def test_browser_fallback_requires_explicit_enable_and_cloud(monkeypatch):
    import tools.browser_tool as browser
    import tools.web_browser_fallback as fallback

    monkeypatch.setattr(fallback, "_fallback_config", lambda: {})
    assert fallback.fallback_enabled("extract") is False

    monkeypatch.setattr(
        fallback, "_fallback_config", lambda: _enabled_config(require_cloud=True)
    )
    monkeypatch.setattr(browser, "_get_cloud_provider", lambda: None)
    monkeypatch.setattr(browser, "check_browser_requirements", lambda: True)
    assert fallback.browser_backend_ready() is False

    monkeypatch.setattr(browser, "_get_cloud_provider", lambda: object())
    assert fallback.browser_backend_ready() is True


def test_retry_classification_never_bypasses_safety_failures():
    import tools.web_browser_fallback as fallback

    assert fallback._extract_needs_fallback({"error": "HTTP 403"}, 20) is True
    # A 429 is an explicit rate limit, not a rendering failure.  Switching IPs
    # through a browser would evade the publisher's throttle, so fail closed.
    assert fallback._extract_needs_fallback({"error": "HTTP 429"}, 20) is False
    assert fallback._extract_needs_fallback(
        {"title": "Just a moment...", "content": "Checking your browser"}, 20
    ) is True
    assert fallback._extract_needs_fallback(
        {"error": "Blocked: redirect targets a private or internal address"}, 20
    ) is False
    assert fallback._extract_needs_fallback(
        {"error": "Response exceeds 4 MiB download limit"}, 20
    ) is False


def test_extract_fallback_replaces_only_retryable_result(monkeypatch):
    import tools.web_browser_fallback as fallback

    attempted = []
    monkeypatch.setattr(
        fallback, "_fallback_config", lambda: _enabled_config(min_content_chars=10)
    )
    monkeypatch.setattr(fallback, "browser_backend_ready", lambda: True)
    monkeypatch.setattr(fallback, "_safe_public_url", lambda url: True)

    def fake_dom(url, **kwargs):
        attempted.append(url)
        return {
            "url": url,
            "title": "Recovered",
            "content": "browser rendered content",
        }, None

    monkeypatch.setattr(fallback, "_browser_dom", fake_dom)
    results = fallback.maybe_extract_with_browser(
        [
            {
                "url": "https://blocked.test/",
                "content": "",
                "error": "HTTP 403",
            },
            {
                "url": "https://private.test/",
                "content": "",
                "error": "Blocked: private or internal network address",
            },
            {
                "url": "https://ok.test/",
                "title": "OK",
                "content": "already enough content",
            },
        ],
        ["https://blocked.test/", "https://private.test/", "https://ok.test/"],
    )

    assert attempted == ["https://blocked.test/"]
    assert results[0]["retrieval"] == "browser-fallback"
    assert results[0]["content"] == "browser rendered content"
    assert results[1]["error"].startswith("Blocked:")
    assert results[2]["content"] == "already enough content"


def test_extract_fallback_recovers_missing_provider_result(monkeypatch):
    import tools.web_browser_fallback as fallback

    monkeypatch.setattr(fallback, "_fallback_config", lambda: _enabled_config())
    monkeypatch.setattr(fallback, "browser_backend_ready", lambda: True)
    monkeypatch.setattr(fallback, "_safe_public_url", lambda url: True)
    monkeypatch.setattr(
        fallback,
        "_browser_dom",
        lambda url, **kwargs: (
            {"url": url, "title": "Late", "content": "rendered missing page"},
            None,
        ),
    )

    results = fallback.maybe_extract_with_browser([], ["https://missing.test/"])
    assert len(results) == 1
    assert results[0]["retrieval"] == "browser-fallback"


def test_reader_fallback_is_host_allowlisted_and_rejects_challenges(monkeypatch):
    import tools.web_browser_fallback as fallback

    config = _enabled_config(
        reader_enabled=True,
        reader_allowed_hosts=["www.vicioussyndicate.com"],
    )
    monkeypatch.setattr(fallback, "_fallback_config", lambda: config)
    monkeypatch.setattr(fallback, "_safe_public_url", lambda url: True)

    class Response:
        status_code = 200
        headers = {"content-type": "text/plain; charset=utf-8"}

        def __init__(self, body):
            self.body = body

        def iter_content(self, chunk_size):
            yield self.body.encode()

        def close(self):
            pass

    valid = (
        "Title: Report\n\n"
        "URL Source: https://www.vicioussyndicate.com/report/\n\n"
        "Markdown Content:\nUseful report content with enough detail."
    )
    monkeypatch.setattr(
        fallback.requests, "get", lambda *args, **kwargs: Response(valid)
    )
    value, error = fallback._reader_extract(
        "https://www.vicioussyndicate.com/report/", min_chars=20, max_chars=1000
    )
    assert error is None
    assert value["title"] == "Report"

    value, error = fallback._reader_extract(
        "https://private.test/report/", min_chars=20, max_chars=1000
    )
    assert value is None
    assert "not allowed" in error

    challenged = (
        "Title: Just a moment...\n\n"
        "URL Source: https://www.vicioussyndicate.com/report/\n\n"
        "Markdown Content:\nPerforming security verification"
    )
    monkeypatch.setattr(
        fallback.requests, "get", lambda *args, **kwargs: Response(challenged)
    )
    value, error = fallback._reader_extract(
        "https://www.vicioussyndicate.com/report/", min_chars=1, max_chars=1000
    )
    assert value is None
    assert "challenge-protected" in error


def test_extract_uses_reader_only_after_browser_failure(monkeypatch):
    import tools.web_browser_fallback as fallback

    config = _enabled_config(
        min_content_chars=10,
        reader_enabled=True,
        reader_allowed_hosts=["www.vicioussyndicate.com"],
    )
    monkeypatch.setattr(fallback, "_fallback_config", lambda: config)
    monkeypatch.setattr(fallback, "browser_backend_ready", lambda: True)
    monkeypatch.setattr(fallback, "_safe_public_url", lambda url: True)
    monkeypatch.setattr(
        fallback, "_browser_dom", lambda *args, **kwargs: (None, "challenge")
    )
    monkeypatch.setattr(
        fallback,
        "_reader_extract",
        lambda *args, **kwargs: (
            {
                "url": "https://www.vicioussyndicate.com/report/",
                "title": "Report",
                "content": "reader recovered report",
            },
            None,
        ),
    )
    result = fallback.maybe_extract_with_browser(
        [
            {
                "url": "https://www.vicioussyndicate.com/report/",
                "content": "",
                "error": "HTTP 403",
            }
        ],
        ["https://www.vicioussyndicate.com/report/"],
    )
    assert result[0]["retrieval"] == "reader-fallback"
    assert result[0]["content"] == "reader recovered report"


def test_extract_uses_reader_when_browser_is_not_ready(monkeypatch):
    import tools.web_browser_fallback as fallback

    config = _enabled_config(
        min_content_chars=10,
        reader_enabled=True,
        reader_allowed_hosts=["www.vicioussyndicate.com"],
    )
    monkeypatch.setattr(fallback, "_fallback_config", lambda: config)
    monkeypatch.setattr(fallback, "browser_backend_ready", lambda: False)
    monkeypatch.setattr(fallback, "_safe_public_url", lambda url: True)
    monkeypatch.setattr(
        fallback,
        "_reader_extract",
        lambda *args, **kwargs: (
            {
                "url": "https://www.vicioussyndicate.com/report/",
                "title": "Report",
                "content": "reader recovered without local browser",
            },
            None,
        ),
    )
    result = fallback.maybe_extract_with_browser(
        [{"url": "https://www.vicioussyndicate.com/report/", "content": "", "error": "HTTP 403"}],
        ["https://www.vicioussyndicate.com/report/"],
    )
    assert result[0]["retrieval"] == "reader-fallback"


def test_browser_dom_always_cleans_up_and_rechecks_redirect(monkeypatch):
    import tools.browser_tool as browser
    import tools.web_browser_fallback as fallback

    cleaned = []
    calls = {"safe": 0}
    monkeypatch.setattr(
        fallback, "_fallback_config", lambda: _enabled_config(settle_seconds=0)
    )

    def safe_url(url):
        calls["safe"] += 1
        return "internal" not in url

    monkeypatch.setattr(fallback, "_safe_public_url", safe_url)
    monkeypatch.setattr(
        browser,
        "browser_navigate",
        lambda url, task_id=None: json.dumps(
            {"success": True, "url": "http://internal.test/", "title": "Oops"}
        ),
    )
    monkeypatch.setattr(browser, "cleanup_browser", cleaned.append)

    value, error = fallback._browser_dom(
        "https://public.test/",
        expression="fixed-expression",
        min_chars=1,
        task_prefix="test",
    )
    assert value is None
    assert "public Internet boundary" in error
    assert calls["safe"] >= 2
    assert len(cleaned) == 1


def test_browser_search_runs_only_after_primary_failure(monkeypatch):
    import tools.web_browser_fallback as fallback

    monkeypatch.setattr(fallback, "_fallback_config", lambda: _enabled_config())
    monkeypatch.setattr(fallback, "browser_backend_ready", lambda: True)
    monkeypatch.setattr(fallback, "_safe_public_url", lambda url: True)

    primary = {
        "success": True,
        "data": {
            "web": [
                {
                    "title": "Existing",
                    "url": "https://existing.test/",
                    "description": "already works",
                    "position": 1,
                }
            ]
        },
    }
    monkeypatch.setattr(
        fallback,
        "_browser_dom",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("browser fallback should not run")
        ),
    )
    assert fallback.maybe_search_with_browser(primary, "query", 5) is primary

    rate_limited = {"success": False, "error": "HTTP 429: rate limited"}
    assert (
        fallback.maybe_search_with_browser(rate_limited, "query", 5)
        is rate_limited
    )


def test_hsguru_failed_site_query_retries_public_index_only(monkeypatch):
    import ddgs
    import tools.web_browser_fallback as fallback

    calls = []

    class Client:
        def __init__(self, timeout):
            assert timeout == 10

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def text(self, query, backend, max_results):
            calls.append((query, backend, max_results))
            if query.endswith(" meta"):
                return []
            return [
                {"title": "Meta", "href": "https://www.hsguru.com/meta"},
                {"title": "Noise", "href": "https://example.com/"},
            ]

    monkeypatch.setattr(fallback, "_fallback_config", lambda: _enabled_config())
    monkeypatch.setattr(ddgs, "DDGS", Client)
    monkeypatch.setattr(
        fallback,
        "browser_backend_ready",
        lambda: (_ for _ in ()).throw(AssertionError("browser should not run")),
    )

    failed = {"success": False, "error": "No results found"}
    result = fallback.maybe_search_with_browser(
        failed, "site:hsguru.com/meta Hearthstone tier list", 3
    )
    assert calls == [
        ("site:hsguru.com HSGuru meta", "yahoo", 3),
        ("site:hsguru.com HSGuru", "yahoo", 3),
    ]
    assert result["retrieval"] == "public-index-retry"
    assert [hit["url"] for hit in result["data"]["web"]] == [
        "https://www.hsguru.com/meta"
    ]


def test_hsguru_index_retry_does_not_expand_non_site_or_rate_limited_queries(
    monkeypatch,
):
    import ddgs
    import tools.web_browser_fallback as fallback

    monkeypatch.setattr(fallback, "_fallback_config", lambda: _enabled_config())
    monkeypatch.setattr(
        ddgs,
        "DDGS",
        lambda: (_ for _ in ()).throw(AssertionError("index retry should not run")),
    )
    monkeypatch.setattr(fallback, "browser_backend_ready", lambda: False)

    failed = {"success": False, "error": "No results found"}
    assert fallback.maybe_search_with_browser(failed, "Hearthstone GitHub API", 3) is failed

    limited = {"success": False, "error": "HTTP 429 rate limited"}
    assert (
        fallback.maybe_search_with_browser(
            limited, "site:hsguru.com HSGuru decks", 3
        )
        is limited
    )


def test_hsguru_named_query_retries_when_primary_has_no_hsguru_hit(monkeypatch):
    import tools.web_browser_fallback as fallback

    monkeypatch.setattr(fallback, "_fallback_config", lambda: _enabled_config())
    primary = {
        "success": True,
        "data": {"web": [{"title": "Other", "url": "https://example.com/"}]},
    }
    retried = {
        "success": True,
        "data": {"web": [{"title": "Meta", "url": "https://www.hsguru.com/meta"}]},
        "retrieval": "public-index-retry",
    }
    monkeypatch.setattr(
        fallback, "_retry_hsguru_public_index", lambda *args, **kwargs: retried
    )
    monkeypatch.setattr(
        fallback,
        "browser_backend_ready",
        lambda: (_ for _ in ()).throw(AssertionError("browser should not run")),
    )
    result = fallback.maybe_search_with_browser(
        primary, "HSGuru current Hearthstone meta", 3
    )
    assert result is retried


def test_browser_search_filters_engine_and_private_links(monkeypatch):
    import tools.web_browser_fallback as fallback

    monkeypatch.setattr(fallback, "_fallback_config", lambda: _enabled_config())
    monkeypatch.setattr(fallback, "browser_backend_ready", lambda: True)
    monkeypatch.setattr(
        fallback,
        "_safe_public_url",
        lambda url: "127.0.0.1" not in url,
    )
    monkeypatch.setattr(
        fallback,
        "_browser_dom",
        lambda url, **kwargs: (
            {
                "url": url,
                "title": "Search",
                "content": "Search results",
                "items": [
                    {
                        "title": "Navigation",
                        "url": "https://www.google.com/preferences",
                    },
                    {
                        "title": "Google help",
                        "url": "https://support.google.com/websearch/answer/86640",
                    },
                    {
                        "title": "Result A",
                        "url": "https://www.google.com/url?q=https%3A%2F%2Fa.test%2F",
                        "description": "Result A summary",
                    },
                    {
                        "title": "Internal",
                        "url": "http://127.0.0.1/admin",
                        "description": "no",
                    },
                    {
                        "title": "Result B",
                        "url": "https://b.test/",
                        "description": "Result B details",
                    },
                ],
            },
            None,
        ),
    )

    result = fallback.maybe_search_with_browser(
        {"success": False, "error": "DDGS blocked"}, "test query", 2
    )
    assert result["success"] is True
    assert result["retrieval"] == "browser-fallback"
    assert [row["url"] for row in result["data"]["web"]] == [
        "https://a.test/",
        "https://b.test/",
    ]


def test_web_tool_dispatches_internal_fallback_without_browser_tool_registration(
    monkeypatch,
):
    import agent.web_search_registry as registry
    import tools.web_browser_fallback as fallback
    import tools.web_tools as web_tools

    class Provider:
        name = "fake-search"
        display_name = "Fake search"

        def supports_search(self):
            return True

        def search(self, query, limit):
            return {"success": False, "error": "blocked"}

    monkeypatch.setattr(web_tools, "_ensure_web_plugins_loaded", lambda: None)
    monkeypatch.setattr(web_tools, "_get_search_backend", lambda: "fake-search")
    monkeypatch.setattr(registry, "get_provider", lambda name: Provider())
    monkeypatch.setattr(
        fallback,
        "maybe_search_with_browser",
        lambda primary, query, limit: {
            "success": True,
            "data": {"web": [{"title": "Recovered", "url": "https://a.test/"}]},
            "retrieval": "browser-fallback",
        },
    )

    result = json.loads(web_tools.web_search_tool("query", 1))
    assert result["success"] is True
    assert result["retrieval"] == "browser-fallback"


def test_web_extract_dispatches_internal_browser_fallback(monkeypatch):
    import tools.web_browser_fallback as fallback
    import tools.web_tools as web_tools

    class Provider:
        name = "fake-extract"
        display_name = "Fake extract"

        def supports_extract(self):
            return True

        def extract(self, urls, **kwargs):
            return [{"url": urls[0], "content": "", "error": "HTTP 403"}]

    monkeypatch.setattr(
        fallback,
        "maybe_extract_with_browser",
        lambda results, urls: [
            {
                "url": urls[0],
                "title": "Recovered",
                "content": "browser-rendered content",
                "retrieval": "browser-fallback",
            }
        ],
    )

    result = web_tools._sync_extract_with_browser_fallback(
        Provider(), ["https://blocked.test/"], format="markdown"
    )
    assert result[0]["title"] == "Recovered"
    assert result[0]["content"] == "browser-rendered content"


def test_zendesk_article_api_url_is_exact_host_and_article_path_only():
    import tools.web_browser_fallback as fallback

    config = _enabled_config(zendesk_article_api_hosts=["support.discord.com"])
    mapped = fallback._zendesk_article_api_url(
        "https://support.discord.com/hc/en-us/articles/115000084051-Age-Restricted"
        "?utm_source=x#top",
        config,
    )
    assert mapped == (
        "https://support.discord.com/api/v2/help_center/en-us/articles/115000084051.json",
        "115000084051",
    )
    assert fallback._zendesk_article_api_url(
        "https://support.discord.com/hc/articles/42", config
    ) == ("https://support.discord.com/api/v2/help_center/articles/42.json", "42")

    for url in (
        "http://support.discord.com/hc/en-us/articles/42",
        "https://support.discord.com.evil.test/hc/en-us/articles/42",
        "https://evil.test/hc/en-us/articles/42",
        "https://user:pass@support.discord.com/hc/en-us/articles/42",
        "https://support.discord.com:8443/hc/en-us/articles/42",
        "https://support.discord.com/hc/en-us/sections/42",
        "https://support.discord.com/hc/en-us/articles/42/comments",
        "https://support.discord.com/api/v2/help_center/en-us/articles/42.json",
    ):
        assert fallback._zendesk_article_api_url(url, config) is None, url
    assert fallback._zendesk_article_api_url(
        "https://support.discord.com/hc/en-us/articles/42", _enabled_config()
    ) is None


def test_zendesk_article_extract_validates_api_response(monkeypatch):
    import tools.web_browser_fallback as fallback
    from plugins.web.simple_http import provider

    config = _enabled_config(zendesk_article_api_hosts=["support.discord.com"])
    monkeypatch.setattr(fallback, "_fallback_config", lambda: config)
    monkeypatch.setattr(fallback, "_safe_public_url", lambda url: True)
    page = "https://support.discord.com/hc/en-us/articles/42-Policy"
    api = "https://support.discord.com/api/v2/help_center/en-us/articles/42.json"

    def article(**overrides):
        value = {
            "id": 42,
            "title": "Policy",
            "html_url": page,
            "draft": False,
            "updated_at": "2026-10-11T19:42:21Z",
            "body": "<h2>Rules</h2><p>Mark channels as <b>age-restricted</b>.</p>"
            "<script>alert(1)</script>",
        }
        value.update(overrides)
        return value

    def serve(payload, final_url=api, content_type="application/json"):
        body = json.dumps({"article": payload}).encode()
        monkeypatch.setattr(
            provider,
            "_fetch",
            lambda url: (final_url, content_type, body, "utf-8"),
        )

    serve(article())
    value, error = fallback._zendesk_article_extract(page, min_chars=10, max_chars=5000)
    assert error is None
    assert value["url"] == page
    assert value["title"] == "Policy"
    assert value["content"].startswith("# Policy\n\nLast updated: 2026-10-11T19:42:21Z")
    assert "age-restricted" in value["content"]
    assert "<b>" not in value["content"] and "alert(1)" not in value["content"]

    rejected = (
        (article(id=43), {}, "different article"),
        (article(draft=True), {}, "draft"),
        (article(html_url="https://evil.test/hc/en-us/articles/42"), {}, "unexpected article URL"),
        (article(body="<p></p>"), {}, "empty or challenge"),
        (article(), {"final_url": "https://evil.test/a.json"}, "crossed the allowed host"),
        (article(), {"content_type": "text/html"}, "unsupported content type"),
    )
    for payload, kwargs, expected in rejected:
        serve(payload, **kwargs)
        value, error = fallback._zendesk_article_extract(page, min_chars=10, max_chars=5000)
        assert value is None and expected in error, (expected, error)

    def fail(url):
        raise ValueError("HTTP 403")

    monkeypatch.setattr(provider, "_fetch", fail)
    value, error = fallback._zendesk_article_extract(page, min_chars=10, max_chars=5000)
    assert value is None and "HTTP 403" in error

    value, error = fallback._zendesk_article_extract(
        "https://other.test/hc/en-us/articles/42", min_chars=10, max_chars=5000
    )
    assert value is None and "not an allowlisted" in error


def test_extract_prefers_help_center_api_before_browser(monkeypatch):
    import tools.web_browser_fallback as fallback

    page = "https://support.discord.com/hc/en-us/articles/42-Policy"
    monkeypatch.setattr(
        fallback, "_fallback_config", lambda: _enabled_config(min_content_chars=10)
    )
    monkeypatch.setattr(fallback, "browser_backend_ready", lambda: True)
    monkeypatch.setattr(fallback, "_safe_public_url", lambda url: True)
    monkeypatch.setattr(
        fallback,
        "_zendesk_article_extract",
        lambda *args, **kwargs: (
            {"url": page, "title": "Policy", "content": "article from api"},
            None,
        ),
    )

    def no_browser(*args, **kwargs):
        raise AssertionError("browser must not start after an API recovery")

    monkeypatch.setattr(fallback, "_browser_dom", no_browser)
    result = fallback.maybe_extract_with_browser(
        [{"url": page, "content": "", "error": "HTTP 403"}], [page]
    )
    assert result[0]["retrieval"] == "help-center-api"
    assert result[0]["content"] == "article from api"


def test_extract_uses_browser_when_help_center_api_fails(monkeypatch):
    import tools.web_browser_fallback as fallback

    page = "https://support.discord.com/hc/en-us/articles/42-Policy"
    monkeypatch.setattr(
        fallback, "_fallback_config", lambda: _enabled_config(min_content_chars=10)
    )
    monkeypatch.setattr(fallback, "browser_backend_ready", lambda: True)
    monkeypatch.setattr(fallback, "_safe_public_url", lambda url: True)
    monkeypatch.setattr(
        fallback,
        "_zendesk_article_extract",
        lambda *args, **kwargs: (None, "Help Center API request failed: HTTP 403"),
    )
    monkeypatch.setattr(
        fallback,
        "_browser_dom",
        lambda *args, **kwargs: (
            {"url": page, "title": "Policy", "content": "article from browser"},
            None,
        ),
    )
    result = fallback.maybe_extract_with_browser(
        [{"url": page, "content": "", "error": "HTTP 403"}], [page]
    )
    assert result[0]["retrieval"] == "browser-fallback"
