"""Manipulation of the DoA Comics database"""
import logging
from pathlib import Path
from sqlite3 import Connection, Cursor, Row, connect

from .helpers import calc_path

logger = logging.getLogger(__name__)


class ComicDB:
    """Comic DB Interface"""

    def __init__(self, dbfile):
        self.filename: Path = calc_path(dbfile)
        if not self.filename:
            raise ValueError("No database to pull comic info from provided")
        self.conn = None
        self.database = None

    def open(self):
        """Open a connection to the database and return a cursor"""
        self.conn: Connection = connect(f"file:{self.filename}?mode=ro", uri=True)
        self.conn.row_factory = Row
        self.database: Cursor = self.conn.cursor()
        return self.database

    def close(self):
        """Close connection to the database"""
        if self.conn is not None:
            return self.conn.close()
        return None

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return exc_type is None
