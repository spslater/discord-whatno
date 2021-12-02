"""Test the bot from the CLI"""
import logging
import sys
from argparse import ArgumentParser
from os import getenv

from dotenv import load_dotenv

from . import WhatnoBot


def build_parser():
    """Parse commands to call them"""
    temp = ArgumentParser()
    temp.add_argument(
        "-o",
        "--output",
        dest="logfile",
        help="log file",
        metavar="FILENAME",
    )
    temp.add_argument(
        "-q",
        "--quite",
        dest="quite",
        default=False,
        action="store_true",
        help="quite output",
    )
    temp.add_argument(
        "-l",
        "--level",
        dest="level",
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="logging level for output",
        metavar="LEVEL",
    )

    temp.add_argument(
        "-e",
        "--env",
        dest="envfile",
        help="env file with connection info",
        metavar="ENV",
    )
    temp.add_argument(
        "-t",
        "--token",
        nargs=1,
        dest="token",
        help="Discord API Token.",
        metavar="TOKEN",
    )

    return temp


args = build_parser().parse_args()
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


whatno = WhatnoBot(args.token or getenv("DISCORD_TOKEN", None))
whatno.run()
