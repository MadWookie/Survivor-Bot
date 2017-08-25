from random import randint
import time

from discord.ext import commands
import discord

from cogs.menus import Menus, ARROWS, CANCEL
from utils.json import Dict
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
        self.xp = Dict('xp', loop=bot.loop, int_keys=True)

    def check_cd(self, uid):
        if uid in self.xp:
            if time.time() - self.xp[uid]["cd"] < xp_cooldown:
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
        if self.check_cd(uid):
            if uid not in self.xp:
                self.xp[uid] = {
                    "cd": None,
                    "xp": 0,
                    "level": 0,
                    "prestige": 0
                }
            self.xp[uid]["cd"] = time.time()
            self.xp[uid]["xp"] += randint(xp_min_amount, xp_max_amount)
            if self.xp[uid]['xp'] >= level_req(self.xp[uid]['level'] + 1):
                self.xp[uid]['xp'] = abs(level_req(self.xp[uid]['level'] + 1) - self.xp[uid]['xp'])
                self.xp[uid]['level'] += 1
                if self.xp[uid]['level'] == 30:
                    self.xp[uid]['level'] = 0
                    self.xp[uid]['prestige'] += 1
                    await message.channel.send('**{}** has prestiged and is now prestige level **{}**!'.format(message.author.name, self.xp[uid]['prestige']))
                    return
                await message.channel.send('**{}** has reached level **{}**!'.format(message.author.name, self.xp[uid]['level']))
            await self.xp.save()

###################
#                 #
# LEVEL           #
#                 #
###################

    @checks.no_delete
    @commands.command(hidden=True)
    async def level(self, ctx, user: discord.Member = None):
        if user is None:
            user = ctx.author
        name = user.name
        uid = user.id
        if uid in self.xp:
            prestige = self.xp[uid]['prestige']
            level = self.xp[uid]['level']
            cur_xp = self.xp[uid]['xp']
            needed = level_req(level + 1)
        else:
            level, cur_xp, needed, prestige = (0, 0, 0, 0)
        thumbnail = 'http://unitedsurvivorsgaming.com/P{}.png'.format(prestige)
        print(len(str(cur_xp)))
        print(len(str(needed)))
        embed = discord.Embed(title='', colour=0xffffff)
        embed.set_author(name=name, icon_url=user.avatar_url)
        embed.set_thumbnail(url=thumbnail)
        embed.add_field(name='LEVEL', value=level)
        embed.add_field(name='XP', value='{}/{}'.format(cur_xp, needed))
        await ctx.send(embed=embed)

###################
#                 #
# RANK            #
#                 #
###################

    @commands.command()
    async def rank(self, ctx):
        ordered = sorted(self.xp.items(), key=lambda p: (p[1]['prestige'], p[1]['level'], p[1]['xp']), reverse=True)
        options = [[{'name': 'Rank', 'value': ''}, {'name': 'User', 'value': ''}]]
        on_cur_page = 0
        for ind, pair in enumerate(ordered, start=1):
            uid, stats = pair
            member = ctx.guild.get_member(uid)
            if member is None:
                continue
            if options[-1][0]['value']:
                options[-1][0]['value'] += '\n'
            options[-1][0]['value'] += '#{}'.format(ind)
            if options[-1][1]['value']:
                options[-1][1]['value'] += '\n'
            options[-1][1]['value'] += member.name
            on_cur_page += 1
            if on_cur_page == 10:
                options.append([{'name': 'Rank', 'value': ''}, {'name': 'User', 'value': ''}])
                on_cur_page = 0
        title = '**Leaderboard**'
        description = '{0[0]} Click to go back a page.\n{0[1]} Click to go forward a page.\n{1} Click to exit the list.'.format(ARROWS, CANCEL)
        await self.embed_reaction_menu(options, ctx.author, ctx.channel, 0, timeout=120, title=title, description=description)

###################
#                 #
# CLEANXP         #
#                 #
###################

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def cleanxp(self, ctx):
        ordered = sorted(self.xp.items(), key=lambda p: (p[1]['prestige'], p[1]['level'], p[1]['xp']))
        gone = []
        for uid, stats in ordered:
            member = ctx.guild.get_member(uid)
            if member is None:
                gone.append(uid)
                continue
        if gone:
            for uid in gone:
                self.xp.pop(uid)
            await self.xp.save()
        await ctx.send(':white_check_mark: Banned Members Purged.')


def setup(bot):
    bot.add_cog(Exp(bot))
