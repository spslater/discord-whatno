"""DoA Comic Reread Bot

Bot publishes a weeks worth of DoA comics every day.
"""

import logging
import re
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from datetime import datetime, timedelta
from json import dump, load
from os import getenv
from sqlite3 import Connection, Cursor, connect
from sys import exc_info, stdout
from time import sleep
from traceback import format_tb

from dotenv import load_dotenv

from discord import Colour, Embed

from .discordcli import DiscordCLI

# pylint: disable=too-many-instance-attributes
class ComicReread(DiscordCLI):
    """Comic Reread Bot

    Handles the publishing of the comics and updating the schedule.
    Also can send messages manually to Discord.

    :param database_filename: sqlite3 database filename containing comic information
    :type database_filename: str
    :param schedule_filename: json filename with publishing schedule
    :type schedule_filename: str
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
    :param send_comic: send that days comics to the channel, defaults to True
    :type send_comic: bool, optional
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
        database_filename: str,
        schedule_filename: str,
        guild_name: str = None,
        guild_id: int = None,
        channel_name: str = None,
        channel_id: int = None,
        info: str = False,
        info_file: str = None,
        message: str = None,
        message_file: str = None,
        edit_file: str = None,
        send_comic: bool = True,
        delete: int = None,
        delete_file: str = None,
        embed_file: str = None,
        refresh: int = None,
        refresh_file: str = None,
    ):
        super().__init__(
            guild_name=guild_name,
            guild_id=guild_id,
            channel_name=channel_name,
            channel_id=channel_id,
            info=info,
            info_file=info_file,
            message=message,
            message_file=message_file,
            edit_file=edit_file,
            delete=delete,
            delete_file=delete_file,
            embed_file=embed_file,
            refresh=refresh,
            refresh_file=refresh_file,
        )

        self.database_filename = database_filename
        self.conn = None
        self.database = None

        self.schedule_filename = schedule_filename
        with open(self.schedule_filename, "r") as fp:
            self.schedule = load(fp)

        self.send_comic = send_comic

        self._logger = logging.getLogger(self.__class__.__name__)

    def _get_connection(self) -> Connection:
        """Create database connection"""
        if self.conn is None:
            self.conn = connect(self.database_filename)
        return self.conn

    def _get_database(self) -> Cursor:
        """Get cursor to database"""
        if self.database is None:
            self.database = self._get_connection().cursor()
        return self.database

    # pylint: disable=invalid-name
    @staticmethod
    def _date_from_week(yr: int, wk: int, wd: int) -> str:
        """Generate YYYY-MM-DD from year, week number, day number"""
        ywd = f"{yr}-{wk}-{wd}"
        iso_date = datetime.strptime(ywd, "%G-%V-%u")
        return datetime.strftime(iso_date, "%Y-%m-%d")

    def _build_date_list(self, date_string: str) -> list[str]:
        """Dates for the 7 days of a given week"""
        yr, wk, _ = datetime.strptime(date_string, "%Y-%m-%d").isocalendar()
        return [
            self._date_from_week(yr, wk, 1),
            self._date_from_week(yr, wk, 2),
            self._date_from_week(yr, wk, 3),
            self._date_from_week(yr, wk, 4),
            self._date_from_week(yr, wk, 5),
            self._date_from_week(yr, wk, 6),
            self._date_from_week(yr, wk, 7),
        ]

    def _get_tags(self, date_string: str) -> str:
        """Comma seperated tags from a comic"""
        self._get_database().execute(
            "SELECT tag FROM Tag WHERE comicId = ?",
            (date_string,),
        )
        rows = self._get_database().fetchall()
        return [r[0] for r in rows]

    def _build_embeds(self, date_string: str) -> list[Embed]:
        """Generated embeds of comics for a given week"""
        embeds = []

        days = tuple(self.schedule["days"][date_string])
        self._logger.debug("Getting comics on following days: %s", days)
        self._get_database().execute(
            f"""SELECT
            Comic.release as release,
            Comic.title as title,
            Comic.image as image,
            Comic.url as url,
            Alt.alt as alt
        FROM Comic
        JOIN Alt ON Comic.release = Alt.comicId
        WHERE release IN {days}"""
        )

        rows = self._get_database().fetchall()
        self._logger.debug("%s comics from current week", len(rows))
        for row in rows:
            release = row[0]
            title = row[1]
            image = row[2].split("_", maxsplit=3)[3]
            url = row[3]
            alt = f"||{row[4]}||"
            img_url = f"https://www.dumbingofage.com/comics/{image}"
            tags = [
                f"[{tag}](https://www.dumbingofage.com/tag/{re.sub(' ', '-', tag)}/)"
                for tag in self._get_tags(release)
            ]
            tag_text = ", ".join(tags)

            self._logger.debug('Generating embed for "%s" from %s', title, release)
            embed = Embed(title=title, url=url, colour=Colour.random())
            embed.add_field(name=alt, value=tag_text)
            embed.set_image(url=img_url)
            embed.set_footer(text=release)
            embeds.append(embed)

        self._backup_embeds(embeds, date_string)

        return embeds

    async def send_weekly_comics(self):
        """Send the comics for todays dates to primary channel"""
        self._logger.info("Sending comics for today.")

        channel = self._get_channel()
        today = datetime.strftime(datetime.now(), "%Y-%m-%d")
        embeds = self._build_embeds(today)
        for embed in embeds:
            self._logger.debug(embed.__repr__())
            await channel.send(embed=embed)
            sleep(3)

    def update_schedule(self):
        """Update the schedule file with the week's comics that were just published"""
        self._logger.info("Checking schedule to see if it needs updating")
        old_week = self.schedule["next_week"]
        now = datetime.strftime(datetime.now(), "%Y-%m-%d")
        while old_week <= now:
            new_week = datetime.strptime(old_week, "%Y-%m-%d") + timedelta(days=7)
            new_week_str = datetime.strftime(new_week, "%Y-%m-%d")
            self.schedule["next_week"] = new_week_str

            last_day = sorted(self.schedule["days"].keys())[-1]
            next_day = datetime.strptime(last_day, "%Y-%m-%d") + timedelta(days=1)
            next_day_str = datetime.strftime(next_day, "%Y-%m-%d")

            self.schedule["days"][next_day_str] = self._build_date_list(new_week_str)

            old_week = self.schedule["next_week"]

        with open(self.schedule_filename, "w+") as fp:
            dump(self.schedule, fp, sort_keys=True, indent="\t")

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

        if self.send_comic:
            self._logger.info(
                'Sending Comics to channel "%s" on guild "%s"',
                channel,
                guild,
            )
            await self.send_weekly_comics()
            self.update_schedule()

        if self.conn is not None:
            self.conn.close()
        await self.logout()

    async def on_error(self, *args, **kwargs):
        """Log information when CLient encounters an error and clean up connections"""
        err_type, err_value, err_traceback = exc_info()
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
        if self.conn is not None:
            self.conn.close()
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
        "-d, --database",
        dest="database",
        help="Sqlite3 database with comic info.",
        metavar="SQLITE3",
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
        "-s",
        "--schedule",
        dest="schedule",
        help="JSON file to load release information from.",
        metavar="FILENAME",
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
    database = args.database or getenv("DATABASE")
    schedule = args.schedule or getenv("SCHEDULE")
    embed = args.schedule or getenv("EMBED")

    ComicReread(
        database_filename=database,
        schedule_filename=schedule,
        guild_name=guild_name,
        guild_id=guild_id,
        channel_name=channel_name,
        channel_id=channel_id,
        info=args.info,
        info_file=args.infofile,
        message=args.message,
        message_file=args.messagefile,
        edit_file=args.editfile,
        send_comic=args.send_comic,
        delete=args.delete,
        delete_file=args.deletefile,
        embed_file=embed,
        refresh=args.refresh,
        refresh_file=args.refreshfile,
    ).run(token)


if __name__ == "__main__":
    _main()
