"""Real AIAgent and Anthropic SDK against a local server: key type, failover, run_code files."""

import importlib.util
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

PLUGIN_DIR = Path(
    os.environ.get("CHATBIRD_PLUGIN_DIR") or Path.home() / ".hermes" / "plugins" / "chatbird-policy"
)


class _Mock:
    """One local server playing both Anthropic and the OpenAI-compatible fallback."""

    def __init__(self):
        self.requests: list[dict] = []
        self.anthropic_error: dict | None = None
        self.deleted: list[str] = []
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def _reply(self, status, payload, content_type="application/json"):
                body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _record(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}") if length else {}
                mock.requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
                return body

            def do_POST(self):
                body = self._record()
                if self.path.endswith("/messages"):
                    if mock.anthropic_error:
                        return self._reply(mock.anthropic_error["status"], mock.anthropic_error["body"])
                    if body.get("stream"):
                        return self._stream_anthropic()
                    return self._reply(200, mock.anthropic_message(body))
                if self.path.endswith("/chat/completions"):
                    if body.get("stream"):
                        return self._stream_openai()
                    return self._reply(200, {
                        "id": "c1", "object": "chat.completion", "created": 1, "model": body.get("model"),
                        "choices": [{"index": 0, "finish_reason": "stop",
                                     "message": {"role": "assistant", "content": "FALLBACK_OK"}}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    })
                return self._reply(404, {"error": "unknown route"})

            def _sse(self, events):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for name, data in events:
                    prefix = f"event: {name}\n" if name else ""
                    self.wfile.write(f"{prefix}data: {json.dumps(data) if data != '[DONE]' else data}\n\n".encode())
                self.wfile.flush()
                self.close_connection = True

            def _stream_openai(self):
                chunk = {"id": "c1", "object": "chat.completion.chunk", "created": 1, "model": "m"}
                self._sse([
                    (None, {**chunk, "choices": [{"index": 0, "delta": {"role": "assistant", "content": "FALLBACK_OK"},
                                                  "finish_reason": None}]}),
                    (None, {**chunk, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}),
                    (None, "[DONE]"),
                ])

            def _stream_anthropic(self):
                self._sse([
                    ("message_start", {"type": "message_start", "message": {
                        "id": "m1", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5", "content": [],
                        "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}}}),
                    ("content_block_start", {"type": "content_block_start", "index": 0,
                                             "content_block": {"type": "text", "text": ""}}),
                    ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                             "delta": {"type": "text_delta", "text": "PRIMARY_OK"}}),
                    ("content_block_stop", {"type": "content_block_stop", "index": 0}),
                    ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                                       "usage": {"output_tokens": 1}}),
                    ("message_stop", {"type": "message_stop"}),
                ])

            def do_GET(self):
                self._record()
                if self.path.startswith("/v1/files/") and self.path.split("?")[0].endswith("/content"):
                    return self._reply(200, b"PNGDATA", "application/octet-stream")
                if self.path.startswith("/v1/files/"):
                    file_id = self.path.split("?")[0].rsplit("/", 1)[-1]
                    return self._reply(200, {
                        "id": file_id, "type": "file", "filename": "chart.png", "size_bytes": 7,
                        "mime_type": "image/png", "created_at": "2026-11-02T00:00:00Z",
                    })
                return self._reply(404, {"error": "unknown route"})

            def do_DELETE(self):
                self._record()
                mock.deleted.append(self.path.split("?")[0].rsplit("/", 1)[-1])
                return self._reply(200, {"id": mock.deleted[-1], "type": "file_deleted"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def anthropic_message(self, body):
        content = [{"type": "text", "text": "PRIMARY_OK"}]
        container = None
        if body.get("tools") and body["tools"][0].get("name") == "code_execution":
            container = {"id": "container_1", "expires_at": "2026-11-02T01:00:00Z"}
            content = [
                {"type": "server_tool_use", "id": "srv_1", "name": "code_execution", "input": {"code": "print(1)"}},
                {"type": "code_execution_tool_result", "tool_use_id": "srv_1", "content": {
                    "type": "code_execution_result", "stdout": "1\n", "stderr": "", "return_code": 0,
                    "content": [{"type": "code_execution_output", "file_id": "file_abc"}]}},
                {"type": "text", "text": "done"},
            ]
        return {
            "id": "m1", "type": "message", "role": "assistant", "model": body.get("model"), "content": content,
            "stop_reason": "end_turn", "stop_sequence": None, "container": container,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def mock():
    instance = _Mock()
    yield instance
    instance.close()


def _agent(mock, monkeypatch, tmp_path):
    from run_agent import AIAgent

    home = tmp_path / ".hermes"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("XIAOMI_API_KEY", "xiaomi-test")
    monkeypatch.setenv("XIAOMI_BASE_URL", f"{mock.url}/v1")
    return AIAgent(
        model="claude-sonnet-5-5", provider="anthropic", api_mode="anthropic_messages",
        base_url=mock.url, api_key="sk-ant-usr-testkey", quiet_mode=True, enabled_toolsets=[],
        skip_context_files=True, skip_memory=True, max_iterations=2,
        fallback_model={"provider": "xiaomi", "model": "mimo-v2.6-flash"},
    )


def test_user_scoped_key_authenticates_with_x_api_key(mock, monkeypatch, tmp_path):
    agent = _agent(mock, monkeypatch, tmp_path)

    result = agent.run_conversation("hello")

    assert result["final_response"] == "PRIMARY_OK"
    sent = next(r for r in mock.requests if r["path"].endswith("/messages"))
    headers = {key.lower(): value for key, value in sent["headers"].items()}
    assert headers["x-api-key"] == "sk-ant-usr-testkey"
    assert "authorization" not in headers
    assert "oauth" not in headers.get("anthropic-beta", "")
    agent.close()


@pytest.mark.parametrize(
    "status, error_type, message",
    [
        (400, "invalid_request_error", "You have reached your specified API usage limits."),
        (400, "invalid_request_error", "Your credit balance is too low to access the Anthropic API."),
        (403, "permission_error", "Your organization has hit its monthly spend limit."),
    ],
)
def test_exhausted_primary_fails_over_to_the_configured_fallback(mock, monkeypatch, tmp_path, status, error_type, message):
    mock.anthropic_error = {
        "status": status, "body": {"type": "error", "error": {"type": error_type, "message": message}},
    }
    agent = _agent(mock, monkeypatch, tmp_path)

    result = agent.run_conversation("hello")

    assert result["final_response"] == "FALLBACK_OK"
    assert agent.provider == "xiaomi"
    assert any(r["path"].endswith("/chat/completions") for r in mock.requests)
    agent.close()


def test_run_code_downloads_and_deletes_generated_files_with_the_real_sdk(mock, monkeypatch, tmp_path):
    if not (PLUGIN_DIR / "__init__.py").exists():
        pytest.skip("chatbird-policy plugin not found; set CHATBIRD_PLUGIN_DIR")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-usr-testkey")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", mock.url)
    spec = importlib.util.spec_from_file_location("chatbird_policy_under_test", PLUGIN_DIR / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    result = json.loads(module._handle_run_code({"task": "plot"}))

    assert result["success"] is True, result
    assert result["output"].startswith("1")
    assert len(result["files"]) == 1
    path = result["files"][0].removeprefix("MEDIA:")
    assert Path(path).read_bytes() == b"PNGDATA"
    assert Path(path).suffix == ".png"
    assert mock.deleted == ["file_abc"]

    from gateway.platforms.base import BasePlatformAdapter

    media, _ = BasePlatformAdapter.extract_media(f"Here is the chart.\n{result['files'][0]}")
    assert media == [(path, False)]
