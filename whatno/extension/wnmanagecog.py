"""Test and general functions Cog"""
import logging

from discord import ExtensionError
from discord.ext.commands import Cog, command, is_owner, group


def setup(bot):
    """Add the Test Cog to the Bot"""
    bot.add_cog(WNManageCog(bot))


class WNManageCog(Cog, name="Manage Extensions"):
    """Manage commands for the WhatnoBot"""

    def __init__(self, bot):
        self._logger = logging.getLogger(self.__class__.__name__)

        super().__init__()
        self.bot = bot

    @staticmethod
    def _module_name(name):
        prefix = __name__.rsplit(".", 1)[0]
        if name.startswith(prefix):
            return name
        return f"{prefix}.{name}"

    @is_owner()
    @command()
    async def load(self, ctx, *, module):
        """Loads a module."""
        module = self._module_name(module)
        try:
            self.bot.load_extension(module)
        except ExtensionError as e:
            await ctx.send(f"{e.__class__.__name__}: {e}")
        else:
            self.bot.loaded_extensions.add(module)
            await ctx.send("\N{OK HAND SIGN} Loaded moduel! \N{GRINNING FACE}")

    @is_owner()
    @command()
    async def unload(self, ctx, *, module):
        """Unloads a module."""
        module = self._module_name(module)
        if module == __name__:
            await ctx.send(
                (
                    "\N{ANGRY FACE} Why are you trying to unload this module???"
                    "You need it dummy \N{FACE WITH STUCK-OUT TONGUE}"
                )
            )
            return
        try:
            self.bot.unload_extension(module)
        except ExtensionError as e:
            await ctx.send(f"{e.__class__.__name__}: {e}")
        else:
            self.bot.loaded_extensions.discard(module)
            await ctx.send("\N{OK HAND SIGN} Unload successful! \N{WAVING HAND SIGN}")

    @is_owner()
    @command(name="list")
    async def list_exts(self, ctx):
        """List loaded modules"""
        exts = "\n".join(self.bot.loaded_extensions)
        await ctx.send(f"```\n{exts}\n```")

    @is_owner()
    @group(name="reload")
    async def reload(self, ctx, *, module="all"):
        """Reloads a module."""
        if module == "all":
            with ctx.typing():
                for mod in self.bot.loaded_extensions:
                    try:
                        self.bot.reload_extension(mod)
                    except ExtensionError as e:
                        await ctx.send(f"{e.__class__.__name__}: {e}")
            await ctx.send(
                "\N{OK HAND SIGN} Reloaded all extensions! \N{GRINNING FACE}"
            )
            return
        module = self._module_name(module)
        if module not in self.bot.loaded_extensions:
            await ctx.send("\N{THUMBS DOWN SIGN} Module is not loaded dummy")
            return
        with ctx.typing():
            try:
                self.bot.reload_extension(module)
            except ExtensionError as e:
                await ctx.send(f"{e.__class__.__name__}: {e}")
            else:
                await ctx.send("\N{OK HAND SIGN} Reload successful! \N{GRINNING FACE}")
