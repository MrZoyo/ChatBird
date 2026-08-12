import json
import stat
from types import SimpleNamespace

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
    allowed, reason = slash_adapter._evaluate_slash_authorization(
        _interaction("518184812381732865", guild_id=None), "/help",
    )

    assert allowed is False
    assert "guild id missing" in reason


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
