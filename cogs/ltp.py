import asyncio

from discord.ext import commands
import discord

from cogs.menus import Menus, ARROWS, CANCEL
from utils.utils import wrap
from utils import checks, errors


def ltpchannel():
    def check(ctx):
        if ctx.channel.name in ['role-assigning']:
            return True
        raise errors.WrongChannel(discord.utils.get(ctx.guild.channels, name='role-assigning'))
    return commands.check(check)


class LTP(Menus):
    def __init__(self, bot):
        self.bot = bot

###################
#                 #
# LTP             #
#                 #
###################

    async def get_game(self, ctx, game_name):
        return await ctx.con.fetchval('''
            SELECT name FROM ltp WHERE $1 = ANY(aliases)
            ''', game_name.upper().replace(' ', ''))

    async def get_all_games(self, ctx):
        return await ctx.con.fetchval('''
            SELECT ARRAY(SELECT name FROM ltp ORDER BY name)
            ''')

    async def get_role(self, ctx, game_name):
        game = await self.get_game(ctx, game_name)
        role = discord.utils.get(ctx.guild.roles, name=game)
        return role

    async def get_all_roles(self, ctx):
        games = await self.get_all_games(ctx)
        roles = [role for role in ctx.guild.roles if role.name in games]
        return roles

    async def game_role_helper(self, ctx, member, game_name, toggle):
        if toggle:
            say_temps = (':x: You\'re already assigned to the **{role}** role.',
                         ':white_check_mark: Assigned **{role}** role.',
                         ':x: **Invalid Game**.\nWant a game added? Ask *__MadWookie__* to add it.')
        else:
            say_temps = (':x: You\'re not assigned to the **{role}** role.',
                         ':white_check_mark: Removed **{role}** role.',
                         ':x: **Invalid Game**.\nWant a game added? Ask *__MadWookie__* to add it.')
        changed = 0
        role_name = None
        role = await self.get_role(ctx, game_name)
        if role:
            role_name = role.name
            if toggle:
                if role not in member.roles:
                    await member.add_roles(role)
                    changed = 1
            else:
                if role in member.roles:
                    await member.remove_roles(role)
                    changed = 1
        else:
            changed = 2
        await ctx.send(say_temps[int(changed)].format(role=role_name), delete_after=20)

    @checks.db
    @ltpchannel()
    @commands.group(invoke_without_command=True)
    async def ltp(self, ctx, *, game_name: str):
        """Adds you to a specified game role."""
        await self.game_role_helper(ctx, ctx.author, game_name, True)

###################
#                 #
# STOP            #
#                 #
###################

    async def stop_all_helper(self, ctx, member):
        temp = ':clock{}: Removing roles.. *please wait*...'
        emsg = await ctx.send(temp.format(1))
        roles = [role for role in await self.get_all_roles(ctx) if role in member.roles]
        len_roles = len(roles)
        await asyncio.sleep(1)
        for i, role in enumerate(roles):
            try:
                await member.remove_roles(role)
            except discord.Forbidden:
                pass
            await emsg.edit(content=temp.format(((i * 2) % 12) + 1))
            if i != (len_roles - 1):
                await asyncio.sleep(1)
        await emsg.edit(content=':white_check_mark: Removed **all** game roles.', delete_after=15)

    @checks.db
    @ltpchannel()
    @ltp.command()
    async def stop(self, ctx, *, game_name: str):
        """Removes you from a specified game role."""
        await self.game_role_helper(ctx, ctx.author, game_name, False)

    @checks.db
    @ltpchannel()
    @ltp.command()
    async def stopall(self, ctx):
        """Remove all your game roles."""
        await self.stop_all_helper(ctx, ctx.author)

###################
#                 #
# LIST            #
#                 #
###################

    @checks.db
    @ltpchannel()
    @ltp.command(name='list')
    async def list_roles(self, ctx):
        roles = [role.name for role in await self.get_all_roles(ctx)]
        header = "**Game List**"
        spacer = '-=-=-=--=-=-=--=-=-=--=-=-=-=-=-=-=-=-=-=-=-=-=-=-'
        key = f'{ARROWS[0]} Click to go back a page.\n{ARROWS[1]} Click to go forward a page.\n{CANCEL} Click to exit the list.'
        info = wrap('To assign yourself one of these roles just use **!ltp ``Game``**.', spacer, sep='\n')
        header = '\n'.join([header, key, info])
        await self.reaction_menu(roles, ctx.author, ctx.channel, 0, per_page=20, timeout=120, code=False, header=header, return_from=roles)


def setup(bot):
    bot.add_cog(LTP(bot))
