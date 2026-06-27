# ChatBird

Discord bot deployment for Hermes Agent backed by Xiaomi MiMo.

ChatBird is a private Discord assistant for the Bird Gaming server. The bot is
also known as 小鸟聊天助手, 乌鸦, or ChatBird.

## Public Documents

- [Privacy Policy](PRIVACY.md)
- [Discord Privileged Intent Application Notes](docs/discord-intent-application.md)
- [Bird-Bot Reference for ChatBird](docs/bird-bot-guide.md)

## Runtime

- Host: `aliyun-germany`
- Hermes provider: `xiaomi`
- Model: `mimo-v2.5`
- Discord guild: `1146359014968537089`
- Service target: Hermes messaging gateway

## Required Secrets

Do not commit real values. Put them in `/root/.hermes/.env` on the server:

```env
XIAOMI_API_KEY=...
DISCORD_BOT_TOKEN=...
DISCORD_ALLOWED_USERS=...
# or:
# DISCORD_ALLOWED_ROLES=...
```

Hermes refuses Discord messages unless at least one allowlist is configured. Prefer a narrow `DISCORD_ALLOWED_USERS` value while testing.

## Server Commands

```bash
ssh aliyun-germany
hermes chat --provider xiaomi --model mimo-v2.5
hermes gateway
```

For persistent operation:

```bash
hermes gateway install --system
hermes gateway start --system
hermes gateway status --system
journalctl -u hermes-gateway -f
```

## Discord Requirements

Enable these in the Discord Developer Portal for the bot:

- Server Members Intent
- Message Content Intent

ChatBird does not require Presence Intent.

Invite scope:

- `bot`
- `applications.commands`

Minimum permission integer from Hermes docs:

```text
274878286912
```

## Notes

- In server channels, Hermes defaults to responding only when the bot is mentioned.
- Hermes can auto-create a thread per mention. Keep that default unless a specific channel should be inline chat.
- The Alibaba Cloud security group only needs SSH for deployment; Discord uses outbound WebSocket/HTTPS from the server.
