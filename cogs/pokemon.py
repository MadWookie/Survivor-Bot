from fuzzywuzzy import process
from itertools import groupby
from random import randint
import asyncpg
import asyncio
import re

from discord.ext import commands
import aiohttp
import discord

from cogs.menus import Menus, STAR, GLOWING_STAR, SPARKLES, SPACER, ARROWS, DONE, CANCEL
from utils import errors, checks
from utils.utils import wrap


pokeballs = ('Pokeball', 'Greatball', 'Ultraball', 'Masterball')


def pokechannel():
    def check(ctx):
        if ctx.channel.name in ['pokemon']:
            return True
        raise errors.WrongChannel(discord.utils.get(ctx.guild.channels, name='pokemon'))
    return commands.check(check)


def xp_to_level(level):
    return (level ** 3) // 2


def level_from_xp(xp):
    return int((xp * 2) ** (1/3))


def catch(mon, ball):
    r = randint(1, 100)
    legendary = mon['legendary']
    mythical = mon['mythical']
    if (ball == 0 and r < (15 if mythical else 25 if legendary else 50)) \
            or (ball == 1 and r < (25 if mythical else 35 if legendary else 75)) \
            or (ball == 2 and r < (35 if mythical else 50 if legendary else 90)) \
            or (ball == 3 and r < (65 if mythical else 90 if legendary else 100)):
        return True
    return False


def poke_converter(ctx, user_or_num):
    if user_or_num is None:
        return None
    match = re.match(r'<@!?([0-9]*)>$', user_or_num)
    if match is not None:
        return ctx.guild.get_member(int(match.group(1)))
    if user_or_num.isdigit():
        return int(user_or_num)
    else:
        return user_or_num


def is_shiny(trainer: asyncpg.Record, personality: int):
    b = bin(personality)[2:].zfill(32)
    upper, lower = map(int, (b[:16], b[16:]))
    return (((trainer['user_id'] % 65536) ^ trainer['secret_id']) ^ (upper ^ lower)) <= (65536 / 400)


def get_star(mon: asyncpg.Record):
    return GLOWING_STAR if mon['mythical'] else STAR if mon['legendary'] else ''


async def get_pokemon_color(ctx, num=0, *, mon: asyncpg.Record=None):
    if num:
        mon = await ctx.con.fetch('''
            SELECT type FROM pokemon WHERE num = $1 AND form_id = 0
            ''', num)
    if mon is not None:
        colors = await ctx.con.fetch('''
            SELECT color FROM types WHERE name = ANY($1)''', mon['type'])
        return round(sum(color['color'] for color in colors) / len(colors))
    return 0

async def set_inventory(ctx, uid, inv):
    return await ctx.con.execute('''
        UPDATE trainers SET inventory = $1 WHERE user_id = $2
        ''', inv, uid)


async def get_found_counts(ctx, uid):
    return await ctx.con.fetch('''
        SELECT num, form_id, COUNT(*) AS count,
        (SELECT name || (CASE WHEN mythical THEN '$2' WHEN legendary THEN '$3' ELSE '' END) FROM pokemon WHERE pokemon.num = found.num LIMIT 1),
        (SELECT form FROM pokemon WHERE pokemon.num = found.num AND pokemon.form_id = found.form_id)
        FROM found WHERE owner = $1 GROUP BY num, form_id ORDER BY num, form_id
        ''', uid, GLOWING_STAR, STAR)

async def get_rewards(ctx):
    return await ctx.con.fetch('''
        SELECT * FROM rewards
        ''')


