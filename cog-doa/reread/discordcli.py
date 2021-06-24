"""Discord CLI Bot

Bot meant to run specific commands and not stay open
and listen to discord.
"""

import logging
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from json import dump, load
from os import getenv
from sys import exc_info, stdout
from time import sleep
from traceback import format_tb
from typing import Union

from dotenv import load_dotenv

from discord import Client, Colour, Embed, Forbidden, HTTPException, NotFound
from discord.channel import DMChannel, GroupChannel, TextChannel
from discord.guild import Guild


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
    def __init__(
        self,
        guild_name: str = None,
        guild_id: int = None,
        channel_name: str = None,
        channel_id: int = None,
        info: str = False,
        info_file: str = None,
        message: str = None,
        message_file: str = None,
        edit_file: str = None,
        delete: int = None,
        delete_file: str = None,
        embed_file: str = None,
        refresh: int = None,
        refresh_file: str = None,
    ):
        super().__init__()

        self.guild_name = guild_name
        self.guild_id = guild_id
        self.guild = None

        self.channel_name = channel_name
        self.channel_id = channel_id
        self.channel = None

        self.info = info
        self.info_file = info_file

        self.message = message
        self.message_file = message_file

        self.edit_file = edit_file

        self.delete = delete
        self.delete_file = delete_file

        self.embed_file = embed_file

        self.refresh = refresh
        self.refresh_file = refresh_file

        self._logger = logging.getLogger(self.__class__.__name__)

        if self.channel_id is None and self.channel_name is None:
            raise RuntimeError("Channel Id or Name not added to Client.")

    def _get_guild(self) -> Guild:
        """Get primary Guild object"""
        if self.guild is None:
            logging.debug("Getting guild.")
            if self.guild_id is None and self.guild_name is None:
                channel = self._get_channel()
                self.guild = channel.guild
                self.guild_id = self.guild.id
                self.guild_name = self.guild.name
            elif self.guild_id is None and self.guild_name is not None:
                # pylint: disable=not-an-iterable
                for guild in self.fetch_guilds():
                    if guild.name == self.guild_name:
                        self.guild_id = int(guild.id)
                        break
                if self.guild_id is None:
                    raise RuntimeError("Guild Name not found in list of guilds.")
            self.guild = super().get_guild(self.guild_id)
        return self.guild

    def _get_channel(self) -> Union[DMChannel, GroupChannel, TextChannel]:
        """Get primary Channel object"""
        if self.channel is None:
            if self.channel_id is None:
                self._logger.debug("Getting channel.")
                channels = None
                try:
                    self._logger.debug("Trying to get channel from specific guild.")
                    if self.guild is None:
                        self._get_guild()
                    channels = self.guild.fetch_channels()
                except RuntimeError:
                    self._logger.debug(
                        "Error getting from guild, trying to get from all availible channels."
                    )
                    channels = self.get_all_channels()

                for channel in channels:
                    if channel.name == self.channel_name:
                        self.channel_id = int(channel.id)
                        break
                if self.channel_id is None:
                    raise RuntimeError(
                        "Channel Name not found in list of available channels."
                    )
            self.channel = super().get_channel(self.channel_id)
            if self.guild is None:
                self._get_guild()
        if self.channel.guild.id != self.guild_id:
            self._logger.warning(
                "Guild provided channel (%s) belongs to does not match provied guild (%s).",
                self.channel.guild.name,
                self.guild_name,
            )
        return self.channel

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

    def print_info(self):
        """Print info on bot's connection to discord.

        This info includes the primary guild and channel, as well as the number of guilds the bot
        can connect to, their names, and the number of channels and their names in each guild.

        If `info_file` is set, then the information will also be saved to that filename.
        """
        main_guild = self._get_guild()
        main_channel = self._get_channel()
        info = ""
        info += f"Accessing Guild: {main_guild.name} ({main_guild.id})\n"
        info += f"Accessing Channel: {main_channel.name} ({main_channel.id})\n"
        info += f"Total Number of Guilds: {len(self.guilds)}\n"
        for guild in self.guilds:
            info += f"Guild: {guild.name} ({guild.id})\n"
            info += f"\tTotal Number of Channels: {len(guild.channels)}\n"
            for channel in guild.channels:
                info += f"\tChannel: {channel.name} ({channel.id})\n"

        if self.info:
            print(info)

        if self.info_file is not None:
            with open(self.info_file, "w+") as fp:
                fp.write(info)

    async def send_message(self):
        """Sends a message to the primary channel

        Message is either explicitly passed in via the `message` argument when initalizing or
        via a filename whose whole contents are sent. If both values are set, the explicit
        message is sent first, followed by the file contents.
        """
        channel = self._get_channel()
        if self.message is not None:
            self._logger.debug("Sending a plaintext message")
            await channel.send(self.message)

        if self.message_file is not None:
            self._logger.debug("Loading text from file: %s", self.message_file)
            with open(self.message_file, "r") as fp:
                data = fp.read()
                await channel.send(data)

    async def delete_message(self):
        """Delete message via given ids

        Id is either explicitly passed in via the `delete` argument when initalizing or via a
        filename where each line is a message id. Both values can be set at the same time.
        """
        channel = self._get_channel()
        mids = []
        if self.delete is not None:
            self._logger.debug("Deleting %s messages from cli", len(self.delete))
            mids.extend(self.delete)

        if self.delete_file is not None:
            with open(self.delete_file, "r") as fp:
                file_mids = [
                    int(m.strip()) for m in fp.read().splitlines() if m.strip()
                ]
                mids.extend(file_mids)
            self._logger.debug(
                "Deleting %s messages from file: %s",
                len(file_mids),
                self.delete_file,
            )

        self._logger.info("Deleting %s messages", len(mids))
        for mid in mids:
            self._logger.debug('Attemping to delete "%s"', mid)
            try:
                msg = await channel.fetch_message(mid)
                await msg.delete()
            except (NotFound, HTTPException) as e:
                self._logger.warning('Unable to get message "%s": %s', mid, e)

    async def edit_message(self):
        """Edit messages based on JSON file given

        File specifies the message id (mid) to edit. If it's a regular text message, `text` field
        is what the new message should say. If it is an embed, `title`, `url`, `image`, `footer`
        can be included if those values should be changed. A `field` dict with `value` and/or
        `name` to change the first field.
        """
        channel = self._get_channel()
        mids = []
        if self.edit_file is not None:
            with open(self.edit_file, "r") as fp:
                data = load(fp)
            mids.extend(data)

        embeds = []
        for mid in mids:
            try:
                msg = await channel.fetch_message(mid["mid"])
            except (NotFound, HTTPException, Forbidden) as e:
                self._logger.warning('Unable to get message "%s": %s', mid, e)
                continue

            if msg.embeds:
                embed = msg.embeds[0]

                embed.colour = Colour.random()
                embed.title = mid.get("title", embed.title)
                embed.url = mid.get("url", embed.url)
                embed.set_image(url=mid.get("image", embed.image.url))
                embed.set_footer(text=mid.get("footer", embed.footer.text))

                old_field = embed.fields[0]
                new_field = mid.get("field", {})
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
                finally:
                    sleep(1)

            else:
                text = mid.get("text")
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
                finally:
                    sleep(1)

    async def refresh_message(self):
        """Refresh the color of an embed message to try and get any imbeds to load

        Id is either explicitly passed in via the `refresh` argument when initalizing or via a
        filename where each line is a message id. Both values can be set at the same time.
        """
        channel = self._get_channel()
        mids = []
        if self.refresh is not None:
            self._logger.debug("Reloading %s messages from cli", len(self.refresh))
            mids.extend(self.refresh)

        if self.refresh_file is not None:
            with open(self.refresh_file, "r") as fp:
                file_mids = [
                    int(m.strip()) for m in fp.read().splitlines() if m.strip()
                ]
                mids.extend(file_mids)
            self._logger.debug(
                "Reloading %s messages from file: %s",
                len(file_mids),
                self.refresh_file,
            )

        self._logger.info("Editing %s messages", len(mids))
        for mid in mids:
            try:
                msg = await channel.fetch_message(mid)
            except (NotFound, HTTPException, Forbidden) as e:
                self._logger.warning('Unable to get message "%s": %s', mid, e)
                continue
            embed = msg.embeds[0]
            embed.colour = Colour.random()
            self._logger.debug(embed.__repr__())
            try:
                await msg.edit(embed=embed)
            except (HTTPException, Forbidden) as e:
                self._logger.warning('Unable to edit message "%s": %s', mid, e)
            finally:
                sleep(1)

    async def on_ready(self):
        """Called by the Client after all prep data has been recieved from Discord

        Checks which arguments were passed in and makes the appropriate calls.
        Can print info, send a message, delete a message, refresh an embed, or
        send the comics for today's date.

        Closes the connection after everything is complete.
        """
        self._logger.info("%s has connected to Discord!", self.user)

        channel = self._get_channel()
        guild = self._get_guild()

        if self.info or self.info_file is not None:
            self._logger.info("Printing info about Client.")
            self.print_info()

        if self.message is not None or self.message_file is not None:
            self._logger.info(
                'Sending a message to channel "%s" on guild "%s"',
                channel,
                guild,
            )
            await self.send_message()

        if self.delete is not None or self.delete_file is not None:
            self._logger.info(
                'Deleting messages in channel "%s" on guild "%s"',
                channel,
                guild,
            )
            await self.delete_message()

        if self.refresh is not None or self.refresh_file is not None:
            self._logger.info(
                'Reloading messages in channel "%s" on guild "%s"',
                channel,
                guild,
            )
            await self.refresh_message()

        if self.edit_file is not None:
            self._logger.info(
                'Editing messages in channel "%s" on guild "%s"',
                channel,
                guild,
            )
            await self.edit_message()

        await self.logout()

    async def on_error(self, *args, **kwargs):
        """Log information when CLient encounters an error and clean up connections"""
        err_type, err_value, err_traceback = exc_info()
        tb_list = "\n".join(format_tb(err_traceback))
        tb_string = " | ".join(tb_list.splitlines())
        self._logger.debug(
            "Error cause by call with args and kwargs: %s %s", args, kwargs
        )
        self._logger.error(
            "%s: %s | Traceback: %s", err_type.__name__, err_value, tb_string
        )
        await self.logout()


