import asyncio
import json
import stat
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from plugins.platforms.discord.adapter import DiscordAdapter


def _adapter() -> DiscordAdapter:
    adapter = object.__new__(DiscordAdapter)
    adapter._allowed_user_ids = {"518184812381732865"}
    adapter._allowed_role_ids = set()
    return adapter


def _interaction(
    user_id: str,
    guild_id: str | None = "1146359014968537089",
    channel_id: str = "1146359015715110992",
):
    guild = SimpleNamespace(id=int(guild_id)) if guild_id is not None else None
    return SimpleNamespace(
        user=SimpleNamespace(id=int(user_id), roles=[]),
        guild=guild,
        guild_id=int(guild_id) if guild_id is not None else None,
        channel=SimpleNamespace(id=int(channel_id)),
        channel_id=int(channel_id),
    )


@pytest.fixture
def slash_adapter(monkeypatch):
    monkeypatch.setenv("DISCORD_ALLOW_ALL_USERS", "true")
    monkeypatch.setenv("DISCORD_AUTO_THREAD", "false")
    monkeypatch.setenv("DISCORD_HISTORY_BACKFILL", "false")
    monkeypatch.setenv(
        "DISCORD_ALLOWED_CHANNELS",
        "1146359015715110992,1154706638901612625,1220876330913234944",
    )
    monkeypatch.setenv("CHATBIRD_ADMIN_USERS", "518184812381732865")
    monkeypatch.setenv(
        "CHATBIRD_ADMIN_CHANNELS",
        "1146359014968537089:1154706638901612625,"
        "921407984586866778:1220876330913234944",
    )
    adapter = _adapter()
    adapter._discord_allowed_guilds = lambda: {
        "1146359014968537089",
        "921407984586866778",
    }
    return adapter


def test_discord_allow_all_users_overrides_existing_owner_allowlist(monkeypatch):
    monkeypatch.setenv("DISCORD_ALLOW_ALL_USERS", "true")

    assert _adapter()._is_allowed_user("999999999999999999") is True


def test_public_slash_command_is_available_to_guild_members(slash_adapter):
    allowed, reason = slash_adapter._evaluate_slash_authorization(
        _interaction("999999999999999999"), "/help",
    )

    assert allowed is True
    assert reason is None


def test_admin_slash_command_rejects_guild_members(slash_adapter):
    allowed, reason = slash_adapter._evaluate_slash_authorization(
        _interaction("999999999999999999"), "/restart",
    )

    assert allowed is False
    assert "administrators" in reason


def test_admin_slash_command_rejects_admin_in_regular_channel(slash_adapter):
    allowed, reason = slash_adapter._evaluate_slash_authorization(
        _interaction("518184812381732865"), "/restart",
    )

    assert allowed is False
    assert "administrator channel" in reason


def test_admin_slash_command_allows_admin_in_guild_admin_channel(slash_adapter):
    allowed, reason = slash_adapter._evaluate_slash_authorization(
        _interaction(
            "518184812381732865",
            channel_id="1154706638901612625",
        ),
        "/restart",
    )

    assert allowed is True
    assert reason is None


def test_admin_slash_command_rejects_wrong_guild_channel_pair(slash_adapter):
    allowed, reason = slash_adapter._evaluate_slash_authorization(
        _interaction(
            "518184812381732865",
            guild_id="921407984586866778",
            channel_id="1154706638901612625",
        ),
        "/restart",
    )

    assert allowed is False
    assert "administrator channel" in reason


def test_slash_commands_are_disabled_in_dms(slash_adapter):
    import discord

    interaction = _interaction("518184812381732865", guild_id=None)
    interaction.channel = object.__new__(discord.DMChannel)
    allowed, reason = slash_adapter._evaluate_slash_authorization(interaction, "/help")

    assert allowed is False
    assert "disabled in DMs" in reason


def test_slash_command_without_a_guild_is_denied(slash_adapter):
    allowed, reason = slash_adapter._evaluate_slash_authorization(
        _interaction("518184812381732865", guild_id=None), "/help",
    )

    assert allowed is False
    assert "allowed_guilds" in reason