async def get_evolution_chain(ctx, num):
    chain = [await ctx.con.fetchrow('''
        SELECT prev, next,
        (SELECT name || (CASE WHEN mythical THEN $2 WHEN legendary THEN $3 ELSE '' END) FROM pokemon p WHERE p.num = e.num LIMIT 1) AS name
        FROM evolutions e WHERE num = $1
        ''', num, GLOWING_STAR, STAR)]
    cur_ind = 0
    if chain[0]['prev'] is not None:
        chain.insert(0, await ctx.con.fetchrow('''
            SELECT prev,
            (SELECT name || (CASE WHEN mythical THEN $2 WHEN legendary THEN $3 ELSE '' END) FROM pokemon p WHERE p.num = e.num LIMIT 1) AS name
            FROM evolutions e WHERE next = $1
            ''', num, GLOWING_STAR, STAR))
        cur_ind += 1
        if chain[0]['prev'] is not None:
            chain.insert(0, await ctx.con.fetchrow('''
                SELECT name || (CASE WHEN mythical THEN $2 WHEN legendary THEN $3 ELSE '' END) AS name FROM pokemon WHERE num = $1 LIMIT 1
                ''', chain[0]['prev'], GLOWING_STAR, STAR))
            cur_ind += 1
    if chain[-1]['next'] is not None:
        chain.extend(await ctx.con.fetch('''
            SELECT
            (SELECT name || (CASE WHEN mythical THEN $2 WHEN legendary THEN $3 ELSE '' END) FROM pokemon p WHERE p.num = e.num LIMIT 1) AS name,
            (SELECT ARRAY(SELECT (SELECT name || (CASE WHEN mythical THEN $2 WHEN legendary THEN $3 ELSE '' END) AS name FROM pokemon p WHERE p.num = e2.num LIMIT 1)
                          FROM evolutions e2 WHERE e2.num = e.next)) AS next
            FROM evolutions e WHERE prev = $1
            ''', num, GLOWING_STAR, STAR))
    if len(chain) == 1:
        return 'This Pokémon does not evolve.'
    start = '\N{BALLOT BOX WITH CHECK}'.join(r['name'] for r in chain[:cur_ind + 1])
    after = chain[cur_ind + 1:]
    chains = []
    # Option 1
    # A -> B -> D
    # A -> C -> E
    if not after:
        chains.append(start)
    else:
        for m in after:
            m = dict(m)
            if not m['next']:
                chains.append(ARROWS[1].join((start, m['name'])))
            else:
                for name in m['next']:
                    chains.append(ARROWS[1].join((start, m['name'], name)))
    return '\n'.join(chains)
    # Option 2
    # A -> B | C -> D | E
    # return ARROWS[1].join((start,
    #                        ' | '.join(nxt['name'] for nxt in after),
    #                        ' | '.join(last for nxt in after for last in nxt['next'])))

async def get_player(ctx, uid):
    player_data = await ctx.con.fetchrow("""
                                INSERT INTO trainers (user_id) VALUES ($1)
                                ON CONFLICT (user_id) DO UPDATE SET user_id=$1
                                RETURNING *
                                """, uid)
    return player_data

async def get_player_pokemon(ctx, uid):
    player_pokemon = await ctx.con.fetch("""
                                   SELECT * FROM found WHERE owner=$1
                                   """, uid)
    return player_pokemon

async def get_pokemon(ctx, num):
    mon_info = await ctx.con.fetchrow("""
                             SELECT * FROM pokemon WHERE num=$1
                             """, num)
    return mon_info

async def is_legendary(ctx, num, uid, id):
    count = await ctx.con.fetch("""
                          SELECT COUNT(*) FROM found WHERE owner=$1 AND id=$2 AND num=ANY(SELECT num 
                          FROM pokemon WHERE num=$3 AND legendary=True)
                          """, uid, id, num)
    return count[0]['count'] > 0

async def is_mythical(ctx, num, uid, id):
    count = await ctx.con.fetch("""
                          SELECT COUNT(*) FROM found WHERE owner=$1 AND id=$2 AND num=ANY(SELECT num 
                          FROM pokemon WHERE num=$3 AND mythical=True)
                          """, uid, id, num)
    return count[0]['count'] > 0


class Pokemon(Menus):
    def __init__(self, bot):
        self.bot = bot
        self.image_path = 'data/pokemon/images/{}/{}-{}.gif'
        self.trades = {}

###################
#                 #
# INVENTORY       #
#                 #
###################

    @checks.db
    @commands.command(aliases=['inv'])
    @pokechannel()
    async def inventory(self, ctx):
        thumbnail = 'http://unitedsurvivorsgaming.com/backpack.png'
        player_data = await get_player(ctx, ctx.author.id)
        inv = player_data['inventory']
        all_items = await ctx.con.fetch('''
            SELECT name FROM items ORDER BY id ASC
            ''')
        em = discord.Embed(title=f'{ctx.author.name} | {inv["money"]}\ua750')
        items = []
        for item in all_items[1:]:
            if inv.get(item['name']) or item['name'].endswith('ball'):
                key = self.bot.get_emoji_named(item['name']) or item['name']
                items.append(f"{key} | {inv.get(item['name'])}")
        em.set_thumbnail(url=thumbnail)
        em.add_field(name='Inventory', value='\n'.join(items))
        await ctx.send(embed=em, delete_after=60)

