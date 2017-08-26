from collections import Counter
from random import randint
import asyncio
import re

from discord.ext import commands
import aiohttp
import discord

from cogs.menus import Menus, ARROWS, DONE, CANCEL
from utils.json import Dict, List
from utils.utils import wrap
from utils import errors

ITEMS = [{'price': 10, 'name': 'pokeballs', 'display': lambda c: discord.utils.get(c.guild.emojis, name='Pokeball')},
         {'price': 100, 'name': 'ultraballs', 'display': lambda c: discord.utils.get(c.guild.emojis, name='Ultraball')},
         {'price': 500, 'name': 'masterballs', 'display': lambda c: discord.utils.get(c.guild.emojis, name='Masterball')}]


def pokechannel():
    def check(ctx):
        if ctx.channel.name in ['pokemon']:
            return True
        raise errors.WrongChannel(discord.utils.get(ctx.guild.channels, name='pokemon'))
    return commands.check(check)


def catch(mon, ball):
    if ball == 2:
        return True
    r = randint(1, 100)
    legendary = mon['legendary']
    if (ball == 0 and r < (25 if legendary else 50)) \
            or (ball == 1 and r < (50 if legendary else 90)):
        return True
    return False


def poke_converter(ctx, user_or_num):
    if user_or_num is None:
        return None
    match = re.match(r'<@!?([0-9]*)>$', user_or_num)
    if match is not None:
        return ctx.guild.get_member(int(match.group(1)))
    try:
        return int(user_or_num)
    except ValueError:
        return None


class Pokemon(Menus):
    def __init__(self, bot):
        self.bot = bot
        self.image_path = 'data/pokemon/images/{}/{}-{}.gif'
        self.trades = {}
        self.poke_info = Dict('pokemon', 'pokemon', loop=bot.loop, int_keys=True)
        self.rewards = List('rewards', 'pokemon', loop=bot.loop)

        def int_keys_and_counter():
            for uid, data in self.found_pokemon.copy().items():
                self.found_pokemon[int(uid)] = self.found_pokemon.pop(uid)
                for mon, count in data['pokemon'].copy().items():
                    if count:
                        data['pokemon'][int(mon)] = data['pokemon'].pop(mon)
                data['pokemon'] = Counter(data['pokemon'])
        self.found_pokemon = Dict('found_pokemon', 'pokemon', loop=bot.loop, after_load=int_keys_and_counter)

    def get_player(self, uid):
        if uid not in self.found_pokemon:
            self.found_pokemon[uid] = {'pokemon': Counter(), 'inventory': {'money': 1500, 'pokeballs': 40, 'ultraballs': 5, 'masterballs': 1}}
        return self.found_pokemon[uid]

###################
#                 #
# INVENTORY       #
#                 #
###################

    @commands.command(aliases=['inv'])
    @pokechannel()
    async def inventory(self, ctx):
        inv = self.get_player(ctx.author.id)['inventory']
        em = discord.Embed(title=f'{ctx.author.name} | {inv["money"]}\ua750')
        items = [f'{item["display"](ctx)} | {inv[item["name"]]}' for item in ITEMS]
        em.add_field(name='Inventory', value='\n'.join(items))
        await ctx.send(embed=em, delete_after=60)

###################
#                 #
# REWARD          #
#                 #
###################

    @commands.command()
    @commands.cooldown(1, 10800, commands.BucketType.user)
    @pokechannel()
    async def reward(self, ctx):
        """Collect a reward for free every 3 hours!"""
        player_name = ctx.author.name
        userdata = self.get_player(ctx.author.id)
        reward_bullet = randint(1, 5)
        if reward_bullet == 1:
            userdata['inventory']['money'] += 250
        elif reward_bullet == 2:
            userdata['inventory']['money'] += 500
        elif reward_bullet == 3:
            userdata['inventory']['pokeballs'] += 1
        elif reward_bullet == 4:
            userdata['inventory']['pokeballs'] += 5
        elif reward_bullet == 5:
            userdata['inventory']['ultraballs'] += 1
        await ctx.send(f'{player_name} has recived **{self.rewards[reward_bullet - 1]}**!', delete_after=60)
        await self.found_pokemon.save()

