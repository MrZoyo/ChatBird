from pathlib import Path
import sys
from types import SimpleNamespace


def _skill(tmp_path: Path) -> Path:
    path = tmp_path / "safe"
    path.mkdir(exist_ok=True)
    (path / "SKILL.md").write_text(
        "---\nname: safe\ndescription: Safe public research\n---\n\nUse web_search.\n",
        encoding="utf-8",
    )
    return path


class _Parent:
    provider = "openai"
    model = "test-model"
    _credential_pool = None


def test_independent_review_is_tool_free_and_accepts_exact_json(tmp_path, monkeypatch):
    import agent.background_review as review

    captured = {}

    class FakeReviewer:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_conversation(self, **kwargs):
            captured["run"] = kwargs
            return {"final_response": '{"decision":"approve","reason":"safe"}'}

        def close(self):
            pass

    monkeypatch.setitem(sys.modules, "run_agent", SimpleNamespace(AIAgent=FakeReviewer))
    monkeypatch.setattr(
        review,
        "_resolve_review_runtime",
        lambda _agent: {
            "provider": "openai", "model": "test-model", "api_mode": None,
            "base_url": "", "api_key": "",
        },
    )
    decision = review._independent_public_skill_review(_Parent(), _skill(tmp_path), "safe")
    assert decision.approved is True
    assert captured["enabled_toolsets"] == []
    assert captured["disabled_toolsets"] == ["all"]
    assert captured["skip_memory"] is True
    assert captured["skip_context_files"] is True
    assert captured["run"]["conversation_history"] == []


def test_independent_review_rejects_malformed_error_and_timeout(tmp_path, monkeypatch):
    import agent.background_review as review

    class MalformedReviewer:
        def __init__(self, **_kwargs):
            pass

        def run_conversation(self, **_kwargs):
            return {"final_response": 'approved {"decision":"approve","reason":"safe"}'}

        def close(self):
            pass

    monkeypatch.setitem(sys.modules, "run_agent", SimpleNamespace(AIAgent=MalformedReviewer))
    monkeypatch.setattr(
        review,
        "_resolve_review_runtime",
        lambda _agent: {
            "provider": "openai", "model": "test-model", "api_mode": None,
            "base_url": "", "api_key": "",
        },
    )
    malformed = review._independent_public_skill_review(
        _Parent(), _skill(tmp_path), "safe"
    )
    assert malformed.approved is False
    assert "malformed" in malformed.reason

    class ErrorReviewer(MalformedReviewer):
        def run_conversation(self, **_kwargs):
            raise RuntimeError("review unavailable")

    monkeypatch.setitem(sys.modules, "run_agent", SimpleNamespace(AIAgent=ErrorReviewer))
    failed = review._independent_public_skill_review(_Parent(), _skill(tmp_path), "safe")
    assert failed.approved is False
    assert "failed" in failed.reason

    class NeverFinishes:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

        def join(self, timeout):
            assert timeout == review._PUBLIC_SKILL_REVIEW_TIMEOUT_SECONDS

        def is_alive(self):
            return True

    monkeypatch.setattr(review.threading, "Thread", NeverFinishes)
    timed_out = review._independent_public_skill_review(_Parent(), _skill(tmp_path), "safe")
    assert timed_out.approved is False
    assert "timed out" in timed_out.reason


def test_background_target_rebinds_captured_discord_identity(monkeypatch):
    import agent.background_review as review
    from gateway.session_context import get_session_env

    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "discord")
    monkeypatch.setenv("HERMES_SESSION_CHAT_ID", "222")
    monkeypatch.setenv("HERMES_SESSION_USER_ID", "333")
    monkeypatch.setenv("HERMES_SESSION_KEY", "agent:main:discord:guild-111")
    captured = {}

    def run(*_args):
        captured["platform"] = get_session_env("HERMES_SESSION_PLATFORM")
        captured["chat_id"] = get_session_env("HERMES_SESSION_CHAT_ID")
        captured["user_id"] = get_session_env("HERMES_SESSION_USER_ID")
        captured["session_key"] = get_session_env("HERMES_SESSION_KEY")

    monkeypatch.setattr(review, "_run_review_in_thread", run)
    target, _ = review.spawn_background_review_thread(object(), [], review_skills=True)
    monkeypatch.delenv("HERMES_SESSION_PLATFORM")
    monkeypatch.delenv("HERMES_SESSION_CHAT_ID")
    monkeypatch.delenv("HERMES_SESSION_USER_ID")
    monkeypatch.delenv("HERMES_SESSION_KEY")
    target()
    assert captured == {
        "platform": "discord",
        "chat_id": "222",
        "user_id": "333",
        "session_key": "agent:main:discord:guild-111",
    }
