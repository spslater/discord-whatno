"""Test and general functions Cog"""
from discord.ext.commands import Cog, command
from discord.commands import slash_command

ALLOW_SLASH = [365677277821796354, 248732519204126720]

def setup(bot):
    """Add the Test Cog to the Bot"""
    bot.add_cog(WNTestCog(bot))

class WNTestCog(Cog, name="General"):
    """Test commands for the WhatnoBot"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @command()
    async def test(self, ctx):
        """Send a message to test this command is working

        this is extra info... shh!
        """
        return await ctx.send("Test recieved! :D")

    @slash_command(guild_ids=ALLOW_SLASH, name="test")
    async def slashtest(self, ctx):
        """Send a message to test slash command is working

        this is extra info... shh!
        """
        await ctx.respond("Slash test recieved! :D")
