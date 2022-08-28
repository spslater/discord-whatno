"""Manipulation of the DoA Comics database"""
import logging
import re
from datetime import datetime, timedelta
from json import dump, load
from pathlib import Path
from sqlite3 import Connection, IntegrityError, Row, connect
from typing import Union

from .helpers import TimeTravel, calc_path

logger = logging.getLogger(__name__)

class DictRow:
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

class ComicDB:
    """Comic DB Interface"""

    def __init__(self, dbfile, readonly=True):
        self.readonly = readonly
        self.filename: Path = calc_path(dbfile)
        if not self.filename:
            raise ValueError("No database to pull comic info from provided")
        self.conn = None

    def setup(self):
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


class Schedule:
    """Manage schedule database"""

    def __init__(self, schedule):
        self.schedule_filename: Path = calc_path(schedule)
        if not self.schedule_filename:
            raise ValueError("No schedule for when to publish comics provided")
        self.schedule = None

    def __getitem__(self, key):
        if self.schedule is None:
            self.load()
        return self.schedule[key]

    def __setitem__(self, key, value):
        if self.schedule is None:
            self.load()
        self.schedule[key] = value

    def load(self):
        """Load schedule from file"""
        with open(self.schedule_filename, "r") as fp:
            self.schedule = load(fp)

    def save(self):
        """Save schedule to file"""
        if self.schedule:
            with open(self.schedule_filename, "w+") as fp:
                dump(self.schedule, fp, sort_keys=True, indent="\t")

    def __enter__(self):
        self.load()
        return self.schedule

    def __exit__(self, exc_type, exc_value, traceback):
        self.save()
        return exc_type is None


class ComicInfo:
    """Manage and get Comic information"""

    def __init__(self, database, schedule):
        self.database_file = database
        self.schedule_file = schedule
        ComicDB(self.database_file, False).setup()

    def _database(self, readonly=True):
        return ComicDB(self.database_file, readonly)

    def _schedule(self):
        return Schedule(self.schedule_file)

    def _get_tags(self, date_string: str) -> list[str]:
        """Comma seperated tags from a comic"""
        with self._database() as database:
            rows = database.execute(
                "SELECT tag FROM Tag WHERE comicId = ?",
                (date_string,),
            ).fetchall()
        return [r["tag"] for r in rows]

    def new_latest(self, mid, url):
        """Save latest comic published to latest channel"""
        with self._database(readonly=False) as database:
            if url.endswith(".png"):
                og = url
                img = f"%{url.split('/')[-1]}"
                res = database.execute(
                    "SELECT url FROM Comic WHERE image LIKE ?",
                    (img,),
                )
                url = res.fetchone()["url"]
            try:
                database.execute("INSERT INTO Latest VALUES (?,?)", (mid, url))
            except IntegrityError:
                pass

    def save_reacts(self, reacts):
        """Save live reacts from recent comic"""
        with self._database(readonly=False) as database:
            for react in reacts:
                try:
                    database.execute("INSERT INTO React VALUES (?,?,?)", react)
                except IntegrityError:
                    pass

    def save_discussion(self, comic, message):
        """Save the message that was part of a comics discussion"""
        content = message.content if message.content.strip() else None
        if message.attachments:
            logger.debug("%s attaches: %s", message.id, message.attachments)
        attach = message.attachments[0].url if message.attachments else None
        embed = str(message.embeds[0].to_dict()) if message.embeds else None
        with self._database(readonly=False) as database:
            data = (
                message.id,
                message.created_at.timestamp(),
                message.author.id,
                comic,
                content,
                attach,
                embed,
            )
            try:
                database.execute(
                    "INSERT INTO Discussion VALUES (?,?,?,?,?,?,?)",
                    data,
                )
            except IntegrityError:
                database.execute(
                    """
                    UPDATE Discussion
                    SET
                        msg = ?,
                        time = ?,
                        user = ?,
                        comic = ?,
                        content = ?,
                        attach = ?,
                        embed = ?
                    WHERE msg = ?
                    """,
                    (*data, message.id),
                )

    def _add_reacts(self, results: list[DictRow]) -> list[DictRow]:
        """Add the reacts as a list of tuples"""
        with self._database() as database:
            for result in results:
                reacts = database.execute(
                    f"""SELECT reaction, count(reaction) as num
                        FROM React
                        WHERE msg = {result['msg']} AND uid != 639324610772467714
                        GROUP BY msg, reaction
                        ORDER BY reaction ASC"""
                ).fetchall()
                if reacts:
                    #setattr(result, "reacts", [(react["reaction"], react["num"]) for react in reacts])
                    result["reacts"] = [(react["reaction"], react["num"]) for react in reacts]
                print(result)
        print(results)
        return results

    def released_on(self, dates: Union[str, list[str]]) -> list[DictRow]:
        """Get database rows for comics released on given dates"""
        if isinstance(dates, str):
            dates = [dates]
        with self._database() as database:
            results = database.execute(
                f"""SELECT
                    Comic.release as release,
                    Comic.title as title,
                    Comic.image as image,
                    Comic.url as url,
                    Alt.alt as alt,
                    Latest.msg as msg
                FROM Comic
                JOIN Alt ON Comic.release = Alt.comicId
                JOIN Latest ON Comic.url = Latest.url
                WHERE release IN {dates}"""
            ).fetchall()
        results = self._add_reacts(results)
        return results

    def todays_reread(self, date=None):
        """Get information for comic reread"""
        with self._schedule() as schedule:
            date_string = date or TimeTravel.datestr()
            days = tuple(schedule["days"][date_string])
            logger.debug("Getting comics on following days: %s", days)

        entries = []
        comics = self.released_on(days)
        logger.debug("%s comics from current week", len(comics))
        for comic in comics:
            release = comic["release"]
            image = comic["image"].split("_", maxsplit=3)[3]
            tags = [
                f"[{tag}](https://www.dumbingofage.com/tag/{re.sub(' ', '-', tag)}/)"
                for tag in self._get_tags(release)
            ]

            entries.append(
                {
                    "title": comic["title"],
                    "url": comic["url"],
                    "alt": f"||{comic['alt']}||",
                    "tags": ", ".join(tags) or "no tags today",
                    "image": f"https://www.dumbingofage.com/comics/{image}",
                    "release": release,
                    "reacts": comic["reacts"],
                }
            )
        return entries

    def update_schedule(self):
        """Update the schedule every week"""
        logger.info("Checking schedule to see if it needs updating")
        with self._schedule() as schedule:
            old_week = schedule["next_week"]
            now = TimeTravel.datestr()
            while old_week <= now:
                new_week = datetime.strptime(old_week, "%Y-%m-%d") + timedelta(days=7)
                new_week_str = datetime.strftime(new_week, "%Y-%m-%d")
                schedule["next_week"] = new_week_str

                last_day = sorted(schedule["days"].keys())[-1]
                next_day = datetime.strptime(last_day, "%Y-%m-%d") + timedelta(days=1)
                next_day_str = datetime.strftime(next_day, "%Y-%m-%d")

                schedule["days"][next_day_str] = TimeTravel.week_dates(new_week_str)

                old_week = schedule["next_week"]
