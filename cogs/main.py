import datetime
import time

from discord.ext import commands
import discord

from utils.json import Dict
from utils import checks


DEFAULT_SETTINGS = {'GREETING': 'Welcome {0.name} to {1.name}!', 'ON': False}


###################
#                 #
# MAIN            #
#                 #
###################


class Main:
    def __init__(self, bot):
        self.bot = bot
        self.settings = Dict('welcome', loop=bot.loop, int_keys=True)

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

    def get_welcome_channel(self, guild):
        if guild is None:
            return None
        return discord.utils.get(guild.channels, name='welcome')

    @commands.group()
    @commands.has_permissions(manage_guild=True)
    async def welcomeset(self, ctx):
        """Sets welcome module settings."""
        guild = ctx.guild
        if guild.id not in self.settings:
            self.settings[guild.id] = DEFAULT_SETTINGS
            await self.settings.save()
        settings = self.settings[guild.id]
        if ctx.invoked_subcommand is None:
            msg = "```\n"
            msg += f'GREETING: {settings["GREETING"]}\n'
            msg += f'ON: {settings["ON"]}\n'
            msg += '```'
            await ctx.send(msg)

    @checks.no_delete
    @welcomeset.command()
    async def greeting(self, ctx, *, format_msg):
        """Sets the welcome message format for the server.

        {0} is user
        {1} is server"""
        guild = ctx.guild
        self.settings[guild.id]['GREETING'] = format_msg
        await self.settings.save()
        await ctx.send('Welcome message set for the server.')
        await self.send_testing_msg(ctx)

    @welcomeset.command()
    async def toggle(self, ctx):
        """Turns on/off welcoming new users to the server"""
        guild = ctx.guild
        self.settings[guild.id]['ON'] = not self.settings[guild.id]['ON']
        if self.settings[guild.id]['ON']:
            await ctx.send('I will now welcome new users to the server.')
            await self.send_testing_msg(ctx)
        else:
            await ctx.send('I will no longer welcome new users.')
        await self.settings.save()

    async def on_member_join(self, member):
        guild = member.guild
        channel = self.get_welcome_channel(guild)
        member_role = self.get_role_member(guild)
        if guild.id not in self.settings:
            self.settings[guild.id] = DEFAULT_SETTINGS
            await self.settings.save()
        if not self.settings[guild.id]['ON']:
            return
        if channel is not None:
            await channel.send(self.settings[guild.id]['GREETING'].format(member, guild))
        if member_role is not None:
            await member.add_roles(member_role)

    async def send_testing_msg(self, ctx):
        guild = ctx.guild
        channel = self.get_welcome_channel(guild)
        await ctx.channel.send(f'Sending a testing message to {channel.mention}')
        try:
            await channel.send(self.settings[guild.id]['GREETING'].format(ctx.author, guild))
        except AttributeError:
            await ctx.channel.send('Channel does not exist.')
        except discord.DiscordException as e:
            await ctx.channel.send(f'`{e}`')

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
