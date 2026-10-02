# Free Discord Moderation Bot

A free, self-hostable Discord moderation bot built with discord.py. It combines slash commands, configurable prefix commands, persistent SQLite settings, per-command permission levels, moderation logging, cases, timeout, purge, slowmode, lock/unlock, warnings, softban and a Components V2 config panel.

## Features
- Slash commands and configurable prefix commands
- Components V2 /config dashboard
- Permission levels 1-5 per command
- Configurable moderator roles for levels 1-5
- /setpermissionlevel command 1-5
- /setrolelevel role 1-5
- Warn, kick, ban, unban, softban, timeout/mute, unmute
- Purge, slowmode, lock, unlock, nick
- Persistent moderation cases and warnings
- Moderation log channel
- Optional DM notices for moderation actions
- Per-server prefix
- SQLite storage with no external database required

## Setup
1. Create a Discord application and bot.
2. Enable Message Content Intent if you want prefix commands.
3. Copy .env.example to .env and set DISCORD_TOKEN.
4. Install dependencies with: python -m pip install -r requirements.txt
5. Start with: python bot.py
6. Invite the bot with the permissions it needs.

## Permission levels
1 = Trial Moderator
2 = Moderator
3 = Senior Moderator
4 = Administrator
5 = Owner

The server owner, configured owner IDs and Discord Administrators are always treated as level 5. Other users receive levels through configured roles using /setrolelevel.

The custom permission system does not replace Discord permissions. A user must pass both the custom level and the underlying Discord permission required for an action.


## Planned settings
The configuration dashboard includes server-wide punishment and logging settings.


# Complete Command Guide

## Moderation commands

### /warn — warn a member
Adds an active warning and creates a case.
Prefix: **.warn @User reason**
Example: **.warn @User spamming**

### /warnings — view warnings
Shows active warnings for a member.
Prefix: **.warnings @User**

### /clearwarnings — clear warnings
Removes all active warnings from a member.
Prefix: **.clearwarnings @User**

### /kick — kick a member
Kicks the member. With prefix commands, the command message is deleted and the bot does not leave a public response.
Prefix: **.kick @User reason**
Kick does not support a temporary duration.

### /ban — permanent or temporary ban
The final word can be a duration.

**Temporary:** **.ban 123456789 spam 1d**

**Permanent:** **.ban 123456789 spam**

Supported duration units are **s**, **m**, **h**, **d**, and **w**.

The number of recent days of messages removed by a ban is configured in **/config → Settings**.

### /softban — remove recent messages without keeping the ban
The bot bans the member and immediately removes the ban. This is useful when you want recent messages removed without leaving the member banned.
Prefix: **.softban @User spam**

### /unban — remove a ban
Unbans a user by mention, username resolution, or user ID where Discord can resolve it.
Prefix: **.unban 123456789 appeal approved**

### /mute and /timeout — temporary timeout
These use Discord's native timeout system.
Prefix examples:
- **.mute 123456789 spam 1h**
- **.timeout 123456789 flooding 30m**
- **.mute 123456789 repeated spam 1d**

A duration is required for a timeout. Discord timeouts have a 28-day maximum.

### /unmute — remove a timeout
Removes the current timeout.
Prefix: **.unmute @User appeal approved**

## Channel commands

### /purge
Deletes 1-100 recent messages. The prefix invocation is deleted and the prefix version intentionally leaves no bot confirmation.
Prefix: **.purge 50**

### /slowmode
Sets channel slowmode in seconds. Use 0 to disable it.
Prefix: **.slowmode 10**

### /lock
Prevents the default @everyone role from sending messages in the current channel.
Prefix: **.lock**

### /unlock
Restores normal @everyone sending permissions.
Prefix: **.unlock**

### /nick
Changes or clears a member nickname.
Prefix: **.nick @User New Name**
Use no nickname after the member to clear it.

## Information commands

### /ping
Shows latency and the number of servers.
Prefix: **.ping**

### /userinfo
Shows account, join, role, ID, and bot information.
Prefix: **.userinfo @User**

### /serverinfo
Shows server owner, member count, channel count, role count, verification level, and creation time.
Prefix: **.serverinfo**

### /level
Shows the effective custom moderation level for a member.
Prefix: **.level @User**

### /help
Shows the command guide inside Discord.
Prefix: **.help**

## Configuration commands

### /config
Opens the Components V2 server control center.

The dashboard has:
- **Home** — quick setup status
- **Roles** — select Discord roles and assign levels
- **Permissions** — choose a command and change its required level
- **Settings** — punishment behavior
- **Server** — prefix and moderation logs

The selected tab is disabled, and every dashboard selection edits the same message and saves immediately.

### /setpermissionlevel
Sets the required custom level for a command.
Example: **/setpermissionlevel command:ban level:2**

### /setrolelevel
Assigns a Discord role a custom level.
Example: **/setrolelevel role:@Moderators level:4**

### /setprefix
Changes the server prefix.
Example: **/setprefix prefix:.**

### /setlogchannel
Sets or clears the moderation log channel.
Example: **/setlogchannel channel:#mod-logs**

### /setmuterole
Sets or clears the legacy mute role setting.

## Permission levels

The bot uses **1 as the highest level** and **5 as the lowest**:

1. **Level 1 — Owner / Full Control**
2. **Level 2 — Administrator**
3. **Level 3 — Senior Moderator**
4. **Level 4 — Moderator**
5. **Level 5 — Trial Moderator**

If **/ban** requires Level 2:
- Level 1 can use it
- Level 2 can use it
- Levels 3, 4, and 5 cannot use it

The bot also checks Discord permissions and role hierarchy. Custom levels never grant Discord permissions the bot or member does not actually have.

## Punishment settings

The Settings page is designed so a new server owner does not need to edit IDs or code.

### Require Reasons
When enabled, punishment commands require a reason.

### Moderation DMs
When enabled, the bot attempts to DM the affected user with the action, reason, case number, and duration.

### Ban Message Deletion
Choose 0-7 days of recent messages to remove when a ban is issued.

### Softban Message Deletion
Choose 0-7 days of recent messages to remove during a softban.

## Cases

Punishments create persistent case numbers.

A case stores:
- action
- target
- moderator
- reason
- duration when applicable
- timestamp

Temporary bans are stored in SQLite so the bot can still process the expiration after a restart.

## Recommended first setup

1. Run **/config**.
2. Open **Roles** and assign your staff roles.
3. Open **Permissions** and change command levels if needed.
4. Open **Settings** and decide whether reasons and moderation DMs are required.
5. Set ban and softban message deletion.
6. Open **Server** and set your prefix and moderation log channel.
7. Test **/level**, **/warn**, and **/config** before giving staff access.
