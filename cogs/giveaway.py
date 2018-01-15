import random

from discord.ext import commands
import discord

from cogs.menus import Menus


def get_role(guild):
    return discord.utils.get(guild, name='Giveaway')


async def get_entrants(guild, remove=True):
    role = get_role(guild)
    entrants = []
    for m in guild.members:
        if role in m.roles:
            entrants.append(m)
            if remove:
                await m.remove_roles(role)
    return entrants


class Giveaway(Menus):
    def __init__(self, bot):
        self.bot = bot
        self.giveaways = {}  # {guild.id: {'creator': discord.Member, 'reward': str}}
        self.booted = {}  # {guild.id: [member.id, ...]}

    @commands.group(invoke_without_command=True)
    async def giveaway(self, ctx):
        ...

    @giveaway.command()
    async def enter(self, ctx):
        """Enter the currently active giveaway."""
        if ctx.author.id in self.booted.get(ctx.guild.id, []):
            await ctx.send("You were booted from the current giveaway.")
        await ctx.author.add_roles(get_role(ctx.guild))
        await ctx.send(f'{ctx.author.display_name} has been entered into the giveaway.')

    @commands.has_role('Giveaway')
    @giveaway.command()
    async def withdraw(self, ctx):
        """Leave the currently active giveaway."""
        await ctx.author.remove_roles(get_role(ctx.guild))
        await ctx.send(f'{ctx.author.display_name} has left the giveaway.')

    @giveaway.command(name='list')
    async def list_(self, ctx):
        """List the members that have joined the giveaway."""
        entrants = await get_entrants(ctx.guild, remove=False)
        mentions = [e.mention for e in entrants]
        await self.embed_reaction_menu(mentions, ctx.author, ctx, count=0)

    @giveaway.command()
    async def info(self, ctx):
        """Get info about the currently active giveaway."""
        if ctx.guild.id not in self.giveaways:
            await ctx.send('There is no active giveaway.')
            return
        giveaway = self.giveaways[ctx.guild.id]
        await ctx.send(f"The currently active giveaway is for \"{giveaway['reward']}\" and is hosted by {giveaway['creator'].display_name}.")

    @commands.has_permissions(administrator=True)
    @giveaway.command()
    async def start(self, ctx, reward):
        """Start a new giveaway."""
        if ctx.guild.id in self.giveaways:
            await ctx.send('A giveaway is already active here.')
            return
        self.giveaways[ctx.guild.id] = {'creator': ctx.author, 'reward': reward}
        await ctx.send(f'The giveaway "{reward}" is now active.')

    @commands.has_permissions(administrator=True)
    @giveaway.command()
    async def add(self, ctx, member: discord.Member):
        """Manually enter someone into the giveaway.

        This will bypass the booted check."""
        if ctx.guild.id not in self.giveaways:
            await ctx.send('No giveaway is currently active.')
            return
        await member.add_roles(get_role(ctx.guild))
        await ctx.send(f'{member.display_name} has been entered into the giveaway.')

    @commands.has_permissions(administrator=True)
    @giveaway.command(aliases='kick')
    async def boot(self, ctx, member: discord.Member):
        """Boot someone from the giveaway."""
        if ctx.guild.id not in self.giveaways:
            await ctx.send('No giveaway is currently active.')
            return
        await member.remove_roles(get_role(ctx.guild))
        if ctx.guild.id in self.booted:
            self.booted[ctx.guild.id].append(member.id)
        await ctx.send(f'{member.display_name} has been {ctx.invoked_with}ed from the giveaway.')

    @commands.has_permissions(administrator=True)
    @giveaway.command()
    async def draw(self, ctx, count=1):
        """Draw the winner of the giveaway."""
        if count < 1:
            await ctx.send('Try the "end" command instead.')
            return
        elif ctx.guild.id not in self.giveaways:
            await ctx.send('No giveaway is currently active.')
            return
        giveaway = self.giveaways.pop(ctx.guild.id)
        entrants = await get_entrants(ctx.guild)
        self.booted.pop(ctx.guild.id, None)
        if count == 1:
            winner = random.choice(entrants)
            await ctx.send(f"{winner.mention} won the giveaway for \"{giveaway['reward']}\" by {giveaway['creator'].mention}.")
        else:
            winners = random.sample(entrants, count)
            await ctx.send(f"The winners of the giveaway for \"{giveaway['reward']}\" by {giveaway['creator'].mention} are " +
                           ' '.join(m.mention for m in winners))

    @commands.has_permissions(administrator=True)
    @giveaway.command(aliases=['cancel'])
    async def end(self, ctx):
        """End the giveaway without drawing a winner."""
        if ctx.guild.id not in self.giveaways:
            await ctx.send('No giveaway is currently active.')
            return
        giveaway = self.giveaways.pop(ctx.guild.id)
        await get_entrants(ctx.guild)
        self.booted.pop(ctx.guild.id, None)
        await ctx.send(f"The giveaway for \"{giveaway['reward']}\" by {giveaway['creator'].mention} has been cancelled.")