###################
#                 #
# REWARD          #
#                 #
###################

    @checks.db
    @commands.command()
    @commands.cooldown(1, 10800, commands.BucketType.user)
    @pokechannel()
    async def reward(self, ctx):
        """Collect a reward for free every 3 hours!"""
        user = ctx.author
        player_data = await get_player(ctx, user.id)
        inv = player_data['inventory']
        reward = await ctx.con.fetchrow('''
            SELECT * FROM rewards ORDER BY random() LIMIT 1
            ''')
        item, count = reward['name'], reward['num']
        inv[item] = inv.get(item, 0) + count
        await set_inventory(ctx, user.id, inv)
        await ctx.send(f"{user.name} has recived {count} **{item}{'s' if count != 1 else ''}**!", delete_after=60)

###################
#                 #
# POKEMON         #
#                 #
###################

    @checks.db
    @commands.group(invoke_without_command=True, aliases=['pokemen', 'pokermon'])
    @commands.cooldown(1, 150, commands.BucketType.user)
    @pokechannel()
    async def pokemon(self, ctx):
        """Gives you a random Pokemon!"""
        player_name = ctx.author.name
        player_id = ctx.author.id
        mon = await ctx.con.fetchrow('''
            SELECT num, name, form, form_id, type, legendary, mythical, rand(4294967295) as personality,
            (SELECT form FROM pokemon p2 WHERE p2.num = pokemon.num AND p2.form_id = 0) AS base_form,
            (SELECT ARRAY(SELECT color FROM types WHERE types.name = ANY(type))) AS colors 
            FROM pokemon ORDER BY random() LIMIT 1''')
        trainer = await get_player(ctx, player_id)
        inv = trainer['inventory']
        balls = [self.bot.get_emoji_named(ball) for ball in pokeballs if inv.get(ball)]
        star = GLOWING_STAR if mon['mythical'] else STAR if mon['legendary'] else ''
        shiny = is_shiny(trainer, mon['personality'])
        if shiny:
            if mon['base_form']:
                form = mon['base_form'] + ' '
            else:
                form = ''
            form_id = 0
        else:
            if mon['form']:
                form = mon['form'] + ' '
            else:
                form = ''
            form_id = mon['form_id']
        shine = SPARKLES if shiny else ''
        embed = discord.Embed(description=f'A wild {shine}**{form}{mon["name"]}**{star} appears!'
                                          f'\nUse a {balls[0]} to catch it!')
        embed.color = await get_pokemon_color(ctx, mon=mon)
        embed.set_author(icon_url=ctx.author.avatar_url, name=player_name)
        embed.set_image(url='attachment://pokemon.gif')
        await ctx.con.execute('''
            INSERT INTO seen (user_id, num) VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            ''', player_id, mon['num'])
        msg = await ctx.send(embed=embed, file=discord.File(open(self.image_path.format('normal', mon['num'], 0), 'rb'),
                                                            filename='pokemon.gif'))
        can_react_with = [*balls, CANCEL]
        for emoji in can_react_with:
            await msg.add_reaction(emoji)
        try:
            def check(reaction, user):
                return (reaction.emoji in can_react_with and
                        reaction.message.id == msg.id and
                        user == ctx.author)
            reaction, _ = await self.bot.wait_for('reaction_add', check=check, timeout=20)
        except asyncio.TimeoutError:
            embed.description = f'{shine}**{form}{mon["name"]}**{star} escaped because you took too long! :stopwatch:'
            await msg.edit(embed=embed, delete_after=60)
            await msg.clear_reactions()
            return
        await msg.clear_reactions()
        if reaction.emoji in balls:
            if catch(mon, balls.index(reaction.emoji)):
                embed.description = wrap(f'You caught {shine}**{form}{mon["name"]}**{star} successfully!',
                                         reaction.emoji)
                await msg.edit(embed=embed, delete_after=60)
                level = await ctx.con.fetchval('''
                    SELECT level FROM evolutions WHERE next = $1
                    ''', mon['num']) or 0
                async with ctx.con.transaction():
                    await ctx.con.execute('''
                        INSERT INTO found (num, name, form_id, ball, exp, owner, original_owner, personality) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ''', mon['num'], mon['name'], form_id, reaction.emoji.name, xp_to_level(level), player_id, player_id, mon['personality'])
            else:
                embed.description = f'{shine}**{form}{mon["name"]}**{star} has escaped!'
                await msg.edit(embed=embed, delete_after=60)
            inv[reaction.emoji.name] -= 1
            await set_inventory(ctx, player_id, inv)
        else:
            embed.description = wrap(f'You ran away from {shine}**{form}{mon["name"]}**{star}!', ':chicken:')
            await msg.edit(embed=embed, delete_after=60)

