"""Discord CLI Bot

Bot to perform specific actions on messages in Discord then close

:class DiscordCLI: simple command line interface to perform basic
    actions on Discord messages, multiple actions can be passed at
    one time
"""

import logging
import sys
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser, Namespace
from json import dump, load
from os import getenv
from shlex import split
from shutil import get_terminal_size
from textwrap import indent
from time import sleep
from traceback import format_tb

from discord import Client, Colour, Embed, Forbidden, HTTPException, NotFound
from dotenv import load_dotenv

_HELP_MESSAGE = """usage: {prog} [-h [HELP ...]]
{prog_indent} [--logfile LOGFILE] [-q] [--level LEVEL]
{prog_indent} [-e ENV] [-t TOKEN] [-g GUILD] [-c CHANNEL] [--embeds EMBED]
{prog_indent} [[COMMAND [ARGS ...]] ...]
{tlp_help}
"""


class DiscordCLI(Client):
    """simple command line interface to perform basic actions on Discord messages

    Multiple actions can be passed at one time, these actions include sending
    plaintext messages, sending embeds, editing messages / embeds, deleting messages,
    refreshing embeds, and displaying info on the bots connected guilds / channels.

    Setup is handled via command line arguments. Help can be viewed with the `--help`
    flag, it can be followed by a list of sub commands to see messages for, no sub
    commands listed will display main help info
    """

    def __init__(self):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.token = None
        self.given_channel = None
        self.given_guild = None
        self.channel = None
        self.guild = None
        self.embed_file = None

        self._top_level_parser = None
        self.parser = None
        self.subparsers = None
        self.subparser_list = None
        self.commands = []

        self._setup_parser()

    def _top_level_args(self, args: Namespace):
        """Parser inital arguments needed to connect to Discord

        This is handled by a seperate parser so that none of the
        command arguments accidently get gobbled up (--help does not
        work on subcommands).
        """
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
        self.token = args.token or getenv("DISCORD_TOKEN", None)

        if not self.token:
            raise RuntimeError("No api token provided")

        self.given_guild = args.guild or getenv("DISCORD_GUILD", None)
        self.given_channel = args.guild or getenv("DISCORD_CHANNEL", None)
        if not self.given_channel:
            raise RuntimeError("Channel Id or Name not provided to Client")

    def _info_parser(self, subparsers: ArgumentParser):
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
            "-q",
            "--quite",
            dest="quite",
            action="store_true",
            default="false",
            help="don't print info to stdout",
        )
        return info_parser

    def _message_parser(self, subparsers: ArgumentParser):
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
            "-f",
            "--file",
            nargs="+",
            dest="filename",
            help="send plaintext contents of a file as a message",
            metavar="FILE",
        )
        return message_parser

    def _delete_parser(self, subparsers: ArgumentParser):
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
            "-f",
            "--file",
            nargs="+",
            dest="filename",
            help="message ids to delete from channel",
            metavar="FILE",
        )
        return delete_parser

    def _refresh_parser(self, subparsers: ArgumentParser):
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
            "-f",
            "--file",
            nargs="+",
            dest="filename",
            help="file with list of message ids to refresh",
            metavar="FILE",
        )
        return refresh_parser

    def _edit_parser(self, subparsers: ArgumentParser):
        edit_parser = subparsers.add_parser(
            "edit",
            aliases=["e"],
            help="edit previously sent messages",
            add_help=False,
        )
        edit_parser.set_defaults(func=self.edit_message)
        edit_parser.add_argument(
            "filename",
            nargs="+",
            help="JSON with info on what messages to edit and how",
            metavar="JSON",
        )
        return edit_parser

    def _automate_parser(self, subparsers: ArgumentParser):
        auto_parser = subparsers.add_parser(
            "automate",
            aliases=["a", "auto"],
            help="file with list of sequential commands",
            add_help=False,
        )
        auto_parser.set_defaults(func=self.automate)
        auto_parser.add_argument(
            "filename",
            nargs="+",
            help="filename to load commands from",
            metavar="FILE",
        )

    def _setup_parser(self):
        """Setup the command parser for the various subcommands available"""
        parser = ArgumentParser(
            formatter_class=ArgumentDefaultsHelpFormatter,
            add_help=False,
        )
        subs = parser.add_subparsers()
        self._automate_parser(subs)
        self._delete_parser(subs)
        self._edit_parser(subs)
        self._info_parser(subs)
        self._message_parser(subs)
        self._refresh_parser(subs)

        self.parser = parser
        self.subparsers = subs
        self.update_subparser_list()

    # pylint: disable=protected-access
    def update_subparser_list(self):
        """Update list of subparsers to help with generating help output

        This should be called each time a new sub command is added in a
        subclass of this class
        """
        self.subparser_list = self.parser._subparsers._actions[-1].choices

    def _parse_leftovers(self, leftovers: list[str]) -> list[list[str]]:
        """get leftover arguments from top level parser and split them
        into an argument list for each sub command called
        """
        command_names = self.subparser_list.keys()
        commands = []
        current_command = []
        while leftovers:
            current_arg = leftovers.pop(0)
            if current_arg in command_names:
                commands.append(current_command)
                current_command = [current_arg]
            else:
                current_command.append(current_arg)
        commands.append(current_command)
        return [cmd for cmd in commands if cmd]

    async def _set_guild_connection(self):
        """set info for main guild connection"""
        guild_id = guild_name = None
        try:
            guild_id = int(self.given_guild)
        except (TypeError, ValueError):
            guild_name = self.given_guild

        if guild_id is None and guild_name is not None:
            async for guild in self.fetch_guilds():
                if guild.name == guild_name:
                    guild_id = int(guild.id)
                    break
        if guild_id is None:
            raise RuntimeError("Provided Guild is not an available guild")
        self.guild = super().get_guild(guild_id)

    def _set_channel_connection(self):
        """set info for main channel connection"""
        channel_id = channel_name = None
        try:
            channel_id = int(self.given_channel)
        except (TypeError, ValueError):
            channel_name = self.given_channel

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

    async def _set_discord_connection(self):
        """set information for main guild and channel connection"""
        await self._set_guild_connection()
        self._set_channel_connection()

        if self.channel.guild.id != self.guild.id:
            self._logger.warning(
                "Guild provided channel (%s) belongs to does not match provied guild (%s).",
                self.channel.guild.name,
                self.guild.name,
            )

    def _backup_embeds(self, embeds: list[Embed]):
        """save embeds to a json file"""
        if self.embed_file:
            data = []
            try:
                with open(self.embed_file, "r") as fp:
                    data = load(fp)
            except FileNotFoundError:
                pass
            data.extend([e.to_dict() for e in embeds])
            with open(self.embed_file, "w+") as fp:
                dump(data, fp, sort_keys=True, indent="\t")

    async def automate(self, args: Namespace):
        """run a file to automate calls

        Called automaticaly by the parser when the automate sub
        command is called. No protection against an automate call inside
        another file causeing an infinite loop.

        :param filename: filename with 1 command and it's arguments per line,
            multiple files can be passed
        :type filename: str
        """
        user_args = []
        for filename in args.filename:
            try:
                with open(filename, "r") as fp:
                    user_args.extend(split(fp.read()))
            except FileNotFoundError:
                self._logger.warning("%s not found, skipping", filename)

        for command in self._parse_leftovers(user_args):
            args = self.parser.parse_args(command)
            await args.func(args)

    def print_info(self, args: Namespace):
        """Print info on bot's connection to discord.

        This info includes the primary guild and channel, as well as the number of guilds the bot
        can connect to, their names, and the number of channels and their names in each guild.

        :param filename: file to save information to
        :type filename: str
        :param quite: do not print info to stdout
        :type quite: bool
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

    async def send_message(self, args: Namespace):
        """Sends a plaintext message to the primary channel

        :param message: plaintext to send to discord, multiple messages can be passed
        :type message: str
        :param filename: file to load message from, full contents used as one message;
            multiple files can be passed after a single flag
        :type filename: str
        """
        self._logger.info(
            'Sending a message to channel "%s" on guild "%s"',
            self.channel,
            self.guild,
        )

        for message in args.message:
            self._logger.debug("Sending a plaintext message")
            await self.channel.send(message)

        for filename in args.filename or []:
            self._logger.debug("Loading text from file: %s", filename)
            with open(filename, "r") as fp:
                data = fp.read()
                await self.channel.send(data)

    async def delete_message(self, args: Namespace):
        """Delete message via given ids

        :param delete: message id to delete, multiple ids can be passed
        :type delete: str
        :param filename: file to load ids to delete from, each line should contain 1 message id;
            multiple files can be passed after a single flag
        :type filename: str
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

        for filename in args.filename or []:
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

    async def edit_message(self, args: Namespace):
        """Edit messages based on JSON file given

        JSON struct must be a list of dicts, each dict shoul have message id (mid) to edit.
        If it's a regular text message, the `text` field is what the new message should say.
        If it is an embed, `title`, `url`, `image`, `footer` can be included if those values
        should be changed. A `field` dict with `value` and/or `name` to change the first field.

        :param filename: file to load JSON from; multiple files can be passed
        :type filename: str
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
            try:
                msg = await self.channel.fetch_message(entry["mid"])
            except (NotFound, HTTPException, Forbidden) as e:
                self._logger.warning('Unable to get message "%s": %s', entry["mid"], e)
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
                    self._logger.warning(
                        'Unable to edit message "%s": %s',
                        entry["mid"],
                        e,
                    )
                else:
                    embeds.append(embed)

            else:
                text = entry.get("text")
                if text == msg.content:
                    self._logger.warning(
                        'Message content the same, no edits being made for message "%s"',
                        entry["mid"],
                    )
                    continue
                try:
                    await msg.edit(content=text)
                except (HTTPException, Forbidden) as e:
                    self._logger.warning(
                        'Unable to edit message "%s": %s',
                        entry["mid"],
                        e,
                    )
            sleep(1)
        self._backup_embeds(embeds)

    async def refresh_message(self, args: Namespace):
        """Refresh the color of an embed message to try and get any inbeds (image or video) to load

        :param refresh: message id to refresh, must be an embed message; multiple ids can be passed
        :type refresh: str
        :param filename: file to load ids to refresh from, each line should contain 1 message id;
            multiple files can be passed after a single flag
        :type filename: str
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

        for filename in args.filename or []:
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

    def display_help(self, *parsers: str):
        """Print help messages and exit

        :param parsers: Sub commands to print help message for, if none are provided the
            top level help message will be displayed
        :type parsers: str
        """
        columns = min(80, get_terminal_size()[0])

        if not parsers:
            tlp_len = len(self._top_level_parser.format_usage().splitlines())
            tlp_full = self._top_level_parser.format_help().splitlines()
            tlp_help = "\n".join(tlp_full[tlp_len:])

            prog_indent = "".ljust(len("usage: ") + len(self.parser.prog))
            usage = _HELP_MESSAGE.format(
                prog=self.parser.prog,
                prog_indent=prog_indent,
                tlp_help=tlp_help,
            )
            usage += "\ncommands:"
            parsers = sorted(
                list(set(self.subparser_list.values())),
                key=lambda s: s.prog,
            )
            for parser in parsers:
                prog = parser.prog.split()[-1]
                usage += f"\n  {'-' * len(prog)}\n  {prog}:\n"
                usage += indent(parser.format_help(), "    ")

            print(usage, file=sys.stderr)
            sys.exit(0)

        completed = {}
        unknown = []
        for parser in parsers:
            try:
                subparser = self.subparser_list[parser]
            except KeyError:
                unknown.append(parser)
            else:
                if subparser.prog not in completed.keys():
                    completed[subparser.prog] = subparser
        if unknown:
            print(
                "Unable to display help for following unknown commands:\n",
                *[f"> {cmd}\n" for cmd in unknown],
                file=sys.stderr,
            )

        for parser in completed.values():
            print("-" * columns, file=sys.stderr)
            parser.print_help()
            print(file=sys.stderr)
        sys.exit(0)

    async def on_ready(self):
        """Called by the Client after all prep data has been recieved from Discord

        Checks which arguments were passed in and makes the appropriate calls.
        Can print info, send a message, delete a message, refresh an embed, or
        send the comics for today's date.

        Logs out after everything is complete.
        """
        self._logger.info("%s has connected to Discord!", self.user)

        await self._set_discord_connection()
        for parsed_args in self.commands:
            args = self.parser.parse_args(parsed_args)
            await args.func(args)

        await self.close()

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
            "%s: %s | Traceback:\n%s",
            err_type.__name__,
            err_value,
            tb_string,
        )
        await self.close()

    def parse(self, arguments: list[str] = None):
        """Parse commands to call them"""
        parser = ArgumentParser(
            formatter_class=ArgumentDefaultsHelpFormatter,
            add_help=False,
        )
        info_group = parser.add_argument_group("information")
        info_group.add_argument(
            "-h",
            "--help",
            nargs="*",
            dest="help",
            help="show help message for listed subcommands or main program if none provided",
        )
        logging_group = parser.add_argument_group("logging")
        logging_group.add_argument(
            "--logfile",
            dest="logfile",
            help="log file",
            metavar="LOGFILE",
        )
        logging_group.add_argument(
            "-q",
            "--quite",
            dest="quite",
            default=False,
            action="store_true",
            help="quite output",
        )
        logging_group.add_argument(
            "--level",
            dest="level",
            default="info",
            choices=["debug", "info", "warning", "error", "critical"],
            help="logging level for output",
            metavar="LEVEL",
        )

        discord_group = parser.add_argument_group(
            "discord", "settings for the connection"
        )
        discord_group.add_argument(
            "-e",
            "--env",
            dest="envfile",
            help="env file with connection info",
            metavar="ENV",
        )

        discord_group.add_argument(
            "-t",
            "--token",
            nargs=1,
            dest="token",
            help="Discord API Token.",
            metavar="TOKEN",
        )
        discord_group.add_argument(
            "-g",
            "--guild",
            nargs=1,
            dest="guild",
            help="name or id of guild to post to",
            metavar="GUILD",
        )
        discord_group.add_argument(
            "-c",
            "--channel",
            nargs=1,
            dest="channel",
            help="name or id of channel to post to",
            metavar="CHANNEL",
        )

        discord_group.add_argument(
            "--embeds",
            dest="embedfile",
            help="file to save embeds to for debugging purposes",
            metavar="EMBED",
        )

        self._top_level_parser = parser

        args, leftovers = parser.parse_known_args(arguments)
        self._top_level_args(args)
        self.commands.extend(self._parse_leftovers(leftovers))

        return self

    # pylint: disable=arguments-differ
    def run(self):
        """Run the bot"""
        super().run(self.token)
