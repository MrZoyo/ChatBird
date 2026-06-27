# Bird-Bot Guide for ChatBird

This is a concise reference for answering questions about Bird-Bot in Discord.
Source repository: https://github.com/MrZoyo/Bird-Bot

## What Bird-Bot Is

Bird-Bot is a custom Discord server management and community bot for the Bird Gaming server. It replaces several public bots with local, server-specific features. It is designed for a single server and stores its data locally.

Current documented version: `1.9.1`.

## Setup Summary

For maintainers:

1. Clone the repo.
2. Create a Python 3.12.3 virtual environment, preferably with `uv venv --python 3.12.3`.
3. Install locked dependencies with `uv pip sync requirements.lock`.
4. Copy needed `bot/config/config_*.json.example` files to `config_*.json`.
5. Fill bot token, guild IDs, channel IDs, role IDs, and feature config.
6. Use `config_main.json` `features` to enable only needed modules.
7. Enable Discord privileged intents: Server Members Intent, Presence Intent, and Message Content Intent.
8. Run `python run.py`.

Do not expose or invent real tokens, IDs, or config values when answering users.

## Main Features and Commands

### Voice Channels

Creates temporary voice rooms when users join configured entry channels. Deletes bot-created temp rooms when empty.

Commands:

- `/check_temp_channel_records`
- `/vc_add <channel>`
- `/vc_remove [channel] [channel_id]`
- `/vc_list`

Notable controls include unlock, lock, full, and soundboard buttons in the room panel.

### Invitations and Team-Up

Detects team-up messages and creates invitation links to the user's current voice room. Also supports user signatures and ignore lists.

Commands:

- `/invt <title>`
- `/invt_checkignorelist`
- `/invt_addignorelist <channel>`
- `/invt_removeignorelist [channel] [channel_id]`

### Welcome

Sends welcome messages and images for new members and can DM new users.

Command:

- `/testwelcome <member> <member_number>`

### Status and Logs

Provides voice status, log viewing, and member location checks.

Commands:

- `/check_log <number=x> [log_type=main]`
- `/check_voice_status`
- `/where_is <member>`
- `/print_voice_status`
- `/test_keyword_log [test_message]`

### Achievements

Tracks messages, reactions, voice time, monthly stats, rankings, and manual admin adjustments.

Commands:

- `/achievements [member] [date]`
- `/increase_achievement <member> [reactions] [messages] [time_spent]`
- `/decrease_achievement <member> [reactions] [messages] [time_spent]`
- `/achievement_ranking [date]`
- `/check_achi_op`
- `/rank`

### Roles

Role pickup and management for achievements, star signs, MBTI, gender, and signatures.

Commands:

- `/create_role_pickup <channel>`
- `/create_starsign_pickup <channel>`
- `/create_mbti_pickup <channel>`
- `/create_gender_pickup <channel>`
- `/create_signature_pickup <channel>`
- `/signature_permission_toggle <user_id> <disable>`
- `/signature_clear <user_id>`
- `/signature_set_requirement <minutes>`
- `/signature_check <user_id>`

### Notebook

Admin event logging for member incidents and moderation records.

Commands:

- `/notebook_log <member> <event>`
- `/notebook_member <member>`
- `/notebook_all`
- `/notebook_delete <member> <event_serial_number>`

### Backups

Automated database backups every 6 hours and manual backup support.

Command:

- `/backup_now`

### Giveaways

Giveaways with requirements, time controls, winner selection, archive, and participant tools.

Commands:

- `/ga_create <reaction_req> <message_req> <timespent_req>`
- `/ga_cancel <giveaway_id>`
- `/ga_end <giveaway_id>`
- `/ga_time_extend <giveaway_id> <time>`
- `/ga_participant <giveaway_id>`
- `/ga_description <giveaway_id> <description>`
- `/ga_sendtowinner <giveaway_id>`

### Ratings

Legacy 10-point anonymous rating system.

Commands:

- `/rt_create`
- `/rt_end <rating_id>`
- `/rt_cancel <rating_id>`
- `/rt_description <rating_id> <description>`

### Team-Up Display Board

Maintains a real-time team-up board with auto-refresh and game type categorization.

Commands:

- `/teamup_init <channel>`
- `/teamup_type_add <channel> <game_type>`
- `/teamup_type_delete [channel] [channel_id]`
- `/teamup_type_list`

### Tickets

Modern ticket system based on Discord threads, admin permissions, status buttons, and stats.

Commands:

- `/tickets_init`
- `/tickets_new_stats`
- `/tickets_admin_list`
- `/tickets_admin_add_role <role>`
- `/tickets_admin_remove_role <role>`
- `/tickets_admin_add_user <user>`
- `/tickets_admin_remove_user <user>`
- `/tickets_new_add_user <user>`
- `/tickets_new_accept`
- `/tickets_new_close <reason>`
- `/tickets_refresh_buttons`
- `/tickets_refresh_main`

Legacy archive command:

- `/tickets_archive`

### Shop and Check-In

Points, daily check-in, makeup check-in, transaction history, and admin balance controls.

Commands:

- `/create_checkin_embed <channel>`
- `/checkin_history <user>`
- `/balance_change <user>`
- `/balance_history [user]`

### Private Rooms

Point-based private room purchase, restoration, renewal reminders, cleanup, and ban controls.

Commands:

- `/privateroom_init`
- `/privateroom_setup <channel>`
- `/privateroom_reset`
- `/privateroom_list`
- `/privateroom_ban <user>`

### Games

DnD dice:

- `/dnd_roll <expression> [x]`

Spy mode:

- `/spy_mode <team_size> <spy>`

### Ban and Moderation

Permanent ban, temporary ban, mute, notification settings, and admin permission management.

Commands:

- `/ban <user> <reason> [delete_message_days]`
- `/tempban <user> <duration> <reason> [delete_message_days]`
- `/mute <user> <duration> <reason>`
- `/ban_list_tempbans`
- `/ban_admin_list`
- `/ban_admin_add_role <role>`
- `/ban_admin_delete_role <role>`
- `/ban_admin_add_user <user>`
- `/ban_admin_delete_user <user>`
- `/ban_set_notification_channel <channel>`
- `/ban_remove_notification_channel`
- `/ban_set_invite_link <invite_link>`
- `/ban_remove_invite_link`

## Answering Guidance

When users ask about Bird-Bot:

- Prefer short Chinese answers unless the user asks otherwise.
- Explain the relevant command and what it does.
- If a command is admin-only or dangerous, say so clearly.
- Do not claim current server configuration unless you have checked it.
- Do not run moderation, permission, role, ticket, or config-changing actions unless explicitly asked by an authorized user.
