# Multi-Guild Memory and Operations

ChatBird uses one Discord application and bot token across multiple Discord
servers. The deployed Hermes patch treats each Discord guild ID as a tenant
boundary.

## Isolation Model

For a server message, the guild ID is included in both boundaries:

- Session keys end with `guild-<guild_id>`, so conversation history from one
  server cannot be selected by a session in another server.
- Persistent memory is stored under
  `/root/.hermes/memories/scopes/discord-guild-<guild_id>/MEMORY.md`.
- If Mem0 is enabled later, its user ID is prefixed with the same guild
  namespace. A configured canonical user therefore cannot merge guilds.
- Direct messages are not dispatched into Hermes sessions. They are logged to
  a private mode-`0600` JSONL file and receive no reply.

Every participant in one Discord channel shares the same live conversation
session. Different channels remain separate, and every key retains the Guild
suffix. Channels inside the same Guild share public `MEMORY.md`; personal
profiles and administrator memory use the additional paths documented in
[`multi-user-policy.md`](multi-user-policy.md). ChatBird disables the built-in
shared `USER.md` so personal facts cannot mix between members.

## Adding a Discord Server

1. Add the new guild ID to `discord.allowed_guilds` in
   `/root/.hermes/config.yaml`. Use a YAML list or a comma-separated string.
2. Add only the channels that need ChatBird to `discord.allowed_channels`.
   An empty or omitted channel list allows every channel the bot can view.
3. Keep `require_mention: true`, `auto_thread: false`, and
   `group_sessions_per_user: false` for the shared-channel UX.
4. Restart `hermes-gateway.service` and check that it remains active with no
   restart loop.
5. Mention the bot once in the new server. Hermes creates that Guild's public
   memory directory lazily; user profiles are also created lazily.

An invited server that is absent from `allowed_guilds` is ignored. Do not use
`*` in production. The current production allowlist contains:

- Bird Gaming: `1146359014968537089`
- 秘密研究 (test): `921407984586866778`

The test guild currently accepts ChatBird interactions in `常规`
(`921407984586866781`). Channel IDs from every guild share the same
`discord.allowed_channels` list, while sessions and memory remain guild-scoped.

## Deployment Record

The production Hermes tree is `/usr/local/lib/hermes-agent`. Commit
`49d2aa56` (`fix(discord): isolate guild sessions and memory`) contains the
session, memory, slash-command, and guild allowlist changes. Before deployment,
`/root/.hermes/config.yaml` was backed up to
`/root/.hermes/config.yaml.before-guild-isolation`.

Before the test guild was enabled on 2026-08-11, the configuration was backed
up to `/root/.hermes/config.yaml.before-test-guild`.

The test channel allowlist change was captured afterward in
`/root/.hermes/config.yaml.after-channel-allowlist`.

Focused verification on 2026-08-11 passed 8 isolation tests and 131 directly
related regression tests. The full Hermes suite was intentionally not run on
the production host.

## Small-Server Limits

The production host has about 1.6 GiB RAM, 2 GiB swap, and two CPU cores. Treat
it as a low-resource production machine:

- use targeted reads and searches instead of scanning the full Hermes tree;
- run tests in one process and only for affected modules;
- do not run the full test suite, parallel builds, or broad history backfills;
- keep inbound attachments at the Hermes default of 32 MiB or lower, never
  unlimited; `config.example.yaml` sets the limit explicitly and leaves
  unknown file types blocked;
- keep gateway restarts brief and check service status, restart count, memory,
  and recent logs afterward.
