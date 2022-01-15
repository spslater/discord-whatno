"""Interface for the Voice Stats DB"""
import logging
from pathlib import Path
from sqlite3 import Connection, Row, connect

from .helpers import calc_path

logger = logging.getLogger(__name__)

class VoiceDB:
    """Voice DB Interface"""

    def __init__(self, dbfile, readonly=True):
        self.readonly = readonly
        self.filename: Path = calc_path(dbfile)
        if not self.filename:
            raise ValueError("No database to pull comic info from provided")
        self.conn = None

    def setup(self):
        """setup the voice database"""
        logger.debug("running setup on the comic database")
        script = calc_path("./database.sql")
        with open(script, "r", encoding="utf-8") as fp:
            sql_script = fp.read()

        with self as db:
            db.executescript(sql_script)

    def open(self):
        """Open a connection to the database and return a cursor"""
        self.conn: Connection = (
            connect(f"file:{self.filename}?mode=ro", uri=True)
            if self.readonly
            else connect(self.filename)
        )
        self.conn.row_factory = Row
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
