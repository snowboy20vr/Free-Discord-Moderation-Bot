from __future__ import annotations

import asyncio
import logging
import discord
from discord.ext import commands

from config import TOKEN, PREFIX, OWNER_IDS
from database import Database

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger('moderation-bot')

db = Database()

async def dynamic_prefix(bot: commands.Bot, message: discord.Message):
    if not message.guild:
        return commands.when_mentioned_or(PREFIX)(bot, message)
    return commands.when_mentioned_or(db.settings(message.guild.id)['prefix'])(bot, message)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class ModerationBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=dynamic_prefix, intents=intents, case_insensitive=True, strip_after_prefix=True, owner_ids=OWNER_IDS, help_command=None)
        self.db = db
        self._synced = False

    async def setup_hook(self):
        await self.load_extension('cogs.moderation')
        await self.load_extension('cogs.config_panel')
        await self.load_extension('cogs.general')
        try:
            synced = await self.tree.sync()
            log.info('Synced %s application commands.', len(synced))
            self._synced = True
        except Exception:
            log.exception('Slash command sync failed')

    async def on_ready(self):
        activity = discord.Activity(type=discord.ActivityType.watching, name=f'{len(self.guilds)} servers')
        await self.change_presence(status=discord.Status.online, activity=activity)
        log.info('Logged in as %s (%s)', self.user, self.user.id)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if hasattr(ctx.command, 'on_error'):
            return
        original = getattr(error, 'original', error)
        if isinstance(original, commands.CommandNotFound):
            return
        if isinstance(original, commands.MissingPermissions):
            await ctx.send('❌ You do not have the Discord permissions required for that action.', delete_after=7)
            return
        if isinstance(original, commands.MissingRequiredArgument):
            await ctx.send(f'❌ Missing argument: `{original.param.name}`.', delete_after=7)
            return
        if isinstance(original, commands.BadArgument):
            await ctx.send('❌ I could not understand one of the arguments. Try a mention or user ID.', delete_after=7)
            return
        if isinstance(original, commands.CheckFailure):
            await ctx.send('❌ You do not have the configured permission level for this command.', delete_after=7)
            return
        log.exception('Command error', exc_info=original)
        await ctx.send('❌ Something went wrong while running that command.', delete_after=7)

bot = ModerationBot()

if __name__ == '__main__':
    bot.run(TOKEN)
