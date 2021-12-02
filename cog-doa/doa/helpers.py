"""Helper methods for the DoA Cogs"""
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def calc_path(filename):
    """Calculate a filepath based off of current file"""
    if filename is None:
        return None
    filepath = Path(filename)
    if not filepath.is_absolute():
        filepath = Path(__file__, "..", filepath)
    return filepath.resolve()


class TimeTravel:
    """Helpful Time Functions"""

    @staticmethod
    def datestr():
        """Get the current date as a YYYY-MM-DD string"""
        return datetime.now().strftime("%Y-%m-%d")

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

    @staticmethod
    def next_noon() -> int:
        """Calculate date and number of seconds until the next noon"""
        now = datetime.now()
        today = datetime(now.year, now.month, now.day, 12, 0, 0)
        delta = (today - now).total_seconds()
        if delta > 0:
            date = today.strftime("%Y-%m-%d %H:%M:%S.%f %Z")
            return date, delta
        tomorrow = today + timedelta(days=1)
        delta = (tomorrow - now).total_seconds()
        date = tomorrow.strftime("%Y-%m-%d %H:%M:%S.%f %Z")
        return date, delta