###################
#                 #
# POKEDEX         #
#                 #
###################

    @checks.db
    @commands.group(invoke_without_command=True)
    @pokechannel()
    async def pokedex(self, ctx, *, query):
        """Shows you your Pokedex through a reaction menu."""
        pokedex = self.bot.get_emoji_named('Pokedex')

        query = poke_converter(ctx, query) or ctx.author

        total_pokemon = await ctx.con.fetchval("""
                                      SELECT COUNT(DISTINCT num) FROM pokemon
                                      """)
        if isinstance(query, discord.Member):
            found = await get_player_pokemon(ctx, query.id)
            found_sorted = sorted([mon['name'] for mon in found])
            total_found = len(set(found_sorted))
            remaining = total_pokemon - total_found

            legendaries = await ctx.con.fetchval("""
                                        SELECT COUNT(*) FROM found WHERE owner=$1 AND num=ANY((SELECT num FROM pokemon WHERE legendary=True))
                                        """, query.id)
            mythics = await ctx.con.fetchval("""
                                    SELECT COUNT(*) FROM found WHERE owner=$1 AND num=ANY((SELECT num FROM pokemon WHERE mythical=True))
                                    """, query.id)

            header = f"__{query.name}'s Pokedex__"
            if total_found == 0:
                header += " __is empty.__"
            header = wrap(header, pokedex)
            if total_found == 0:
                return await ctx.send(header, delete_after=60)
            spacer = SPACER * 21

            key = f'{ARROWS[0]} Click to go back a page.\n{ARROWS[1]} Click to go forward a page.\n{CANCEL}' \
                  f' Click to exit your pokedex.'

            counts = wrap(f'**{total_found}** collected out of {remaining} total Pokemon.'
                          f'\n**{total_found - mythics - legendaries}** Normal | **{legendaries}** Legendary {STAR}'
                          f' | **{mythics}** Mythical {GLOWING_STAR}', spacer, sep='\n')

            header = '\n'.join([header, 'Use **!pokedex** ``#`` to take a closer look at your Pokémon!', key, counts])

            options = []
            for mon in found:
                mythical = await is_mythical(ctx, mon['num'], ctx.author.id, mon['id'])
                legendary = await is_legendary(ctx, mon['num'], ctx.author.id, mon['id'])
                count = found.count(mon)
                options.append("**{}.** {}{}{}".format(
                    mon['num'], mon['name'], GLOWING_STAR if mythical else STAR if legendary else '', count if
                    count > 1 else ''))
            await self.reaction_menu(options, ctx.author, ctx.channel, 0, per_page=20, code=False, header=header)
        elif isinstance(query, int):
            if 0 >= query or query > total_pokemon:
                return await ctx.send(f'Pokemon {query} does not exist.')

            image = self.image_path.format('normal', query, 0)
            info = await get_pokemon(ctx, query)

            evo = await get_evolution_chain(ctx, info['num'])
            embed = discord.Embed(description=wrap(f"__{info['name']}{get_star(info)}'s Information__", pokedex) +
                                              f"\n**ID:** {info['num']}"
                                              f"\n**Type:** {' & '.join(info['type'])}\n**Evolutions:**\n {evo}")
            embed.color = await get_pokemon_color(ctx, mon=info)
            embed.set_image(url='attachment://pokemon.gif')
            await ctx.send(embed=embed, file=discord.File(open(image, 'rb'), filename='pokemon.gif'), delete_after=120)
        elif isinstance(query, str):
            pokemon_records = await ctx.con.fetch("""
                                          SELECT name FROM pokemon
                                          """)
            pokemon_names = [mon['name'] for mon in pokemon_records]
            result = list(process.extractOne(query, pokemon_names))
            if result[1] < 70:
                return await ctx.send(f'Pokemon {query} does not exist.')
            pokemon_number = await ctx.con.fetchval("""
                                           SELECT num FROM pokemon WHERE name=$1
                                           """, result[0])
            info = await get_pokemon(ctx, pokemon_number)
            image = self.image_path.format('shiny' if 'shiny' in query.lower() else 'normal', info['num'], 0)

            evo = await get_evolution_chain(ctx, info['num'])
            embed = discord.Embed(description=wrap(f"__{info['name']}{get_star(info)}'s Information__", pokedex) +
                                              f"\n**ID:** {info['num']}"
                                              f"\n**Type:** {' & '.join(info['type'])}\n**Evolutions:**\n {evo}")
            embed.color = await get_pokemon_color(ctx, mon=info)
            embed.set_image(url='attachment://pokemon.gif')
            await ctx.send(embed=embed, file=discord.File(open(image, 'rb'), filename='pokemon.gif'), delete_after=120)

    @checks.db
    @pokedex.command(name='shiny')
    @pokechannel()
    async def pokedex_shiny(self, ctx, *, query):
        pokedex = self.bot.get_emoji_named('Pokedex')

        query = poke_converter(ctx, query) or ctx.author

        total_pokemon = await ctx.con.fetchval("""
                                      SELECT COUNT(DISTINCT num) FROM pokemon
                                      """)
        if isinstance(query, discord.Member):
            found = await get_player_pokemon(ctx, query.id)
            found_sorted = sorted([mon['name'] for mon in found])
            total_found = len(set(found_sorted))
            remaining = total_pokemon - total_found

            legendaries = await ctx.con.fetchval("""
                                        SELECT COUNT(*) FROM found WHERE owner=$1 AND num=ANY((SELECT num FROM pokemon WHERE legendary=True))
                                        """, query.id)
            mythics = await ctx.con.fetchval("""
                                    SELECT COUNT(*) FROM found WHERE owner=$1 AND num=ANY((SELECT num FROM pokemon WHERE mythical=True))
                                    """, query.id)

            header = f"__{query.name}'s Pokedex__"
            if total_found == 0:
                header += " __is empty.__"
            header = wrap(header, pokedex)
            if total_found == 0:
                return await ctx.send(header, delete_after=60)
            spacer = SPACER * 21

            key = f'{ARROWS[0]} Click to go back a page.\n{ARROWS[1]} Click to go forward a page.' \
                  f'\n{CANCEL} Click to exit your pokedex.'

            counts = wrap(f'**{total_found}** collected out of {remaining} total Pokemon.'
                          f'\n**{total_found - mythics - legendaries}** Normal | **{legendaries}** Legendary {STAR}'
                          f' | **{mythics}** Mythical {GLOWING_STAR}', spacer, sep='\n')

            header = '\n'.join([header, 'Use **!pokedex** ``#`` to take a closer look at your Pokémon!', key, counts])
            options = []
            for mon in found:
                mythical = await is_mythical(ctx, mon['num'], ctx.author.id, mon['id'])
                legendary = await is_legendary(ctx, mon['num'], ctx.author.id, mon['id'])
                count = found.count(mon)
                options.append("**{}.** {}{}{}".format(
                    mon['num'], mon['name'], GLOWING_STAR if mythical else STAR if legendary else '', count if
                    count > 1 else ''))
            await self.reaction_menu(options, ctx.author, ctx.channel, 0, per_page=20, code=False, header=header)
        elif isinstance(query, int):
            if 0 >= query or query > total_pokemon:
                return await ctx.send(f'Pokemon {query} does not exist.')

            image = self.image_path.format('shiny', query, 0)
            info = await get_pokemon(ctx, query)

            evo = await get_evolution_chain(ctx, info['num'])
            embed = discord.Embed(description=wrap(f"__{info['name']}{get_star(info)}'s Information__", pokedex) +
                                              f"\n**ID:** {info['num']}\n**Type:** {' & '.join(info['type'])}"
                                              f"\n**Evolutions:**\n {evo}")
            embed.color = await get_pokemon_color(ctx, mon=info)
            embed.set_image(url='attachment://pokemon.gif')
            await ctx.send(embed=embed, file=discord.File(open(image, 'rb'), filename='pokemon.gif'), delete_after=120)
        elif isinstance(query, str):
            pokemon_records = await ctx.con.fetch("""
                                          SELECT name FROM pokemon
                                          """)
            pokemon_names = [mon['name'] for mon in pokemon_records]
            result = list(process.extractOne(query, pokemon_names))
            if result[1] < 70:
                return await ctx.send(f'Pokemon {query} does not exist.')
            pokemon_number = await ctx.con.fetchval("""
                                           SELECT num FROM pokemon WHERE name=$1
                                           """, result[0])
            info = await get_pokemon(ctx, pokemon_number)
            image = self.image_path.format('shiny', info['num'], 0)

            evo = await get_evolution_chain(ctx, info['num'])
            embed = discord.Embed(description=wrap(f"__{info['name']}{get_star(info)}'s Information__", pokedex) +
                                              f"\n**ID:** {info['num']}"
                                              f"\n**Type:** {' & '.join(info['type'])}\n**Evolutions:**\n {evo}")
            embed.color = await get_pokemon_color(ctx, mon=info)
            embed.set_image(url='attachment://pokemon.gif')
            await ctx.send(embed=embed, file=discord.File(open(image, 'rb'), filename='pokemon.gif'), delete_after=120)