###################
#                 #
# POKEMON         #
#                 #
###################

    @commands.group(invoke_without_command=True, aliases=['pokemen', 'pokermon'])
    @commands.cooldown(1, 150, commands.BucketType.user)
    @pokechannel()
    async def pokemon(self, ctx):
        """Gives you a random Pokemon!"""
        player_name = ctx.author.name
        player_id = ctx.author.id
        poke_bullet = randint(1, len(self.poke_info))
        mon = self.poke_info[poke_bullet]
        userdata = self.get_player(player_id)
        balls = [item['display'](ctx) for item in ITEMS]
        embed = discord.Embed(description=f'A wild **{mon["name"]}** appears!\nUse a {balls[0]} to catch it!')
        embed.set_author(icon_url=ctx.author.avatar_url, name=player_name)
        embed.set_image(url='attachment://pokemon.gif')
        msg = await ctx.send(embed=embed, file=discord.File(open(self.image_path.format('normal', poke_bullet, 0), 'rb'), filename='pokemon.gif'))
        can_react_with = []
        for item, emoji in zip(('pokeballs', 'ultraballs', 'masterballs'), balls):
            if userdata['inventory'][item]:
                can_react_with.append(emoji)
        can_react_with.append('\u274c')
        for emoji in can_react_with:
            await msg.add_reaction(emoji)
        try:
            def check(reaction, user):
                return (reaction.emoji in can_react_with and
                        reaction.message.id == msg.id and
                        user == ctx.author)
            reaction, _ = await self.bot.wait_for('reaction_add', check=check, timeout=20)
        except asyncio.TimeoutError:
            embed.description = f'**{mon["name"]}** escaped because you took too long! :stopwatch:'
            await msg.edit(embed=embed, delete_after=60)
            await msg.clear_reactions()
            return
        await msg.clear_reactions()
        if reaction.emoji in balls:
            if catch(mon, balls.index(reaction.emoji)):
                embed.description = wrap(f'You caught **{mon["name"]}** successfully!', reaction.emoji)
                await msg.edit(embed=embed, delete_after=60)
                userdata['pokemon'][poke_bullet] += 1
            else:
                embed.description = f'**{mon["name"]}** has escaped!'
                await msg.edit(embed=embed, delete_after=60)
            item = reaction.emoji.name.lower() + 's'
            userdata['inventory'][item] -= 1
            await self.found_pokemon.save()
        else:
            embed.description = wrap(f'You ran away from **{mon["name"]}**!', ':chicken:')
            await msg.edit(embed=embed, delete_after=60)

###################
#                 #
# POKEDEX         #
#                 #
###################

    @commands.command()
    @pokechannel()
    async def pokedex(self, ctx, user_or_num=None, shiny=''):
        """Shows you your Pokedex through a reaction menu."""
        pokedex_emote = discord.utils.get(ctx.guild.emojis, name='Pokedex')
        user_or_num = poke_converter(ctx, user_or_num) or ctx.author
        if isinstance(user_or_num, discord.abc.User):
            player = user_or_num
            found = {k: v for k, v in self.get_player(player.id)['pokemon'].items() if v}
            found_sorted = sorted(found)
            total = len(found)
            remaining = len(self.poke_info)
            legendaries = sum(1 for p in found if self.poke_info[p]['legendary'])
            header = f"__{player.name}'s Pokedex__"
            if total == 0:
                header += " __is empty.__"
            header = wrap(header, pokedex_emote)
            if total == 0:
                await ctx.send(header, delete_after=60)
                return
            spacer = '-=-=-=--=-=-=--=-=-=--=-=-=-=-=-=-=-=-=-=-=-=-=-=-'
            key = f'{ARROWS[0]} Click to go back a page.\n{ARROWS[1]} Click to go forward a page.\n{CANCEL} Click to exit your pokedex.'
            counts = wrap(f'**{total}** Pokémon out of {remaining}, **{total - legendaries}** Normals, **{legendaries}** Legendaries', spacer, sep='\n')
            header = '\n'.join([header, 'Use **!pokedex ``#``** to take a closer look at your Pokémon!', key, counts])
            options = ['**{}.** {[name]}{}'.format(mon, self.poke_info[mon], f' *x{found[mon]}*' if found[mon] > 1 else '') for mon in found_sorted]
            await self.reaction_menu(options, ctx.author, ctx.channel, 0, per_page=20, code=False, header=header)
        else:
            image = self.image_path.format('shiny' if shiny else 'normal', user_or_num, 0)
            info = self.poke_info[user_or_num]
            evo = info['evolutions'].format(ething='é', evolved=':ballot_box_with_check:', not_evolved=':arrow_right:')
            embed = discord.Embed(title=wrap(f"__{info['name']}'s Information__", pokedex_emote),
                                  description=f"**Type:** {info['type']}\n**Evolutions:** {evo}")
            embed.set_image(url='attachment://pokemon.gif')
            await ctx.send(embed=embed, file=discord.File(open(image, 'rb'), filename='pokemon.gif'), delete_after=120)

