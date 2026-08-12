# Discord Privileged Intent Application Notes

These notes are prepared for the Discord Developer Portal privileged intent
application for ChatBird.

## App Description

ChatBird is a Discord chat assistant based on Hermes Agent. The bot is also
known as 小鸟聊天助手 or 乌鸦. It runs only in servers approved by the operator
and helps users with question answering, translation, information lookup,
channel message summaries, and explanations of server tools such as Bird-Bot.

ChatBird does not proactively speak. It is configured to respond only when a
user explicitly mentions or replies to the bot, and only in allowed channels.
Responses are generated through Hermes Agent using Xiaomi MiMo API.

Only members of operator-approved Discord servers and channels can use the bot.
Direct messages are not answered and are not sent to Hermes Agent; their text
and attachment metadata are retained in a private security and debugging log.

## Public Privacy Policy

Privacy policy URL: `https://github.com/MrZoyo/ChatBird/blob/main/PRIVACY.md`

Summary:

ChatBird only begins responding when users mention or reply to the bot in
allowed channels. A request such as a channel summary may include relevant
recent messages from other users. Message content and supported attachments may
be sent to Xiaomi MiMo API to generate responses and may be stored on our
private server for conversation context, per-server long-term memory,
debugging, access control, and service operation. Sessions and memory are
isolated by Discord guild ID. Data is not sold, not used for advertising, and
not used to train our own machine learning models. Direct messages are logged
but not sent to the response model, and their attachments are not downloaded.

## Requested Intents

Requested:

- Server Members Intent
- Message Content Intent

Not requested:

- Presence Intent

ChatBird does not need Presence Intent because it does not track user online
status, activity, or rich presence.

## Server Members Intent

### Why Server Members Intent Is Needed

ChatBird needs Server Members Intent to identify and authorize server members.
Hermes Agent's Discord gateway uses member and role information to enforce user
and role allowlists, ensuring that only authorized users can interact with the
assistant.

The bot does not bulk scrape the member list, profile users, target ads, or
analyze member behavior. Member data is used only for access control, security
checks, and correct Discord server context.

### Demo Evidence

Screenshots or video should show:

1. The bot responding only to an authorized user.
2. Unauthorized users being ignored or denied.
3. The bot operating in the intended server context.

### External Storage

Answer: Yes.

Explanation:

We may store user IDs, role IDs, channel IDs, message IDs, and conversation
metadata on our private server for access control, debugging, session
continuity, and bot operation. The bot is available to all members only within
operator-approved servers and channels. We do not sell this data or use it for
advertising. Access is limited to authorized server administrators.

## Message Content Intent

### User Opt-Out

Answer: Yes.

Explanation:

Users can avoid directly invoking ChatBird by not mentioning or replying to it.
Relevant recent messages may still be processed when another user explicitly
requests a channel summary. The bot is configured to respond only when invoked,
and only in allowed servers and channels. Users may also ask server
administrators to restrict or remove bot access where practical.

Direct messages do not invoke the assistant and receive no response. Their text
and attachment metadata are nevertheless recorded in a private operator log;
direct-message attachments are not downloaded.

### External Storage

Answer: Yes.

Explanation:

Message content may be stored on our private server as Hermes Agent conversation
context, per-server long-term memory, and logs for debugging, continuity, and
abuse prevention. Message content and supported attachments may also be sent to
Xiaomi MiMo API to generate replies. We do not sell message content and do not
use it for advertising.

Within an allowed server, users in the same channel share conversation history.
Long-term memory is separated into server-wide memory, per-user profiles within
that server, and restricted administrator memory. Direct-message logs have no
fixed automatic deletion period, but do not enter agent context or long-term
memory.

### Machine Learning or AI Training

Answer: No.

Explanation:

Message content is used only to generate responses for the user's request
through Xiaomi MiMo API. We do not use Discord message content to train our own
machine learning or AI models.

### Why Message Content Intent Is Needed

ChatBird is a conversational assistant. It needs Message Content Intent to read
the text of messages that mention or reply to the bot, so it can answer
questions, translate text, summarize recent channel discussion, and help users
understand server tools such as Bird-Bot.

Without Message Content Intent, the bot can receive message events but cannot
read what the user asked, making the assistant unusable. The bot is configured
to avoid passive monitoring: it only responds when explicitly mentioned or
replied to, and only in allowed channels.

### Demo Evidence

Screenshots or video should show:

1. A user mentions ChatBird with a question.
2. ChatBird reads the message and replies.
3. A user asks for a summary of recent channel discussion.
4. ChatBird produces a concise summary.
5. Normal messages that do not mention ChatBird are ignored.

## Suggested Portal Answers

### Does the app have a public privacy policy?

Yes.

Use:

`https://github.com/MrZoyo/ChatBird/blob/main/PRIVACY.md`

### Which privileged intents are requested?

Select:

- Server Members Intent
- Message Content Intent

Do not select Presence Intent.

### Does the app store API data outside Discord?

For Server Members Intent: Yes.

For Message Content Intent: Yes.

### Does the app use message content to train ML or AI models?

No.