###################
#                 #
# SHOP            #
#                 #
###################

    @checks.db
    @commands.group(invoke_without_command=True)
    @pokechannel()
    async def shop(self, ctx, multiple=1):
        if not multiple:
            return
        player_name = ctx.author.name
        player_data = await get_player(ctx, ctx.author.id)
        inventory = player_data['inventory']
        thumbnail = 'http://unitedsurvivorsgaming.com/shop.png'
        title = f'{player_name} | {inventory["money"]}\ua750'
        description = 'Select items to buy{}.'.format(f' in multiples of {multiple}' if multiple > 1 else '')
        balls = await ctx.con.fetch("""
                              SELECT name, price FROM items WHERE price != 0 AND name LIKE '%ball'
                              """)
        display_dict = {}
        for ball in balls:
            display_dict[ball['name']] = discord.utils.get(self.bot.emojis, name=ball['name'])
        options = ['{} {[price]}\ua750 **|** Inventory: {}'.format(display_dict[data['name']], data,
                                                                   inventory[data['name']]) for data in balls]

        selected = await self.embed_menu(options, 'Shop', ctx.author, ctx.channel, -1,
                                         description=description, title=title, thumbnail=thumbnail,
                                         return_from=list(range(len(balls))), multi=True,
                                         display=list(display_dict.values()))
        if not selected:
            return
        bought = []
        total = 0
        for item in set(selected):
            count = selected.count(item) * multiple
            item_info = balls[item]
            item_price, item_name = item_info['price'], item_info['name']
            price = item_price * count
            after = inventory['money'] - price
            if after < 0:
                continue
            total += price
            bought.extend([item] * count)
            inventory['money'] = after
            inventory[item_name] += count
        if total == 0:
            await ctx.send(f"{player_name} didn't buy anything because they're too poor.", delete_after=60)
        else:
            display = []
            for item in set(bought):
                display.append(str(list(display_dict.values())[item]))
                count = bought.count(item)
                if count > 1:
                    display[-1] += f' x{count}'
            await ctx.send(f'{player_name} bought the following for {total}\ua750:\n' + '\n'.join(display),
                           delete_after=60)
            await set_inventory(ctx, ctx.author.id, inventory)