###################
#                 #
# SHOP            #
#                 #
###################

    @commands.group(invoke_without_command=True)
    @pokechannel()
    async def shop(self, ctx, multiple=1):
        if not multiple:
            return
        player_name = ctx.author.name
        userdata = self.get_player(ctx.author.id)
        title = f'{player_name} | {userdata["inventory"]["money"]}\ua750'
        description = 'Select items to buy{}.'.format(f' in multiples of {multiple}' if multiple > 1 else '')
        options = ['{} {[price]}\ua750 **|** Inventory: {}'.format(data['display'](ctx), data, userdata['inventory'][data['name']]) for data in ITEMS]
        balls = [item['display'](ctx) for item in ITEMS]
        selected = await self.embed_menu(options, 'Shop', ctx.author, ctx.channel, -1, description=description, title=title, return_from=list(range(len(ITEMS))), multi=True, display=balls)
        if not selected:
            return
        bought = []
        total = 0
        for item in set(selected):
            count = selected.count(item) * multiple
            price = ITEMS[item]['price'] * count
            after = userdata['inventory']['money'] - price
            if after < 0:
                continue
            total += price
            bought.extend([item] * count)
            userdata['inventory']['money'] = after
            userdata['inventory'][ITEMS[item]['name']] += count
        if total == 0:
            await ctx.send(f"{player_name} didn't buy anything because they're too poor.", delete_after=60)
        else:
            display = []
            for item in set(bought):
                display.append(str(ITEMS[item]['display'](ctx)))
                count = bought.count(item)
                if count > 1:
                    display[-1] += f' x{count}'
            await ctx.send(f'{player_name} bought the following for {total}\ua750:\n' + '\n'.join(display), delete_after=60)
            await self.found_pokemon.save()

###################
#                 #
# SELL            #
#                 #
###################

    @shop.command()
    @pokechannel()
    async def sell(self, ctx):
        player_name = ctx.author.name
        userdata = self.get_player(ctx.author.id)
        found = {k: v for k, v in userdata['pokemon'].items() if v}
        found_sorted = sorted(found)
        found_names = [self.poke_info[num]['name'] for num in found_sorted]
        header = f'**{player_name}**,\nSelect Pokemon to sell.\nNormal = 100\ua750\nLegendary = 600\ua750'
        options = ['**{}.** {[name]}{}'.format(mon, self.poke_info[mon], f' *x{found[mon]}*' if found[mon] > 1 else '') for mon in found_sorted]
        if not options:
            await ctx.send("You don't have any pokemon to sell.", delete_after=60)
            return
        selected = await self.reaction_menu(options, ctx.author, ctx.channel, -1, per_page=20, header=header, code=False, multi=True, return_from=found_sorted, display=found_names)
        if not selected:
            return
        sold = []
        total = 0
        for mon in set(selected):
            while selected.count(mon) > found[mon]:
                selected.remove(mon)
            count = selected.count(mon)
            total += 600 if self.poke_info[mon]['legendary'] else 100
            userdata['pokemon'][mon] -= count
            if not userdata['pokemon'][mon]:
                userdata['pokemon'].pop(mon)
            sold.append('**{[name]}**{}'.format(self.poke_info[mon], f' *x{count}*' if count > 1 else ''))
        userdata['inventory']['money'] += total
        await self.found_pokemon.save()
        await ctx.send(f'{player_name} sold the following for {total}\ua750:\n' + '\n'.join(sold), delete_after=60)

