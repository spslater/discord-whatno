"""Helper methods for the DoA Cogs"""
import logging
from datetime import datetime
# from os import getenv
from pathlib import Path

from pytz import timezone

logger = logging.getLogger(__name__)


def calc_path(filename):
    """Calculate a filepath based off of current file"""
    if filename is None:
        return None
    filepath = Path(filename)
    if not filepath.is_absolute():
        filepath = Path(__file__, "..", filepath)
    return filepath.resolve()


TZNAME = "US/Eastern"
TIMEZONE = timezone(TZNAME)


class TimeTravel:
    """Helpful Time Functions"""

    # pylint: disable=invalid-name
    tz = TIMEZONE

    @staticmethod
    # pylint: disable=invalid-name
    def timeoffset(tz=TZNAME):
        """Get the hours and minutes to add to a loacal time to
        get it as a  naive utc time"""
        off = datetime.now(timezone(tz)).strftime("%z")
        mult = 1 if off[0] == "-" else -1
        hour = int(off[1:3]) * mult
        mins = int(off[3:5]) * mult
        return hour, mins

    @staticmethod
    def datestr(date=None):
        """Get the current date as a YYYY-MM-DD string"""
        display = date or datetime.now()
        return display.strftime("%Y-%m-%d")

    @staticmethod
    def week_day(year: int, week: int, weekday: int) -> str:
        """Generate YYYY-MM-DD from year, week number, day number"""
        ywd = f"{year}-{week}-{weekday}"
        iso_date = datetime.strptime(ywd, "%G-%V-%u")
        return datetime.strftime(iso_date, "%Y-%m-%d")

    @classmethod
    def week_dates(cls, date_string: str) -> list[str]:
        """Dates for the 7 days of a given week

        This will give the full week any specific day falls on, if date is a Wednesday
        it'll give the preceding Monday and Tuesday, the given Wednesday, and the
        following Thursday, Friday, Saturday, and Sunday. ISO standard starts the week
        on a Monday (1) and ends on Sunday (7).
        """
        year, week, _ = datetime.strptime(date_string, "%Y-%m-%d").isocalendar()
        return [
            cls.week_day(year, week, 1),
            cls.week_day(year, week, 2),
            cls.week_day(year, week, 3),
            cls.week_day(year, week, 4),
            cls.week_day(year, week, 5),
            cls.week_day(year, week, 6),
            cls.week_day(year, week, 7),
        ]


# def allow_slash():
#     """Guild ids to allow slash commands for"""
#     return [
#         int(g.strip())
#         for g in getenv("DISCORD_ALLOW_SLASH", "").split(",")
#         if g.strip()
#     ]
