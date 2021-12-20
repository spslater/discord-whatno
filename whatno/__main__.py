"""Test the bot from the CLI"""
import logging
import logging.config
import sys
from argparse import ArgumentParser
from os import getenv

from dotenv import load_dotenv

from . import WhatnoBot


def build_parser():
    """Parse commands to call them"""
    temp = ArgumentParser()
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
load_dotenv(args.envfile)

logging_config = getenv("DISCORD_LOGGING_CONFIG")
if logging_config:
    logging.config.fileConfig(logging_config)

whatno = WhatnoBot(args.token or getenv("DISCORD_TOKEN", None))
whatno.run()
