from random import randint
import time

from discord.ext import commands
import discord

from cogs.menus import Menus, ARROWS, CANCEL
from utils import checks

xp_cooldown = 60
xp_min_amount = 15
xp_max_amount = 25
# xp_min_amount = 30 #Double XP
# xp_max_amount = 50 #Double XP


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
            if time.time() - self.cooldowns[member.guild.id][member.id] < xp_cooldown:
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
            add_xp = randint(xp_min_amount, xp_max_amount)
            async with self.bot.db_pool.acquire() as con:
                for wait in range(3):  # try updating XP 3 times.
                    try:
                        async with con.transaction(isolation='serializable'):
                            rec = await con.fetchrow('''
                                SELECT xp, level, prestige FROM experience WHERE user_id = $1 AND guild_id = $2
                                ''', uid, gid) or {'xp': 0, 'level': 0, 'prestige': 0}
                            self.cooldowns[gid][uid] = time.time()
                            xp = rec['xp'] + add_xp
                            level = rec['level']
                            prestige = rec['prestige']
                            to_next_level = level_req(level + 1)
                            if xp >= to_next_level:
                                xp -= to_next_level
                                level += 1
                                if level == 30:
                                    level = 0
                                    prestige += 1
                                    prestiged = True
                                else:
                                    leveled = True
                            await con.execute('''
                                INSERT INTO experience (guild_id, user_id, xp, level, prestige) VALUES ($1, $2, $3, $4, $5)
                                ON CONFLICT (guild_id, user_id) DO
                                UPDATE SET xp = $3, level = $4, prestige = $5
                                ''', gid, uid, xp, level, prestige)
                    except asyncpg.SerializationError:
                        prestiged = False  # in case fails 3 times
                        leveled = False
                        await asyncio.sleep(wait)
                        continue
                    else:
                        break
            if prestiged:
                await message.channel.send(f'**{message.author.name}** has prestiged and is now prestige level **{prestige}**!')
            elif leveled:
                await message.channel.send(f'**{message.author.name}** has reached level **{level}**!')

###################
#                 #
# LEVEL           #
#                 #
###################

    @checks.db
    @checks.no_delete
    @commands.command(hidden=True)
    async def level(self, ctx, user: discord.Member = None):
        if user is None:
            user = ctx.author
        name = user.name
        uid = user.id
        gid = ctx.guild.id
        rec = await ctx.con.fetchrow('''
            SELECT xp, level, prestige FROM experience WHERE user_id = $1 AND guild_id = $2
            ''', uid, gid) or {'xp': 0, 'level': 0, 'prestige': 0}
        xp, level, prestige = rec['xp'], rec['level'], rec['prestige']
        to_next_level = level_req(level + 1)
        thumbnail = f'http://unitedsurvivorsgaming.com/P{prestige}.png'
        embed = discord.Embed(colour=0xffffff)
        embed.set_author(name=name, icon_url=user.avatar_url)
        embed.set_thumbnail(url=thumbnail)
        embed.add_field(name='LEVEL', value=level)
        embed.add_field(name='XP', value=f'{xp}/{to_next_level}')
        await ctx.send(embed=embed)

###################
#                 #
# RANK            #
#                 #
###################

    @checks.db
    @commands.command()
    async def rank(self, ctx):
        ordered = await ctx.con.fetch('''
            SELECT * FROM experience WHERE guild_id = $1 ORDER BY prestige DESC, level DESC, xp DESC
            ''', ctx.guild.id)
        options = [[{'name': 'Rank', 'value': ''}, {'name': 'User', 'value': ''}]]
        on_cur_page = 0
        ind = 1
        for xp in ordered:
            if on_cur_page == 10:
                options.append([{'name': 'Rank', 'value': ''}, {'name': 'User', 'value': ''}])
                on_cur_page = 0
            uid, stats = pair
            member = ctx.guild.get_member(uid)
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
    @commands.command()
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
        await ctx.send(f':white_check_mark: {removed} removed members purged.')


def setup(bot):
    bot.add_cog(Exp(bot))