###################
#                 #
# SELL            #
#                 #
###################

    @checks.db
    @shop.command()
    @pokechannel()
    async def sell(self, ctx):
        spacer = SPACER * 24
        player_name = ctx.author.name
        user_pokemon = await get_player_pokemon(ctx, ctx.author.id)
        player_data = await get_player(ctx, ctx.author.id)
        inventory = player_data['inventory']
        found_names = [poke['name'] for poke in user_pokemon]
        header = f'**{player_name}**,\nSelect Pokemon to sell.\n' + wrap(f'**100**\ua750 Normal | **600**\ua750'
                                                                         f' Legendary {STAR} | **1000**\ua750'
                                                                         f' Mythical {GLOWING_STAR}', spacer, sep='\n')
        options = []
        for mon in user_pokemon:
            mythical = await is_mythical(ctx, mon['num'], ctx.author.id, mon['id'])
            legendary = await is_legendary(ctx, mon['num'], ctx.author.id, mon['id'])
            count = user_pokemon.count(mon)
            options.append("**{}.** {}{}{}".format(
                mon['num'], mon['name'], GLOWING_STAR if mythical else STAR if legendary else '', count if
                count > 1 else ''))
        if not options:
            await ctx.send("You don't have any pokemon to sell.", delete_after=60)
            return
        selected = await self.reaction_menu(options, ctx.author, ctx.channel, -1, per_page=20, header=header,
                                            code=False, multi=True, return_from=user_pokemon, display=found_names)
        if not selected:
            return
        sold = []
        total = 0
        for mon in [k for k, v in groupby(sorted(selected))]:
            count = selected.count(mon)
            if await is_mythical(ctx, mon['num'], ctx.author.id, mon['id']):
                total += 1000
            elif await is_legendary(ctx, mon['num'], ctx.author.id, mon['id']):
                total += 600
            else:
                total += 100
            await ctx.con.execute("""
                          DELETE FROM found WHERE id=$1
                          """, mon['id'])
            sold.append("**{}**{}".format(mon['name'], f' *x{count}*' if count > 1 else ''))
            inventory['money'] += total
        await set_inventory(ctx, ctx.author.id, inventory)
        await ctx.send(f'{player_name} sold the following for {total}\ua750:\n' + '\n'.join(sold), delete_after=60)

