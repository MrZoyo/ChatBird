# Discord Intents and Permissions

ChatBird should be installed with OAuth scopes `bot` and
`applications.commands`. Grant permissions per channel instead of giving the
bot broad server-wide access.

## Gateway Intents

### Required

- **Message Content Intent**: needed to read ordinary message text, replies,
  captions, and attachment metadata when users talk to the bot.

### Conditional

- **Server Members Intent**: enable it when `DISCORD_ALLOWED_ROLES` is used,
  when allowlists contain usernames instead of numeric IDs, or when features
  need member/role lookup. Hermes only requests this intent in those cases.
- **Presence Intent**: not needed. Enable it only if a future feature actually
  reads online status or user activities.

Hermes also requests normal guild messages, direct messages, and voice-state
events. These are not privileged intents.

## Minimum Text and Attachment Permissions

- View Channels
- Send Messages
- Read Message History
- Embed Links
- Attach Files
- Add Reactions, if processing/status reactions remain enabled

These Discord permissions let the bot receive text, images, Discord voice
messages, audio, video, PDFs, Office documents, archives, and other
attachments. ChatBird disables automatic thread creation, so it does not need
Create Public Threads or Send Messages in Threads for normal operation.
Attachments do not require a separate privileged intent;
they arrive with message events.

Receiving an attachment is separate from parsing it or sending its contents to
the configured model provider. Hermes only processes supported media and
document types by default. Enabling `allow_any_attachment` under
`platforms.discord.extra` would widen that data-processing scope and requires
an explicit privacy decision. Keep it disabled unless that is intended, and
keep `max_attachment_bytes` at 32 MiB or lower on the production host.

## Optional Voice-Channel Permissions

Only grant these if ChatBird will join live voice channels:

- Connect
- Speak
- Use Voice Activity

Live transcription also needs a speech-to-text provider and meaningful CPU and
memory. Continuous voice listening is not recommended on the current small
server. Receiving a voice-message attachment does not require voice-channel
permissions.

## Permissions Not Granted by Default

Do not grant Administrator. ChatBird also does not need Manage Server, Mention
Everyone, Kick Members, or Ban Members for conversational and attachment
features. Add Manage Messages, Manage Threads, Manage Channels, Manage Roles,
or Moderate Members only when a separately reviewed moderation feature truly
needs it.

Use four access layers for public deployment: `allowed_guilds`, then
`allowed_channels`, mention-required mode, then the request-scoped ChatBird
tool policy. Normal Guild members may chat, but sensitive tools require both
the administrator user ID and a private administrator channel ID. Leave
`@everyone` and role mentions disabled.

The private administrator channel needs only View Channel, Send Messages, and
Read Message History for the Bot role. Keep ordinary members unable to view
that channel; otherwise sensitive replies would enter a transcript they can
read.
