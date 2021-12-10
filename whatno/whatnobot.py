"""Whatno Discord Bot
Bot for Whatno to do whatever I want it to do, loads different
commands from different cogs

:class WhatnoBot: Discord Bot
"""
import logging
from pathlib import Path
from sys import exc_info
from traceback import format_tb

from discord import ExtensionFailed, NoEntryPointError
from discord.ext.commands import Bot, when_mentioned_or


class WhatnoBot(Bot):  # pylint: disable=too-many-ancestors
    """Bot to talk to discord"""

    def __init__(self, token, prefix=".."):
        self._logger = logging.getLogger(self.__class__.__name__)
        if not token:
            raise RuntimeError("No api token provided")
        self.token = token

        super().__init__(
            command_prefix=when_mentioned_or(prefix),
            strip_after_prefix=True,
            case_insensitive=True,
        )
        self.loaded_extensions = set()
        self.load_extensions()

    @staticmethod
    def get_available_extensions():
        """Get list of available extensions in extension folder"""
        root = "whatno/extension"
        module = root.replace("/", ".")
        root = Path(root).resolve()
        available = set()
        for filename in root.glob("*"):
            if filename.match("__pycache__"):
                continue

            src = Path(filename)
            rec = src.parent.resolve() / src.name if src.is_symlink() else src.resolve()
            available.add(".".join([module, rec.relative_to(root).stem]))
        return available

    def load_extensions(self):
        """Load the extensions found in the extension folder"""
        root = "whatno/extension"
        module = root.replace("/", ".")
        root = Path(root).resolve()
        for module in self.get_available_extensions():
            self._logger.info("loading: %s", module)
            try:
                self.load_extension(module)
            except (
                NoEntryPointError,
                ExtensionFailed,
            ) as e:
                _, _, err_traceback = exc_info()
                tb_list = "\n".join(format_tb(err_traceback))
                tb_str = " | ".join(tb_list.splitlines())
                self._logger.info("load? %s: %s | %s", module, e, tb_str)
            else:
                self.loaded_extensions.add(module)

    async def sync_commands(self):
        pass

    async def on_ready(self):
        """Called by the Client after all prep data has been recieved from Discord

        Checks which arguments were passed in and makes the appropriate calls.
        Can print info, send a message, delete a message, refresh an embed, or
        send the comics for today's date.

        Logs out after everything is complete.
        """
        self._logger.info("%s has connected to Discord!", self.user)

    async def on_error(self, *args, **kwargs):
        """Log information when CLient encounters an error and clean up connections"""
        err_type, err_value, err_traceback = exc_info()
        tb_list = "\n".join(format_tb(err_traceback))
        tb_string = " | ".join(tb_list.splitlines())
        self._logger.debug(
            "Error cause by call with args and kwargs: %s %s",
            args,
            kwargs,
        )
        self._logger.error(
            "%s: %s | Traceback: %s",
            err_type.__name__,
            err_value,
            tb_string,
        )
        await self.close()

    async def on_command_error(self, context, exception):
        self._logger.warning(
            "%s; guild %s (%s); channel %s (%s); mid: %s; author: %s (%s); message: %s",
            exception,
            context.guild.name,
            context.guild.id,
            context.channel.name,
            context.channel.id,
            context.message.id,
            context.author.nick,
            context.author.id,
            context.message.content,
        )

    # pylint: disable=arguments-differ
    def run(self):
        """Run the bot"""
        super().run(self.token)
