"""Whatno Discord Bot
Bot for Whatno to do whatever I want it to do, loads different
commands from different cogs

:class WhatnoBot: Discord Bot
"""
import logging
from sys import exc_info
from traceback import format_tb

from discord import Intents
from discord.ext.commands import Bot, when_mentioned_or
from environs import Env

from .extension import (doacomic, instadown, snaplookup, stats, wnmessage,
                        wntest)

logger = logging.getLogger(__name__)


class WhatnoBot(Bot):  # pylint: disable=too-many-ancestors
    """Bot to talk to discord"""

    def __init__(self, token, env=None, prefix="%"):
        if not token:
            raise RuntimeError("No api token provided")
        self.env = env or Env()
        self.token = token
        self.prefix = prefix
        self.storage = self.env.path("STORAGE", "storage").resolve()

        super().__init__(
            command_prefix=when_mentioned_or(prefix),
            strip_after_prefix=True,
            case_insensitive=True,
            intents=Intents.all(),
        )
        self.load_cogs()

    def load_cogs(self):
        """Load the cogs found in the extension folder"""
        logger.info(
            "loading cogs: doacomic, instadown, snaplookup, stats, wnmessage, wntest"
        )
        wntest(self)
        wnmessage(self)
        instadown(self)
        snaplookup(self)
        doacomic(self)
        stats(self)

    # pylint: disable=too-many-arguments
    async def get_history(
        self,
        channel_id,
        user_id=None,
        after=None,
        before=None,
        oldest_first=True,
    ):
        """Get history as a list from a channel"""
        channel = await self.fetch_channel(channel_id)
        history = channel.history(
            limit=None,
            after=after,
            before=before,
            oldest_first=oldest_first,
        )
        if user_id:
            history = history.filter(lambda msg: msg.author.id == user_id)
        return history

    # pylint: disable=arguments-differ
    async def sync_commands(self):
        pass

    async def on_message(self, message):
        if message.content.startswith(self.prefix) or message.content.startswith(
            f"<@!{self.user.id}>"
        ):
            ctx = await self.get_context(message)
            cog = ctx.command.cog.__class__.__name__ if ctx.command else None
            cmd = ctx.command.name if ctx.command else None
            logger.debug(
                "%s.%s | %s %s; %s.%s.%s | %s (%s)",
                cog,
                cmd,
                ctx.guild.name,
                ctx.channel.name,
                ctx.guild.id,
                ctx.channel.id,
                ctx.message.id,
                ctx.author.nick,
                ctx.author.id,
            )
            await self.process_commands(message)

    async def on_ready(self):
        """Called by the Client after all prep data has been recieved from Discord

        Checks which arguments were passed in and makes the appropriate calls.
        Can print info, send a message, delete a message, refresh an embed, or
        send the comics for today's date.

        Logs out after everything is complete.
        """
        logger.info("%s has connected to Discord!", self.user)

    async def on_error(self, *args, **kwargs):
        """Log information when CLient encounters an error and clean up connections"""
        err_type, err_value, err_traceback = exc_info()
        tb_list = "\n".join(format_tb(err_traceback))
        tb_string = " | ".join(tb_list.splitlines())
        logger.debug(
            "Error cause by call with args and kwargs: %s %s",
            args,
            kwargs,
        )
        logger.error(
            "%s: %s | Traceback: %s",
            err_type.__name__,
            err_value,
            tb_string,
        )
        await self.close()

    @staticmethod
    async def on_command_error(context, exception):
        logger.warning(
            "%s | %s %s; %s.%s.%s | %s (%s): %s",
            exception,
            context.guild.name,
            context.channel.name,
            context.guild.id,
            context.channel.id,
            context.message.id,
            context.author.nick,
            context.author.id,
            context.message.content,
        )
        try:
            original = exception.original
            tb_list = "\n".join(format_tb(original.__traceback__))
            tb_string = " | ".join(tb_list.splitlines())
            logger.debug("Command error from: %s | %s", original, tb_string)
        except AttributeError:
            pass

    # pylint: disable=arguments-differ
    def run(self):
        """Run the bot"""
        super().run(self.token)
