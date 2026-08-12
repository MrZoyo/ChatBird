# ChatBird Privacy Policy

Last updated: 2026-08-12

ChatBird is a Discord assistant available only in servers approved by its
operator. It is powered by Hermes Agent and Xiaomi MiMo. The bot is also known
as 小鸟聊天助手, 乌鸦, or ChatBird.

## What ChatBird Does

ChatBird responds to users when they explicitly mention or reply to the bot in
allowed Discord channels. It can answer questions, translate text, summarize
recent channel discussion, look up information, and explain server tools such as
Bird-Bot.

ChatBird is configured not to speak proactively. It should not post in channels
unless a user asks it to respond through a mention, reply, or another explicit
interaction.

Direct messages are not answered and are not sent to the conversational agent.
They are recorded in a private operator log for security and debugging.

## Data Processed

ChatBird may process the following Discord data:

- Discord user IDs, channel IDs, guild IDs, message IDs, and timestamps.
- Message content from messages that mention or reply to ChatBird.
- Attachments included with a request, such as images, audio, video, and
  supported documents.
- Recent channel context needed to answer a user request, such as summarizing a
  recent discussion.
- Bot interaction metadata, logs, and session context needed for operation,
  debugging, abuse prevention, and access control.
- Direct-message text and attachment metadata. Direct-message attachments are
  not downloaded by ChatBird.

## Why Message Content Is Needed

ChatBird is a conversational assistant. It needs message content to understand
the user's question, translate text, summarize discussion, and provide relevant
answers. Without message content access, ChatBird can receive message events but
cannot know what the user asked.

## How Data Is Used

Data is used only to operate ChatBird, provide requested replies, maintain
conversation continuity, debug issues, and enforce access control.

Message content, relevant context, and supported attachments may be sent to
Xiaomi MiMo API to generate responses. Discord data is not sold, not used for
advertising, and not used to train our own machine learning or AI models.

## Storage

ChatBird may store conversation context, selected long-term memory, logs, and
related metadata on a private server controlled by the bot operator. Stored
data is used for bot operation, debugging, continuity, and abuse prevention.
Server-channel sessions and long-term memory are separated by Discord guild ID;
one Discord server cannot recall another server's ChatBird memory. Users in the
same allowed channel share that channel's conversation history. Long-term
memory is divided into server-wide memory, per-user profiles within that
server, and a restricted administrator memory. Direct messages do not enter any
of these memories or the conversational agent.

Ordinary users cannot directly instruct ChatBird to write long-term memory.
ChatBird may choose to retain stable preferences or user characteristics, but
does not intentionally store ordinary users' task instructions, credentials,
or prompt-injection text as memory. Ordinary users are also restricted to
conversation, web lookup, supported attachment analysis, clarification, and
the limited memory function described above. Sensitive agent tools and
administrator memory are available only to the configured administrator in a
designated private administrator channel.

Direct-message logs are stored separately with restricted file permissions.
They contain message text and attachment metadata, but are not automatically
deleted after a fixed retention period. Users should therefore not send
sensitive information to ChatBird by direct message.

Access to the server-side bot configuration and logs is limited to authorized
administrators.

## User Choice

Users can avoid directly invoking ChatBird by not mentioning or replying to it.
When another user asks for a channel summary or supplies quoted context,
relevant recent messages may still be processed. The bot is configured to
respond only in allowed servers and channels and only when explicitly invoked.
Sending a direct message does not invoke the assistant, but the message is
still recorded as described above.

Users may contact their Discord server administrators or the bot operator to
request access restrictions, removal of stored bot data where practical, or
clarification about how ChatBird is used in the server.

## Data Sharing

ChatBird may send user prompts, relevant context, and supported attachments to
Xiaomi MiMo API to generate responses. We do not sell Discord data or share it
with advertisers.

## Contact

For privacy questions, contact the administrators of the Discord server where
ChatBird is installed or open an issue in this repository.
