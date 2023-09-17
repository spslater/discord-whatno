"""Helper methods for the Whatno Cogs"""
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser
from io import UnsupportedOperation, StringIO
from json import dumps
from os import fsync
from pathlib import Path

from tinydb import JSONStorage, TinyDB
from tinydb.table import Document, Table
from pytz import timezone


def calc_path(filename):
    """Calculate a filepath based off of current file"""
    if filename is None:
        return None
    filepath = Path(filename)
    if not filepath.is_absolute():
        filepath = Path(__file__, "..", filepath)
    return filepath.resolve()

def strim(s):
    return re.sub(r'[^a-zA-Z0-9]', '', s.lower())


class PrettyJSONStorage(JSONStorage):
    """Story TinyDB data in a pretty format"""

    def write(self, data):
        self._handle.seek(0)
        serialized = dumps(data, indent=4, sort_keys=True, **self.kwargs)
        try:
            self._handle.write(serialized)
        except UnsupportedOperation as e:
            raise IOError(
                f'Cannot write to the database. Access mode is "{self._mode}"'
            ) from e

        self._handle.flush()
        fsync(self._handle.fileno())

        self._handle.truncate()

class StrTable(Table):
    document_id_class = str

class PrettyStringDB(TinyDB):
    table_class = StrTable
    default_storage_class = PrettyJSONStorage


class CleanHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs= True
        self.text = StringIO()

    def handle_data(self, d):
        self.text.write(d)

    def process(self, data):
        self.feed(data)
        return self.text.getvalue()


async def aget_json(session, url):
    async with session.get(url) as r:
        return await r.json()


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
