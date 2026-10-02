from __future__ import annotations

import discord
from config import OWNER_IDS

LEVEL_NAMES = {
    1: 'Trial Moderator',
    2: 'Moderator',
    3: 'Senior Moderator',
    4: 'Administrator',
    5: 'Owner',
}

DEFAULT_LEVELS = {
    'help': 1,
    'ping': 1,
    'level': 1,
    'userinfo': 1,
    'serverinfo': 1,
    'warn': 2,
    'warnings': 2,
    'clearwarnings': 3,
    'kick': 3,
    'mute': 3,
    'timeout': 3,
    'unmute': 3,
    'ban': 4,
    'unban': 4,
    'softban': 4,
    'purge': 2,
    'slowmode': 3,
    'lock': 3,
    'unlock': 3,
    'nick': 3,
    'config': 4,
    'setpermissionlevel': 5,
    'setrolelevel': 5,
    'setprefix': 5,
    'setlogchannel': 5,
    'setmuterole': 5,
}

def highest_level(member: discord.Member, role_levels: dict[int, int]) -> int:
    if member.id in OWNER_IDS or member.guild.owner_id == member.id or member.guild_permissions.administrator:
        return 5
    return max((role_levels.get(role.id, 0) for role in member.roles), default=0)

def can_use(member: discord.Member, required: int, role_levels: dict[int, int]) -> bool:
    return highest_level(member, role_levels) >= required

def default_level(command_name: str) -> int:
    return DEFAULT_LEVELS.get(command_name.lower().lstrip('/'), 3)