###################
#                 #
# TRADE           #
#                 #
###################

    @pokemon.command()
    @pokechannel()
    async def trade(self, ctx, user: discord.Member):
        """Trade pokemon with another user."""
        author = ctx.author
        if author.id == user.id:
            await ctx.send('You cannot trade with yourself.', delete_after=60)
            return
        channel = ctx.channel
        cancelled = '**{.name}** cancelled the trade.'
        fmt = '**{}.** {[name]}{}'
        a_data = self.get_player(author.id)['pokemon']
        a_found = {k: v for k, v in a_data.items() if v}
        a_sorted = sorted(a_found)
        a_names = [self.poke_info[num]['name'] for num in a_sorted]
        a_options = [fmt.format(mon, self.poke_info[mon], f' *x{a_found[mon]}*' if a_found[mon] > 1 else '') for mon in a_sorted]
        b_data = self.get_player(user.id)['pokemon']
        b_found = {k: v for k, v in b_data.items() if v}
        b_sorted = sorted(b_found)
        b_names = [self.poke_info[num]['name'] for num in b_sorted]
        b_options = [fmt.format(mon, self.poke_info[mon], f' *x{b_found[mon]}*' if b_found[mon] > 1 else '') for mon in b_sorted]
        header = '**{.name}**,\nSelect the pokemon you wish to trade with **{.name}**'
        selected = await asyncio.gather(self.reaction_menu(a_options, author, channel, -1, code=False, header=header.format(author, user), return_from=a_sorted, allow_none=True, multi=True, display=a_names),
                                        self.reaction_menu(b_options, user, channel, -1, code=False, header=header.format(user, author), return_from=b_sorted, allow_none=True, multi=True, display=b_names))
        if all(s is None for s in selected):
            await ctx.send('No one responded to the trade.', delete_after=60)
            return
        elif selected[0] is None:
            await ctx.send(cancelled.format(author), delete_after=60)
            return
        elif selected[1] is None:
            await ctx.send(cancelled.format(user), delete_after=60)
            return
        for selections, found, member in zip(selected, (a_found, b_found), (author, user)):
            for mon in set(selections):
                if selections.count(mon) > found[mon]:
                    await ctx.send(f'{member.name} selected more {self.poke_info[mon]["name"]} than they have.', delete_after=60)
                    return
        accept_msg = await ctx.send("**{.name}**'s offer: {}\n**{.name}**'s offer: {}\nDo you accept?".format(
            author, ', '.join(fmt.format(mon, self.poke_info[mon], '') for mon in selected[0]) or 'None',
            user, ', '.join(fmt.format(mon, self.poke_info[mon], '') for mon in selected[1]) or 'None'))
        await accept_msg.add_reaction(DONE)
        await accept_msg.add_reaction(CANCEL)
        accepted = {author.id: None, user.id: None}
        accept_reaction = None
        reacted = None

        def accept_check(reaction, reaction_user):
            if reaction.message.id != accept_msg.id or reaction.emoji not in (DONE, CANCEL):
                return False
            if reaction.emoji == DONE:
                nonlocal accept_reaction
                accept_reaction = reaction
            if reaction_user.id in accepted:
                accept = reaction.emoji == DONE
                accepted[reaction_user.id] = accept
                if not accept:
                    return True
            return all(isinstance(value, bool) for value in accepted.values())

        try:
            with aiohttp.Timeout(60):
                while True:
                    await self.bot.wait_for('reaction_add', check=accept_check)
                    if accepted[author.id] and accepted[user.id]:
                        reacted = await accept_reaction.users().flatten()
                        if author in reacted and user in reacted:
                            break
                    elif any(not value for value in accepted.values()):
                        break
        except asyncio.TimeoutError:
            pass

        if all(accepted[u.id] is None for u in (author, user)):
            await ctx.send('No one responded to the trade.', delete_after=60)
            return

        for u in (author, user):
            if reacted and u not in reacted:
                accepted[u.id] = False
            if not accepted[u.id]:
                await ctx.send(f'**{u.name}** declined the trade.', delete_after=60)
                return
        for mon in selected[0]:
            a_data[mon] -= 1
            if not a_data[mon]:
                a_data.pop(mon)
            b_data[mon] += 1
        for mon in selected[1]:
            b_data[mon] -= 1
            if not b_data[mon]:
                b_data.pop(mon)
            a_data[mon] += 1
        await self.found_pokemon.save()
        await ctx.send(f'Completed trade between **{author.name}** and **{user.name}**.', delete_after=60)


def setup(bot):
    bot.add_cog(Pokemon(bot))
