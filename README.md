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
