import asyncio

from discord.ext import commands
import discord

from cogs.menus import Menus, ARROWS, CANCEL
from utils.utils import wrap
from utils import errors


def ltpchannel():
    def check(ctx):
        if ctx.channel.name in ['role-assigning']:
            return True
        raise errors.WrongChannel(discord.utils.get(ctx.guild.channels, name='role-assigning'))
    return commands.check(check)


class LTP(Menus):
    def __init__(self, bot):
        self.bot = bot
        self.game_aliases = {
            'League of Legends': ("LEAGUEOFLEGENDS", "LOL", "LEAGUE", "IMFUCKINGTILTED", "TILTED"),
            'Minecraft': ("MINECRAFT", "MC"),
            'Diablo 3': ("DIABLO3", "DIABLO3", "D3"),
            'Civilization V': ("CIV", "CIVV", "CIV5", "CIVILIZATIONV", "CIVILIZATION5", "CIVILIZATION"),
            'Civilization VI': ("NEWCIV", "CIVVI", "CIV6", "CIVILIZATIONVI", "CIVILIZATION6", "NEWCIVILIZATION"),
            'Heroes & Generals': ("H&G", "HEROES&GENERALS"),
            'Aberoth': ("ABEROTH"),
            'Men of War: Assault Squad 2': ("MOW:AS2", "MOW", "MENOFWAR", "MENOFWAR:ASSAULTSQUAD2", "MOWAS2", "AS2", "ASSAULTSQUAD", "ASSAULTSQUAD2"),
            'Mount & Blade: Warband': ("MOUNTANDBLADE", "MOUNTANDBLADE:WARBAND", "MOUNT&BLADE", "MOUNT&BLADE:WARBAND", "M&B", "WARBAND"),
            'Roblox': ("ROBLOX", "KIDSGAME"),
            'Project Reality': ("PROJECTREALITY", "PR", "PR:BF2"),
            'World of Warcraft': ("WOW", "WORLDOFWARCRAFT", "WARCRAFT"),
            'D&D': ("DUNGEONS&DRAGONS", "DND", "D&D"),
            'RimWorld': ("RIMWORLD"),
            'Battlefield 1': ("BF1", "BATTLEFIELD 1", "BATTLEFIELDONE"),
            'Hypixel': ("HYPIXEL"),
            'Wikian': ("WIKIA", "WIKIAN", "FANDOM", "WIKI"),
            'World of Tanks': ("WOT", "WORLDOFTANKS"),
            'Brawlhalla': ("BRAWLHALLA"),
            'Smash Bros': ("SMASHBROS", "SMASH"),
            'Overwatch': ("OVERWATCH"),
            'CSGO': ("CS:GO", "CSGO", "COUNTERSTRIKEGO", "COUNTERSTRIKEGLOBALOFFENCIVE"),
            'Guild Wars 2': ("GUILDWARS", "GW2", "GUILDWARS 2"),
            'Heroes of The Storm': ("HOTS", "HEROESOFTHESTORM"),
            'Rocket League': ("ROCKETLEAGUE", "ROCKETLEAGUE"),
            'World of Warships': ("WORLDOFWARSHIPS", "WARSHIPS"),
            'War Thunder': ("WARTHUNDER", "WT"),
            'Warframe': ("WARFRAME", "WARFRAME"),
            'Garrys Mod': ("GMOD", "GARRYSMOD"),
            'Battlefield 4': ("BATTLEFIELD4", "BF4"),
            'Left 4 Dead 2': ("LEFTFORDEAD2", "LEFT4DEAD2", "L4D2", "LEFT4DEAD", "LEFTFORDEAD"),
            'Team Fortress 2': ("TF2", "TEAMFORTRESS2"),
            'World of Warplanes': ("WORLDOFWARPLANES", "WARPLANES"),
            'Geometry Dash': ("GEOMETRYDASH", "GD"),
            'osu!': ("OSU", "OSU!"),
            'Runescape': ("RUNESCAPE", "RS"),
            'Paragon': ("PARAGON"),
            'Dont Starve Together': ("DST", "DONTSTARVE", "DONTSTARVETOGETHER"),
            'Hearts of Iron IV': ("HOI4" "HEARTSOFIRON IV", "HEARTSOFIRON4", "HEARTSOFIRON"),
            'Binding of Isaac': ("BINDING", "BINDINGOFISAAC", "BOI"),
            'Path of Exile': ("PATHOFEXILE", "POE"),
            'Smite': ('SMITE'),
            'Starbound': ("STARBOUND"),
            'Rust': ("RUST", "NAKEDPEOPLEWITHROCKS"),
            '.io Games': (".IO", "IO", ".IOGAMES", "IOGAMES", "BROWSERGAMES", "FLASHGAMES"),
            'Verdun': ("VERDUN"),
            'Payday': ("PAYDAY", "PAYDAY 2"),
            'Unturned': ("UNTURNED"),
            'Paladins': ("PALADINS"),
            'GTAV': ("GTAV", "GTA5", "GRANDTHEFTAUTOFIVE", "GRANDTHEFTAUTOV" "GRANDTHEFTAUTO5"),
            'PUBG': ("PUBG", "PLAYERUNKNOWNBATTLEGROUND", "PLAYERUNKNOWNBATTLEGROUNDS", "PLAYERUNKNOWN", "BATTLEGROUND"),
            'Destiny 2': ("DESTINY2")
        }

