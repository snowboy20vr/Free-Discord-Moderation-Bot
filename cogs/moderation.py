from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import commands, tasks
from discord import app_commands

from utils.permissions import can_use, default_level, highest_level
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


def split_reason_duration(details: str | None) -> tuple[str, timedelta | None]:
    details = (details or '').strip()
    if not details:
        return '', None
    parts = details.split()
    possible = parse_duration(parts[-1])
    if possible:
        return ' '.join(parts[:-1]).strip(), possible
    return details, None


def hierarchy_ok(ctx, member: discord.Member) -> bool:
    if member == ctx.guild.owner or member == ctx.author:
        return False
    if ctx.guild.me and member.top_role >= ctx.guild.me.top_role:
        return False
    moderator_level = highest_level(ctx.author, ctx.bot.db.role_levels(ctx.guild.id))
    target_level = highest_level(member, ctx.bot.db.role_levels(ctx.guild.id))
    return target_level > moderator_level


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.expiration_worker.start()

    def cog_unload(self):
        self.expiration_worker.cancel()

    @tasks.loop(minutes=1)
    async def expiration_worker(self):
        for item in self.bot.db.due_temp_punishments():
            guild = self.bot.get_guild(int(item['guild_id']))
            if guild and item['action'] == 'ban':
                try:
                    await guild.unban(
                        discord.Object(int(item['user_id'])),
                        reason=f"Temporary ban Case #{item['case_id']} expired",
                    )
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass
            self.bot.db.remove_temp_punishment(item['guild_id'], item['user_id'], item['action'])

    @expiration_worker.before_loop
    async def before_expiration_worker(self):
        await self.bot.wait_until_ready()

    async def require_reason(self, ctx, reason: str) -> bool:
        if self.bot.db.settings(ctx.guild.id).get('require_reason', 1) and not reason.strip():
            await ctx.send('❌ A reason is required for this punishment.', ephemeral=bool(ctx.interaction))
            return False
        return True

    async def finish_silent(self, ctx, text: str):
        if ctx.interaction:
            await ctx.send(text, ephemeral=True)
        elif ctx.message:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass

    async def record(self, ctx, action, target, reason, duration=None):
        case_id = self.bot.db.next_case(ctx.guild.id, action, target.id, ctx.author.id, reason, duration)
        await send_modlog(ctx.guild, self.bot.db, action, case_id, ctx.author, target, reason, duration)
        await dm_action(self.bot.db, ctx.guild, target, action, reason, ctx.author, case_id, duration)
        return case_id

    @commands.hybrid_command(name='warn', description='Warn a member and create a case.')
    @app_commands.describe(member='Member to warn', reason='Reason for the warning')
    @permission_check()
    async def warn(self, ctx, member: discord.Member, *, reason: str = ''):
        if not await self.require_reason(ctx, reason):
            return
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
    async def kick(self, ctx, member: discord.Member, *, reason: str = ''):
        if not await self.require_reason(ctx, reason):
            return
        if not hierarchy_ok(ctx, member):
            return await ctx.send('❌ That member is above my role or your role.', ephemeral=bool(ctx.interaction))
        case_id = await self.record(ctx, 'kick', member, reason)
        try:
            await member.kick(reason=f'Case #{case_id} • {reason}')
        except discord.Forbidden:
            return await ctx.send('❌ Discord denied the kick. Check my Kick Members permission and role hierarchy.')
        await self.finish_silent(ctx, f'👢 Kicked {member} • Case #{case_id}.')

    @commands.hybrid_command(name='ban', description='Ban a member.')
    @app_commands.describe(member='Member to ban', details='Reason, optionally ending with a duration such as 1d')
    @permission_check()
    async def ban(self, ctx, member: discord.Member, *, details: str = ''):
        reason, duration = split_reason_duration(details)
        if not await self.require_reason(ctx, reason):
            return
        if not hierarchy_ok(ctx, member):
            return await ctx.send('❌ That member is above my role or your role.', ephemeral=bool(ctx.interaction))
        settings = self.bot.db.settings(ctx.guild.id)
        delete_days = max(0, min(7, int(settings.get('ban_delete_days', 1))))
        case_id = await self.record(ctx, 'ban', member, reason, duration)
        try:
            await member.ban(reason=f'Case #{case_id} • {reason}', delete_message_seconds=delete_days * 86400)
        except discord.Forbidden:
            return await ctx.send('❌ Discord denied the ban. Check my Ban Members permission and role hierarchy.', ephemeral=bool(ctx.interaction))
        if duration:
            self.bot.db.add_temp_punishment(ctx.guild.id, member.id, 'ban', case_id, datetime.now(timezone.utc) + duration)
        status = f'for {duration_text(duration)}' if duration else 'permanently'
        await self.finish_silent(ctx, f'🔨 Banned {member} {status} • Case #{case_id}.')

    @commands.hybrid_command(name='softban', description='Ban and immediately unban a member to remove recent messages.')
    @permission_check()
    async def softban(self, ctx, member: discord.Member, *, reason: str = ''):
        if not await self.require_reason(ctx, reason):
            return
        if not hierarchy_ok(ctx, member):
            return await ctx.send('❌ That member is above my role or your role.', ephemeral=bool(ctx.interaction))
        settings = self.bot.db.settings(ctx.guild.id)
        delete_days = max(0, min(7, int(settings.get('softban_delete_days', 1))))
        case_id = await self.record(ctx, 'softban', member, reason)
        try:
            await member.ban(reason=f'Softban Case #{case_id} • {reason}', delete_message_seconds=delete_days * 86400)
            await ctx.guild.unban(discord.Object(member.id), reason=f'Softban Case #{case_id}')
        except discord.Forbidden:
            return await ctx.send('❌ Discord denied the softban. Check Ban Members permission.', ephemeral=bool(ctx.interaction))
        await self.finish_silent(ctx, f'🧹 Softbanned {member} • Case #{case_id}.')

    @commands.hybrid_command(name='unban', description='Unban a user by ID or resolved user.')
    @permission_check()
    async def unban(self, ctx, user: discord.User, *, reason: str = ''):
        if not await self.require_reason(ctx, reason):
            return
        case_id = await self.record(ctx, 'unban', user, reason)
        try:
            await ctx.guild.unban(user, reason=f'Case #{case_id} • {reason}')
        except discord.NotFound:
            return await ctx.send('❌ That user is not banned.')
        except discord.Forbidden:
            return await ctx.send('❌ Discord denied the unban.')
        await self.finish_silent(ctx, f'🔓 Unbanned {user} • Case #{case_id}.')

    async def do_timeout(self, ctx, member, duration_value, reason, action='mute'):
        if isinstance(duration_value, timedelta):
            delta = duration_value
        else:
            reason, delta = split_reason_duration(f'{reason} {duration_value}'.strip())
        if not delta:
            await ctx.send('❌ A timeout duration is required at the end, like spam 1d.', ephemeral=bool(ctx.interaction))
            return
        if not await self.require_reason(ctx, reason):
            return
        if not hierarchy_ok(ctx, member):
            await ctx.send('❌ That member is above my role or your role.', ephemeral=bool(ctx.interaction))
            return
        if not delta or delta.total_seconds() > 28 * 86400:
            await ctx.send('❌ Duration must be between 1s and 28d, like `10m`, `2h`, or `7d`.', ephemeral=bool(ctx.interaction))
            return
        case_id = await self.record(ctx, action, member, reason, duration_text(delta))
        try:
            await member.timeout(delta, reason=f'Case #{case_id} • {reason}')
        except discord.Forbidden:
            return await ctx.send('❌ Discord denied the timeout. Check Moderate Members permission and role hierarchy.')
        await self.finish_silent(ctx, f'🔇 Timed out {member} for {duration_text(delta)} • Case #{case_id}.')

    @commands.hybrid_command(name='mute', description='Timeout a member.')
    @permission_check()
    async def mute(self, ctx, member: discord.Member, *, details: str = ''):
        reason, duration = split_reason_duration(details)
        await self.do_timeout(ctx, member, duration or '', reason, 'mute')

    @commands.hybrid_command(name='timeout', description='Timeout a member.')
    @permission_check()
    async def timeout(self, ctx, member: discord.Member, *, details: str = ''):
        reason, duration = split_reason_duration(details)
        await self.do_timeout(ctx, member, duration or '', reason, 'timeout')

    @commands.hybrid_command(name='unmute', description='Remove a member timeout.')
    @permission_check()
    async def unmute(self, ctx, member: discord.Member, *, reason: str = ''):
        if not await self.require_reason(ctx, reason):
            return
        if not hierarchy_ok(ctx, member):
            return await ctx.send('❌ That member is above my role or your role.', ephemeral=bool(ctx.interaction))
        case_id = await self.record(ctx, 'unmute', member, reason)
        try:
            await member.timeout(None, reason=f'Case #{case_id} • {reason}')
        except discord.Forbidden:
            return await ctx.send('❌ Discord denied removing the timeout.')
        await self.finish_silent(ctx, f'🔊 Removed timeout from {member} • Case #{case_id}.')

    @commands.hybrid_command(name='purge', description='Delete recent messages.')
    @app_commands.describe(amount='Number of messages to delete, up to 100')
    @permission_check()
    async def purge(self, ctx, amount: int):
        if not 1 <= amount <= 100:
            return await ctx.send('❌ Purge amount must be between 1 and 100.', ephemeral=bool(ctx.interaction))
        if not isinstance(ctx.channel, discord.TextChannel):
            return await ctx.send('❌ This command only works in text channels.', ephemeral=bool(ctx.interaction))
        if not ctx.channel.permissions_for(ctx.guild.me).manage_messages:
            return await ctx.send('❌ I need Manage Messages here.', ephemeral=bool(ctx.interaction))
        if ctx.interaction:
            await ctx.defer(ephemeral=True)
            deleted = await ctx.channel.purge(limit=amount)
            await ctx.followup.send(f'🧹 Deleted **{len(deleted)}** message(s).', ephemeral=True)
        else:
            # The global command-completion handler removes the .purge trigger.
            # Purge only the requested number of channel messages and stays silent.
            await ctx.channel.purge(limit=amount)

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