###################
#                 #
# TRADE           #
#                 #
###################

    @commands.command()
    @pokechannel()
    async def trade(self, ctx, user: discord.Member):
        """Trade pokemon with another user."""
        author = ctx.author
        if author.id == user.id:
            await ctx.send('You cannot trade with yourself.', delete_after=60)
            return
        channel = ctx.channel
        cancelled = '**{.name}** cancelled the trade.'
        fmt = '**{}.** {[name]}{}{}'
        a_data = self.get_player(author.id)['pokemon']
        a_found = {k: v for k, v in a_data.items() if v}
        a_sorted = sorted(a_found)
        a_names = [self.poke_info[num]['name'] for num in a_sorted]
        a_options = [fmt.format(mon, self.poke_info[mon], GLOWING_STAR if self.poke_info[mon]['mythical']
                                else STAR if self.poke_info[mon]['legendary'] else '', f' *x{a_found[mon]}*'
                                if a_found[mon] > 1 else '') for mon in a_sorted]
        b_data = self.get_player(user.id)['pokemon']
        b_found = {k: v for k, v in b_data.items() if v}
        b_sorted = sorted(b_found)
        b_names = [self.poke_info[num]['name'] for num in b_sorted]
        b_options = [fmt.format(mon, self.poke_info[mon], GLOWING_STAR if self.poke_info[mon]['mythical']
                                else STAR if self.poke_info[mon]['legendary'] else '', f' *x{b_found[mon]}*'
                                if b_found[mon] > 1 else '') for mon in b_sorted]
        header = '**{.name}**,\nSelect the pokemon you wish to trade with **{.name}**'
        selected = await asyncio.gather(self.reaction_menu(a_options, author, channel, -1, code=False,
                                                           header=header.format(author, user), return_from=a_sorted,
                                                           allow_none=True, multi=True, display=a_names),

                                        self.reaction_menu(b_options, user, channel, -1, code=False,
                                                           header=header.format(user, author), return_from=b_sorted,
                                                           allow_none=True, multi=True, display=b_names))
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
                    await ctx.send(f'{member.name} selected more {self.poke_info[mon]["name"]} than they have.',
                                   delete_after=60)
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
