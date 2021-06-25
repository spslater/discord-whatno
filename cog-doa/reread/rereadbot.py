"""DoA Comic Reread Bot

Bot publishes a weeks worth of DoA comics every day.
"""
import logging
import re
from datetime import datetime, timedelta
from json import dump, load
from os import getenv
from sqlite3 import connect

from discord import Embed

from .abstractcomic import AbstractComic


class DoaReread(AbstractComic):
    """Comic Reread Bot

    Handles the publishing of the comics and updating the schedule.
    Also can send messages manually to Discord.
    """

    def __init__(self):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.comic_parser.add_argument(
            "-d",
            "--database",
            dest="database",
            help="Sqlite3 database with comic info.",
            metavar="SQLITE3",
        )
        self.comic_parser.add_argument(
            "-s",
            "--schedule",
            dest="schedule",
            help="JSON file to load release information from.",
            metavar="FILENAME",
        )

        self.conn = None
        self.database = None

        self.schedule_filename = None
        self.schedule = None

        self.send_comic = False
        self.date_strings = []

    def _setup_comic(self, args):
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
        self.database.execute(
            "SELECT tag FROM Tag WHERE comicId = ?",
            (date_string,),
        )
        rows = self.database.fetchall()
        return [r[0] for r in rows]

    def get_embeds(self) -> list[Embed]:
        """Generated embeds of comics"""
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

    async def send_comic(self, args):
        """Send the comics for todays dates to primary channel"""
        self._logger.info("Sending comics for today.")
        self._setup_comic(args)
        if args.comic:
            await self.default_send_comic()
        self.update_schedule()

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
        await super().on_ready()
        self._close_db()

    async def on_error(self, *args, **kwargs):
        super().on_error()
        self._close_db()


if __name__ == "__main__":
    DoaReread().parse().run()
