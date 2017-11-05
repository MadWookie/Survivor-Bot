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
            'Giveaway': ("GIVEAWAY", "GIVE AWAY"),
            '.io Games': (".IO", "IO", ".IOGAMES", "IOGAMES", "BROWSERGAMES", "FLASHGAMES"),
            'Aberoth': ("ABEROTH"),
            'Battlefield 1': ("BF1", "BATTLEFIELD 1", "BATTLEFIELDONE"),
            'Battlefield 4': ("BATTLEFIELD4", "BF4"),
            'Brawlhalla': ("BRAWLHALLA"),
            'Binding of Isaac': ("BINDING", "BINDINGOFISAAC", "BOI"),
            'Civilization V': ("CIV", "CIVV", "CIV5", "CIVILIZATIONV", "CIVILIZATION5", "CIVILIZATION"),
            'Civilization VI': ("NEWCIV", "CIVVI", "CIV6", "CIVILIZATIONVI", "CIVILIZATION6", "NEWCIVILIZATION"),
            'CSGO': ("CS:GO", "CSGO", "COUNTERSTRIKEGO", "COUNTERSTRIKEGLOBALOFFENCIVE"),
            'Destiny 2': ("DESTINY2"),
            'Diablo 3': ("DIABLO3", "DIABLO3", "D3"),
            'Dont Starve Together': ("DST", "DONTSTARVE", "DONTSTARVETOGETHER"),
            'Dota 2': ("DOTA", "DOTA 2", "DOTA TWO", "DOTA2"),
            'Divinity: Orginal Sin 2': ("DUNGEONS&DRAGONS", "DND", "D&D", "DIVINITY", "DIVINITY2", "DIVINITY:ORGINALSIN", "DIVINITY:ORGINALSIN2", "DIVINITYORIGINALSIN", "DIVINITYORIGINALSIN2"),
            'Garrys Mod': ("GMOD", "GARRYSMOD"),
            'Geometry Dash': ("GEOMETRYDASH", "GD"),
            'GTAV': ("GTAV", "GTA5", "GRANDTHEFTAUTOFIVE", "GRANDTHEFTAUTOV" "GRANDTHEFTAUTO5"),
            'Guild Wars 2': ("GUILDWARS", "GW2", "GUILDWARS 2"),
            'Hearts of Iron IV': ("HOI4" "HEARTSOFIRON IV", "HEARTSOFIRON4", "HEARTSOFIRON"),
            'Heroes & Generals': ("H&G", "HEROES&GENERALS"),
            'Heroes of The Storm': ("HOTS", "HEROESOFTHESTORM"),
            'Hypixel': ("HYPIXEL"),
            'League of Legends': ("LEAGUEOFLEGENDS", "LOL", "LEAGUE", "IMFUCKINGTILTED", "TILTED"),
            'Left 4 Dead 2': ("LEFTFORDEAD2", "LEFT4DEAD2", "L4D2", "LEFT4DEAD", "LEFTFORDEAD"),
            'Men of War: Assault Squad 2': ("MOW:AS2", "MOW", "MENOFWAR", "MENOFWAR:ASSAULTSQUAD2", "MOWAS2", "AS2", "ASSAULTSQUAD", "ASSAULTSQUAD2"),
            'Minecraft': ("MINECRAFT", "MC"),
            'Mount & Blade: Warband': ("MOUNTANDBLADE", "MOUNTANDBLADE:WARBAND", "MOUNT&BLADE", "MOUNT&BLADE:WARBAND", "M&B", "WARBAND"),
            'osu!': ("OSU", "OSU!"),
            'Overwatch': ("OVERWATCH"),
            'Paladins': ("PALADINS"),
            'Paragon': ("PARAGON"),
            'Path of Exile': ("PATHOFEXILE", "POE"),
            'Payday': ("PAYDAY", "PAYDAY 2"),
            'Project Reality': ("PROJECTREALITY", "PR", "PR:BF2"),
            'PUBG': ("PUBG", "PLAYERUNKNOWNBATTLEGROUND", "PLAYERUNKNOWNBATTLEGROUNDS", "PLAYERUNKNOWN", "BATTLEGROUND"),
            'RimWorld': ("RIMWORLD"),
            'Roblox': ("ROBLOX", "KIDSGAME"),
            'Rocket League': ("ROCKETLEAGUE", "ROCKETLEAGUE"),
            'Runescape': ("RUNESCAPE", "RS", "OSRS", "RS3"),
            'Rust': ("RUST", "NAKEDPEOPLEWITHROCKS"),
            'Smash Bros': ("SMASHBROS", "SMASH"),
            'Smite': ('SMITE'),
            'Starbound': ("STARBOUND"),
            'Team Fortress 2': ("TF2", "TEAMFORTRESS2"),
            'Unturned': ("UNTURNED"),
            'Verdun': ("VERDUN"),
            'Warframe': ("WARFRAME", "WARFRAME"),
            'War Thunder': ("WARTHUNDER", "WT"),
            'Wikian': ("WIKIA", "WIKIAN", "FANDOM", "WIKI"),
            'World of Tanks': ("WOT", "WORLDOFTANKS"),
            'World of Warcraft': ("WOW", "WORLDOFWARCRAFT", "WARCRAFT"),
            'World of Warplanes': ("WORLDOFWARPLANES", "WARPLANES"),
            'World of Warships': ("WORLDOFWARSHIPS", "WARSHIPS")
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
