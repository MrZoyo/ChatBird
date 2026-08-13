<p align="center">
  <img src="assets/chatbird-banner.png" alt="ChatBird banner" width="100%">
</p>

<h1 align="center">ChatBird</h1>

<p align="center">
  <strong>A secure AI assistant for multiple Discord servers</strong>
</p>

<p align="center">
  <a href="README.md">简体中文</a> · English
</p>

<p align="center">
  <a href="https://github.com/NousResearch/hermes-agent">
    <img src="https://img.shields.io/badge/BUILT%20ON-HERMES%20AGENT-6C5CE7?style=for-the-badge" alt="Built on Hermes Agent">
  </a>
  <a href="PRIVACY.md">
    <img src="https://img.shields.io/badge/PRIVACY-GUILD%20ISOLATED-2EA44F?style=for-the-badge" alt="Guild-isolated privacy">
  </a>
  <a href="hermes-stack.lock">
    <img src="https://img.shields.io/badge/INTEGRATION-REPRODUCIBLE-0969DA?style=for-the-badge" alt="Reproducible integration">
  </a>
</p>

ChatBird is a Discord AI assistant integration built on
[Hermes Agent](https://github.com/NousResearch/hermes-agent). It lets one bot
account serve multiple guilds while adding access control, guild-scoped
sessions and memory, restricted tools, web retrieval, and a reproducible patch
workflow for public Discord deployments.

ChatBird does not require a specific model provider, cloud platform, or server.
Choose the model, host, and deployment method that fit your environment; this
repository defines the behavior, security boundaries, and Hermes integration.

## Features

| Capability | What it provides |
| --- | --- |
| Multi-guild isolation | Every conversation session and persistent memory scope includes `guild_id` |
| Default-deny access | Only explicitly configured `allowed_guilds` and `allowed_channels` are accepted |
| Category inheritance | Guild channels, including voice-channel chat, inherit their category allowlist entry; threads inherit their parent channel |
| Explicit activation | Normal channel messages reach the model only after a mention or reply to the bot |
| Public tool policy | Public users receive chat, restricted web access, supported attachment analysis, and limited memory operations |
| Dual administrator checks | Sensitive features require both an administrator user and the current `guild_id:channel_id` |
| DM isolation | Direct messages do not enter model sessions and receive no bot reply |
| Reproducible integration | The upstream commit, patch order, and test overlays live in `hermes-stack.lock` |

## Request flow

```text
Discord message
  -> Guild allowlist
  -> Channel / Category allowlist
  -> Mention or reply check
  -> Guild-scoped session and memory
  -> Request-scoped tool policy
  -> Configured model provider
```

The primary isolation contract is simple: **Discord sessions and persistent
memory must never cross guild boundaries.** Any guild missing from
`discord.allowed_guilds` must be denied by default.

## Quick start

ChatBird is not a full copy of Hermes Agent. Prepare a clean Hermes checkout,
then apply the patch stack maintained in this repository.

### 1. Prepare Hermes Agent

```bash
git clone https://github.com/NousResearch/hermes-agent.git hermes-agent
git -C hermes-agent checkout f53b184c48712bcbb98556a6314cd1f240fc104d
```

[`hermes-stack.lock`](hermes-stack.lock) is authoritative; use its new value
after an upstream-base update.

### 2. Check and apply the patch stack

```bash
scripts/apply-hermes-patches.sh ./hermes-agent --check
scripts/apply-hermes-patches.sh ./hermes-agent
```

The script stops if the checkout is dirty, the base commit differs, a patch is
missing, a patch no longer applies, or a test overlay conflicts with an
upstream file.

### 3. Configure the deployment

Start from the sanitized examples:

```bash
cp config.example.yaml /path/to/hermes/config.yaml
cp .env.example /path/to/hermes/.env
```

At minimum:

- choose a model provider and model through Hermes Agent's configuration;
- set the Discord bot token;
- list every accepted guild under `discord.allowed_guilds`;
- list accepted channels or categories under `discord.allowed_channels`;
- configure `CHATBIRD_ADMIN_USERS` and `CHATBIRD_ADMIN_CHANNELS`;
- keep `group_sessions_per_user: false` and
  `memory.user_profile_enabled: false` to use ChatBird's shared-channel and
  layered-memory policy.

All IDs and credentials in the examples are placeholders. Keep real secrets in
the deployment environment and never commit them.

### 4. Configure the Discord application

In the [Discord Developer Portal](https://discord.com/developers/applications):

1. Create an application and bot user.
2. Enable **Message Content Intent**.
3. Enable **Server Members Intent** if you use role authorization, user
   allowlists, or member lookup.
4. Invite the bot with the `bot` and `applications.commands` scopes.
5. Grant only the permissions needed to read channels and history, send
   messages, embed links, upload files, add reactions, and use application
   commands. Do not grant `Administrator`.

See [Discord permissions](docs/discord-permissions.md) for details.

## Configuration principles

### Models and runtime environment

ChatBird does not restrict the model API, inference backend, operating system,
or cloud platform. Configure model access through Hermes Agent and choose the
deployment directory, service manager, and resource limits for your host. The
main README intentionally avoids presenting one deployment's model or server as
a project requirement.

### Guild and channel allowlists

```yaml
discord:
  allowed_guilds:
    - "111111111111111111"
  allowed_channels:
    - "222222222222222222" # Channel or Category ID
  require_mention: true
  thread_require_mention: true
  auto_thread: false
```

Guild channels, including a voice channel's built-in text chat, expose their
category through discord.py's `category`/`category_id`; threads expose their
parent through `parent`/`parent_id`. Message and slash-command authorization
use the same inheritance rule.

When a temporary voice channel is deleted, the adapter cancels agent turns for
that channel ID that are running, queued, or waiting to be batched, and stops
handling the old session. Transcript history remains subject to the retention
policy. A later temporary channel has a new channel ID and therefore a new
session.

### Administrator boundary

```env
CHATBIRD_ADMIN_USERS=123456789012345678
CHATBIRD_ADMIN_CHANNELS=111111111111111111:222222222222222222
```

Administrator capabilities open only when the user ID and current
`GuildID:ChannelID` both match. Missing or malformed mappings and calls from a
public channel fail closed.

### Web capabilities

The repository includes a public-channel policy for web queries. Operators can
choose the search and content-extraction backends for each deployment. Public
web access does not grant terminal, file, code-execution, or interactive
browser capabilities.

## Troubleshooting

### I mentioned the bot, but it did not reply

Channel authorization runs before the mention check. Confirm, in order:

1. the current guild appears in `discord.allowed_guilds`;
2. the channel ID or containing category ID appears in
   `discord.allowed_channels`;
3. a guild channel, including voice-channel chat, resolves its category through
   `category`/`category_id`;
4. a thread resolves its parent through `parent`/`parent_id`;
5. the message actually mentions the bot or replies to one of its messages.

The previous implementation read only the thread-specific `parent` fields, so
normal text channels and voice-channel chat inside an allowed category could
be rejected as unauthorized. The current patch handles categories and threads
separately and adds regression coverage for text messages, voice-channel chat,
slash commands, and deleted-channel cleanup.

### Why maintain a patch stack?

ChatBird preserves the full upstream Hermes history and tracks only reviewed
differences. Upgrades can be rebuilt from the locked upstream commit, conflicts
can be handled patch by patch, and final files can be compared without
maintaining a long-lived source-code fork.

## Repository layout

| Path | Purpose |
| --- | --- |
| [`hermes-stack.lock`](hermes-stack.lock) | Locks the upstream repository, base commit, patch order, and test overlays |
| [`patches/`](patches/) | Hermes patches, reference configuration, and patch notes |
| [`plugins/chatbird-policy/`](plugins/chatbird-policy/) | Request-scoped access and layered-memory policy plugin |
| [`scripts/apply-hermes-patches.sh`](scripts/apply-hermes-patches.sh) | Checks or applies the complete patch stack |
| [`config.example.yaml`](config.example.yaml) | Sanitized behavior configuration example |
| [`.env.example`](.env.example) | Environment-variable placeholders |
| [`docs/`](docs/) | Access, isolation, privacy, and operations documentation |

## Verification

Patch changes should, at minimum:

1. pass `--check` against a clean checkout at the locked base;
2. apply the complete patch stack from that base;
3. pass syntax checks for changed Python files;
4. pass focused tests for the affected behavior;
5. produce the expected rebuilt files.

Avoid repository-wide scans, full test suites, and high-concurrency builds on a
resource-constrained production host. Validate locally or in a temporary
worktree, then deploy only the required files and run focused smoke tests.

## Documentation

| Document | Contents |
| --- | --- |
| [Production state](docs/production-state.md) | Non-secret deployment state, validation records, and operational notes for the current instance |
| [Multi-user policy](docs/multi-user-policy.md) | Public-user, administrator, tool, and memory boundaries |
| [Multi-guild memory](docs/multi-guild-memory.md) | Guild-scoped sessions and persistent memory |
| [Discord permissions](docs/discord-permissions.md) | Required bot permissions and attachment behavior |
| [Discord intent application](docs/discord-intent-application.md) | Material for privileged-intent review |
| [Patch-stack notes](patches/README.md) | Patch maintenance, upgrade, and validation rules |
| [Privacy policy](PRIVACY.md) | Data processing and retention boundaries |

## Upstream and licensing

ChatBird is built on [Hermes Agent](https://github.com/NousResearch/hermes-agent).
Before using or distributing this repository, follow the license terms of both
this project and its upstream dependencies.
