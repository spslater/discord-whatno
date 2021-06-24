"""Discord CLI Bot

Bot meant to run specific commands and not stay open
and listen to discord.
"""

import logging
import sys
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from json import dump, load
from os import getenv
from shutil import get_terminal_size
from time import sleep
from traceback import format_tb

from dotenv import load_dotenv

from discord import Client, Colour, Embed, Forbidden, HTTPException, NotFound


# pylint: disable=too-many-instance-attributes
class DiscordCLI(Client):
    """Discord CLI

    Also can send messages manually to Discord.

    :param guild_name: name of guild to connect to, defaults to None
    :type guild_name: str, optional
    :param guild_id: id of guild to connect to, defaults to None
    :type guild_id: int, optional
    :param channel_name: name of channel to publish in, defaults to None
    :type channel_name: str, optional
    :param channel_id: id of channel to publish in, defaults to None
    :type channel_id: int, optional
    :param info: print info about connection to stdout, defaults to False
    :type info: str, optional
    :param info_file: filename to save info to along side stdout, defaults to None
    :type info_file: str, optional
    :param message: mannually set message to send to channel, defaults to None
    :type message: str, optional
    :param message_file: filename to read contents of to send to channel, defaults to None
    :type message_file: str, optional
    :param edit_file: filename to read contents of to edit different messages, defaults to None
    :type edit_file: str, optional
    :param delete: delete specific message previouslly sent, defaults to None
    :type delete: int, optional
    :param delete_file: filename containing message ids to delete, defaults to None
    :type delete_file: str, optional
    :param embed_file: filename to load an embed dict from, defaults to None
    :type embed_file: str, optional
    :param refresh: embed message ids to refresh because the images embeding, defaults to None
    :type refresh: int, optional
    :param refresh_file: filename with embed message ids to refresh, defaults to None
    :type refresh_file: str, optional
    :raises RuntimeError: Channel Name / Id missing.
    """

    # pylint: disable=too-many-arguments,too-many-locals
    def __init__(self):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.token = None
        self.channel = None
        self.guild = None
        self.embed_file = None
        self.leftovers = None
        self.subparsers = None

        self._setup_parser()

    def _top_level_args(self, args):
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
        if args.quite:
            logging.disable(logging.CRITICAL)

        if args.help is not None:
            self.display_help(*args.help)

        load_dotenv(args.envfile, verbose=(args.level == "DEBUG"))

        self.embed_file = args.embedfile or getenv("EMBED", None)

    def _discord_parser(self, subparsers):
        discord_parser = subparsers.add_parser(
            "discord",
            aliases=["d"],
            help="discord connection info",
            add_help=False,
        )
        discord_parser.set_defaults(func=self._set_discord_connection)
        discord_parser.add_argument(
            "token",
            nargs="?",
            help="discord api token",
        )
        discord_parser.add_argument(
            "guild",
            nargs="?",
            help="name or id of guild to post to",
        )
        discord_parser.add_argument(
            "channel",
            nargs="?",
            help="name or id of channel to post to",
        )

        discord_parser.add_argument(
            "-t",
            "--token",
            nargs=1,
            dest="token",
            help="Discord API Token.",
            metavar="TOKEN",
        )
        discord_parser.add_argument(
            "-g",
            "--guild",
            nargs=1,
            dest="guild",
            help="name or id of guild to post to",
            metavar="GUILD",
        )
        discord_parser.add_argument(
            "-c",
            "--channel",
            nargs=1,
            dest="channel",
            help="name or id of channel to post to",
            metavar="CHANNEL",
        )
        return discord_parser

    def _info_parser(self, subparsers):
        info_parser = subparsers.add_parser(
            "info",
            aliases=["i"],
            help="print to stdout availble guilds and channels",
            add_help=False,
        )
        info_parser.set_defaults(func=self.print_info)
        info_parser.add_argument(
            "filename",
            nargs="?",
            help="file to save info print to",
        )
        info_parser.add_argument(
            "-f",
            "--file",
            dest="filename",
            help="file to save info print to",
            metavar="FILENAME",
        )
        info_parser.add_argument(
            "-q",
            "--quite",
            dest="quite",
            action="store_true",
            default="false",
            help="don't print info to stdout",
        )
        return info_parser

    def _message_parser(self, subparsers):
        message_parser = subparsers.add_parser(
            "message",
            aliases=["m", "msg"],
            help="send plaintext messages to the configured channel",
            add_help=False,
        )
        message_parser.set_defaults(func=self.send_message)
        message_parser.add_argument(
            "message",
            nargs="*",
            help="send plaintext message",
        )
        message_parser.add_argument(
            "-m",
            "--msg",
            "--message",
            nargs="*",
            dest="message",
            help="send plaintext message",
            metavar="MESSAAGE",
        )
        message_parser.add_argument(
            "-f",
            "--file",
            nargs="*",
            dest="filename",
            help="send plaintext contents of a file as a message",
            metavar="FILENAME",
        )
        return message_parser

    def _delete_parser(self, subparsers):
        delete_parser = subparsers.add_parser(
            "delete",
            aliases=["d", "del"],
            help="delete provided messages",
            add_help=False,
        )
        delete_parser.set_defaults(func=self.delete_message)
        delete_parser.add_argument(
            "delete",
            nargs="*",
            type=int,
            help="message ids to delete from channel",
            metavar="MID",
        )
        delete_parser.add_argument(
            "-d",
            "--del",
            "--delete",
            dest="delete",
            nargs="*",
            type=int,
            help="message ids to delete from channel",
            metavar="MID",
        )
        delete_parser.add_argument(
            "-f",
            "--file",
            nargs="*",
            dest="filename",
            help="message ids to delete from channel",
            metavar="MID",
        )
        return delete_parser

    def _refresh_parser(self, subparsers):
        refresh_parser = subparsers.add_parser(
            "refresh",
            aliases=["r", "re", "ref"],
            help="refresh embeds to help get embed to show up",
            add_help=False,
        )
        refresh_parser.set_defaults(func=self.refresh_message)
        refresh_parser.add_argument(
            "refresh",
            nargs="*",
            type=int,
            help="message ids to refresh from channel",
            metavar="MID",
        )
        refresh_parser.add_argument(
            "-r",
            "--refresh",
            nargs="*",
            dest="refresh",
            type=int,
            help="message ids to refresh from channel",
            metavar="MID",
        )
        refresh_parser.add_argument(
            "-f",
            "--file",
            nargs="*",
            dest="filename",
            help="file with list of message ids to refresh",
            metavar="FILE",
        )
        return refresh_parser

    def _edit_parser(self, subparsers):
        edit_parser = subparsers.add_parser(
            "edit",
            aliases=["e"],
            help="edit previously sent messages",
            add_help=False,
        )
        edit_parser.set_defaults(func=self.edit_message)
        edit_parser.add_argument(
            "filename",
            nargs="*",
            help="JSON with info on what messages to edit and how",
            metavar="JSON",
        )
        edit_parser.add_argument(
            "-f",
            "--file",
            nargs="*",
            dest="filename",
            help="JSON with info on what messages to edit and how",
            metavar="JSON",
        )
        return edit_parser

    def _setup_parser(self):
        parser = ArgumentParser(
            formatter_class=ArgumentDefaultsHelpFormatter,
            add_help=False,
        )
        parser.add_argument(
            "-h",
            "--help",
            nargs="*",
            dest="help",
            help="show help message for listed subcommands or main program if none provided",
        )
        parser.add_argument(
            "-l",
            "--logfile",
            dest="logfile",
            help="log file",
            metavar="LOGFILE",
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
            "--level",
            dest="level",
            default="info",
            choices=["debug", "info", "warning", "error", "critical"],
            help="logging level for output",
            metavar="LEVEL",
        )

        parser.add_argument(
            "--env",
            "-e",
            dest="envfile",
            help="env file with connection info",
            metavar="ENV",
        )
        parser.add_argument(
            "--embeds",
            dest="embedfile",
            help="file to save embeds to for debugging purposes",
            metavar="EMBED",
        )

        subs = parser.add_subparsers()
        self._delete_parser(subs)
        self._discord_parser(subs)
        self._edit_parser(subs)
        self._info_parser(subs)
        self._message_parser(subs)
        self._refresh_parser(subs)

        # pylint: disable=protected-access
        self.subparsers = parser._subparsers._actions[-1].choices

        self.parser = parser

    def _set_guild_connection(self, args):
        try:
            guild_id = int(args.guild)
        except ValueError:
            guild_name = args.guild

        if guild_id is None and guild_name is not None:
            # pylint: disable=not-an-iterable
            for guild in self.fetch_guilds():
                if guild.name == guild_name:
                    guild_id = int(guild.id)
                    break
        if guild_id is None:
            raise RuntimeError("Provided Guild is not an available guild")
        self.guild = super().get_guild(guild_id)

    def _set_channel_connection(self, args):
        try:
            channel_id = int(args.channel)
        except ValueError:
            channel_name = args.channel

        if channel_id is None:
            self._logger.debug("Getting channel.")
            channels = []
            try:
                self._logger.debug("Trying to get channel from specific guild.")
                channels = self.guild.fetch_channels()
            except RuntimeError:
                self._logger.debug(
                    (
                        "Error getting channels from guild, "
                        "trying to get from all availible channels."
                    )
                )
                channels = self.get_all_channels()

            for channel in channels:
                if channel.name == channel_name:
                    channel_id = int(channel.id)
                    break
            if channel_id is None:
                raise RuntimeError("Provided channel is not an available channels")
        self.channel = super().get_channel(channel_id)

        if self.channel is None:
            raise RuntimeError("Channel Id or Name not added to Client.")

    def _set_discord_connection(self, args):
        if args.help:
            self.display_help("discord",)

        self.token = args.token or getenv("DISCORD_TOKEN", None)
        if not self.token:
            raise RuntimeError("No api token provided")

        self._set_guild_connection(args)
        self._set_channel_connection(args)

        if self.channel.guild.id != self.guild.id:
            self._logger.warning(
                "Guild provided channel (%s) belongs to does not match provied guild (%s).",
                self.channel.guild.name,
                self.guild.name,
            )

    def _backup_embeds(self, embeds: list[Embed], date_string: str):
        """Save embeds to a json file"""
        if self.embed_file:
            prev = None
            try:
                with open(self.embed_file, "r") as fp:
                    prev = load(fp)
            except FileNotFoundError:
                prev = {}
            prev[date_string] = [e.to_dict() for e in embeds]
            with open(self.embed_file, "w+") as fp:
                dump(prev, fp, sort_keys=True, indent="\t")

    def print_info(self, args):
        """Print info on bot's connection to discord.

        This info includes the primary guild and channel, as well as the number of guilds the bot
        can connect to, their names, and the number of channels and their names in each guild.

        If `filename` is set, then the information will also be saved to that filename.
        """
        self._logger.info("Printing info about Client.")

        info = (
            f"Accessing Guild: {self.guild.name} ({self.guild.id})\n"
            f"Accessing Channel: {self.channel.name} ({self.channel.id})\n"
            f"Total Number of Guilds: {len(self.guilds)}\n"
        )
        for guild in self.guilds:
            info += (
                f"Guild: {guild.name} ({guild.id})\n"
                f"\tTotal Number of Channels: {len(guild.channels)}\n"
            )
            for channel in guild.channels:
                info += f"\tChannel: {channel.name} ({channel.id})\n"

        if not args.quite:
            print(info)

        if args.filename:
            with open(args.filename, "w+") as fp:
                fp.write(info)

    async def send_message(self, args):
        """Sends a message to the primary channel

        Message is either explicitly passed in via the `message` argument when initalizing or
        via a filename whose whole contents are sent. If both values are set, the explicit
        message is sent first, followed by the file contents.
        """
        self._logger.info(
            'Sending a message to channel "%s" on guild "%s"',
            self.channel,
            self.guild,
        )

        for message in args.message:
            self._logger.debug("Sending a plaintext message")
            await self.channel.send(message)

        for filename in args.filename:
            self._logger.debug("Loading text from file: %s", filename)
            with open(filename, "r") as fp:
                data = fp.read()
                await self.channel.send(data)

    async def delete_message(self, args):
        """Delete message via given ids

        Id is either explicitly passed in via the `delete` argument when initalizing or via a
        filename where each line is a message id. Both values can be set at the same time.
        """
        self._logger.info(
            'Deleting messages in channel "%s" on guild "%s"',
            self.channel,
            self.guild,
        )

        mids = []
        if args.delete:
            self._logger.debug("Deleting %s messages from cli", len(args.delete))
            mids.extend(args.delete)

        for filename in args.filename:
            try:
                with open(filename, "r") as fp:
                    data = fp.readlines()
            except FileNotFoundError:
                self._logger.warning("%s not found, skipping", filename)
                continue

            file_mids = []
            for mid in data:
                try:
                    file_mids.append(int(mid.strip()))
                except ValueError:
                    pass
            mids.extend(file_mids)
            self._logger.debug(
                "Loaded %s messages to delete from %s",
                len(file_mids),
                filename,
            )

        self._logger.info("Deleting %s messages", len(mids))
        for mid in mids:
            self._logger.debug('Attemping to delete "%s"', mid)
            try:
                msg = await self.channel.fetch_message(mid)
                await msg.delete()
            except (NotFound, HTTPException) as e:
                self._logger.warning('Unable to get message "%s": %s', mid, e)

    async def edit_message(self, args):
        """Edit messages based on JSON file given

        File specifies the message id (mid) to edit. If it's a regular text message, `text` field
        is what the new message should say. If it is an embed, `title`, `url`, `image`, `footer`
        can be included if those values should be changed. A `field` dict with `value` and/or
        `name` to change the first field.
        """
        self._logger.info(
            'Editing messages in channel "%s" on guild "%s"',
            self.channel,
            self.guild,
        )

        entries = []
        for filename in args.filename:
            try:
                with open(filename, "r") as fp:
                    data = load(fp)
            except FileNotFoundError:
                self._logger.warning("%s not found, skipping", filename)
            else:
                entries.extend(data)

        embeds = []
        for entry in entries:
            mid = entry["mid"]
            try:
                msg = await self.channel.fetch_message(mid)
            except (NotFound, HTTPException, Forbidden) as e:
                self._logger.warning('Unable to get message "%s": %s', mid, e)
                continue

            if msg.embeds:
                embed = msg.embeds[0]

                embed.colour = Colour.random()
                embed.title = entry.get("title", embed.title)
                embed.url = entry.get("url", embed.url)
                embed.set_image(url=entry.get("image", embed.image.url))
                embed.set_footer(text=entry.get("footer", embed.footer.text))

                old_field = embed.fields[0]
                new_field = entry.get("field", {})
                field = {
                    "name": new_field.get("name", old_field.name),
                    "value": new_field.get("value", old_field.value),
                }
                embed.set_field_at(0, **field)

                self._logger.debug(embed.__repr__())
                try:
                    await msg.edit(embed=embed)
                except (HTTPException, Forbidden) as e:
                    self._logger.warning('Unable to edit message "%s": %s', mid, e)
                else:
                    embeds.append(embed)

            else:
                text = entry.get("text")
                if text == msg.content:
                    self._logger.warning(
                        'Message content the same, no edits being made for message "%s"',
                        mid,
                    )
                    continue
                try:
                    await msg.edit(content=text)
                except (HTTPException, Forbidden) as e:
                    self._logger.warning('Unable to edit message "%s": %s', mid, e)
            sleep(1)
        self._backup_embeds(embeds, None)

    async def refresh_message(self, args):
        """Refresh the color of an embed message to try and get any imbeds to load

        Id is either explicitly passed in via the `refresh` argument when initalizing or via a
        filename where each line is a message id. Both values can be set at the same time.
        """
        self._logger.info(
            'Reloading messages in channel "%s" on guild "%s"',
            self.channel,
            self.guild,
        )

        mids = []
        if args.refresh:
            self._logger.debug("Reloading %s messages from cli", len(args.refresh))
            mids.extend(args.refresh)

        for filename in args.filename:
            try:
                with open(filename, "r") as fp:
                    data = fp.readlines()
            except FileNotFoundError:
                self._logger.warning("%s not found, skipping", filename)
                continue

            file_mids = []
            for mid in data:
                try:
                    file_mids.append(int(mid.strip()))
                except ValueError:
                    pass
            mids.extend(file_mids)
            self._logger.debug(
                "Loaded %s messages to refresh from %s",
                len(file_mids),
                filename,
            )

        self._logger.info("Refreshing %s messages", len(mids))
        for mid in mids:
            try:
                msg = await self.channel.fetch_message(mid)
            except (NotFound, HTTPException, Forbidden) as e:
                self._logger.warning('Unable to get message "%s": %s', mid, e)
                continue
            embed = msg.embeds[0]
            embed.colour = Colour.random()
            self._logger.debug(embed.__repr__())
            try:
                await msg.edit(embed=embed)
            except (HTTPException, Forbidden) as e:
                self._logger.warning('Unable to refresh message "%s": %s', mid, e)
            sleep(1)

    def display_help(self, *parsers):
        if not parsers:
            self.parser.print_help()
            sys.exit(0)

        completed = {}
        unknown = False
        for parser in parsers:
            try:
                subparser = self.subparsers[parser]
            except KeyError:
                print(f"Unknown command: {parser}", file=sys.stderr)
                unknown = True
            else:
                if subparser.prog not in completed.keys():
                    completed[subparser.prog] = subparser
        if unknown:
            print(file=sys.stderr)

        columns = min(80, get_terminal_size()[0])
        for parser in completed.values():
            print("-"*columns, file=sys.stderr)
            parser.print_help()
            print(file=sys.stderr)
        sys.exit(0)

    async def on_ready(self):
        """Called by the Client after all prep data has been recieved from Discord

        Checks which arguments were passed in and makes the appropriate calls.
        Can print info, send a message, delete a message, refresh an embed, or
        send the comics for today's date.

        Closes the connection after everything is complete.
        """
        self._logger.info("%s has connected to Discord!", self.user)

        while self.leftovers:
            args, self.leftovers = self.parser.parse_known_args(self.leftovers)
            args.func(args)

        await self.logout()

    async def on_error(self, *args, **kwargs):
        """Log information when CLient encounters an error and clean up connections"""
        err_type, err_value, err_traceback = sys.exc_info()
        tb_list = "\n".join(format_tb(err_traceback))
        tb_string = " | ".join(tb_list.splitlines())
        self._logger.debug(
            "Error cause by call with args and kwargs: %s %s", args, kwargs
        )
        self._logger.error(
            "%s: %s | Traceback: %s", err_type.__name__, err_value, tb_string
        )
        await self.logout()

    def parse(self, arguments=None):
        args, self.leftovers = self.parser.parse_known_args(arguments)
        self._top_level_args(args)
        self.run(self.token)


def _main():
    DiscordCLI().parse()


if __name__ == "__main__":
    _main()
