import traceback
import asyncpg
import discord
import asyncio
import json
import time

from discord.ext.commands.view import StringView
from discord.ext import commands

from utils import errors
import config


async def set_codecs(con):
    await con.set_type_codec('json', schema='pg_catalog',
                             encoder=lambda v: json.dumps(v),
                             decoder=lambda v: json.loads(v))


class SurvivorBot(commands.Bot):
    async def logout(self):
        await self.db_pool.close()
        await super().logout()

    def get_emoji_named(self, name):
        return discord.utils.get(self.emojis, name=name.replace('-', '').replace(' ', ''))

    async def is_command(self, message):
        cmds = []
        for cmd in self.commands:
            cmds.append(cmd.name)
            cmds.extend(cmd.aliases)

        def check(prefix):
            view = StringView(message.content)
            return view.skip_string(prefix) and view.get_word() in cmds
        if callable(self.command_prefix):
            prefixes = self.command_prefix(self, message)
            if asyncio.iscoroutine(prefixes):
                prefixes = await prefixes
        else:
            prefixes = bot.command_prefix
        if isinstance(prefixes, list):
            return any(check(prefix) for prefix in prefixes)
        elif isinstance(prefixes, str):
            return check(prefixes)

    async def send_help(self, ctx):
        cmd = ctx.command
        cmds = [str(ctx.invoked_with)]
        while cmd.parent is not None:
            cmds.insert(0, str(cmd.parent))
            cmd = cmd.parent
        await ctx.invoke(self.get_command('help'), *cmds)

    async def is_owner(self, user):
        try:
            return user.id in config.owner_ids
        except AttributeError:
            return super().is_owner(user)

    async def on_ready(self):
        if not hasattr(self, 'uptime'):
            self.uptime = int(time.perf_counter())

        self.ready = True
        print('------')
        print(f'{len(self.cogs)} active cogs with {len(self.commands)} commands')
        print('------')

    async def on_message(self, message):
        if message.guild is None or \
                not self.ready:
            return
        async with self.db_pool.acquire() as con:
            plonked = await con.fetchval('''
                SELECT EXISTS(SELECT * FROM plonks WHERE user_id = $1 and guild_id = $2)
                ''', message.author.id, message.guild.id)
            if plonked:
                return
        await bot.process_commands(message)

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            minutes, seconds = map(int, divmod(error.retry_after, 60))
            hours, minutes = map(int, divmod(minutes, 60))
            fmt = []
            if hours:
                fmt.append(f'{hours}h')
            if minutes:
                fmt.append(f'{minutes}m')
            if seconds:
                fmt.append(f'{seconds}s')
            left = ' '.join(fmt)
            await ctx.send(f'You are on cooldown. Try again in {left}.', delete_after=10)
            await ctx.message.delete()
        elif isinstance(error, errors.WrongChannel):
            if error.channel is not None:
                msg = f":x: **You can't do that here.**\nPlease do this in {error.channel.mention}"
            else:
                msg = "You can't use that command in this server."
            await ctx.send(msg, delete_after=10)
        elif isinstance(error, commands.CommandNotFound):
            pass
        else:
            exc = getattr(error, 'original', error)
            msg = f'Error with message\n{ctx.message.content}'
            tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            print('\n'.join((msg, tb)))
            await ctx.send(str(exc))


formatter = commands.HelpFormatter(show_check_failure=True)

initial_extensions = [f'cogs.{ext}' for ext in
                      ('exp', 'ltp', 'main', 'pokemon', 'utility')]

description = 'Survivor Bot - Created by MadWookie & sgtlaggy.'
bot = SurvivorBot(command_prefix=['!'], description=description, formatter=formatter, request_offline_members=True)
bot.ready = False
bot.db_pool = bot.loop.run_until_complete(asyncpg.create_pool(config.dsn, init=set_codecs))

for ext in initial_extensions:
    try:
        bot.load_extension(ext)
    except Exception as e:
        print('Failed loading cog {ext} on startup.')
        print(e)


@bot.before_invoke
async def before_invoke(ctx):
    if getattr(ctx.command, '_db', False):
        ctx.con = await bot.db_pool.acquire()


@bot.after_invoke
async def after_invoke(ctx):
    if getattr(ctx, '_delete_ctx', True):
        try:
            await ctx.message.delete()
        except:
            pass
    try:
        await bot.db_pool.release(ctx.con)
    except AttributeError:
        pass


try:
    bot.run(config.token)
except Exception as e:
    print(e)
