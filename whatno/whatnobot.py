"""Whatno Discord Bot
Bot for Whatno to do whatever I want it to do, loads different
commands from different cogs

:class WhatnoBot: Discord Bot
"""
import logging
import sys
from argparse import ArgumentParser
from os import getenv
from traceback import format_tb

from discord.ext.commands import Bot, when_mentioned_or
from dotenv import load_dotenv


class WhatnoBot(Bot):  # pylint: disable=too-many-ancestors
    """Bot to talk to discord"""

    def __init__(self, prefix=when_mentioned_or("..")):
        self._logger = logging.getLogger(self.__class__.__name__)
        super().__init__(
            command_prefix=prefix,
            strip_after_prefix=True,
        )
        self.token = None

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
        err_type, err_value, err_traceback = sys.exc_info()
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

    def parse(self, arguments: list[str] = None):
        """Parse commands to call them"""
        parser = ArgumentParser()
        parser.add_argument(
            "-o",
            "--output",
            dest="logfile",
            help="log file",
            metavar="FILENAME",
        )
        parser.add_argument(
            "-q",
            "--quite",
            dest="quite",
            default=False,
            action="store_true",
            help="quite output",
        )
        parser.add_argument(
            "-l",
            "--level",
            dest="level",
            default="info",
            choices=["debug", "info", "warning", "error", "critical"],
            help="logging level for output",
            metavar="LEVEL",
        )

        parser.add_argument(
            "-e",
            "--env",
            dest="envfile",
            help="env file with connection info",
            metavar="ENV",
        )
        parser.add_argument(
            "-t",
            "--token",
            nargs=1,
            dest="token",
            help="Discord API Token.",
            metavar="TOKEN",
        )

        args = parser.parse_args(arguments)
        load_dotenv(args.envfile, verbose=(args.level == "DEBUG"))

        log_level = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }

        handler_list = (
            [logging.StreamHandler(sys.stdout), logging.FileHandler(args.logfile)]
            if args.logfile
            else [logging.StreamHandler(sys.stdout)]
        )

        logging.basicConfig(
            format="%(asctime)s\t[%(levelname)s]\t{%(module)s}\t%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            level=log_level[args.level],
            handlers=handler_list,
        )
        logging.getLogger("discord.client").setLevel(logging.INFO)
        logging.getLogger("discord.gateway").setLevel(logging.WARN)

        if args.quite:
            logging.disable(logging.CRITICAL)

        self.token = args.token or getenv("DISCORD_TOKEN", None)

        if not self.token:
            raise RuntimeError("No api token provided")

        return self

    # pylint: disable=arguments-differ
    def run(self):
        """Run the bot"""
        super().run(self.token)
