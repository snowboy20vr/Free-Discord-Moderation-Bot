from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands

from utils.permissions import can_use, default_level, LEVEL_NAMES, DEFAULT_LEVELS

COMMANDS = sorted(DEFAULT_LEVELS)
COMMAND_PAGES = [COMMANDS[:25], COMMANDS[25:]]

class LevelSelect(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        options = [discord.SelectOption(label=f'Level {i}', description=LEVEL_NAMES[i], value=str(i)) for i in range(1, 6)]
        super().__init__(placeholder='Set the selected command to level 1-5', min_values=1, max_values=1, options=options, custom_id='config_level_select')

    async def callback(self, interaction: discord.Interaction):
        command = self.parent_view.selected_command
        if not command:
            return await interaction.response.send_message('Select a command first.', ephemeral=True)
        level = int(self.values[0])
        self.parent_view.bot.db.set_command_level(interaction.guild.id, command, level)
        self.parent_view.selected_level = level
        self.parent_view.rebuild()
        await interaction.response.edit_message(view=self.parent_view)

class CommandSelect(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        page = parent_view.command_page
        commands_on_page = COMMAND_PAGES[page]
        options = [
            discord.SelectOption(
                label=f'/{name}',
                description=f'Current: Level {parent_view.bot.db.get_command_level(parent_view.guild.id, name, default_level(name))}',
                value=name,
                default=name == parent_view.selected_command
            )
            for name in commands_on_page
        ]
        super().__init__(
            placeholder=f'Choose a command (page {page + 1}/{len(COMMAND_PAGES)})',
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f'config_command_select_{page}'
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_command = self.values[0]
        self.parent_view.selected_level = self.parent_view.bot.db.get_command_level(interaction.guild.id, self.values[0], default_level(self.values[0]))
        self.parent_view.rebuild()
        await interaction.response.edit_message(view=self.parent_view)

class CommandPageSelect(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(
                label=f'Command page {i + 1}',
                description=f'{len(page)} commands',
                value=str(i),
                default=i == parent_view.command_page
            )
            for i, page in enumerate(COMMAND_PAGES)
        ]
        super().__init__(
            placeholder='Choose a command page',
            min_values=1,
            max_values=1,
            options=options,
            custom_id='config_command_page_select'
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.command_page = int(self.values[0])
        self.parent_view.rebuild()
        await interaction.response.edit_message(view=self.parent_view)

class ConfigTab(discord.ui.Button):
    def __init__(self, parent_view, tab, label, emoji):
        self.parent_view = parent_view
        self.tab = tab
        super().__init__(label=label, emoji=emoji, style=discord.ButtonStyle.secondary, custom_id=f'config_tab_{tab}')

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.tab = self.tab
        self.parent_view.rebuild()
        await interaction.response.edit_message(view=self.parent_view)

class ConfigView(discord.ui.LayoutView):
    def __init__(self, bot, guild, author):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.author = author
        self.tab = 'overview'
        self.selected_command = None
        self.selected_level = None
        self.command_page = 0
        self.rebuild()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message('This configuration panel belongs to someone else.', ephemeral=True)
            return False
        return True

    def rebuild(self):
        self.clear_items()
        settings = self.bot.db.settings(self.guild.id)

        self.add_item(discord.ui.TextDisplay(
            f'# 🛡️ Server Control Center\n**{self.guild.name}**\n\n'
            'Configure moderation, permissions and server behavior without leaving Discord.'
        ))

        tabs = discord.ui.ActionRow()
        tabs.add_item(ConfigTab(self, 'overview', 'Overview', '🏠'))
        tabs.add_item(ConfigTab(self, 'commands', 'Command Permissions', '🛡️'))
        tabs.add_item(ConfigTab(self, 'server', 'Server', '⚙️'))
        tabs.add_item(ConfigTab(self, 'settings', 'Settings', '🛠️'))
        tabs.add_item(ConfigTab(self, 'roles', 'Role Levels', '🎖️'))
        self.add_item(tabs)
        self.add_item(discord.ui.Separator())

        log_channel = f'<#{settings["log_channel_id"]}>' if settings['log_channel_id'] else 'Not configured'
        mute_role = f'<@&{settings["mute_role_id"]}>' if settings['mute_role_id'] else 'Discord timeout mode'
        dm_status = 'Enabled' if settings['dm_actions'] else 'Disabled'

        if self.tab == 'overview':
            self.add_item(discord.ui.TextDisplay(
                f'## Overview\n'
                f'Prefix: {settings["prefix"]}\n'
                f'Log channel: {log_channel}\n'
                f'Mute role: {mute_role}\n'
                f'Moderation DMs: {dm_status}\n\n'
                'Use the tabs above to configure the server.'
            ))
        elif self.tab == 'commands':
            selected = self.selected_command or 'None'
            level = self.selected_level or '—'
            self.add_item(discord.ui.TextDisplay(
                f'## Command Permissions\n'
                f'Selected: /{selected}\n'
                f'Required level: {level}\n\n'
                '1 • Trial Moderator\n'
                '2 • Moderator\n'
                '3 • Senior Moderator\n'
                '4 • Administrator\n'
                '5 • Owner'
            ))
            page_row = discord.ui.ActionRow()
            page_row.add_item(CommandPageSelect(self))
            self.add_item(page_row)
            command_row = discord.ui.ActionRow()
            command_row.add_item(CommandSelect(self))
            self.add_item(command_row)
            level_row = discord.ui.ActionRow()
            level_row.add_item(LevelSelect(self))
            self.add_item(level_row)
        elif self.tab == 'settings':
            self.add_item(discord.ui.TextDisplay(
                '## Settings\n\n'
                'Server-wide moderation behavior can be configured here.\n'
                'Reasons, direct-message notices, and recent-message cleanup are supported.\n\n'
                'Temporary ban: .ban 123456789 spam 1d\n'
                'Permanent ban: .ban 123456789 spam\n'
                'Temporary mute: .mute 123456789 spam 1d'
            ))
        elif self.tab == 'server':
            self.add_item(discord.ui.TextDisplay(
                '## Server Settings\n\n'
                'Use /setprefix to change the prefix.\n'
                'Use /setlogchannel to choose the moderation log channel.\n'
                'Use /setmuterole to configure a legacy mute role.\n\n'
                'Settings are stored permanently in SQLite.'
            ))
        else:
            roles = self.bot.db.role_levels(self.guild.id)
            lines = ['## Role Permission Levels']
            if not roles:
                lines.append('No custom role levels are configured yet.')
            else:
                for role_id, level in roles.items():
                    role = self.guild.get_role(role_id)
                    if role:
                        lines.append(f'{role.mention} → Level {level} ({LEVEL_NAMES[level]})')
            lines.append('\nUse /setrolelevel to assign a role a level.')
            self.add_item(discord.ui.TextDisplay('\n'.join(lines)))

def config_check():
    async def predicate(ctx: commands.Context):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return False
        required = ctx.bot.db.get_command_level(ctx.guild.id, ctx.command.qualified_name, default_level(ctx.command.qualified_name))
        return can_use(ctx.author, required, ctx.bot.db.role_levels(ctx.guild.id))
    return commands.check(predicate)

class ConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='config', description='Open the Components V2 server control center.')
    @config_check()
    async def config(self, ctx):
        if not ctx.guild:
            return await ctx.send('❌ This command can only be used in a server.', ephemeral=bool(ctx.interaction))
        view = ConfigView(self.bot, ctx.guild, ctx.author)
        if ctx.interaction:
            await ctx.interaction.response.send_message(view=view, ephemeral=True)
        else:
            await ctx.send(view=view)

    @commands.hybrid_command(name='setpermissionlevel', description='Set the required level for a command.')
    @app_commands.describe(command='Command name without the slash', level='Required level from 1 to 5')
    @config_check()
    async def setpermissionlevel(self, ctx, command: str, level: app_commands.Range[int, 1, 5]):
        command = command.lower().lstrip('/')
        if command not in COMMANDS and not self.bot.get_command(command):
            return await ctx.send(f'❌ Unknown command {command}.', ephemeral=bool(ctx.interaction))
        self.bot.db.set_command_level(ctx.guild.id, command, int(level))
        await ctx.send(f'✅ /{command} now requires Level {level} — {LEVEL_NAMES[int(level)]}.')

    @commands.hybrid_command(name='setrolelevel', description='Give a role a moderation permission level.')
    @config_check()
    async def setrolelevel(self, ctx, role: discord.Role, level: app_commands.Range[int, 1, 5]):
        self.bot.db.set_role_level(ctx.guild.id, role.id, int(level))
        await ctx.send(f'✅ {role.mention} is now Level {level} — {LEVEL_NAMES[int(level)]}.')

    @commands.hybrid_command(name='setprefix', description='Change the server prefix.')
    @config_check()
    async def setprefix(self, ctx, prefix: str):
        if len(prefix) > 5 or any(ch.isspace() for ch in prefix):
            return await ctx.send('❌ Prefix must be 1-5 non-space characters.', ephemeral=bool(ctx.interaction))
        self.bot.db.set_setting(ctx.guild.id, 'prefix', prefix)
        await ctx.send(f'✅ Prefix changed to {prefix}. Example: {prefix}warn @user reason')

    @commands.hybrid_command(name='setlogchannel', description='Set or clear the moderation log channel.')
    @config_check()
    async def setlogchannel(self, ctx, channel: discord.TextChannel | None = None):
        self.bot.db.set_setting(ctx.guild.id, 'log_channel_id', channel.id if channel else None)
        await ctx.send(f'✅ Moderation logs: {channel.mention if channel else "disabled"}.')

    @commands.hybrid_command(name='setmuterole', description='Set the legacy mute role.')
    @config_check()
    async def setmuterole(self, ctx, role: discord.Role | None = None):
        self.bot.db.set_setting(ctx.guild.id, 'mute_role_id', role.id if role else None)
        await ctx.send(f'✅ Mute role: {role.mention if role else "not configured"}.')

async def setup(bot):
    await bot.add_cog(ConfigCog(bot))
