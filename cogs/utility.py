import datetime
import asyncio
import logging

from discord.ext import commands
import discord

from utils import checks


def pin_check(m):
    return not m.pinned


class Utility:
    def __init__(self, bot):
        self.bot = bot
        self.purge_task = self.bot.loop.create_task(self.purge())
        self.log_ignore = ['pokemon', 'role-assigning', 'bot-spam']

    def __unload(self):
        self.purge_task.cancel()

###################
#                 #
# CLEANER         #
#                 #
###################

    async def purge(self):
        await self.bot.wait_until_ready()
        channels = [chan for chan in self.bot.get_all_channels() if chan.name in ('role-assigning', 'music', 'pokemon')]
        while not self.bot.is_closed():
            await asyncio.gather(*[chan.purge(limit=300, check=pin_check) for chan in channels], loop=self.bot.loop)
            await asyncio.sleep(10800, loop=self.bot.loop)

###################
#                 #
# LOGGING         #
#                 #
###################

    def get_logging_channel(self, ctx):
        if ctx.guild is None:
            return None
        return discord.utils.get(ctx.guild.channels, name='logs')

    async def log(self, color, content, author, timestamp=None):
        timestamp = timestamp or datetime.datetime.utcnow()
        embed = discord.Embed(colour=color, description=content, timestamp=timestamp)
        embed.set_author(name=str(author), icon_url=author.avatar_url)
        try:
            await self.get_logging_channel(author).send(embed=embed)
        except AttributeError:
            pass

    async def on_member_join(self, member):
        await self.log(discord.Colour.green(), '**[USER JOIN]**', member)

    async def on_member_remove(self, member):
        await self.log(discord.Colour(0x5b0506), '**[USER LEAVE]**', member)

    async def on_message_delete(self, message):
        if message.channel.name in self.log_ignore or await self.bot.is_command(message):
            return
        logging_channel = self.get_logging_channel(message)
        if logging_channel is None:
            return
        if message.channel.id == logging_channel.id:
            embed = discord.Embed.from_data(message.embeds[0])
            await logging_channel.send('Someone deleted this!', embed=embed)
            return
        if message.author.bot:
            return
        if not message.content and message.attachments:
            content = 'Attachments:'
            content += '\n'.join('{0[filename]} {0[url]}'.format(attach) for attach in message.attachments)
        else:
            content = message.content
        description = f'{message.channel.mention}\n{content}'
        embed = discord.Embed(colour=discord.Colour.red(), description='**[MESSAGE DELETED]**\n' + description)
        embed.set_author(name=str(message.author), icon_url=message.author.avatar_url)
        embed.timestamp = datetime.datetime.utcnow()
        await logging_channel.send(embed=embed)

    async def on_message_edit(self, message, edit):
        if message.author.bot or message.content == edit.content or \
                message.channel.name in self.log_ignore:
            return
        logging_channel = self.get_logging_channel(message)
        if logging_channel is None:
            return
        member = message.author
        embed = discord.Embed(colour=discord.Colour.gold())
        embed.set_author(name=str(member), icon_url=member.avatar_url)
        embed.timestamp = datetime.datetime.utcnow()
        if len(message.content) + len(edit.content) >= 1964:
            embed.description = '**[MESSAGE EDITED 1/2]**\n{0.channel.mention}\n**OLD ⮞** {0.content}'.format(message)
            await logging_channel.send(embed=embed)
            embed.description = '**[MESSAGE EDITED 2/2]**\n{0.channel.mention}\n**NEW ⮞** {0.content}'.format(edit)
            await logging_channel.send(embed=embed)
        else:
            embed.description = '**[MESSAGE EDITED]**\n{0.channel.mention}\n**OLD ⮞** {0.content}\n**NEW ⮞**' \
                                ' {1.content}'.format(message, edit)
            await logging_channel.send(embed=embed)

###################
#                 #
# PLONKING        #
#                 #
###################

    @checks.db
    @commands.command()
    @commands.is_owner()
    async def plonk(self, ctx, user: discord.Member):
        """Adds a user to the bot's blacklist"""
        try:
            async with ctx.con.transaction():
                await ctx.con.execute('''
                    INSERT INTO plonks (guild_id, user_id) VALUES ($1, $2)
                    ''', ctx.guild.id, user.id)
        except asyncpg.UniqueViolationError:
            await ctx.send('User is already plonked.')
        else:
            await ctx.send('User has been plonked.')

    @checks.db
    @commands.command()
    @commands.is_owner()
    async def unplonk(self, ctx, user: discord.Member):
        """Removes a user from the bot's blacklist"""
        async with ctx.con.transaction():
            res = await ctx.con.execute('''
                DELETE FROM plonks WHERE guild_id = $1 and user_id = $2
                ''', ctx.guild.id, user.id)
        deleted = int(res.split()[-1])
        if deleted:
            await ctx.send('User is no longer plonked.')
        else:
            await ctx.send('User is not plonked.')

###################
#                 #
# CLEANUP         #
#                 #
###################

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def cleanup(self, ctx):
        """Deletes messages.

        cleanup messages [amount]
        cleanup user [name/mention] [amount]"""
        await self.bot.send_help(ctx)

    @cleanup.command()
    async def user(self, ctx, user: discord.Member, number: int):
        """Deletes last X messages from specified user."""
        if number < 1:
            number = 1
        message = ctx.message
        author = ctx.author
        channel = ctx.channel
        logging.info("{0.name}({0.id}) deleted {1} messages made by {2.name}({2.id}) in channel {3}".format(
            author, number, user, message.channel.mention))

        def is_user(m):
            return m.id == message.id or m.author == user

        try:
            await channel.purge(limit=number + 1, check=is_user)
        except discord.errors.Forbidden:
            await ctx.send('I need permissions to manage messages in this channel.')

    @cleanup.command()
    async def messages(self, ctx, number: int):
        """Deletes last X messages.

        Example:
        cleanup messages 26"""
        if number < 1:
            number = 1
        author = ctx.author
        channel = ctx.channel
        logging.info("{}({}) deleted {} messages in channel {}".format(
            author.name, author.id, number, channel.mention))
        try:
            await channel.purge(limit=number + 1)
        except discord.errors.Forbidden:
            await ctx.send('I need permissions to manage messages in this channel.')

###################
#                 #
# COGS            #
#                 #
###################

    @commands.command(hidden=True)
    @commands.is_owner()
    async def reload(self, ctx, *, ext):
        """Reload a cog."""
        if not ext.startswith('cogs.'):
            ext = f'cogs.{ext}'
        try:
            self.bot.unload_extension(ext)
        except:
            pass
        try:
            self.bot.load_extension(ext)
        except Exception as e:
            await ctx.send(e)
        else:
            await ctx.send(f'Cog {ext} reloaded.')

    @commands.command(hidden=True)
    @commands.is_owner()
    async def load(self, ctx, *, ext):
        """Load a cog."""
        if not ext.startswith('cogs.'):
            ext = f'cogs.{ext}'
        try:
            self.bot.load_extension(ext)
        except Exception as e:
            await ctx.send(e)
        else:
            await ctx.send(f'Cog {ext} loaded.')

    @commands.command(hidden=True)
    @commands.is_owner()
    async def unload(self, ctx, *, ext):
        """Unload a cog."""
        if not ext.startswith('cogs.'):
            ext = f'cogs.{ext}'
        try:
            self.bot.unload_extension(ext)
        except:
            await ctx.send(f'Cog {ext} is not loaded.')
        else:
            await ctx.send(f'Cog {ext} unloaded.')


def setup(bot):
    bot.add_cog(Utility(bot))
