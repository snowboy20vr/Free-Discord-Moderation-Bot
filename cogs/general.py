from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands

from utils.permissions import can_use, default_level, LEVEL_NAMES


def permission_check():
    async def predicate(ctx: commands.Context):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return False
        required = ctx.bot.db.get_command_level(ctx.guild.id, ctx.command.qualified_name, default_level(ctx.command.qualified_name))
        return can_use(ctx.author, required, ctx.bot.db.role_levels(ctx.guild.id))
    return commands.check(predicate)


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='ping', description='Show bot latency and status.')
    @permission_check()
    async def ping(self, ctx):
        ms = round(self.bot.latency * 1000)
        await ctx.send(f'🏓 **Pong!** `{ms}ms` • {len(self.bot.guilds)} servers')

    @commands.hybrid_command(name='userinfo', description='Show information about a member.')
    @app_commands.describe(member='The member to inspect')
    @permission_check()
    async def userinfo(self, ctx, member: discord.Member | None = None):
        member = member or ctx.author
        embed = discord.Embed(title=f'User Information • {member}', colour=member.colour or discord.Colour.blurple())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name='User ID', value=str(member.id), inline=True)
        embed.add_field(name='Account', value=discord.utils.format_dt(member.created_at, 'R'), inline=True)
        embed.add_field(name='Joined', value=discord.utils.format_dt(member.joined_at, 'R') if member.joined_at else 'Unknown', inline=True)
        embed.add_field(name='Top Role', value=member.top_role.mention if member.top_role else '@everyone', inline=True)
        embed.add_field(name='Bot', value='Yes' if member.bot else 'No', inline=True)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='serverinfo', description='Show information about this server.')
    @permission_check()
    async def serverinfo(self, ctx):
        g = ctx.guild
        embed = discord.Embed(title=f'{g.name} • Server Information', colour=discord.Colour.blurple())
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name='Owner', value=f'<@{g.owner_id}>', inline=True)
        embed.add_field(name='Members', value=str(g.member_count), inline=True)
        embed.add_field(name='Channels', value=str(len(g.channels)), inline=True)
        embed.add_field(name='Roles', value=str(len(g.roles)), inline=True)
        embed.add_field(name='Created', value=discord.utils.format_dt(g.created_at, 'R'), inline=True)
        embed.add_field(name='Verification', value=str(g.verification_level).replace('_', ' ').title(), inline=True)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='help', description='Open the command guide.')
    @permission_check()
    async def help(self, ctx):
        prefix = self.bot.db.settings(ctx.guild.id)['prefix'] if ctx.guild else '!'
        embed = discord.Embed(title='Moderation Bot • Command Guide', colour=discord.Colour.blurple(), description='Clean, configurable moderation for your server.')
        embed.add_field(name='Moderation', value='`warn` `warnings` `clearwarnings` `kick` `ban` `unban` `softban` `mute` `unmute` `timeout`', inline=False)
        embed.add_field(name='Channel', value='`purge` `slowmode` `lock` `unlock` `nick`', inline=False)
        embed.add_field(name='Configuration', value='`config` `setpermissionlevel` `setrolelevel` `setprefix` `setlogchannel` `setmuterole`', inline=False)
        embed.add_field(name='Prefix', value=f'Current prefix: `{prefix}`', inline=False)
        embed.set_footer(text='Slash commands and prefix commands are both supported.')
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='level', description='Show your effective moderation level.')
    async def level(self, ctx, member: discord.Member | None = None):
        member = member or ctx.author
        if member.guild.owner_id == member.id:
            level = 1
        elif member.guild_permissions.administrator:
            level = 2
        else:
            configured = [self.bot.db.role_levels(ctx.guild.id).get(r.id) for r in member.roles if self.bot.db.role_levels(ctx.guild.id).get(r.id) is not None]
            level = min(configured) if configured else 5
        await ctx.send(f'🛡️ {member.mention} has permission level **{level} — {LEVEL_NAMES[level]}**.')

async def setup(bot):
    await bot.add_cog(General(bot))
