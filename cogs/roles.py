from discord.ext import commands
import discord

from cogs.menus import Menus
from utils import checks


class DummyCTX:
    def __init__(self, model, con):
        self.model = model
        self.con = con

    def __getattr__(self, attr):
        return getattr(self.model, attr)


class Roles(Menus):
    def __init__(self, bot):
        self.bot = bot

###################
#                 #
# LTP             #
#                 #
###################

    async def get_blacklisted_roles(self, ctx):
        ids = await ctx.con.fetchval('''
            SELECT ARRAY(SELECT role_id FROM rolesblacklist)
            ''')
        roles = []
        for role_id in ids:
            role = ctx.guild.get_role(role_id)
            if role:
                roles.append(role)
        return roles

    @commands.group(invoke_without_command=True, pass_context=False)
    async def roles(self):
        pass

    @checks.db
    @commands.is_owner()
    @roles.group(invoke_without_command=True)
    async def blacklist(self, ctx):
        roles = await self.get_blacklisted_roles(ctx)
        if not roles:
            await ctx.send('No roles have been blacklisted.')
            return
        await self.reaction_menu(sorted(r.name for r in roles), ctx.author, ctx,
                                 count=0, header="**__Blacklisted Roles__**")

    @checks.db
    @commands.is_owner()
    @blacklist.command()
    async def add(self, ctx, *roles: discord.Role):
        if not roles:
            await ctx.send('No roles given.')
            return
        await ctx.con.executemany('''
            INSERT INTO rolesblacklist VALUES ($1)
            ON CONFLICT DO NOTHING
            ''', [(r.id,) for r in roles])
        await ctx.send('Added roles to blacklist.')

    @checks.db
    @commands.is_owner()
    @blacklist.command()
    async def remove(self, ctx, *roles: discord.Role):
        if not roles:
            await ctx.send('No roles given.')
            return
        await ctx.con.executemany('''
            DELETE FROM rolesblacklist WHERE role_id=$1
            ''', [(r.id,) for r in roles])
        await ctx.send('Removed roles from blacklist.')

    async def on_member_update(self, before, after):
        if before.activity != after.activity and after.activity is not None:
            role = discord.utils.get(after.guild.roles, name=after.activity.name)
            if role is None or role in after.roles:
                return
            async with self.bot.db_pool.acquire() as con:
                opted_out = await con.fetchval('''
                    SELECT EXISTS(SELECT * FROM rolesoptout WHERE user_id=$1)
                    ''', after.id)
                blacklisted = await con.fetchval('''
                    SELECT EXISTS(SELECT * FROM rolesblacklist WHERE role_id=$1)
                    ''', role.id)
            if not blacklisted and not opted_out:
                await after.add_roles(role)

    async def on_raw_reaction_add(self, payload):
        if payload.message_id != 503361951737577482 or payload.emoji.name not in ('\N{NO ENTRY SIGN}', '\N{WHITE QUESTION MARK ORNAMENT}'):
            return
        user = self.bot.get_guild(payload.guild_id).get_member(payload.user_id)
        async with self.bot.db_pool.acquire() as con:
            blacklisted = await self.get_blacklisted_roles(DummyCTX(user, con))
            if payload.emoji.name == '\N{WHITE QUESTION MARK ORNAMENT}':
                games = sorted(r.name for r in user.guild.roles if r not in blacklisted and r.name != '@everyone')
                await self.reaction_menu(games, user, user, count=0, header='**__Available Game Roles__**')
            else:
                await con.execute('''
                    INSERT INTO rolesoptout VALUES ($1)
                    ''', user.id)
                to_remove = [r for r in user.roles if r not in blacklisted and r.name != '@everyone']
                if to_remove:
                    await user.remove_roles(*to_remove)

    async def on_raw_reaction_remove(self, payload):
        if payload.message_id != 503361951737577482 or payload.emoji.name != '\N{NO ENTRY SIGN}':
            return
        user = self.bot.get_guild(payload.guild_id).get_member(payload.user_id)
        async with self.bot.db_pool.acquire() as con:
            await con.execute('''
                DELETE FROM rolesoptout WHERE user_id=$1
                ''', user.id)


def setup(bot):
    bot.add_cog(LTP(bot))
