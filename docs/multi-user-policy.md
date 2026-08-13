# Discord Multi-User Policy

ChatBird treats a Discord text channel as a collaborative room. All people in
the same allowed channel share one Hermes transcript, while the existing
`guild-<guild_id>` session suffix prevents cross-server history access.

## Conversation Boundary

```yaml
group_sessions_per_user: false

discord:
  require_mention: true
  auto_thread: false
  history_backfill: true
  history_backfill_limit: 50
```

The bot replies inline only when mentioned. Messages posted between two bot
turns can be supplied as bounded recent context on the next mention. They are
not independently dispatched to the model when nobody mentions the bot.

## Request-Scoped Authorization

The `chatbird-policy` plugin reads the current Discord user and channel from
Hermes gateway ContextVars on every turn and every tool call. It never trusts
the user ID cached on a shared `AIAgent` instance.

An administrator turn requires both:

- a user ID in `CHATBIRD_ADMIN_USERS`; and
- the current `guild_id:channel_id` pair in `CHATBIRD_ADMIN_CHANNELS`.

For the current deployment:

```env
CHATBIRD_ADMIN_USERS=518184812381732865
CHATBIRD_ADMIN_CHANNELS=1146359014968537089:1154706638901612625,921407984586866778:1220876330913234944
```

Bare channel IDs and malformed mappings are ignored, so privileged mode fails
closed. A channel configured for one Guild cannot authorize a turn in another.

The double check keeps an administrator's sensitive tool results out of public
shared transcripts. In a public channel, the administrator receives the same
safe tool surface as every other participant.

Public policy permits only `web_search`, `web_extract`, `vision_analyze`,
`clarify`, `skills_list`, `skill_view`, and constrained `chatbird_memory`
profile operations when those tools are registered. `skills_list` and
`skill_view` expose only independently reviewed public skills whose current
files still match the approved SHA-256 digest. Public reads are inert: no
template expansion, inline command execution, credential setup, or host-path
disclosure is allowed. Production uses DDGS for no-key `web_search` and the
request-driven `simple-http` provider for static HTML/text/JSON/XML extraction.
Every other
tool is denied at the pre-execution hook, including terminal, host-file access,
code execution, built-in memory, session search, Cron, Skill management,
delegation, messaging, computer use, and Kanban tools. Discord slash commands
use a separate fail-closed gate. `/help`, `/whoami`, `/status`, `/version`, and
`/usage` are public inside allowed Guild channels. Every other built-in,
plugin, or newly discovered slash command is administrator-only and requires
the same administrator user ID plus the current Guild's administrator channel.
DM slash commands are rejected, and `/skill` autocomplete returns no catalog
entries to ordinary users.

Hermes normally asks the model to load a relevant Skill before using even a
basic tool. Public ChatBird turns receive a filtered index, so the model may
load only listed, currently approved public skills and must call `web_search`
directly when none applies. It may follow with `web_extract` for fuller static
page context. A failure from another denied tool must never be reported as if
public-channel policy blocked either web tool.

Public-origin background self-improvement may propose a new public skill or an
update to an already approved public skill. The mutation is built in a private
candidate directory, checked for inert text-only content, then sent to a
separate tool-free reviewer agent. Publication occurs only after an exact
approval response; rejection, timeout, malformed output, missing identity, or
policy failure preserves the old approved version. Public-origin background
review cannot edit an unapproved/private skill or delete any skill.

The browser fallback remains an implementation detail of `web_search` and
`web_extract`; it does not add `browser_*` to the public allowlist. After a
primary-provider failure, HTTP 403/5xx/timeout, JavaScript challenge, or empty
page, Hermes may open one short-lived local Chromium session, perform a fixed
DOM read, and close it. A process-wide semaphore permits one browser fallback
at a time. The helper independently enforces public HTTP/HTTPS URL and
website-policy checks before navigation and after redirects. It cannot click,
type, log in, download, or evaluate user-supplied JavaScript, and it does not
switch IPs to bypass an HTTP 429 rate limit. Local Chromium can render
JavaScript, but it does not guarantee passage through CAPTCHA, residential-IP,
or advanced anti-bot challenges.

