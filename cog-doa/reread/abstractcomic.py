"""Abscract Comic Discord Bot

:class AbstractComic: abstract class to help easy publishing
    a webcomic to discord for community rereads
"""
from abc import ABC, abstractmethod
from time import sleep

from discord import Colour, Embed

from .discordcli import DiscordCLI


class AbstractComic(ABC, DiscordCLI):
    """abstract class to help easy publishing a webcomic to discord
    for community rereads

    Adds a new sub parser to the DiscordCLI argument parser, `comic`
    that accepts a list of days to publish (none listed means todays date)
    and a flag, `--no-comic` to prevent publishing of comics when run.
    Useful for when other maintenance actions should be run.

    :method get_embeds: build the embeds Discord will publish, a simple way
        the would be building a dictionary with the info and passing it to
        `default_embeds` for a simple comic embed
    :return get_embeds: list of formated Discord Embeds to publish
    :rtype get_embeds: list[Embed]
    :method send_comic: makes the actual send message call to Discord and
        preform any other actions as well, method called automatically when
        the `comic` command is parsed by the argument parser
    :return send_comic: None
    :rtype send_comic: None
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.comic_parser = self._comic_parser()
        self.update_subparser_list()

    def _comic_parser(self):
        """Add the `comic` sub command to the DiscordCLI parser"""
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
        """build the embeds Discord will publish

        A simple way the would be building a dictionary with the info
        and passing it to `default_embeds` for a simple comic embed
        """

    @abstractmethod
    async def send_comic(self, args):
        """makes the actual send message call to Discord

        method called automatically when the `comic` command is
        parsed by the argument parser
        """

    def default_embeds(self, entries: list[dict[str, str]]):
        """Basic way to generate the embeds"""
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
        """Basic way to send the comics to discord"""
        for embed in self.get_embeds():
            self._logger.debug(embed.to_dict())
            await self.channel.send(embed=embed)
            sleep(3)
