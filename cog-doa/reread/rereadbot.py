"""DoA Comic Reread Bot

Discord bot for publishing a weeks worth of DoA
comics every day as part of a community reread.

:class DoaReread: Discord Bot that publishes a weeks
    of DoA comics every day
"""
import logging
import re
from argparse import Namespace
from datetime import datetime, timedelta
from json import dump, load
from os import getenv
from sqlite3 import connect, Connection, Cursor
from typing import Union

from discord import Embed

from .abstractcomic import AbstractComic


class DoaReread(AbstractComic):
    """Discord Bot that publishes a weeks of DoA comics every day

    Handles the publishing of the comics and updating the schedule.
    Setup is handled via command line arguments. Parameters listed
    are for managing the comic specifically, and don't include other
    capabilities a DiscordCLI subclass can perform.

    Expands on the AbstractComic `comic` argument sub command by adding
    a `database` and `schedule` flags for the comic database and publishing
    schedule. These values can also be set in an environment file with the
    keys `DATABASE` and `SCHEDULE` respectively

    :param database: filename of the sqlite3 database with the comic
        info stored in it; flags: `-d`, `--database`
    :type database: str
    :param schedule: filename of json document that contains the list
        of comics to publish on specific days; flags: `-s`, `--schedule`
    :type schedule: str
    :param day: send comics from specific days listed, if not specificed,
        today's comics will be sent; positional argument, format: YYYY-MM-DD
    :type day: str

    :method get_embeds: build the embeds Discord will publish by
        calling `default_embeds`
    :return get_embeds: list of formated Discord Embeds to publish
    :rtype get_embeds: list[Embed]
    :method send_comic: sets up the database connection and schedule to send
        the days comics to Discord, uses the `default_send_comic`, updates the
        schedule as well; called automatically when the `comic` command is
        parsed by the argument parser
    :return send_comic: None
    :rtype send_comic: None
    :method update_schedule: update the schedule with new comics to keep reread
        on track as it catches up to the present day
    :return update_schedule: None
    :rtype update_schedule: None
    :method on_ready: should not be manually called, used by the Discord api
    :method on_error: should not be manually called, used by the Discord api
    :method run: DiscordCLI's run() method calls the Discord api's run(token)
        with the provided user token, this should be called when everything
        is setup and the comics should be sent to Discord.
    """

    def __init__(self):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.comic_parser.description = """Database and Schedule can be set in an
            environment file with the keys `DATABASE` and `SCHEDULE` respectively"""
        self.comic_parser.add_argument(
            "-d",
            "--database",
            dest="database",
            help="filename of the sqlite3 database with the comic info stored in it",
            metavar="SQLITE3",
        )
        self.comic_parser.add_argument(
            "-s",
            "--schedule",
            dest="schedule",
            help=(
                "filename of json document that contains the list "
                "of comics to publish on specific days"
            ),
            metavar="FILENAME",
        )

        self.conn: Connection = None
        self.database: Cursor = None

        self.schedule_filename: str = None
        self.schedule: Union[list, dict] = None

        self.send_comic: bool = False
        self.date_strings: list[str] = []

    def _setup_comic(self, args: Namespace):
        """Setup database and schedule connections to access comic info"""
        database_filename = args.database or getenv("DATABASE", None)
        self.schedule_filename = args.schedule or getenv("SCHEDULE", None)

        if not database_filename:
            raise ValueError("No database to pull comic info from provided")
        if not self.schedule_filename:
            raise ValueError("No schedule for when to publish comics provided")

        self.conn = connect(database_filename)
        self.database = self.conn.cursor()

        with open(self.schedule_filename, "r") as fp:
            self.schedule = load(fp)

        self.date_strings = args.day or [datetime.strftime(datetime.now(), "%Y-%m-%d")]

    def _close_db(self):
        if self.conn is not None:
            self.conn.close()

    @staticmethod
    def _date_from_week(year: int, week: int, weekday: int) -> str:
        """Generate YYYY-MM-DD from year, week number, day number"""
        ywd = f"{year}-{week}-{weekday}"
        iso_date = datetime.strptime(ywd, "%G-%V-%u")
        return datetime.strftime(iso_date, "%Y-%m-%d")

    def _build_date_list(self, date_string: str) -> list[str]:
        """Dates for the 7 days of a given week

        This will give the full week any specific day falls on, if date is a Wednesday
        it'll give the preceding Monday and Tuesday, the given Wednesday, and the
        following Thursday, Friday, Saturday, and Sunday. ISO standard starts the week
        on a Monday (1) and ends on Sunday (7).
        """
        year, week, _ = datetime.strptime(date_string, "%Y-%m-%d").isocalendar()
        return [
            self._date_from_week(year, week, 1),
            self._date_from_week(year, week, 2),
            self._date_from_week(year, week, 3),
            self._date_from_week(year, week, 4),
            self._date_from_week(year, week, 5),
            self._date_from_week(year, week, 6),
            self._date_from_week(year, week, 7),
        ]

    def _get_tags(self, date_string: str) -> str:
        """Comma seperated tags from a comic"""
        self.database.execute(
            "SELECT tag FROM Tag WHERE comicId = ?",
            (date_string,),
        )
        rows = self.database.fetchall()
        return [r[0] for r in rows]

    def get_embeds(self) -> list[Embed]:
        """Generated Discord Embeds of comics

        Generates a list of dictionaries from that database that is
        passed to the default Embed generator and returned.

        :returns: formatted embeds for each comic to be posted, in order
        :rtype: list[Embed]
        """
        entries = []
        for date_string in self.date_strings:
            days = tuple(self.schedule["days"][date_string])
            self._logger.debug("Getting comics on following days: %s", days)
            self.database.execute(
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

            rows = self.database.fetchall()
            self._logger.debug("%s comics from current week", len(rows))
            for row in rows:
                release = row[0]
                image = row[2].split("_", maxsplit=3)[3]
                tags = [
                    f"[{tag}](https://www.dumbingofage.com/tag/{re.sub(' ', '-', tag)}/)"
                    for tag in self._get_tags(release)
                ]

                entries.append(
                    {
                        "title": row[1],
                        "url": row[3],
                        "alt": f"||{row[4]}||",
                        "tags": ", ".join(tags),
                        "image": f"https://www.dumbingofage.com/comics/{image}",
                        "release": release,
                    }
                )

        return self.default_embeds(entries)

    async def send_comic(self, args: Namespace):
        """Send the comics for todays given to primary channel

        Uses the default AbstractComic `default_send_comic` to
        send the comics, always updates the schedule when run.
        """
        self._logger.info("Sending comics for today.")
        self._setup_comic(args)
        if args.comic:
            await self.default_send_comic()
        self.update_schedule()

    def update_schedule(self):
        """Update the schedule file with the week's comics that were just published

        If a more than a week has passed since last update, it will loop thru each week
        since last update, adding the comics as it goes.

        Updates on Sunday.
        """
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

        Calls the DiscordCLI `on_ready` which loops thru the commands and executes
        them in order.

        Closes the connection database after everything is complete.
        """
        await super().on_ready()
        self._close_db()

    async def on_error(self, *args, **kwargs):
        """Calls the DiscordCLI `on_error` and closes the database afterward"""
        super().on_error()
        self._close_db()
