from __future__ import annotations

import discord
from database import Database

async def send_modlog(guild: discord.Guild, db: Database, action: str, case_id: int, moderator: discord.abc.User, target: discord.abc.User | discord.Member | discord.Object, reason: str, duration: str | None = None) -> None:
    settings = db.settings(guild.id)
    channel_id = settings.get('log_channel_id')
    if not channel_id:
        return
    channel = guild.get_channel(int(channel_id))
    if not isinstance(channel, discord.TextChannel):
        return
    embed = discord.Embed(title=f'{action.title()} • Case #{case_id}', colour=discord.Colour.blurple(), timestamp=discord.utils.utcnow())
    embed.add_field(name='Target', value=f'{getattr(target, "mention", target)} (`{getattr(target, "id", "unknown")}`)', inline=False)
    embed.add_field(name='Moderator', value=f'{moderator.mention} (`{moderator.id}`)', inline=True)
    embed.add_field(name='Reason', value=reason[:1024], inline=False)
    if duration:
        embed.add_field(name='Duration', value=duration, inline=True)
    try:
        await channel.send(embed=embed)
    except discord.HTTPException:
        pass

async def dm_action(db: Database, guild: discord.Guild, target: discord.User | discord.Member, action: str, reason: str, moderator: discord.User | discord.Member, case_id: int, duration: str | None = None) -> None:
    if not db.settings(guild.id).get('dm_actions', 1):
        return
    embed = discord.Embed(title=f'Moderation action in {guild.name}', colour=discord.Colour.orange())
    embed.add_field(name='Action', value=action.title(), inline=True)
    embed.add_field(name='Case', value=f'#{case_id}', inline=True)
    embed.add_field(name='Reason', value=reason[:1024], inline=False)
    if duration:
        embed.add_field(name='Duration', value=duration, inline=True)
    embed.set_footer(text=f'Moderator: {moderator}')
    try:
        await target.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass
