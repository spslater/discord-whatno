"""Abscract Comic"""
import re
from abc import ABC, abstractmethod
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser, Namespace
from datetime import datetime, timedelta
from json import dump, load
from os import getenv
from sqlite3 import Connection, Cursor, connect
from sys import exc_info, stdout
from time import sleep
from traceback import format_tb
from typing import Optional

from dotenv import load_dotenv

from discord import Colour, Embed

from discordcli import DiscordCLI

class AbstractComic(ABC, DiscordCLI):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.comic_parser = self._comic_parser()
        self.update_subparser_list()

    def _comic_parser(self):
        comic_parser = self.subparsers.add_parser(
            "comic",
            aliases=["c"],
            help="update channel with comics",
            add_help=False,
        )
        comic_parser.set_defaults(func=self.send_comic)
        comic_parser.add_argument(
            "day",
            nargs="*",
            help="what days to send",
        )
        comic_parser.add_argument(
            "-n",
            "--no-comic",
            dest="comic",
            action="store_false",
            default=True,
            help="do not send todays comics",
        )

        return comic_parser

    @abstractmethod
    def get_embeds(self):
        pass

    @abstractmethod
    def send_comic(self, args):
        pass

    def default_embeds(self, entries: list[dict[str, str]]):
        embeds = []
        for entry in entries:
            title = entry.get("title", None)
            url = entry.get("url", None)
            alt = entry.get("alt", None)
            tag_text = entry.get("tags", None)
            img_url = entry.get("image", None)
            release = entry.get("release", None)

            embed = Embed(title=title, url=url, colour=Colour.random())
            embed.add_field(name=alt, value=tag_text)
            embed.set_image(url=img_url)
            embed.set_footer(text=release)
            embeds.append(embed)

        self._backup_embeds(embeds)
        return embeds

    async def default_send_comic(self):
        for embed in self.get_embeds():
            self._logger.debug(embed.to_dict())
            await self.channel.send(embed=embed)
            sleep(3)
