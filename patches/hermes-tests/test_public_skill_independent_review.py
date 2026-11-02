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
    import agent.background_review as background
    import tools.public_skill_review as review

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
        background,
        "_resolve_review_runtime",
        lambda _agent: {
            "provider": "openai", "model": "test-model", "api_mode": None,
            "base_url": "", "api_key": "",
        },
    )
    decision = review.independent_public_skill_review(_Parent(), _skill(tmp_path), "safe")
    assert decision.approved is True
    assert captured["enabled_toolsets"] == []
    assert captured["disabled_toolsets"] == ["all"]
    assert captured["skip_memory"] is True
    assert captured["skip_context_files"] is True
    assert captured["run"]["conversation_history"] == []


def test_independent_review_rejects_malformed_error_and_timeout(tmp_path, monkeypatch):
    import agent.background_review as background
    import tools.public_skill_review as review

    class MalformedReviewer:
        def __init__(self, **_kwargs):
            pass

        def run_conversation(self, **_kwargs):
            return {"final_response": 'approved {"decision":"approve","reason":"safe"}'}

        def close(self):
            pass

    monkeypatch.setitem(sys.modules, "run_agent", SimpleNamespace(AIAgent=MalformedReviewer))
    monkeypatch.setattr(
        background,
        "_resolve_review_runtime",
        lambda _agent: {
            "provider": "openai", "model": "test-model", "api_mode": None,
            "base_url": "", "api_key": "",
        },
    )
    malformed = review.independent_public_skill_review(
        _Parent(), _skill(tmp_path), "safe"
    )
    assert malformed.approved is False
    assert "malformed" in malformed.reason

    class ErrorReviewer(MalformedReviewer):
        def run_conversation(self, **_kwargs):
            raise RuntimeError("review unavailable")

    monkeypatch.setitem(sys.modules, "run_agent", SimpleNamespace(AIAgent=ErrorReviewer))
    failed = review.independent_public_skill_review(_Parent(), _skill(tmp_path), "safe")
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
    timed_out = review.independent_public_skill_review(_Parent(), _skill(tmp_path), "safe")
    assert timed_out.approved is False
    assert "timed out" in timed_out.reason


def test_review_thread_keeps_the_discord_identity_after_the_turn_ends():
    """run_agent starts the fork through propagate_context_to_thread; the gate needs this identity."""
    import threading

    from gateway.session_context import clear_session_vars, get_session_env, set_session_vars
    from tools.thread_context import propagate_context_to_thread

    captured = {}

    def read_identity():
        captured.update(
            platform=get_session_env("HERMES_SESSION_PLATFORM"),
            chat_id=get_session_env("HERMES_SESSION_CHAT_ID"),
            user_id=get_session_env("HERMES_SESSION_USER_ID"),
            session_key=get_session_env("HERMES_SESSION_KEY"),
        )

    tokens = set_session_vars(
        platform="discord", chat_id="222", user_id="333", session_key="agent:main:discord:group:222:guild-111",
    )
    try:
        target = propagate_context_to_thread(read_identity)
    finally:
        clear_session_vars(tokens)
    worker = threading.Thread(target=target)
    worker.start()
    worker.join()

    assert captured == {
        "platform": "discord",
        "chat_id": "222",
        "user_id": "333",
        "session_key": "agent:main:discord:group:222:guild-111",
    }


def test_public_review_fork_only_keeps_reviewed_skill_tools(monkeypatch):
    import tools.public_skill_policy as policy
    from tools.public_skill_review import public_review_scope

    monkeypatch.setattr(policy, "is_public_discord_context", lambda: True)
    whitelist, reset = public_review_scope(
        _Parent(), {"skills_list", "skill_view", "skill_manage", "read_file", "search_files", "memory"},
    )
    assert policy._REVIEW_CALLBACK.get() is not None
    reset()
    assert policy._REVIEW_CALLBACK.get() is None
    assert whitelist == {"skills_list", "skill_view", "skill_manage", "chatbird_memory"}


def test_private_review_fork_keeps_its_whitelist(monkeypatch):
    import tools.public_skill_policy as policy
    from tools.public_skill_review import public_review_scope

    monkeypatch.setattr(policy, "is_public_discord_context", lambda: False)
    whitelist, reset = public_review_scope(_Parent(), {"skill_manage", "read_file"})
    reset()
    assert whitelist == {"skill_manage", "read_file"}
