import asyncio

from discord.ext import commands
import discord

from cogs.menus import Menus, ARROWS, CANCEL
from utils import errors


def wrap(to_wrap, wrap_with, sep=' '):
    return "{1}{2}{0}{2}{1}".format(to_wrap, wrap_with, sep)


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
            'League of Legends': ("LEAGUE OF LEGENDS", "LOL", "LEAGUE", "IM FUCKING TILTED", "TILTED"),
            'Minecraft': ("MINECRAFT", "MC"),
            'Diablo 3': ("DIABLO 3", "DIABLO3", "D3"),
            'Civilization V': ("CIV", "CIV V", "CIV 5", "CIVILIZATION V", "CIVILIZATION 5", "CIVILIZATION"),
            'Civilization VI': ("NEW CIV", "CIV VI", "CIV 6", "CIVILIZATION VI", "CIVILIZATION 6", "NEW CIVILIZATION"),
            'Heroes & Generals': ("H&G", "HEROES & GENERALS"),
            'Aberoth': ("ABEROTH"),
            'Men of War: Assault Squad 2': ("MOW:AS2", "MOW", "MEN OF WAR", "MEN OF WAR: ASSAULT SQUAD 2", "MOWAS2", "AS2", "ASSAULT SQUAD", "ASSAULT SQUAD 2"),
            'Mount & Blade: Warband': ("MOUNT AND BLADE", "MOUNT AND BLADE: WARBAND", "MOUNT & BLADE", "MOUNT & BLADE: WARBAND", "M&B", "WARBAND"),
            'Roblox': ("ROBLOX", "KIDS GAME"),
            'Project Reality': ("PROJECT REALITY", "PR", "PR:BF2"),
            'World of Warcraft': ("WOW", "WORLD OF WARCRAFT", "WARCRAFT"),
            'D&D': ("DUNGEONS & DRAGONS", "DND", "D&D"),
            'RimWorld': ("RIMWORLD", "RIMJOBWORLD", "RIM WORLD", "RIM JOB WORLD"),
            'Battlefield 1': ("BF1", "BATTLEFIELD 1", "BATTLEFIELD ONE"),
            'Hypixel': ("HYPIXEL"),
            'WynnCraft': ("WYNNCRAFT"),
            'Wikian': ("WIKIA", "WIKIAN", "FANDOM", "WIKI"),
            'World of Tanks': ("WOT", "WORLD OF TANKS"),
            'Brawlhalla': ("BRAWLHALLA", "BRAWL HALLA"),
            'Smash Bros': ("SMASH BROS", "SMASHBROS", "SMASH"),
            'Overwatch': ("OVERWATCH", "OW", "OVER WATCH"),
            'CSGO': ("CS:GO", "CS GO", "COUNTER STRIKE GO", "COUNTER STRIKE GLOBAL OFFENCIVE", "CSGO"),
            'Guild Wars 2': ("GUILD WARS", "GW2", "GUILD WARS 2"),
            'Heroes of The Storm': ("HOTS", "HEROES OF THE STORM"),
            'Rocket League': ("ROCKET LEAGUE", "ROCKETLEAGUE"),
            'World of Warships': ("WORLD OF WARSHIPS", "WARSHIPS"),
            'War Thunder': ("WAR THUNDER", "WARTHUNDER", "WT"),
            'Warframe': ("WARFRAME", "WAR FRAME"),
            'Garrys Mod': ("GMOD", "GARRYS MOD"),
            'Battlefield 4': ("BATTLEFIELD 4", "BF4", "BATTLE FIELD 4"),
            'Left 4 Dead 2': ("LEFT FOR DEAD 2", "LEFT 4 DEAD 2", "L4D2", "LEFT4DEAD2", "LEFTFORDEAD2", "LEFT 4 DEAD", "LEFT FOR DEAD"),
            'Team Fortress 2': ("TF2", "TEAM FORTRESS 2", "TEAMFORTRESS2"),
            'World of Warplanes': ("WORLD OF WARPLANES", "WARPLANES"),
            'Geometry Dash': ("GEOMETRY DASH", "GD"),
            'osu!': ("OSU", "OSU!"),
            'Runescape': ("RUNESCAPE", "RS"),
            'Paragon': ("PARAGON"),
            'Dont Starve Together': ("DST", "DONT STARVE", "DONT STARVE TOGETHER"),
            'Hearts of Iron IV': ("HOI4" "HEARTS OF IRON IV", "HEARTS OF IRON 4", "HEARTS OF IRON"),
            'Binding of Isaac': ("BINDING", "BINDING OF ISAAC", "BOI"),
            'Path of Exile': ("PATH OF EXILE", "POE"),
            'Smite': ('SMITE'),
            'Starbound': ("STARBOUND", "STAR BOUND"),
            'Rust': ("RUST", "NAKED PEOPLE WITH ROCKS"),
            '.io Games': (".IO GAMES", "IO GAMES", "BROWSER GAMES", "FLASH GAMES", ".IO", "IO", ".IOGAMES", "IOGAMES"),
            'Verdun': ("VERDUN"),
            'Payday': ("PAYDAY", "PAYDAY 2"),
            'Unturned': ("UNTURNED"),
            'Paladins': ("PALADINS"),
            'PUBG': ("PUBG", "PLAYERUNKNOWN BATTLEGROUND", "PLAYERUNKNOWN BATTLEGROUNDS", "PLAYER UNKNOWN BATTLEGROUND", "PLAYER UNKNOWN BATTLEGROUNDS", "PLAYERUNKNOWN", "PLAYER UNKNOWN BATTLE GROUND")
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
            if game_name.upper() in aliases:
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
        key = '{0[0]} Click to go back a page.\n{0[1]} Click to go forward a page.\n{1} Click to exit the list.'.format(ARROWS, CANCEL)
        info = wrap('To assign yourself one of these roles just use **!ltp ``Game``**.', spacer, sep='\n')
        header = '\n'.join([header, key, info])
        await self.reaction_menu(roles, ctx.author, ctx.channel, 0, per_page=20, timeout=120, code=False, header=header, return_from=roles)


def setup(bot):
    bot.add_cog(LTP(bot))
