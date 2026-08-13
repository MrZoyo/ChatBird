---
name: chatbird-admin
description: Manage the ChatBird production Discord configuration, channel allowlists, layered memory, knowledge base, and Hermes gateway. Use before changing ChatBird configuration or restarting its gateway.
---

# ChatBird Administration

## Protect tenant boundaries

- Keep `discord.allowed_guilds` explicit. Never use `*` in production.
- Keep `memory.user_profile_enabled: false`. This Hermes setting enables a shared `USER.md` and can mix profiles in a multi-user Discord deployment.
- Treat ChatBird user profiles as already enabled. The `chatbird-policy` plugin stores them through `chatbird_memory` under `memories/chatbird/profiles/discord-guild-<guild_id>/<user_id>.md`.
- Keep `group_sessions_per_user: false`; ChatBird shares channel conversation history while isolating every session and persistent-memory path by Guild.
- Never read or print `/root/.hermes/.env`.

If an administrator asks to enable user profiles, explain that ChatBird profiles already operate through `chatbird_memory`. Do not change `memory.user_profile_enabled`, and do not restart solely for that request.

## Modify production configuration

Use `hermes config set <section>.<key> <value>` for simple values. Use a narrowly targeted edit for lists. After any change:

1. Validate the affected non-secret fields.
2. Run `/root/.hermes/chatbird/validate-production-config.py` against `/root/.hermes/config.yaml`.
3. Restart `hermes-gateway.service` only when the setting requires it.
4. Confirm the service is `active/running`, check its restart count, and inspect recent logs.

Do not claim a configuration change is live before the required restart succeeds.

## Maintain the Bird-Bot guide

The guide lives at `/root/.hermes/knowledge/bird-bot-guide.md`. When a user reports a version mismatch or asks whether it is current, compare the repository README, changelog, and package version. Record the checked date and version without copying credentials into the guide.
