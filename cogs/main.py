import datetime
import time

from discord.ext import commands
import discord

from utils import checks


###################
#                 #
# MAIN            #
#                 #
###################


class Main:
    def __init__(self, bot):
        self.bot = bot

###################
#                 #
# STATS           #
#                 #
###################

    @commands.group(invoke_without_command=True)
    async def stats(self, ctx):
        """Lets you see various stats regarding the server."""
        await self.bot.send_help(ctx)

    @stats.command(aliases=['guild'])
    async def server(self, ctx):
        guild = ctx.guild
        thumbnail = 'http://unitedsurvivorsgaming.com/logo.png'
        text_channels, voice_channels = 0, 0
        for chan in guild.channels:
            if isinstance(chan, discord.TextChannel):
                text_channels += 1
            elif isinstance(chan, discord.VoiceChannel):
                voice_channels += 1
        title = f'**{guild.name}**'
        description = guild.created_at.strftime('Created on %B %d{} %Y')
        day = guild.created_at.day
        description = description.format("th" if 4 <= day % 100 <= 20 else
                                         {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th"))
        footer = f'{ctx.invoked_with.title()} ID: {guild.id}'
        embed = discord.Embed(colour=discord.Colour(0xffffff), title=title, description=description)
        embed.set_thumbnail(url=thumbnail)
        embed.add_field(name='Region', value=guild.region)
        embed.add_field(name='Members', value=len(guild.members))
        embed.add_field(name='Text Channels', value=text_channels)
        embed.add_field(name='Voice Channels', value=voice_channels)
        embed.add_field(name='Roles', value=len(guild.roles))
        embed.add_field(name='Owner', value=guild.owner)
        embed.set_footer(text=footer)
        await ctx.send(embed=embed)

    @stats.command()
    async def invites(self, ctx):
        guild = ctx.guild
        thumbnail = 'http://unitedsurvivorsgaming.com/logo.png'
        title = f'**{guild.name}**'
        description = 'Recruitment Stats'
        footer = 'These stats are for Recruiters+ to see how many people they have invited.'
        embed = discord.Embed(colour=discord.Colour(0xffffff), title=title, description=description)
        inviters = {}
        for invite in await guild.invites():
            if invite.inviter.bot or invite.inviter == guild.owner:
                continue
            if invite.inviter in inviters:
                inviters[invite.inviter] += invite.uses
            else:
                inviters[invite.inviter] = invite.uses
        if not inviters:
            await ctx.send('No inviter stats.')
            return
        inviters = sorted(inviters.items(), key=lambda p: p[1], reverse=True)
        embed.set_thumbnail(url=thumbnail)
        embed.add_field(name='Users', value='\n'.join(p[0].display_name for p in inviters))
        embed.add_field(name='Total Users Recruited', value='\n'.join(str(p[1]) for p in inviters))
        embed.set_footer(text=footer)
        await ctx.send(embed=embed)

###################
#                 #
# WELCOME         #
#                 #
###################

    def get_role_member(self, guild):
        if guild is None:
            return None
        return discord.utils.get(guild.roles, name='Member')

    async def get_welcome_channel(self, guild, *, channel_id=None, con=None):
        if guild is None:
            return None
        if con:
            channel_id = await con.fetchval('''
                SELECT channel_id FROM greetings WHERE guild_id = $1
                ''', guild.id)
        channel = None
        if channel_id:
            channel = discord.utils.get(guild.channels, id=channel_id)
        return channel or discord.utils.get(guild.channels, name='welcome')

    @checks.db
    @commands.group()
    @commands.has_permissions(manage_guild=True)
    async def welcomeset(self, ctx):
        """Sets welcome module settings."""
        guild = ctx.guild
        async with ctx.con.transaction():
            settings = await ctx.con.fetchrow('''
                INSERT INTO greetings (guild_id) VALUES ($1)
                ON CONFLICT (guild_id) DO
                UPDATE SET guild_id = $1 RETURNING *
                ''', guild.id)
        if ctx.invoked_subcommand is None:
            msg = ['```']
            msg.append(f"Enabled: {settings['enabled']}")
            channel = await self.get_welcome_channel(guild, channel_id=settings['channel_id'])
            msg.append(f'Channel: {channel.mention if channel else None}')
            msg.append(f"Message: {settings['message']}")
            msg.append('```')
            await ctx.send('\n'.join(msg))

    @checks.db
    @checks.no_delete
    @welcomeset.command(aliases=['message'])
    async def greeting(self, ctx, *, format_msg):
        """Sets the welcome message format for the server.

        {0} is user
        {1} is server"""
        async with ctx.con.transaction():
            await ctx.con.execute('''
                UPDATE greetings SET message = $1 WHERE guild_id = $2
                ''', format_msg, ctx.guild.id)
        await ctx.send('Welcome message set for the server.')
        await self.send_testing_msg(ctx)

    @checks.db
    @welcomeset.command()
    async def toggle(self, ctx, enable: bool=None):
        """Turns on/off welcoming new users to the server."""
        guild = ctx.guild
        async with ctx.con.transaction():
            before = await ctx.con.fetchval('''
                SELECT enabled FROM greetings WHERE guild_id = $1
                ''', guild.id)
            if enable is None or enable != before:
                after = await ctx.con.fetchval('''
                    UPDATE greetings SET enabled = NOT enabled WHERE guild_id = $1 RETURNING enabled
                    ''', guild.id)
            else:
                after = before
        if after == before:
            if after:
                await ctx.send('Welcome message is already enabled.')
            else:
                await ctx.send('Welcome message is already disabled.')
        elif after:
            await ctx.send('I will now welcome new users to the server.')
            await self.send_testing_msg(ctx)
        else:
            await ctx.send('I will no longer welcome new users.')

    @checks.db
    @welcomeset.command()
    async def channel(self, ctx, channel: discord.Channel=None):
        """Sets the channel for welcoming new users."""
        guild = ctx.guild
        channel = channel or ctx.channel
        async with ctx.con.transaction():
            await ctx.con.execute('''
                UPDATE greetings SET channel_id = $1 WHERE guild_id = $2
                ''', channel.id, guild.id)
        await ctx.send(f'Set {channel.mention} as welcome channel.')

    async def on_member_join(self, member):
        guild = member.guild
        async with self.bot.db_pool.acquire() as con:
            settings = await con.fetchrow('''
                SELECT * FROM greetings WHERE guild_id = $1
                ''', guild.id)
        channel = await self.get_welcome_channel(guild, channel_id=settings['channel_id'])
        member_role = self.get_role_member(guild)
        if not settings['enabled']:
            return
        if channel is not None:
            await channel.send(settings['message'].format(member, guild))
        if member_role is not None:
            await member.add_roles(member_role)

    async def send_testing_msg(self, ctx):
        guild = ctx.guild
        con = getattr(ctx, 'con', None)
        local = con is None
        if local:
            con = await self.bot.db_pool.acquire()
        try:
            channel = await self.get_welcome_channel(guild, con=con)
            message = await con.fetchval('''
                SELECT message FROM greetings WHERE guild_id = $1
                ''', guild.id)
        finally:
            if local:
                await self.bot.db_pool.release(con)

        if channel is not None:
            await ctx.channel.send(f'Sending a testing message to {channel.mention}')
            try:
                await channel.send(self.settings[guild.id]['GREETING'].format(ctx.author, guild))
            except discord.DiscordException as e:
                await ctx.channel.send(f'`{e}`')
        else:
            await ctx.channel.send('Neither the set channel nor channel named "welcome" exists.')

###################
#                 #
# MISCELLANEOUS   #
#                 #
###################

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def playing(self, ctx, *, status: str):
        """Sets the 'Playing' message for the bot."""
        await self.bot.change_presence(game=discord.Game(name=status))

    @commands.command()
    async def uptime(self, ctx):
        up = abs(self.bot.uptime - int(time.perf_counter()))
        up = datetime.timedelta(seconds=up)
        await ctx.send(f'`Uptime: {up}`')


def setup(bot):
    bot.add_cog(Main(bot))
