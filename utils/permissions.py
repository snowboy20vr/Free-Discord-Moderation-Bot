from __future__ import annotations

import discord
from config import OWNER_IDS

# Lower number = MORE POWER.
LEVEL_NAMES = {
    1: 'Owner / Full Control',
    2: 'Administrator',
    3: 'Senior Moderator',
    4: 'Moderator',
    5: 'Trial Moderator',
}

DEFAULT_LEVELS = {
    'help': 5,
    'ping': 5,
    'level': 5,
    'userinfo': 5,
    'serverinfo': 5,
    'warn': 4,
    'warnings': 4,
    'clearwarnings': 3,
    'kick': 3,
    'mute': 3,
    'timeout': 3,
    'unmute': 3,
    'ban': 2,
    'unban': 2,
    'softban': 2,
    'purge': 4,
    'slowmode': 3,
    'lock': 3,
    'unlock': 3,
    'nick': 3,
    'config': 2,
    'setpermissionlevel': 1,
    'setrolelevel': 1,
    'setprefix': 1,
    'setlogchannel': 1,
    'setmuterole': 1,
    'setlevelname': 1,
}

def highest_level(member: discord.Member, role_levels: dict[int, int]) -> int:
    if member.id in OWNER_IDS or member.guild.owner_id == member.id:
        return 1
    if member.guild_permissions.administrator:
        return 2
    configured = [role_levels.get(role.id) for role in member.roles if role_levels.get(role.id) is not None]
    return min(configured) if configured else 999

def can_use(member: discord.Member, required: int, role_levels: dict[int, int]) -> bool:
    return highest_level(member, role_levels) <= required

def default_level(command_name: str) -> int:
    return DEFAULT_LEVELS.get(command_name.lower().lstrip('/'), 4)
