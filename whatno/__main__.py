"""Test the bot from the CLI"""
import logging
import logging.config
from argparse import ArgumentParser

from environs import Env

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
    temp.add_argument(
        "-d",
        "--dev",
        action="store_true",
        default=False,
        dest="devmode",
        help="Enable DevMode (alt prefix)",
    )
    temp.add_argument(
        "-s",
        "--storage",
        nargs=1,
        dest="storage",
        help="directory where persistant files are being stored",
    )

    return temp


args = build_parser().parse_args()
env = Env()
env.read_env(args.envfile, False)  # do not recurse up directories to find a .env file

with env.prefixed("DISCORD_"):
    logging_config = env("LOGGING_CONFIG")
    token = args.token or env("TOKEN")

    if logging_config:
        logging.config.fileConfig(logging_config)

    if args.devmode:
        whatno = WhatnoBot(token, env=env, prefix="~")
    else:
        whatno = WhatnoBot(token, env=env)

    whatno.run()
