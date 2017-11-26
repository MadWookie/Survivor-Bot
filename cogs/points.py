import asyncio

from discord.ext import commands
import discord

from utils import checks


class Points:
    def __init__(self, bot):
        self.bot = bot

###################
#                 #
# BUMP            #
#                 #
###################

    @checks.db
    @commands.command()
    @commands.guild_only()
    async def bump(self, ctx):
        """Bump the server through ServerHound and get points for it."""
        user = ctx.author.name
        hound = 222853335877812224
        hidden_channel = discord.utils.get(ctx.guild.channels, name='logs')
        if not hidden_channel:
            await ctx.send('Hidden channel does not exist, just use ``=bump``')
            return

        def check(m):
            return m.author.id == hound and m.channel.id == hidden_channel.id

        await hidden_channel.send('=bump', delete_after=5)
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=5)
        except asyncio.TimeoutError:
            reply = 'There is an issue with ServerHound. Please try again in a bit.',
        else:
            if 'Bumped' in msg.content:
                reply = f'**{user}** has bumped the server! *+2 point!*'
                await ctx.con.execute('''
                    INSERT INTO bumps (guild_id, user_id, total, current) VALUES
                    ($1, $2, 1, 2) ON CONFLICT (guild_id, user_id) DO
                    UPDATE SET total = bumps.total + 1, current = bumps.current + 2
                    ''', ctx.guild.id, ctx.author.id)
            elif 'wait' in msg.content:
                reply = f'{msg.content}.'
            else:
                reply = msg.content
        await ctx.send(reply, delete_after=120)

###################
#                 #
# BALANCE         #
#                 #
###################

    @checks.db
    @commands.command(aliases=['bal'])
    @commands.guild_only()
    async def balance(self, ctx):
        """See how many times you've bumped the server through ServerHound."""
        user = ctx.author.name
        row = await ctx.con.fetchrow('''
            SELECT total, current FROM bumps WHERE guild_id = $1 AND user_id = $2
            ''', ctx.guild.id, ctx.author.id)
        if row is None:
            total, current = 0, 0
        else:
            total, current = row['total'], row['current']
        await ctx.send(f'**{user}**, you have bumped this server **{total}** times, and have a balance of **{current}**.', delete_after=120)

###################
#                 #
# PAY             #
#                 #
###################

    @checks.db
    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def pay(self, ctx, member: discord.Member, amount: int):
        """Allows admins to give people points."""
        await ctx.con.execute('''
            INSERT INTO bumps (guild_id, user_id, total, current) VALUES
            ($1, $2, $3, $3) ON CONFLICT (guild_id, user_id) DO
            UPDATE SET current = bumps.current + $3
            ''', ctx.guild.id, member.id, amount)
        await ctx.send(f'**{member.name}** has been given {amount} points.')

###################
#                 #
# RANKUP          #
#                 #
###################

    @checks.db
    @commands.command()
    @commands.guild_only()
    async def rankup(self, ctx):
        """Allows users to rank up using points."""
        member = ctx.message.author
        member_role = discord.utils.get(ctx.guild.roles, id=185182567648067584)
        dedicated_role = discord.utils.get(ctx.guild.roles, id=374441904286334976)
        veteran_role = discord.utils.get(ctx.guild.roles, id=374441810438914059)
        survivor_role = discord.utils.get(ctx.guild.roles, id=374444597620899840)
        current = await ctx.con.fetchval('''
            SELECT current FROM bumps WHERE guild_id = $1 AND user_id = $2
            ''', ctx.guild.id, ctx.author.id) or 0
        if member_role in member.roles:
            cost = 25
            new_role = dedicated_role
            old_role = member_role
        elif dedicated_role in member.roles:
            cost = 50
            new_role = veteran_role
            old_role = dedicated_role
        elif veteran_role in member.roles:
            cost = 100
            new_role = survivor_role
            old_role = veteran_role
        elif survivor_role in member.roles:
            await ctx.send(f'**{member.name}**, you already have the highest rank avalible.', delete_after=120)
            return
        else:
            await ctx.send(f'**{member.name}**, you don\'t have any roles, please contact a staff member to get this fixed.', delete_after=120)
            return
        if current >= cost:
            await ctx.con.execute('''
                UPDATE bumps SET current = current - $3 WHERE guild_id = $1 AND user_id = $2
                ''', ctx.guild.id, member.id, cost)
            await member.add_roles(new_role)
            await member.remove_roles(old_role)
            await ctx.send(f'**{member.name}** has ranked up and is now a {new_role}.', delete_after=120)
        else:
            await ctx.send(f'*Sorry* **{member.name}**, you don\'t have enough points to rank up.\nYou still need **{cost - current}** points to rank up.', delete_after=120)


def setup(bot):
    bot.add_cog(Points(bot))
