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

if [[ "${DISCORD_ALLOW_ALL_USERS:-}" != "true" && -z "${DISCORD_ALLOWED_USERS:-}" && -z "${DISCORD_ALLOWED_ROLES:-}" ]]; then
  echo "set DISCORD_ALLOW_ALL_USERS=true, DISCORD_ALLOWED_USERS, or DISCORD_ALLOWED_ROLES" >&2
  exit 1
fi

if [[ -z "${CHATBIRD_ADMIN_USERS:-}" || -z "${CHATBIRD_ADMIN_CHANNELS:-}" ]]; then
  echo "set CHATBIRD_ADMIN_USERS and CHATBIRD_ADMIN_CHANNELS" >&2
  exit 1
fi

IFS=',' read -r -a admin_channel_pairs <<< "$CHATBIRD_ADMIN_CHANNELS"
for pair in "${admin_channel_pairs[@]}"; do
  if [[ ! "$pair" =~ ^[0-9]+:[0-9]+$ ]]; then
    echo "CHATBIRD_ADMIN_CHANNELS must use GuildID:ChannelID pairs" >&2
    exit 1
  fi
done

if [[ -z "${CHATBIRD_HOME_CHANNELS:-}" ]]; then
  echo "set CHATBIRD_HOME_CHANNELS with one GuildID:ChannelID pair per Guild" >&2
  exit 1
fi

IFS=',' read -r -a home_channel_pairs <<< "$CHATBIRD_HOME_CHANNELS"
for pair in "${home_channel_pairs[@]}"; do
  if [[ ! "$pair" =~ ^[0-9]+:[0-9]+$ ]]; then
    echo "CHATBIRD_HOME_CHANNELS must use GuildID:ChannelID pairs" >&2
    exit 1
  fi
done

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
chmod 600 "$tmp"

{
  printf 'XIAOMI_API_KEY=%s\n' "$XIAOMI_API_KEY"
  printf 'DISCORD_BOT_TOKEN=%s\n' "$DISCORD_BOT_TOKEN"
  printf 'DISCORD_ALLOWED_USERS=%s\n' "${DISCORD_ALLOWED_USERS:-}"
  printf 'DISCORD_ALLOWED_ROLES=%s\n' "${DISCORD_ALLOWED_ROLES:-}"
  printf 'DISCORD_ALLOW_ALL_USERS=%s\n' "${DISCORD_ALLOW_ALL_USERS:-false}"
  printf 'CHATBIRD_ADMIN_USERS=%s\n' "$CHATBIRD_ADMIN_USERS"
  printf 'CHATBIRD_ADMIN_CHANNELS=%s\n' "$CHATBIRD_ADMIN_CHANNELS"
  printf 'DISCORD_HOME_CHANNEL=%s\n' "${DISCORD_HOME_CHANNEL:-}"
  printf 'CHATBIRD_HOME_CHANNELS=%s\n' "$CHATBIRD_HOME_CHANNELS"
  printf 'CHATBIRD_DISABLE_HOME_CHANNEL_NOTICE=%s\n' "${CHATBIRD_DISABLE_HOME_CHANNEL_NOTICE:-true}"
  printf 'CHATBIRD_DISABLE_DM_REPLIES=%s\n' "${CHATBIRD_DISABLE_DM_REPLIES:-true}"
  printf 'CHATBIRD_LOG_DMS=%s\n' "${CHATBIRD_LOG_DMS:-true}"
  printf 'DISCORD_AUTO_THREAD=%s\n' "${DISCORD_AUTO_THREAD:-false}"
} > "$tmp"

scp "$tmp" "$host:/root/.hermes/.env.tmp"
ssh "$host" 'install -m 600 /root/.hermes/.env.tmp /root/.hermes/.env && rm -f /root/.hermes/.env.tmp'
