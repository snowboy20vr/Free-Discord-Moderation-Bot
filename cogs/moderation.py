from __future__ import annotations

import re
from datetime import timedelta
import discord
from discord.ext import commands
from discord import app_commands

from utils.permissions import can_use, default_level
from utils.modlog import send_modlog, dm_action


def permission_check():
    async def predicate(ctx: commands.Context):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return False
        required = ctx.bot.db.get_command_level(ctx.guild.id, ctx.command.qualified_name, default_level(ctx.command.qualified_name))
        return can_use(ctx.author, required, ctx.bot.db.role_levels(ctx.guild.id))
    return commands.check(predicate)


def parse_duration(value: str) -> timedelta | None:
    match = re.fullmatch(r'(?i)(\d+)\s*([smhdw])', value.strip())
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2).lower()
    seconds = amount * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}[unit]
    return timedelta(seconds=seconds)


def duration_text(delta: timedelta) -> str:
    seconds = int(delta.total_seconds())
    for name, size in [('week', 604800), ('day', 86400), ('hour', 3600), ('minute', 60), ('second', 1)]:
        if seconds >= size:
            count = seconds // size
            return f'{count} {name}{"s" if count != 1 else ""}'
    return '0 seconds'


def hierarchy_ok(ctx, member: discord.Member) -> bool:
    return member != ctx.guild.owner and member != ctx.author and member.top_role < ctx.guild.me.top_role


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def record(self, ctx, action, target, reason, duration=None):
        case_id = self.bot.db.next_case(ctx.guild.id, action, target.id, ctx.author.id, reason, duration)
        await send_modlog(ctx.guild, self.bot.db, action, case_id, ctx.author, target, reason, duration)
        await dm_action(self.bot.db, ctx.guild, target, action, reason, ctx.author, case_id, duration)
        return case_id

    @commands.hybrid_command(name='warn', description='Warn a member and create a case.')
    @app_commands.describe(member='Member to warn', reason='Reason for the warning')
    @permission_check()
    async def warn(self, ctx, member: discord.Member, *, reason: str = 'No reason provided'):
        if not hierarchy_ok(ctx, member):
            return await ctx.send('❌ You cannot warn that member because of role hierarchy.', ephemeral=bool(ctx.interaction))
        warning_id = self.bot.db.add_warning(ctx.guild.id, member.id, ctx.author.id, reason)
        case_id = await self.record(ctx, 'warn', member, reason)
        await ctx.send(f'⚠️ Warned {member.mention}. Warning **#{warning_id}** • Case **#{case_id}**.')

    @commands.hybrid_command(name='warnings', description='View active warnings for a member.')
    @app_commands.describe(member='Member to inspect')
    @permission_check()
    async def warnings(self, ctx, member: discord.Member):
        rows = self.bot.db.warnings_for(ctx.guild.id, member.id)
        embed = discord.Embed(title=f'Warnings • {member}', colour=discord.Colour.orange())
        if not rows:
            embed.description = 'No active warnings.'
        else:
            embed.description = '\n'.join(f'**#{r["warning_id"]}** — {r["reason"][:180]}' for r in rows[:15])
            embed.set_footer(text=f'{len(rows)} active warning(s)')
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='clearwarnings', description='Clear all active warnings for a member.')
    @app_commands.describe(member='Member whose warnings should be cleared')
    @permission_check()
    async def clearwarnings(self, ctx, member: discord.Member):
        count = self.bot.db.clear_warnings(ctx.guild.id, member.id)
        await ctx.send(f'🧹 Cleared **{count}** active warning(s) for {member.mention}.')

    @commands.hybrid_command(name='kick', description='Kick a member.')
    @app_commands.describe(member='Member to kick', reason='Reason')
    @permission_check()
    async def kick(self, ctx, member: discord.Member, *, reason: str = 'No reason provided'):
        if not hierarchy_ok(ctx, member):
            return await ctx.send('❌ That member is above my role or your role.', ephemeral=bool(ctx.interaction))
        case_id = await self.record(ctx, 'kick', member, reason)
        try:
            await member.kick(reason=f'Case #{case_id} • {reason}')
        except discord.Forbidden:
            return await ctx.send('❌ Discord denied the kick. Check my Kick Members permission and role hierarchy.')
        await ctx.send(f'👢 Kicked {member.mention} • Case **#{case_id}**.')

    @commands.hybrid_command(name='ban', description='Ban a member.')
    @app_commands.describe(member='Member to ban', delete_days='Days of recent messages to delete', reason='Reason')
    @app_commands.rename(delete_days='delete_days')
    @permission_check()
    async def ban(self, ctx, member: discord.Member, delete_days: app_commands.Range[int, 0, 7] = 0, *, reason: str = 'No reason provided'):
        if not hierarchy_ok(ctx, member):
            return await ctx.send('❌ That member is above my role or your role.', ephemeral=bool(ctx.interaction))
        case_id = await self.record(ctx, 'ban', member, reason)
        try:
            await member.ban(reason=f'Case #{case_id} • {reason}', delete_message_seconds=int(delete_days) * 86400)
        except discord.Forbidden:
            return await ctx.send('❌ Discord denied the ban. Check my Ban Members permission and role hierarchy.')
        await ctx.send(f'🔨 Banned {member.mention} • Case **#{case_id}**.')

    @commands.hybrid_command(name='softban', description='Ban and immediately unban a member to remove recent messages.')
    @permission_check()
    async def softban(self, ctx, member: discord.Member, delete_days: app_commands.Range[int, 0, 7] = 1, *, reason: str = 'No reason provided'):
        if not hierarchy_ok(ctx, member):
            return await ctx.send('❌ That member is above my role or your role.', ephemeral=bool(ctx.interaction))
        case_id = await self.record(ctx, 'softban', member, reason)
        try:
            await member.ban(reason=f'Softban Case #{case_id} • {reason}', delete_message_seconds=int(delete_days) * 86400)
            await ctx.guild.unban(discord.Object(member.id), reason=f'Softban Case #{case_id}')
        except discord.Forbidden:
            return await ctx.send('❌ Discord denied the softban. Check Ban Members permission.')
        await ctx.send(f'🧹 Softbanned {member.mention} • Case **#{case_id}**.')

    @commands.hybrid_command(name='unban', description='Unban a user by ID or resolved user.')
    @permission_check()
    async def unban(self, ctx, user: discord.User, *, reason: str = 'No reason provided'):
        case_id = await self.record(ctx, 'unban', user, reason)
        try:
            await ctx.guild.unban(user, reason=f'Case #{case_id} • {reason}')
        except discord.NotFound:
            return await ctx.send('❌ That user is not banned.')
        except discord.Forbidden:
            return await ctx.send('❌ Discord denied the unban.')
        await ctx.send(f'🔓 Unbanned **{user}** • Case **#{case_id}**.')

    async def do_timeout(self, ctx, member, duration_value, reason, action='mute'):
        if not hierarchy_ok(ctx, member):
            await ctx.send('❌ That member is above my role or your role.', ephemeral=bool(ctx.interaction))
            return
        delta = parse_duration(duration_value)
        if not delta or delta.total_seconds() > 28 * 86400:
            await ctx.send('❌ Duration must be between 1s and 28d, like `10m`, `2h`, or `7d`.', ephemeral=bool(ctx.interaction))
            return
        case_id = await self.record(ctx, action, member, reason, duration_text(delta))
        try:
            await member.timeout(delta, reason=f'Case #{case_id} • {reason}')
        except discord.Forbidden:
            return await ctx.send('❌ Discord denied the timeout. Check Moderate Members permission and role hierarchy.')
        await ctx.send(f'🔇 Timed out {member.mention} for **{duration_text(delta)}** • Case **#{case_id}**.')

    @commands.hybrid_command(name='mute', description='Timeout a member.')
    @permission_check()
    async def mute(self, ctx, member: discord.Member, duration: str = '10m', *, reason: str = 'No reason provided'):
        await self.do_timeout(ctx, member, duration, reason, 'mute')

    @commands.hybrid_command(name='timeout', description='Timeout a member.')
    @permission_check()
    async def timeout(self, ctx, member: discord.Member, duration: str = '10m', *, reason: str = 'No reason provided'):
        await self.do_timeout(ctx, member, duration, reason, 'timeout')

    @commands.hybrid_command(name='unmute', description='Remove a member timeout.')
    @permission_check()
    async def unmute(self, ctx, member: discord.Member, *, reason: str = 'No reason provided'):
        if not hierarchy_ok(ctx, member):
            return await ctx.send('❌ That member is above my role or your role.', ephemeral=bool(ctx.interaction))
        case_id = await self.record(ctx, 'unmute', member, reason)
        try:
            await member.timeout(None, reason=f'Case #{case_id} • {reason}')
        except discord.Forbidden:
            return await ctx.send('❌ Discord denied removing the timeout.')
        await ctx.send(f'🔊 Removed timeout from {member.mention} • Case **#{case_id}**.')

    @commands.hybrid_command(name='purge', description='Delete recent messages.')
    @app_commands.describe(amount='Number of messages to delete, up to 100')
    @permission_check()
    async def purge(self, ctx, amount: app_commands.Range[int, 1, 100]):
        if not isinstance(ctx.channel, discord.TextChannel):
            return await ctx.send('❌ This command only works in text channels.', ephemeral=bool(ctx.interaction))
        if not ctx.channel.permissions_for(ctx.guild.me).manage_messages:
            return await ctx.send('❌ I need Manage Messages here.', ephemeral=bool(ctx.interaction))
        if ctx.interaction:
            await ctx.defer(ephemeral=True)
            deleted = await ctx.channel.purge(limit=amount)
            await ctx.followup.send(f'🧹 Deleted **{len(deleted)}** message(s).', ephemeral=True)
        else:
            await ctx.message.delete()
            deleted = await ctx.channel.purge(limit=amount)
            await ctx.send(f'🧹 Deleted **{len(deleted)}** message(s).', delete_after=3)

    @commands.hybrid_command(name='slowmode', description='Set channel slowmode.')
    @app_commands.describe(seconds='Slowmode seconds, 0 disables it')
    @permission_check()
    async def slowmode(self, ctx, seconds: app_commands.Range[int, 0, 21600]):
        if not isinstance(ctx.channel, discord.TextChannel):
            return await ctx.send('❌ This only works in text channels.', ephemeral=bool(ctx.interaction))
        await ctx.channel.edit(slowmode_delay=int(seconds), reason=f'Changed by {ctx.author}')
        await ctx.send(f'🐢 Slowmode set to **{seconds}s**.')

    @commands.hybrid_command(name='lock', description='Lock the current channel.')
    @permission_check()
    async def lock(self, ctx):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f'Locked by {ctx.author}')
        await ctx.send('🔒 Channel locked.')

    @commands.hybrid_command(name='unlock', description='Unlock the current channel.')
    @permission_check()
    async def unlock(self, ctx):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f'Unlocked by {ctx.author}')
        await ctx.send('🔓 Channel unlocked.')

    @commands.hybrid_command(name='nick', description='Change or clear a member nickname.')
    @permission_check()
    async def nick(self, ctx, member: discord.Member, nickname: str | None = None):
        if not hierarchy_ok(ctx, member):
            return await ctx.send('❌ That member is above my role or your role.', ephemeral=bool(ctx.interaction))
        await member.edit(nick=nickname, reason=f'Nickname changed by {ctx.author}')
        await ctx.send(f'✏️ Updated nickname for {member.mention}.')

async def setup(bot):
    await bot.add_cog(Moderation(bot))
