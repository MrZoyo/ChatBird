#!/usr/bin/env python3
"""Validate ChatBird's non-secret production configuration invariants."""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when a ChatBird production invariant is violated."""


def _load_config(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot load configuration: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("configuration root must be a mapping")
    return data


def _string_set(value: Any) -> set[str]:
    if isinstance(value, str):
        return {part.strip() for part in value.split(",") if part.strip()}
    if isinstance(value, list):
        return {str(part).strip() for part in value if str(part).strip()}
    return set()


def _mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def validate_config(data: dict[str, Any]) -> None:
    discord = _mapping(data, "discord")
    allowed_guilds = _string_set(discord.get("allowed_guilds"))
    if not allowed_guilds:
        raise ConfigError("discord.allowed_guilds must contain at least one guild ID")
    if "*" in allowed_guilds:
        raise ConfigError("discord.allowed_guilds must not contain '*' in production")
    if any(not guild_id.isdigit() for guild_id in allowed_guilds):
        raise ConfigError("discord.allowed_guilds entries must be numeric Discord guild IDs")

    if "chatbird-policy" not in _string_set(_mapping(data, "plugins").get("enabled")):
        raise ConfigError("plugins.enabled must include chatbird-policy")

    memory = _mapping(data, "memory")
    if memory.get("user_profile_enabled") is not False:
        raise ConfigError(
            "memory.user_profile_enabled must be false; "
            "ChatBird profiles are provided by chatbird-policy"
        )
    if memory.get("write_approval"):
        raise ConfigError(
            "memory.write_approval must stay off; its pending queue is not limited to one guild"
        )

    gateway = _mapping(data, "gateway")
    if gateway.get("strict") is not True or gateway.get("trust_recent_files") is not False:
        raise ConfigError(
            "gateway.strict must be true and gateway.trust_recent_files false; "
            "otherwise a MEDIA: line can upload sessions and memory"
        )

    web = _mapping(data, "web")
    if web.get("keyless_fallback") is not False or web.get("keyless_rescue") is not False:
        raise ConfigError(
            "web.keyless_fallback and web.keyless_rescue must be false; "
            "otherwise failed calls send user queries and URLs to anonymous third-party tiers"
        )

    tool_search = _mapping(_mapping(data, "tools"), "tool_search")
    if tool_search.get("enabled") not in ("off", False):
        raise ConfigError(
            "tools.tool_search.enabled must be off; "
            "the bridge hides chatbird_* tools from public turns"
        )

    if _mapping(data, "browser").get("backend") not in ("off", False):
        raise ConfigError(
            "browser.backend must be off; "
            "the Browser Use default silently disables the restricted browser fallback"
        )

    if _mapping(data, "security").get("allow_lazy_installs") is not False:
        raise ConfigError(
            "security.allow_lazy_installs must be false; a public bot must not install packages at runtime"
        )


def validate_env_file(path: Path) -> None:
    """Check setting names only, so an error can never carry a value.

    Hermes reloads this file over config.yaml on every turn, and the admin mapping decides who
    may run commands and privileged tools.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigError(f"cannot read {path.name}: {exc}") from exc
    names = {
        line.strip().removeprefix("export ").split("=", 1)[0].strip()
        for line in lines
        if "=" in line and not line.lstrip().startswith("#")
    }
    for name in sorted(names):
        if name.startswith("HERMES_MEDIA_"):
            raise ConfigError(
                f"{path.name} must not set {name}; Hermes reloads it each turn over gateway.strict"
            )
    for name in ("CHATBIRD_ADMIN_USERS", "CHATBIRD_ADMIN_CHANNELS"):
        if name not in names:
            raise ConfigError(f"{path.name} must set {name}")


def repair_builtin_profile(path: Path) -> bool:
    data = _load_config(path)
    memory = data.get("memory")
    memory = memory if isinstance(memory, dict) else {}
    if memory.get("user_profile_enabled") is False:
        return False

    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    memory_start: int | None = None
    memory_end = len(lines)
    for index, line in enumerate(lines):
        if re.match(r"^memory\s*:\s*(?:#.*)?$", line.rstrip("\r\n")):
            memory_start = index + 1
            continue
        if memory_start is not None and re.match(r"^[A-Za-z_][\w-]*\s*:", line):
            memory_end = index
            break
    if memory_start is None:
        raise ConfigError("cannot repair missing top-level memory section")

    setting = re.compile(
        r"^(?P<prefix>[ \t]+user_profile_enabled[ \t]*:[ \t]*)"
        r"(?P<value>[^#\r\n]*)(?P<suffix>[ \t]*(?:#.*)?(?:\r?\n)?)$"
    )
    matches = [
        (index, setting.match(lines[index]))
        for index in range(memory_start, memory_end)
        if setting.match(lines[index])
    ]
    if len(matches) != 1:
        raise ConfigError("cannot safely identify one memory.user_profile_enabled line")

    index, match = matches[0]
    assert match is not None
    lines[index] = f"{match.group('prefix')}false{match.group('suffix')}"
    repaired = "".join(lines)

    current_mode = path.stat().st_mode & 0o777
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, current_mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(repaired)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise

    validate_config(_load_config(path))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate ChatBird's production configuration invariants."
    )
    parser.add_argument("config", type=Path)
    parser.add_argument(
        "--repair-profile",
        action="store_true",
        help="atomically restore memory.user_profile_enabled to false",
    )
    args = parser.parse_args()

    try:
        repaired = repair_builtin_profile(args.config) if args.repair_profile else False
        validate_config(_load_config(args.config))
        validate_env_file(args.config.parent / ".env")
    except ConfigError as exc:
        print(f"ChatBird config guard failed: {exc}", file=sys.stderr)
        return 1

    if repaired:
        print("ChatBird config guard restored memory.user_profile_enabled=false")
    else:
        print("ChatBird production config invariants OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
