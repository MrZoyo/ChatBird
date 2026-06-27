#!/usr/bin/env bash
set -euo pipefail

host="${1:-aliyun-germany}"

required=(
  XIAOMI_API_KEY
  DISCORD_BOT_TOKEN
)

for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "missing required env: $name" >&2
    exit 1
  fi
done

if [[ -z "${DISCORD_ALLOWED_USERS:-}" && -z "${DISCORD_ALLOWED_ROLES:-}" ]]; then
  echo "set DISCORD_ALLOWED_USERS or DISCORD_ALLOWED_ROLES" >&2
  exit 1
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
chmod 600 "$tmp"

{
  printf 'XIAOMI_API_KEY=%s\n' "$XIAOMI_API_KEY"
  printf 'DISCORD_BOT_TOKEN=%s\n' "$DISCORD_BOT_TOKEN"
  printf 'DISCORD_ALLOWED_USERS=%s\n' "${DISCORD_ALLOWED_USERS:-}"
  printf 'DISCORD_ALLOWED_ROLES=%s\n' "${DISCORD_ALLOWED_ROLES:-}"
  printf 'DISCORD_ALLOWED_CHANNELS=%s\n' "${DISCORD_ALLOWED_CHANNELS:-}"
  printf 'DISCORD_REQUIRE_MENTION=%s\n' "${DISCORD_REQUIRE_MENTION:-true}"
  printf 'DISCORD_THREAD_REQUIRE_MENTION=%s\n' "${DISCORD_THREAD_REQUIRE_MENTION:-true}"
  printf 'DISCORD_AUTO_THREAD=%s\n' "${DISCORD_AUTO_THREAD:-true}"
} > "$tmp"

scp "$tmp" "$host:/root/.hermes/.env.tmp"
ssh "$host" 'install -m 600 /root/.hermes/.env.tmp /root/.hermes/.env && rm -f /root/.hermes/.env.tmp'
