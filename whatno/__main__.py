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
    temp.add_argument(
        "-c",
        "--cog",
        action="append",
        default=[],
        dest="cogs",
        help="Select which cogs to be loaded, can be used mulitiple times"
    )

    return temp


args = build_parser().parse_args()
env = Env()
env.read_env(args.envfile, recurse=False)  # do not recurse up directories to find a .env file

with env.prefixed("DISCORD_"):
    logging_config = env("LOGGING_CONFIG")
    token = args.token or env("TOKEN")
    storage = args.storage or env("STORAGE")
    cogs = args.cogs or [c.strip() for c in env("COGS", "").split(",")]

    if logging_config:
        logging.config.fileConfig(logging_config)

    if args.devmode or env.bool("DEVMODE"):
        whatno = WhatnoBot(token, env=env, prefix="~", cogs=cogs)
    else:
        whatno = WhatnoBot(token, env=env, storage=storage, cogs=cogs)

    whatno.run()
