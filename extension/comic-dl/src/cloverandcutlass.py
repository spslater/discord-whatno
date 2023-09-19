"""Archive the "Clover and Cutlass" webcomic and update an info database

:class CloverAndCutlass: Clover and Cutlass archiver class
:function main: process comic indvidually from the command line
"""
import logging
import re
from datetime import datetime
from os.path import join
from sqlite3 import connect, OperationalError, Row
from typing import Optional, Union

from bs4 import BeautifulSoup
from bs4.element import Tag

from .comic import Comic, main_setup


class CloverAndCutlass(Comic):
    """Clover and Cutlass comic archiver

    :method process: Archive the comics and save info to database
    """

    def __init__(self, comic: dict, workdir: str, savedir: str) -> None:
        """Initializer

        :param comic: dictionary with info needed for initalization
        :type comic: dict
        :param workdir: working directory where downloaded images get saved to
        :type workdir: str
        :param savedir: directory where the image archives live
        :type savedir: str
        """
        super().__init__(comic, "CloverAndCutlass", workdir, savedir)
        self.database_filename = comic.get("db", f"{self.short_name}.db")
        self.database_path = join(self.loc, self.database_filename)
        self.conn = connect(self.database_path)
        self.database = self.conn.cursor()
        try:
            self._create_tables()
        except OperationalError:
            pass

        self.number_match = re.compile(
            r"^.*?\/comic\/chapter-(?P<chapter>[0-9]+)-page-(?P<page>[0-9]+).*?$"
        )
        self.cover_match = re.compile(
            r"^.*?\/comic\/chapter-(?P<chapter>[0-9]+)-cover.*?$"
        )

    def _create_tables(self):
        """Create tables in database for comic"""
        self.database.executescript(
            """
            CREATE TABLE Comic(
                number PRIMARY KEY,
                release TEXT NOT NULL,
                alt TEXT,
                url TEXT UNIQUE NOT NULL
            );

            CREATE TABLE Tag(
                comicId
                        REFERENCES Comic(number)
                        ON DELETE CASCADE
                        ON UPDATE CASCADE
                        NOT NULL,
                tag TEXT NOT NULL
            );

            CREATE TABLE Character(
                comicId
                        REFERENCES Comic(number)
                        ON DELETE CASCADE
                        ON UPDATE CASCADE
                        NOT NULL,
                character TEXT NOT NULL
            );

            CREATE TABLE Location(
                comicId
                        REFERENCES Comic(number)
                        ON DELETE CASCADE
                        ON UPDATE CASCADE
                        NOT NULL,
                location TEXT NOT NULL
            );
        """
        )

    def _get_release(self, soup: Union[BeautifulSoup, Tag]) -> Optional[str]:
        """Get the release date as string in YYYY-MM-DD format"""
        date_tag = self._search_soup(
            soup,
            [
                {"tag": "div", "class": "blog-wrapper"},
                {"tag": "div", "class": "entry-meta"},
                {"tag": "a"},
            ],
        )
        if date_tag:
            return datetime.strptime(date_tag.text, "%B %d, %Y").strftime("%Y-%m-%d")
        return None

    def _add_comic(
        self, soup: Union[BeautifulSoup, Tag], img_soup: Tag, number: str
    ) -> Row:
        """Add comic info to database"""
        logging.debug("Checking if comic needs to be added to database")
        self.database.execute("SELECT * FROM Comic WHERE number = ?", (number,))
        row = self.database.fetchone()
        if not row:
            logging.info('Inserting new comic "%s"', number)
            release = self._get_release(soup)
            alt_text = self._get_alt(img_soup)
            self.database.execute(
                "INSERT INTO Comic VALUES (?,?,?,?)",
                (number, release, alt_text, self.url),
            )

        self.database.execute("SELECT * FROM Comic WHERE number = ?", (number,))
        return self.database.fetchone()

    def _add_extra(self, comic: Row, extra: Tag, table: str) -> None:
        """Add extra info to database (tag, character, location)"""
        logging.debug("Checking if %s needs to be added to database", table.lower())
        self.database.execute(
            f"SELECT * FROM {table.title()} WHERE comicId = ? AND {table.lower()} = ?",
            (comic[0], extra.text),
        )
        row = self.database.fetchone()
        if not row:
            logging.info(
                'Inserting new %s for "%s": %s', table.lower(), comic[0], extra.text
            )
            self.database.execute(
                f"INSERT INTO {table.title()} VALUES (?,?)",
                (comic[0], extra.text),
            )
        self.database.execute(
            f"SELECT * FROM {table.title()} WHERE comicId = ? and {table.lower()} = ?",
            (comic[0], extra.text),
        )
        return self.database.fetchone()

    def _save_to_database(
        self, soup: Union[BeautifulSoup, Tag], img_soup: Tag, number: str
    ) -> None:
        """Save current comic to database"""
        comic_row = self._add_comic(soup, img_soup, number)
        extra_info = self.search(soup, [{"tag": "footer"}, {"tag": "a"}])
        for extra in extra_info:
            extra_type = re.search(
                r"^.*?\/comic-(?P<type>tag|character|location)\/.*?$", extra["href"]
            )
            if extra_type:
                table = extra_type.group("type")
                self._add_extra(comic_row, extra, table)

        self.conn.commit()

    def process(self):
        """Archive the web comic. Downloads latest if `cur` is True, otherwise downloads all the
        ones from given url.
        """
        while True:
            logging.info("Getting soup for %s", self.url)
            soup = self.get_soup()

            if self.cur:
                prev = self.get_prev(soup)
                prev_soup = self.get_soup(prev)
                self.url = self.get_next(prev_soup)

            img_soup = self.get_image(soup)
            match = self.number_match.search(self.url)

            chapter = "00"
            page = "00"
            if match:
                chapter = match.group("chapter").zfill(2)
                page = match.group("page").zfill(2)
            else:
                match = self.cover_match.search(self.url)
                if match:
                    chapter = match.group("chapter").zfill(2)

            number = f"{chapter}{page}"

            image_name = f"{self.short_name}_{number}.png"
            directory_name = f"ch_{chapter}"
            final_filename, raw_filename = self.get_name_info(
                image_name, directory_name
            )

            self.download_and_save(img_soup, final_filename, raw_filename)
            self.save_to_archive(self.name, final_filename)
            self._save_to_database(soup, img_soup, number)

            logging.info('Done processing comic "%s"', final_filename)

            self.url = self.get_next(soup)
            self.wait_if_need()

            if self.last_comic:
                break

        self.conn.close()
        logging.info('Completed Processing "Clover and Cutlass"')


def main(arguments: Optional[list[str]] = None) -> None:
    """Archive the "Clover and Cutlass" webcomic from the command line.

    :param arguments: list of arguments to pass to the arg parser
    :type arguments: Optional[list[str]]
    """
    comics, workdir, savedir, _ = main_setup("CloverAndCutlass", arguments)

    cac = CloverAndCutlass(comics["cloverandcutlass"], workdir, savedir)
    cac.process()

    logging.info("Completed Comic")


if __name__ == "__main__":
    main()