def _main():
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "-l",
        "--log",
        dest="logfile",
        help="Log file.",
        metavar="LOGFILE",
    )
    parser.add_argument(
        "-q",
        "--quite",
        dest="quite",
        default=False,
        action="store_true",
        help="Quite output",
    )
    parser.add_argument(
        "--mode",
        dest="mode",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level for output",
        metavar="MODE",
    )

    parser.add_argument(
        "-e, --env",
        dest="envfile",
        default=".env",
        help="Environment file to load.",
        metavar="ENV",
    )
    parser.add_argument(
        "-t",
        "--token",
        dest="token",
        help="Discord API Token.",
        metavar="TOKEN",
    )
    parser.add_argument(
        "-gn",
        "--guild-name",
        dest="guild_name",
        help="Name of Guild to post to.",
        metavar="GUILDNAME",
    )
    parser.add_argument(
        "-gi",
        "--guild-id",
        dest="guild_id",
        type=int,
        help="Id of Guild to post to.",
        metavar="GUILDID",
    )
    parser.add_argument(
        "-cn",
        "--channel-name",
        dest="channel_name",
        help="Name of Guild to post to.",
        metavar="CHANNELNAME",
    )
    parser.add_argument(
        "-ci",
        "--channel-id",
        dest="channel_id",
        type=int,
        help="Id of Guild to post to.",
        metavar="CHANNELID",
    )
    parser.add_argument(
        "-nc",
        "--no-comics",
        dest="send_comic",
        default=True,
        action="store_false",
        help="Do not send the weekly comics to the server.",
    )
    parser.add_argument(
        "-i",
        "--info",
        dest="info",
        default=False,
        action="store_true",
        help=(
            "Print out availble guilds and channels and other random info I add. "
            "Prints to stdout, not the log file."
        ),
    )
    parser.add_argument(
        "-if",
        "--info-file",
        dest="infofile",
        help="File to save info print to, won't print to stdout if set and -i flag not used.",
        metavar="FILENAME",
    )
    parser.add_argument(
        "-m",
        "--message",
        dest="message",
        help="Send a plaintext message to the configured channel",
        metavar="MESSAAGE",
    )
    parser.add_argument(
        "-mf",
        "--message-file",
        dest="messagefile",
        help="Send plaintext contents of a file as a message to the configured channel",
        metavar="FILENAME",
    )
    parser.add_argument(
        "--delete",
        dest="delete",
        nargs="*",
        type=int,
        help="Message ids to delete from channel",
        metavar="MID",
    )
    parser.add_argument(
        "--delete-file",
        dest="deletefile",
        help="Message ids to delete from channel",
        metavar="MID",
    )
    parser.add_argument(
        "--embed-file",
        dest="embedfile",
        help="File to print embeds to for debugging purposes",
        metavar="EMBED",
    )
    parser.add_argument(
        "--refresh",
        dest="refresh",
        nargs="*",
        type=int,
        help="Message ids to refresh from channel",
        metavar="MID",
    )
    parser.add_argument(
        "--refresh-file",
        dest="refreshfile",
        help="Message ids to refresh from channel",
        metavar="MID",
    )
    parser.add_argument(
        "--edit-file",
        dest="editfile",
        help="JSON with info on what messages to edit and how",
        metavar="JSON",
    )

    args = parser.parse_args()

    log_level = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    handler_list = (
        [logging.StreamHandler(stdout), logging.FileHandler(args.logfile)]
        if args.logfile
        else [logging.StreamHandler(stdout)]
    )

    logging.basicConfig(
        format="%(asctime)s\t[%(levelname)s]\t{%(module)s}\t%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=log_level[args.mode],
        handlers=handler_list,
    )
    if args.quite:
        logging.disable(logging.CRITICAL)

    load_dotenv(args.envfile, verbose=(args.mode == "DEBUG"))

    token = args.token or getenv("DISCORD_TOKEN")
    guild_name = args.guild_name or getenv("GUILD_NAME")
    guild_id = args.guild_id or int(getenv("GUILD_ID"))
    channel_name = args.channel_name or getenv("CHANNEL_NAME")
    channel_id = args.channel_id or int(getenv("CHANNEL_ID"))
    embed = args.schedule or getenv("EMBED")

    DiscordCLI(
        guild_name=guild_name,
        guild_id=guild_id,
        channel_name=channel_name,
        channel_id=channel_id,
        info=args.info,
        info_file=args.infofile,
        message=args.message,
        message_file=args.messagefile,
        edit_file=args.editfile,
        delete=args.delete,
        delete_file=args.deletefile,
        embed_file=embed,
        refresh=args.refresh,
        refresh_file=args.refreshfile,
    ).run(token)


if __name__ == "__main__":
    _main()
