"""Test and general functions Cog"""
import logging

from discord import ExtensionError
from discord.ext.commands import Cog, group, is_owner

logger = logging.getLogger(__name__)

def setup(bot):
    """Add the Test Cog to the Bot"""
    bot.add_cog(WNManageCog(bot))


class WNManageCog(Cog, name="Manage Extensions"):
    """Manage commands for the WhatnoBot"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @staticmethod
    def _module_name(name):
        prefix = __name__.rsplit(".", 1)[0]
        if name.startswith(prefix):
            return name
        return f"{prefix}.{name}"

    @is_owner()
    @group(name="exts")
    async def exts(self, ctx):
        """Manage bot about extensions"""
        if not ctx.invoked_subcommand:
            msg = "```\n"
            if self.bot.loaded_extensions:
                loaded = "\n".join(self.bot.loaded_extensions)
                msg += f"Loaded\n{loaded}\n"
            unload_exts = (
                self.bot.get_available_extensions() - self.bot.loaded_extensions
            )
            if unload_exts:
                unloaded = "\n".join(unload_exts)
                msg += f"Unloaded\n{unloaded}\n"
            msg += "```"
            await ctx.send(msg)

    @is_owner()
    @exts.command()
    async def load(self, ctx, *, module):
        """Loads a module."""
        await ctx.message.add_reaction("<:wave_Joyce:780682895907618907>")
        module = self._module_name(module)
        try:
            self.bot.load_extension(module)
        except ExtensionError as e:
            await ctx.send(f"{e.__class__.__name__}: {e}")
        else:
            self.bot.loaded_extensions.add(module)
            await ctx.send("\N{OK HAND SIGN} Loaded moduel! \N{GRINNING FACE}")

    @is_owner()
    @exts.command()
    async def unload(self, ctx, *, module):
        """Unloads a module."""
        module = self._module_name(module)
        if module == __name__:
            await ctx.send(
                (
                    "\N{ANGRY FACE} Why are you trying to unload this module??? "
                    "You need it dummy \N{FACE WITH STUCK-OUT TONGUE}"
                )
            )
            return
        await ctx.message.add_reaction("<:wave_Joyce:780682895907618907>")
        try:
            self.bot.unload_extension(module)
        except (ExtensionError, KeyError) as e:
            await ctx.send(f"{e.__class__.__name__}: {e}")
        else:
            self.bot.loaded_extensions.discard(module)
            await ctx.send("\N{OK HAND SIGN} Unload successful! \N{WAVING HAND SIGN}")

    @is_owner()
    @exts.command(name="list")
    async def list_exts(self, ctx):
        """List loaded modules"""
        exts = "\n".join(self.bot.loaded_extensions)
        await ctx.send(f"```\n{exts}\n```")

    @is_owner()
    @exts.command(name="available")
    async def available(self, ctx):
        """List available modules"""
        exts = "\n".join(self.bot.get_available_extensions())
        await ctx.send(f"```\n{exts}\n```")

    async def _reload_module(self, ctx, name):
        try:
            self.bot.reload_extension(name)
        except ExtensionError as e:
            await ctx.send(
                (
                    "\N{THUMBS DOWN SIGN} Unable to reload "
                    f"| {e.__class__.__name__}: {e}"
                )
            )
            return False
        except KeyError:
            await ctx.send(
                (
                    "\N{CONFUSED FACE} Unable to reload? "
                    f"| {e.__class__.__name__}: {e}"
                )
            )
            return False
        else:
            return True

    @is_owner()
    @exts.command(name="reload")
    async def reload(self, ctx, *, module="all"):
        """Reloads a module."""
        await ctx.message.add_reaction("<:wave_Joyce:780682895907618907>")
        if module == "all":
            logger.info("Reloading: %s", ', '.join(self.bot.loaded_extensions))
            good = 0
            total = len(self.bot.loaded_extensions)
            for mod in self.bot.loaded_extensions:
                success = await self._reload_module(ctx, mod)
                good += 1 if success else 0
            await ctx.send(
                f"\N{OK HAND SIGN} Reloaded {good} of {total} extensions! \N{GRINNING FACE}"
            )
            return
        module = self._module_name(module)
        if module not in self.bot.loaded_extensions:
            await ctx.send("\N{THUMBS DOWN SIGN} Module is not loaded dummy")
            return
        logger.info("Reloading: %s", module)
        success = await self._reload_module(ctx, module)
        if success:
            await ctx.send("\N{OK HAND SIGN} Reload successful! \N{GRINNING FACE}")

