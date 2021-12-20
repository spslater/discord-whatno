"""Test and general functions Cog"""
import logging

from discord.ui import Button, View
from discord.ext.commands import Cog, command


logger = logging.getLogger(__name__)


def setup(bot):
    """Add the Test Cog to the Bot"""
    bot.add_cog(WNTestCog(bot))


class WNTestCog(Cog, name="General"):
    """Test commands for the WhatnoBot"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @command()
    async def ping(self, ctx):
        """ping"""
        return await ctx.send("pong")

    @command()
    async def pong(self, ctx):
        """pong"""
        return await ctx.send("ping")

    @command()
    async def test(self, ctx):
        """Send a message to test this command is working

        this is extra info... shh!
        """
        return await ctx.send("Test recieved! :D")

    @command()
    async def source(self, ctx):
        """Get link to source code"""
        await ctx.send(
            "The source code to the whatno bot and other things it can do",
            view=SourceLink(),
        )


class SourceLink(View):
    """Create ui button to link to the source code"""

    def __init__(self):
        super().__init__()
        self.add_item(
            Button(
                label="Source Code",
                url="https://git.whatno.io/discord/whatno",
            )
        )