The same end-to-end validation rule is injected into administrator Discord
turns. Administrators may have direct browser tools for diagnostics, but a
challenge in that route is not evidence that the canonical `web_search` or
`web_extract` path failed. Source capability reports must test the canonical
path first and state route-specific results separately.

If local Chromium still receives a challenge page, production may use Jina
Reader as a final read-only extraction service for the exact allowlisted host
`www.vicioussyndicate.com`. Arbitrary domains, credentials, fragments, and
query strings are never forwarded to that service. Returned source URLs are
checked against the same host and public-network policy before content is
accepted. HSGuru is not sent to the reader service: its public `robots.txt`
permits search/reference use but blocks automated `/api`, `/decks`, and
query-driven statistics routes. Hermes uses DDGS index results and snippets
for HSGuru instead of attempting to bypass those controls. If a query names
HSGuru but the primary results contain no HSGuru link, Hermes broadens it to a
public-index-only HSGuru Meta/Decks query through DDGS's Yahoo index backend;
an empty response may fall back once more to the general HSGuru index. Hermes
keeps only HSGuru result URLs and never retries an explicit rate limit.

## Layered Memory

| Scope | Path | Access |
|---|---|---|
| Guild public memory | `memories/scopes/discord-guild-<guild_id>/MEMORY.md` | Everyone in that Guild; writes require an admin context |
| User profile | `memories/chatbird/profiles/discord-guild-<guild_id>/<user_id>.md` | Injected only for that user; an admin can inspect it |
| Admin memory | `memories/chatbird/admin/discord-guild-<guild_id>/ADMIN.md` | Injected and writable only in an admin context |

The shared Hermes `USER.md` remains disabled. Its
`memory.user_profile_enabled` setting is not the ChatBird profile switch and
must remain `false`. ChatBird profiles are already active through
`chatbird_memory`. The policy plugin blocks administrator and background Skill
attempts to enable the shared setting.

A normal user cannot directly command a profile-memory change. The Agent may
proactively retain only a bounded stable preference, trait, communication
style, or durable personal context. The profile tool rejects direct
“remember/forget” requests, task history, completed-work records,
instruction-like text, credential-like text, and prompt-injection patterns.

## Direct Messages

Human DMs are appended to
`~/.hermes/logs/chatbird-discord-dm.jsonl` with mode `0600`, then immediately
discarded from the reply pipeline. ChatBird never replies to a DM and never
downloads a DM attachment merely for logging; it records text plus bounded
attachment metadata. An administrator may inspect the log only from the
private administrator channel through administrator-gated tools.

## Guild Delivery Targets

Hermes supports one platform-wide `DISCORD_HOME_CHANNEL`, which ChatBird uses
as the intentionally unified cross-platform destination for this deployment.
It is the public test channel, so it must not receive sensitive content. The
administrator context also receives the current Guild's explicit target from:

```env
DISCORD_HOME_CHANNEL=921407984586866781
CHATBIRD_HOME_CHANNELS=1146359014968537089:1148897557947367474,921407984586866778:921407984586866781
CHATBIRD_DISABLE_HOME_CHANNEL_NOTICE=true
```

Scheduled tasks should use `origin` by default. If an explicit destination is
needed, use the mapped channel for the current Guild. A bare `discord` target
uses the unified public test channel by design; do not use it for sensitive
administrator content. `deliver=all` remains restricted to deliberate
administrator use.

## Administrator Channels

The configured Guild-specific administrator channels are:

- Bird Gaming (`1146359014968537089`): `1154706638901612625`
- 秘密研究 (`921407984586866778`): `1220876330913234944`

Discord must grant the Bot role these channel-specific permissions before each
channel can be used:

- View Channel
- Send Messages
- Read Message History
- Embed Links and Attach Files, if administrator responses need them

Do not make this channel visible to ordinary members. No Discord
`Administrator`, Manage Channels, Manage Roles, Kick Members, or Ban Members
permission is required.
