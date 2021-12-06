"""Test and general functions Cog"""
import logging

from discord.ui import Button, View
from discord.commands import slash_command
from discord.ext.commands import Cog, command

# pylint: disable=relative-beyond-top-level
from ..helpers import allow_slash


def setup(bot):
    """Add the Test Cog to the Bot"""
    bot.add_cog(WNTestCog(bot))


class WNTestCog(Cog, name="General"):
    """Test commands for the WhatnoBot"""

    def __init__(self, bot):
        self._logger = logging.getLogger(self.__class__.__name__)

        super().__init__()
        self.bot = bot

    @command()
    async def test(self, ctx):
        """Send a message to test this command is working

        this is extra info... shh!
        """
        return await ctx.send("Test recieved! :D")

    @slash_command(guild_ids=allow_slash(), name="test")
    async def slashtest(self, ctx):
        """Send a message to test slash command is working

        this is extra info... shh!
        """
        await ctx.respond("Slash test recieved! :D")

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
            Button(label="Source Code", url="https://git.whatno.io/discord/whatno")
        )
