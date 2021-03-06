from random import randint
import time
import asyncpg
import asyncio

from discord.ext import commands
import discord

from cogs.menus import Menus, ARROWS, CANCEL
from utils import checks

exp_cooldown = 60
exp_min_amount = 15
exp_max_amount = 25
# exp_min_amount = 30 #Double EXP
# exp_max_amount = 50 #Double EXP


def level_req(level):
    return round(100 * (1.1**(level - 1)))


def total_level(to):
    return sum(level_req(level) for level in range(1, to + 1))


def clean_name(name):
    return name.replace("`", "\\`").replace("@", "@" + u'\u200b')


class Exp(Menus):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}

    def check_cd(self, member):
        if member.guild.id not in self.cooldowns:
            self.cooldowns[member.guild.id] = {}
        if member.id in self.cooldowns[member.guild.id]:
            if time.time() - self.cooldowns[member.guild.id][member.id] < exp_cooldown:
                return False
        return True

###################
#                 #
# ON_MESSAGE      #
#                 #
###################

    async def on_message(self, message):
        if message.author.bot or await self.bot.is_command(message):
            return
        uid = message.author.id
        gid = message.guild.id
        if self.check_cd(message.author):
            prestiged = False
            leveled = False
            add_exp = randint(exp_min_amount, exp_max_amount)
            async with self.bot.db_pool.acquire() as con:
                for wait in range(3):  # try updating XP 3 times.
                    try:
                        async with con.transaction(isolation='serializable'):
                            rec = await con.fetchrow('''
                                SELECT exp, level, prestige FROM experience WHERE user_id = $1 AND guild_id = $2
                                ''', uid, gid) or {'exp': 0, 'level': 0, 'prestige': 0}
                            self.cooldowns[gid][uid] = time.time()
                            exp = rec['exp'] + add_exp
                            level = rec['level']
                            prestige = rec['prestige']
                            to_next_level = level_req(level + 1)
                            if exp >= to_next_level:
                                exp -= to_next_level
                                level += 1
                                if level == 30:
                                    level = 0
                                    prestige += 1
                                    prestiged = True
                                else:
                                    leveled = True
                            await con.execute('''
                                INSERT INTO experience (guild_id, user_id, exp, level, prestige) VALUES ($1, $2, $3, $4, $5)
                                ON CONFLICT (guild_id, user_id) DO
                                UPDATE SET exp = $3, level = $4, prestige = $5
                                ''', gid, uid, exp, level, prestige)
                    except asyncpg.SerializationError:
                        prestiged = False  # in case fails 3 times
                        leveled = False
                        await asyncio.sleep(wait)
                        continue
                    else:
                        break
            if prestiged:
                await message.channel.send(f'**{message.author.name}** has prestiged and is now prestige level **{prestige}**!', delete_after=120)
            elif leveled:
                await message.channel.send(f'**{message.author.name}** has reached level **{level}**!', delete_after=120)

###################
#                 #
# LEVEL           #
#                 #
###################

    @checks.db
    @checks.no_delete
    @commands.command()
    async def level(self, ctx, user: discord.Member = None):
        """Shows your or another persons level."""
        if user is None:
            user = ctx.author
        name = user.name
        uid = user.id
        gid = ctx.guild.id
        rec = await ctx.con.fetchrow('''
            SELECT exp, level, prestige FROM experience WHERE user_id = $1 AND guild_id = $2
            ''', uid, gid) or {'exp': 0, 'level': 0, 'prestige': 0}
        exp, level, prestige = rec['exp'], rec['level'], rec['prestige']
        to_next_level = level_req(level + 1)
        thumbnail = f'http://pokebot.xyz/static/img/prestige/P{prestige}.png'
        embed = discord.Embed(colour=0xffffff)
        embed.set_author(name=name, icon_url=user.avatar_url)
        embed.set_thumbnail(url=thumbnail)
        embed.add_field(name='LEVEL', value=level)
        embed.add_field(name='EXP', value=f'{exp}/{to_next_level}')
        await ctx.send(embed=embed, delete_after=60)

###################
#                 #
# RANK            #
#                 #
###################

    @checks.db
    @commands.command()
    async def rank(self, ctx):
        """Shows the EXP leaderboard."""
        ordered = await ctx.con.fetch('''
            SELECT * FROM experience WHERE guild_id = $1 ORDER BY prestige DESC, level DESC, exp DESC
            ''', ctx.guild.id)
        options = [[{'name': 'Rank', 'value': ''}, {'name': 'User', 'value': ''}]]
        on_cur_page = 0
        ind = 1
        for exp in ordered:
            if on_cur_page == 10:
                options.append([{'name': 'Rank', 'value': ''}, {'name': 'User', 'value': ''}])
                on_cur_page = 0
            member = ctx.guild.get_member(exp['user_id'])
            if member is None:
                continue
            if options[-1][0]['value']:
                options[-1][0]['value'] += '\n'
            options[-1][0]['value'] += f'#{ind}'
            if options[-1][1]['value']:
                options[-1][1]['value'] += '\n'
            options[-1][1]['value'] += member.name
            ind += 1
            on_cur_page += 1
        title = '**Leaderboard**'
        description = f'{ARROWS[0]} Click to go back a page.\n{ARROWS[1]} Click to go forward a page.\n{CANCEL} Click to exit the list.'
        await self.embed_reaction_menu(options, ctx.author, ctx.channel, 0, timeout=120, title=title, description=description)

###################
#                 #
# CLEANXP         #
#                 #
###################

    @checks.db
    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def cleanxp(self, ctx):
        in_guild = [r['user_id'] for r in await ctx.con.fetch('''
            SELECT user_id FROM experience WHERE guild_id = $1
            ''', ctx.guild.id)]
        remove = []
        for uid in in_guild:
            if ctx.guild.get_member(uid) is None:
                remove.append(uid)
        async with ctx.con.transaction():
            res = await ctx.con.execute('''
                DELETE FROM experience WHERE user_id = ANY($1)
                ''', remove)
        removed = res.split()[-1]
        await ctx.send(f':white_check_mark: {removed} removed members purged.', delete_after=60)


def setup(bot):
    bot.add_cog(Exp(bot))
