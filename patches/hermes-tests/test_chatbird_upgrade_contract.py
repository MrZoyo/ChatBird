"""What chatbird-policy and production rely on in Hermes itself.

Each test exercises real Hermes code, so a future upgrade that moves one of these
breaks here rather than silently opening or closing a gate in production.
Set CHATBIRD_PLUGIN_DIR to the plugin; it defaults to the installed copy.
"""

import contextvars
import json
import os
import shutil
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest

PLUGIN_DIR = Path(
    os.environ.get("CHATBIRD_PLUGIN_DIR") or Path.home() / ".hermes" / "plugins" / "chatbird-policy"
)
REPO = Path(__file__).resolve().parents[2]
GUILD, ADMIN_CHANNEL, ADMIN_USER = "1146359014968537089", "1154706638901612625", "518184812381732865"
PUBLIC_KEY = f"agent:main:discord:group:555:guild-{GUILD}"


@pytest.fixture
def home(tmp_path, monkeypatch):
    if not (PLUGIN_DIR / "__init__.py").exists():
        pytest.skip("chatbird-policy plugin not found; set CHATBIRD_PLUGIN_DIR")
    root = tmp_path / ".hermes"
    (root / "plugins").mkdir(parents=True)
    shutil.copytree(PLUGIN_DIR, root / "plugins" / "chatbird-policy", ignore=shutil.ignore_patterns("__pycache__"))
    (root / "config.yaml").write_text(
        textwrap.dedent(
            """\
            gateway:
              strict: true
              trust_recent_files: false
            memory:
              memory_enabled: true
              user_profile_enabled: false
            tools:
              tool_search:
                enabled: "off"
            security:
              allow_lazy_installs: false
            plugins:
              enabled:
                - chatbird-policy
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(root))
    monkeypatch.setenv("_HERMES_GATEWAY", "1")
    monkeypatch.setenv("CHATBIRD_ADMIN_USERS", ADMIN_USER)
    monkeypatch.setenv("CHATBIRD_ADMIN_CHANNELS", f"{GUILD}:{ADMIN_CHANNEL}")
    return root


@pytest.fixture
def manager(home, monkeypatch):
    from hermes_cli import plugins

    instance = plugins.PluginManager()
    monkeypatch.setattr(plugins, "_plugin_manager", instance)
    instance.discover_and_load()
    loaded = instance._plugins["chatbird-policy"]
    assert loaded.enabled and not loaded.error, loaded.error
    return instance


def _bind(platform="discord", user="42", chat="555", key=PUBLIC_KEY):
    from gateway.session_context import set_session_vars

    return set_session_vars(platform=platform, user_id=user, chat_id=chat, session_key=key)


def _gate(tool, session_id=""):
    from hermes_cli.plugins import _dispatch_pre_tool_call_hooks

    return _dispatch_pre_tool_call_hooks(tool, {}, session_id=session_id)[0]


# ── Plugin loading and hook payloads ─────────────────────────────────


def test_plugin_registers_its_tools_and_hooks_through_real_discovery(manager):
    from tools.registry import registry

    names = set(registry.get_all_tool_names())
    assert {"chatbird_memory", "chatbird_channel_history", "chatbird_run_code"} <= names
    assert manager._hooks["pre_tool_call"] and manager._hooks["pre_llm_call"]


def test_discord_tools_stay_directly_callable(manager, monkeypatch):
    """A tool_search bridge would hide plugin tools behind a name the public allowlist denies."""
    from hermes_cli.config import load_config
    from hermes_cli.tools_config import _get_platform_tools
    from model_tools import get_tool_definitions

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-usr-test")
    toolsets = _get_platform_tools(load_config(), "discord")
    names = {
        tool["function"]["name"]
        for tool in get_tool_definitions(enabled_toolsets=sorted(toolsets), quiet_mode=True)
    }

    assert {"chatbird_memory", "chatbird_channel_history", "chatbird_run_code", "web_search"} <= names
    assert not names & {"tool_search", "tool_call", "tool_describe"}


def test_public_turn_is_gated_on_a_real_hook_worker(manager):
    from gateway.session_context import clear_session_vars

    tokens = _bind()
    try:
        assert _gate("web_search") is None
        assert "public-channel policy" in _gate("terminal")
        assert "public-channel policy" in _gate("tool_call")
        assert "session_search" in _gate("session_search")
    finally:
        clear_session_vars(tokens)


def test_admin_turn_keeps_tools_but_never_session_search(manager):
    from gateway.session_context import clear_session_vars

    tokens = _bind(user=ADMIN_USER, chat=ADMIN_CHANNEL, key=f"agent:main:discord:group:{ADMIN_CHANNEL}:guild-{GUILD}")
    try:
        assert _gate("terminal") is None
        assert "session_search" in _gate("session_search")
    finally:
        clear_session_vars(tokens)


def test_lost_identity_is_denied_inside_the_gateway(manager):
    outcome = {}
    worker = threading.Thread(target=lambda: outcome.update(block=_gate("terminal")))
    worker.start()
    worker.join()

    assert "no verified identity" in outcome["block"]


def test_delegate_batch_child_context_keeps_the_public_identity(manager):
    """delegate_task submits children through copy_context().run, so they keep the turn's identity."""
    from gateway.session_context import clear_session_vars

    tokens = _bind()
    try:
        context = contextvars.copy_context()
    finally:
        clear_session_vars(tokens)
    outcome = {}
    worker = threading.Thread(target=lambda: context.run(lambda: outcome.update(block=_gate("terminal"))))
    worker.start()
    worker.join()

    assert "public-channel policy" in outcome["block"]


def test_cron_scope_binds_empty_platform_and_passes_the_gate(manager, tmp_path):
    from cron.scheduler import _CronRunScope

    scope = _CronRunScope({"id": "job1", "name": "job"}, "job1", "exec1")
    scope.enter()
    try:
        from gateway.session_context import get_session_env

        assert get_session_env("HERMES_SESSION_PLATFORM") == ""
        assert get_session_env("HERMES_CRON_SESSION") == "1"
        assert _gate("terminal", session_id="cron_job1_20261102_100000") is None
        assert _gate("terminal", session_id="20261102_100000_abcd") is None
        assert "session_search" in _gate("session_search", session_id="cron_job1_20261102_100000")
    finally:
        scope.exit()


def test_pre_llm_call_returns_policy_and_keeps_the_user_message(manager):
    from gateway.session_context import clear_session_vars
    from hermes_cli.lifecycle import invoke_hook
    from tools.registry import registry

    tokens = _bind()
    try:
        results = invoke_hook(
            "pre_llm_call", session_id="s", task_id="t", turn_id="u", user_message="请记住我喜欢红色",
            conversation_history=[], is_first_turn=True, model="m", platform="discord",
            parent_session_id="", sender_id="42",
        )
        assert any("Trusted ChatBird access policy" in r.get("context", "") for r in results)
        denied = json.loads(
            registry.dispatch("chatbird_memory", {"action": "profile_add", "content": "喜欢红色"})
        )
        assert denied["success"] is False
        assert "directly command" in denied["error"]
    finally:
        clear_session_vars(tokens)


def test_session_identity_carries_the_guild_suffix_the_plugin_parses(manager):
    from gateway.config import Platform
    from gateway.session import SessionSource, build_session_key

    key = build_session_key(
        SessionSource(platform=Platform.DISCORD, chat_id="555", chat_type="group", user_id="42", guild_id=GUILD),
        group_sessions_per_user=False,
    )

    assert key == PUBLIC_KEY


# ── Production config reaches the code that reads it ─────────────────


def test_production_config_reaches_the_discord_gates(tmp_path):
    mirror = PLUGIN_DIR.parents[1] / "patches" / "chatbird-production-config.yaml"
    if not mirror.exists():
        pytest.skip("production config mirror not found")
    root = tmp_path / ".hermes"
    root.mkdir()
    shutil.copy(mirror, root / "config.yaml")
    result = _run_in_gateway(
        root,
        """
        import json
        from gateway.config import Platform, load_gateway_config
        from gateway.display_config import resolve_tool_progress
        from hermes_cli.config import load_config
        from plugins.platforms.discord.adapter import DiscordAdapter
        from tools import browser_tool
        from tools.hook_output_spill import get_spill_config
        from tools.web_tools_rescue import _keyless_rescue_enabled
        from tools.tool_search import ToolSearchConfig
        config = load_gateway_config()
        platform = config.platforms[Platform.DISCORD]
        platform.token = "fake"
        adapter = DiscordAdapter(platform)
        user = load_config()
        print(json.dumps({
            "guilds": sorted(adapter._discord_allowed_guilds()),
            "channels": len(adapter._get_allowed_channels()),
            "mention": adapter._discord_require_mention(),
            "thread_mention": adapter._discord_thread_require_mention(),
            "backfill": [adapter._discord_history_backfill(), adapter._discord_history_backfill_limit()],
            "slash": adapter._slash_commands,
            "per_user": config.group_sessions_per_user,
            "progress": resolve_tool_progress(user, "discord")[0],
            "spill": get_spill_config()["enabled"],
            "rescue": _keyless_rescue_enabled(),
            "tool_search": ToolSearchConfig.from_raw((user.get("tools") or {}).get("tool_search")).enabled,
            "fallback": user.get("fallback_model"),
            "lazy": (user.get("security") or {}).get("allow_lazy_installs"),
            "browser_cli": browser_tool._is_browser_use_cli_mode(),
        }))
        """,
        DISCORD_BOT_TOKEN="fake",
    )

    assert result["guilds"] == ["1146359014968537089", "921407984586866778"]
    assert result["channels"] >= 2
    assert result["mention"] is True and result["thread_mention"] is True
    assert result["backfill"] == [True, 200]
    assert result["slash"] is True
    assert result["per_user"] is False
    assert result["progress"] == "off"
    assert result["spill"] is False
    assert result["rescue"] is False
    assert result["tool_search"] == "off"
    assert result["fallback"] == {"provider": "xiaomi", "model": "mimo-v2.6-flash"}
    assert result["lazy"] is False
    # The Browser Use default turns off the agent-browser path the restricted fallback needs.
    assert result["browser_cli"] is False


# ── Process marker and file delivery ─────────────────────────────────


def _run_in_gateway(home, code, **env):
    script = textwrap.dedent(code)
    environment = {**os.environ, "HERMES_HOME": str(home), "PYTHONPATH": str(REPO), **env}
    environment.pop("_HERMES_GATEWAY", None)
    environment.pop("HERMES_MEDIA_DELIVERY_STRICT", None)
    environment.pop("HERMES_MEDIA_TRUST_RECENT_FILES", None)
    done = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, cwd=REPO, env=environment, timeout=180,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


DELIVERY_PROBE = """
    import json, os, sys
    from pathlib import Path
    import gateway.run as run
    from gateway.platforms.base import (
        BasePlatformAdapter, cache_document_from_bytes, validate_media_delivery_path as check)
    home = Path(os.environ["HERMES_HOME"])
    paths = {
        "session": home / "sessions" / "session_1.json",
        "state": home / "state.db",
        "guild_memory": home / "memories" / "scopes" / "discord-guild-1" / "MEMORY.md",
        "profile": home / "memories" / "chatbird" / "profiles" / "discord-guild-1" / "2.md",
        "soul": home / "SOUL.md",
        "env": home / ".env",
        "config": home / "config.yaml",
        "cached": home / "cache" / "documents" / "doc_1.png",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("x")
    def report():
        return {name: bool(check(str(path))) for name, path in paths.items()}
    def bridged():
        return [os.environ.get("HERMES_MEDIA_DELIVERY_STRICT"), os.environ.get("HERMES_MEDIA_TRUST_RECENT_FILES")]
    at_startup, first = bridged(), report()
    run._reload_runtime_env_preserving_config_authority()
    generated = cache_document_from_bytes(b"png", "chart.png")
    print(json.dumps({
        "marker": os.environ.get("_HERMES_GATEWAY"),
        "at_startup": at_startup, "after_reload": bridged(),
        "first": first, "reloaded": report(),
        "auto_append": sorted(run._AUTO_APPEND_MEDIA_TOOL_NAMES),
        "generated": bool(check(generated)),
        "extracted": BasePlatformAdapter.extract_media(f"Here it is.\\nMEDIA:{generated}")[0][0][0] == generated,
    }))
"""


def test_gateway_import_sets_the_marker_and_strict_delivery(home):
    # HERMES_HOME under $HOME, as on production: a root-run gateway exempts its own home
    # from the denylist, so the strict branch is what keeps these files in.
    result = _run_in_gateway(home, DELIVERY_PROBE, HOME=str(home.parent))

    assert result["marker"] == "1"
    assert result["at_startup"] == ["1", "0"]
    assert result["after_reload"] == ["1", "0"]
    for view in (result["first"], result["reloaded"]):
        assert view.pop("cached") is True
        assert not any(view.values()), view
    assert "chatbird_run_code" not in result["auto_append"]
    assert result["generated"] is True
    assert result["extracted"] is True


def test_env_file_can_silently_disable_strict_delivery(home):
    """Why production's .env must carry no HERMES_MEDIA_* line and the validator enforces it."""
    (home / ".env").write_text("HERMES_MEDIA_DELIVERY_STRICT=0\n", encoding="utf-8")

    result = _run_in_gateway(home, DELIVERY_PROBE, HOME=str(home.parent))

    assert result["at_startup"][0] == "0"
    assert result["first"]["soul"] is True
    assert result["first"]["guild_memory"] is True
    assert result["first"]["profile"] is True


def test_run_code_media_line_does_not_auto_upload():
    from gateway.run import _collect_auto_append_media_tags

    messages = [
        {"role": "assistant", "tool_calls": [{"id": "1", "function": {"name": "chatbird_run_code", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "1", "content": "MEDIA:/root/.hermes/.env"},
    ]

    tags = _collect_auto_append_media_tags(messages, 0, set())

    assert not any("MEDIA:" in str(tag) for tag in (tags[0] if isinstance(tags, tuple) else tags))


# ── Anthropic ────────────────────────────────────────────────────────


def test_sdk_files_api_matches_the_plugin():
    """chatbird_run_code uses client.beta.files; move it to client.files when the SDK pin moves."""
    import anthropic

    assert anthropic.__version__ == "0.87.0"
    files = anthropic.Anthropic(api_key="test").beta.files
    assert all(hasattr(files, name) for name in ("retrieve_metadata", "download", "delete"))


def test_user_scoped_key_is_an_api_key_not_oauth():
    from agent.anthropic_adapter import _is_oauth_token, build_anthropic_client

    assert _is_oauth_token("sk-ant-usr-abcdef") is False
    client = build_anthropic_client("sk-ant-usr-abcdef")
    assert client.api_key == "sk-ant-usr-abcdef"
    assert not client.auth_token


# ── Config ───────────────────────────────────────────────────────────


def test_fallback_model_is_still_read_as_the_chain(home):
    from hermes_cli.fallback_config import get_fallback_chain

    chain = get_fallback_chain({"fallback_model": {"provider": "xiaomi", "model": "mimo-v2.6-flash"}})

    assert [(entry["provider"], entry["model"]) for entry in chain] == [("xiaomi", "mimo-v2.6-flash")]


def test_keyless_web_tiers_stay_off_under_production_config(monkeypatch):
    import tools.web_tools as web_tools
    from tools.web_tools_rescue import _keyless_rescue_enabled

    monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"keyless_rescue": False, "keyless_fallback": False})

    assert _keyless_rescue_enabled() is False