def test_missing_slash_command_text_fails_closed(slash_adapter):
    allowed, reason = slash_adapter._evaluate_slash_authorization(
        _interaction(
            "518184812381732865",
            channel_id="1154706638901612625",
        ),
    )

    assert allowed is False
    assert "missing slash command" in reason


def test_skill_catalog_is_not_available_to_guild_members(slash_adapter):
    allowed, reason = slash_adapter._evaluate_slash_authorization(
        _interaction("999999999999999999"), "/skill",
    )

    assert allowed is False
    assert "administrators" in reason


@pytest.mark.asyncio
async def test_chatbird_dm_log_is_private_and_does_not_download_attachments(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    message = SimpleNamespace(
        created_at=SimpleNamespace(
            isoformat=lambda: "2026-08-11T00:00:00+00:00",
        ),
        id=123,
        author=SimpleNamespace(id=999, display_name="Alice"),
        channel=SimpleNamespace(id=456),
        content="hello from dm",
        attachments=[
            SimpleNamespace(
                id=7,
                filename="note.txt",
                content_type="text/plain",
                size=12,
            ),
        ],
    )

    await _adapter()._log_chatbird_dm(message)

    path = tmp_path / ".hermes" / "logs" / "chatbird-discord-dm.jsonl"
    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["content"] == "hello from dm"
    assert row["user_id"] == "999"
    assert row["attachments"] == [
        {
            "id": "7",
            "filename": "note.txt",
            "content_type": "text/plain",
            "size": 12,
        },
    ]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def _message(*, channel, guild, user_id=999, content="hello", bot=False, message_type=None):
    import discord

    return SimpleNamespace(
        id=123, type=message_type or discord.MessageType.default, content=content, channel=channel, guild=guild,
        author=SimpleNamespace(id=user_id, name="Alice", display_name="Alice", bot=bot, roles=[]),
        mentions=[], attachments=[], reference=None,
        created_at=SimpleNamespace(isoformat=lambda: "2026-11-02T00:00:00+00:00"),
    )


@pytest.fixture
def ingress_adapter(monkeypatch, tmp_path):
    import discord

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setenv("DISCORD_ALLOW_ALL_USERS", "true")
    monkeypatch.setenv("DISCORD_ALLOWED_GUILDS", "100")
    monkeypatch.delenv("CHATBIRD_DISABLE_DM_REPLIES", raising=False)
    monkeypatch.delenv("CHATBIRD_LOG_DMS", raising=False)
    adapter = _adapter()
    adapter._client = SimpleNamespace(user=SimpleNamespace(id=1))
    adapter._ready_event = SimpleNamespace(is_set=lambda: True)
    adapter._background_tasks = set()
    adapter._dedup = SimpleNamespace(is_duplicate=lambda _id: False, contains=lambda _id: False)
    adapter._self_is_explicitly_mentioned = lambda _message: True
    adapter._record_bot_tag_debounce = lambda _message: None
    adapter._handle_message = AsyncMock(return_value=True)
    return adapter, discord


@pytest.mark.asyncio
async def test_dm_is_logged_and_never_dispatched(ingress_adapter, tmp_path):
    adapter, discord = ingress_adapter
    channel = object.__new__(discord.DMChannel)
    message = _message(channel=channel, guild=None)

    assert await adapter._dispatch_discord_message(message) is False
    await asyncio.gather(*adapter._background_tasks)

    adapter._handle_message.assert_not_awaited()
    log = tmp_path / ".hermes" / "logs" / "chatbird-discord-dm.jsonl"
    assert json.loads(log.read_text(encoding="utf-8"))["content"] == "hello"


@pytest.mark.asyncio
async def test_recovered_dm_is_not_dispatched_or_logged_again(ingress_adapter, tmp_path):
    adapter, discord = ingress_adapter
    channel = object.__new__(discord.DMChannel)
    admitted, _role = adapter._discord_message_admission(_message(channel=channel, guild=None), claim=False)

    assert admitted is False
    assert not (tmp_path / ".hermes" / "logs" / "chatbird-discord-dm.jsonl").exists()


@pytest.mark.asyncio
async def test_unknown_guild_message_never_reaches_dispatch(ingress_adapter):
    adapter, _discord = ingress_adapter
    message = _message(channel=SimpleNamespace(id=5), guild=SimpleNamespace(id=200))

    assert await adapter._dispatch_discord_message(message) is False
    adapter._handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_allowed_guild_message_reaches_dispatch(ingress_adapter):
    adapter, _discord = ingress_adapter
    message = _message(channel=SimpleNamespace(id=5), guild=SimpleNamespace(id=100))

    assert await adapter._dispatch_discord_message(message) is True
    adapter._handle_message.assert_awaited_once()


def test_skill_autocomplete_uses_the_command_gate(slash_adapter):
    member = _interaction("999999999999999999")
    assert slash_adapter._evaluate_slash_authorization(member, "/skill")[0] is False
    admin = _interaction("518184812381732865", channel_id="1154706638901612625")
    assert slash_adapter._evaluate_slash_authorization(admin, "/skill")[0] is True


@pytest.mark.parametrize(
    "user_id, channel_id, text, command",
    [
        ("999999999999999999", "1146359015715110992", "/restart", None),
        ("999999999999999999", "1146359015715110992", "/some-private-skill go", None),
        ("518184812381732865", "1146359015715110992", "/restart", None),
        ("518184812381732865", "1154706638901612625", "/restart", "restart"),
        ("999999999999999999", "1146359015715110992", "/status", "status"),
    ],
)
@pytest.mark.asyncio
async def test_typed_commands_pass_the_same_gate_as_native_ones(slash_adapter, user_id, channel_id, text, command):
    """A denied "@bot /restart" reaches the gateway as plain chat, with no command to dispatch."""
    from gateway.config import Platform, PlatformConfig
    from plugins.platforms.discord.adapter import DiscordAdapter

    adapter = DiscordAdapter(PlatformConfig(enabled=True, token="fake"))
    adapter._client = SimpleNamespace(user=SimpleNamespace(id=7))
    adapter._text_batch_delay_seconds = 0
    adapter.handle_message = AsyncMock()
    guild = SimpleNamespace(id=1146359014968537089, name="Bird Gaming")
    channel = SimpleNamespace(id=int(channel_id), name="general", guild=guild, topic=None)
    message = _message(channel=channel, guild=guild, user_id=int(user_id), content=f"<@7> {text}")
    message.mentions = [adapter._client.user]

    await adapter._handle_message(message)

    event = adapter.handle_message.await_args.args[0]
    assert event.source.platform == Platform.DISCORD
    assert event.get_command() == command
    assert event.allow_gateway_control is (command is not None)


@pytest.mark.asyncio
async def test_ordinary_chat_keeps_gateway_control(slash_adapter):
    from gateway.config import PlatformConfig
    from plugins.platforms.discord.adapter import DiscordAdapter

    adapter = DiscordAdapter(PlatformConfig(enabled=True, token="fake"))
    adapter._client = SimpleNamespace(user=SimpleNamespace(id=7))
    adapter._text_batch_delay_seconds = 0
    adapter.handle_message = AsyncMock()
    guild = SimpleNamespace(id=1146359014968537089, name="Bird Gaming")
    channel = SimpleNamespace(id=1146359015715110992, name="general", guild=guild, topic=None)
    message = _message(channel=channel, guild=guild, content="<@7> hello")
    message.mentions = [adapter._client.user]

    await adapter._handle_message(message)

    assert adapter.handle_message.await_args.args[0].allow_gateway_control is True


@pytest.mark.parametrize(
    "text, allowed",
    [("/restart", False), ("/skill", False), ("/model", False), ("/status", True), ("/help", True)],
)
def test_lost_admin_settings_close_the_gate_on_a_chatbird_deployment(monkeypatch, text, allowed):
    monkeypatch.delenv("CHATBIRD_ADMIN_USERS", raising=False)
    monkeypatch.delenv("CHATBIRD_ADMIN_CHANNELS", raising=False)
    monkeypatch.setenv("DISCORD_ALLOWED_GUILDS", "1146359014968537089")
    monkeypatch.setenv("DISCORD_ALLOW_ALL_USERS", "true")

    result, _reason = _adapter()._evaluate_slash_authorization(_interaction("518184812381732865"), text)

    assert result is allowed