###################
#                 #
# LTP             #
#                 #
###################

    async def game_role_helper(self, ctx, member, game_name, toggle):
        if toggle:
            say_temps = (':x: You\'re already assigned to the **{role}** role.',
                         ':white_check_mark: Assigned **{role}** role.',
                         ':x: **Invalid Game**.\nWant a game added? Ask *__MadWookie__* to add it.')
        else:
            say_temps = (':x: You\' not assigned to the **{role}** role.',
                         ':white_check_mark: Removed **{role}** role.',
                         ':x: **Invalid Game**.\nWant a game added? Ask *__MadWookie__* to add it.')
        changed = False
        role_name = None
        for game, aliases in self.game_aliases.items():
            if game_name.upper().replace(' ', '') in aliases:
                role = discord.utils.get(ctx.guild.roles, name=game)
                role_name = game
                if toggle:
                    if role not in member.roles:
                        await member.add_roles(role)
                        changed = True
                else:
                    if role in member.roles:
                        await member.remove_roles(role)
                        changed = True
                break
        else:
            changed = 2
        await ctx.send(say_temps[int(changed)].format(role=role_name), delete_after=20)

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
        for i, game in enumerate(self.game_aliases.keys()):  # Fix logic to only remove roles the member has
            await asyncio.sleep(1)
            try:
                role = discord.utils.get(ctx.guild.roles, name=game)
                await member.remove_roles(role)
            except discord.Forbidden:
                pass
            await emsg.edit(content=temp.format(((i * 2) % 12) + 1))
        await emsg.edit(content=':white_check_mark: Removed **all** game roles.', delete_after=15)

    @ltpchannel()
    @ltp.command()
    async def stop(self, ctx, *, game_name: str):
        """Removes you from a specified game role."""
        await self.game_role_helper(ctx, ctx.author, game_name, False)

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

    @ltpchannel()
    @ltp.command(name='list')
    async def list_roles(self, ctx):
        roles = sorted(self.game_aliases.keys())
        header = "**Game List**"
        spacer = '-=-=-=--=-=-=--=-=-=--=-=-=-=-=-=-=-=-=-=-=-=-=-=-'
        key = f'{ARROWS[0]} Click to go back a page.\n{ARROWS[1]} Click to go forward a page.\n{CANCEL} Click to exit the list.'
        info = wrap('To assign yourself one of these roles just use **!ltp ``Game``**.', spacer, sep='\n')
        header = '\n'.join([header, key, info])
        await self.reaction_menu(roles, ctx.author, ctx.channel, 0, per_page=20, timeout=120, code=False, header=header, return_from=roles)


def setup(bot):
    bot.add_cog(LTP(bot))
