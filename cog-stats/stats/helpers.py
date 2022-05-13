"""Helper methods for the DoA Cogs"""
import logging
from datetime import datetime, timedelta
from math import floor
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


def sec_to_human(secs):
    """Convert duration from seconds to days / hrs / mins / secs"""
    secs = floor(float(secs))
    in_day = 60 * 60 * 24
    in_hour = 60 * 60
    in_minute = 60

    days = secs // in_day
    hours = (secs - (days * in_day)) // in_hour
    minutes = (secs - (days * in_day) - (hours * in_hour)) // in_minute
    seconds = secs % 60

    return days, hours, minutes, seconds


class TimeTravel:
    """Helpful Time Functions"""

    # pylint: disable=invalid-name
    tz = TIMEZONE

    @classmethod
    def sqlts(cls, ts):
        """Convert timestamp to sqlite database time string check"""
        if isinstance(ts, datetime):
            ts = ts.timestamp()
        return datetime.fromtimestamp(ts, tz=cls.tz).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

    @classmethod
    def tsfromdiscord(cls, ts):
        """Convert discord's timestamp to unix timestamp: 2022-05-12T08:46:46.505000+00:00"""
        return datetime.strptime(ts[:-9], "%Y-%m-%dT%H:%M:%S.%f").timestamp()

    @staticmethod
    def timestamp():
        """Get current utc timestamp"""
        return datetime.now().timestamp()

    @staticmethod
    def utcfromtimestamp(timestamp):
        """Convert utc timestamp to datetime"""
        return datetime.utcfromtimestamp(timestamp)

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

    @classmethod
    def fromstr(cls, date_string):
        """Get offset from local string"""
        hour, mins = cls.timeoffset()
        offset = timedelta(hours=hour, minutes=mins)
        date = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
        return date + offset

    @staticmethod
    def datestr(date=None):
        """Get the current date as a YYYY-MM-DD string"""
        display = date or datetime.now()
        return display.strftime("%Y-%m-%d")

    @staticmethod
    def timestr(date=None):
        """Get the current date as a YYYY-MM-DD string"""
        display = date or datetime.now()
        return display.strftime("%Y-%m-%d %H:%M:%S")

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
