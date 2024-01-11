"""Helper methods for the Whatno Cogs"""

import re

# from asyncio import to_thread
from datetime import datetime, timedelta

# from functools import wraps, partial
from html.parser import HTMLParser
from io import StringIO, UnsupportedOperation
from json import dumps
from math import floor
from os import fsync
from pathlib import Path
from sqlite3 import connect

from pytz import timezone
from tinydb import JSONStorage, TinyDB
from tinydb.table import Table


def calc_path(filename):
    """Calculate a filepath based off of current file"""
    if filename is None:
        return None
    filepath = Path(filename)
    if not filepath.is_absolute():
        filepath = Path(__file__, "..", filepath)
    return filepath.resolve()


def strim(s):
    """Remove any non-alphanum characters and make the string lowercase"""
    return re.sub(r"[^a-zA-Z0-9]", "", s.lower())


class PrettyJSONStorage(JSONStorage):
    """Story TinyDB data in a pretty format"""

    def write(self, data):
        self._handle.seek(0)
        serialized = dumps(data, indent=4, sort_keys=True, **self.kwargs)
        try:
            self._handle.write(serialized)
        except UnsupportedOperation as e:
            raise IOError(f'Cannot write to the database. Access mode is "{self._mode}"') from e

        self._handle.flush()
        fsync(self._handle.fileno())

        self._handle.truncate()


class StrTable(Table):
    """Allow using strings instead of ints for table keys"""

    document_id_class = str


class PrettyStringDB(TinyDB):
    """TinyDB that allows using strings at keys
    and saves as pretty JSON
    """

    table_class = StrTable
    default_storage_class = PrettyJSONStorage


# complains about "error" method, but don't know which it's referring too
# pylint: disable=abstract-method
class CleanHTML(HTMLParser):
    """Parse given html and clean the input
    up so that it displays nicely
    """

    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    # pylint: disable=arguments-differ
    def handle_data(self, data):
        """write arbitrary data to the text output"""
        self.text.write(data)

    def process(self, data):
        """clean up given html and return it"""
        self.feed(data)
        return self.text.getvalue()


async def aget_json(session, url):
    """Get json from an async aiohttp GET request"""
    async with session.get(url) as res:
        return await res.json()


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

    @classmethod
    def sqlts(cls, ts):
        """Convert timestamp to sqlite database time string check"""
        if isinstance(ts, datetime):
            ts = ts.timestamp()
        return datetime.fromtimestamp(ts, tz=cls.tz).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

    @staticmethod
    def tsfromdiscord(ts):
        """Convert discord's timestamp to unix timestamp: 2022-05-12T08:46:46.505000+00:00"""
        return datetime.strptime(ts[:-9], "%Y-%m-%dT%H:%M:%S.%f").timestamp()

    @staticmethod
    def tsinpast(days=0, hrs=0, mins=0, secs=0):
        """Get a timestamp in the past"""
        now = datetime.now()
        td = timedelta(days=days, hours=hrs, minutes=mins, seconds=secs)
        return (now - td).timestamp()

    @classmethod
    def pretty_ts(cls, ts):
        """Return a pretty output for the timestamp"""
        val = cls.sqlts(ts)
        date, time = val.split("T")
        time = time.split(".")[0]
        return f"{date} at {time}"

    @classmethod
    def strptime(cls, date):
        try:
            ts = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            ts = datetime.strptime(date, "%Y-%m-%d %H:%M")
        return ts


class DictRow:
    """Turn a row into a dictionary (for dot notation)"""

    def __init__(self, cursor, row):
        self._keys = []
        for idx, col in enumerate(cursor.description):
            setattr(self, col[0], row[idx])

    def __repr__(self):
        vals = [f"{k}: {getattr(self,k)}" for k in self._keys]
        return "DictRow(" + " | ".join(vals) + ")"

    def __getitem__(self, key):
        return getattr(self, key, None)

    def __setitem__(self, key, value):
        self._keys.append(key)
        setattr(self, key, value)


class ContextDB:
    """Sqlite DB for use with context libs"""

    SQL_TIMEOUT = 30.0

    def __init__(self, dbfile, setup_filename, readonly=False):
        self.readonly = readonly
        self.filename = dbfile
        if not self.filename:
            raise ValueError("No database to open")
        self.setup_filename = setup_filename
        self.conn = None

    def setup(self):
        """setup the voice database"""
        script = calc_path(self.setup_filename)
        with open(script, "r", encoding="utf-8") as fp:
            sql_script = fp.read()

        with self as db:
            db.executescript(sql_script)

    def open(self):
        """Open a connection to the database and return a cursor"""
        self.conn = (
            connect(f"file:{self.filename}?mode=ro", uri=True, timeout=self.SQL_TIMEOUT)
            if self.readonly
            else connect(self.filename, timeout=self.SQL_TIMEOUT)
        )
        self.conn.row_factory = DictRow
        return self.conn.cursor()

    def close(self):
        """Close connection to the database"""
        if not self.readonly:
            self.conn.commit()
        return self.conn.close()

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return exc_type is None


# # https://stackoverflow.com/a/65882269
# def threadable(func):
#     """decorator to run long functions as a thread to prevent blocking"""
#     @wraps(func)
#     async def wrapper(*args, **kwargs):
#         return await to_thread(func, *args, **kwargs)

#     return wrapper
