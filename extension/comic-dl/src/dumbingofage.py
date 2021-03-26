"""
Archive the "Dumbing of Age" webcomic and update an info database

Classes:
    DumbingOfAge

Methods:
    main
"""
import logging
from os import makedirs
from os.path import isdir, join, splitext
from sqlite3 import connect, OperationalError, Row
from typing import Optional, Union

from bs4 import BeautifulSoup
from bs4.element import Tag

from .comic import Comic, main_setup


class DumbingOfAge(Comic):
    """
    Dumbing of Age comic archiver

    Methods:
        process(): Archive the comics
    """

    def __init__(self, comic: dict, workdir: str, savedir: str) -> None:
        """
        Initializer

            Parameters:
                comic (dict): dictionary with info needed for initalization
                workdir (str): working directory where downloaded images get saved to
                savedir (str): directory where the image archives live

            Returns:
                None
        """
        super().__init__(comic, "DumbingOfAge", workdir, savedir)
        self.database_filename = None
        if "db" in self.comic:
            self.database_filename = self.comic["db"]
        else:
            self.database_filename = f"{self.short_name}.db"
        if not isdir(self.loc):
            makedirs(self.loc)
        self.database_path = join(self.loc, self.database_filename)
        self.conn = connect(self.database_path)
        self.database = self.conn.cursor()
        try:
            self.create_tables()
        except OperationalError:
            pass
        self.book_list = comic["book"]

    def create_tables(self):
        """Create the needed tables in the SQLite3 database"""
        self.database.executescript(
            """
                CREATE TABLE Arc(
                    number PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    url TEXT UNIQUE NOT NULL
                );

                CREATE TABLE Comic(
                    release PRIMARY KEY,
                    title TEXT NOT NULL,
                    image TEXT UNIQUE NOT NULL,
                    url TEXT UNIQUE NOT NULL,
                    arcId
                            REFERENCES Arc(rowid)
                            ON DELETE CASCADE
                            ON UPDATE CASCADE
                            NOT NULL
                );

                CREATE TABLE Alt(
                    comicId
                            UNIQUE
                            REFERENCES Comic(release)
                            ON DELETE CASCADE
                            ON UPDATE CASCADE
                            NOT NULL,
                    alt TEXT NOT NULL
                );

                CREATE TABLE Tag(
                    comicId
                            REFERENCES Comic(release)
                            ON DELETE CASCADE
                            ON UPDATE CASCADE
                            NOT NULL,
                    tag TEXT NOT NULL
                );
        """
        )

    @staticmethod
    def _get_tags(soup: Union[BeautifulSoup, Tag]) -> list[str]:
        """
        Get list of tags for the comic.

            Parameters:
                soup (Union[BeautifulSoup, Tag]): soup to search for tags

            Returns:
                tag_list (list[str]): list of tags for the comic
        """
        tag_list = []
        tags = soup.find("div", {"class": "post-tags"}).find_all("a")
        for tag in tags:
            tag_list.append(tag.text)
        return tag_list

    def get_archive_url(self, soup: Union[BeautifulSoup, Tag]) -> Optional[str]:
        """
        Get direct link to comic instead of homepage of website

            Parameters:
                soup (Union[BeautifulSoup, Tag]): soup of comic homepage

            Returns:
                url (Optional[str]): direct url link to comic
        """
        logging.debug("Getting archive url from landing page")
        prev = self.get_prev(soup)
        prev_soup = self.get_soup(prev)
        return self.get_next(prev_soup)

    def get_title(self, soup: Union[BeautifulSoup, Tag]) -> Optional[str]:
        """
        Get title of comic

            Parameters:
                soup (Union[BeautifulSoup, Tag]): soup of current comic

            Returns:
                title (Optional[str]): title of comic
        """
        logging.debug("Getting title of current comic")
        title_tag = self._search_soup(
            soup, [{"tag": "h2", "class": "post-title"}, {"tag": "a"}]
        )
        if title_tag:
            return title_tag.text
        return None

    def get_arc_name(self, soup: Union[BeautifulSoup, Tag]) -> Optional[str]:
        """
        Get name of current arc

            Parameters:
                soup (Union[BeautifulSoup, Tag]): soup of current comic

            Returns:
                arc (Optional[str]): name of current arc
        """
        logging.debug("Getting current arc name")
        arc_tag = self._search_soup(
            soup, [{"tag": "li", "class": "storyline-root"}, {"tag": "a"}]
        )
        if arc_tag:
            return arc_tag.text[5:]
        return None

    def add_arc(self, image_filename: str, arc_name: str) -> Optional[Row]:
        """
        Add arc to info database if it doesn't exist, otherwise return existing row.

            Parameters:
                image_filename (str): name of saved image to parse info for database from
                arc_name (str): full name of arc

            Returns:
                row (Optional[Row]): database row of added arc

        """
        logging.debug("Checking if arc needs to be added to database")
        data = image_filename.split("_")
        num = data[1]
        name = data[2]
        book = int(num[0:2])
        arc = int(num[2:4])
        url = f"https://www.dumbingofage.com/category/comic/book-{book}/{arc}-{name}/"

        self.database.execute("SELECT * FROM Arc WHERE number = ?", (num,))
        row = self.database.fetchone()

        if not row:
            logging.info('Inserting new arc: "%s"', arc_name)
            self.database.execute(
                "INSERT INTO Arc VALUES (?,?,?)", (num, arc_name, url)
            )
            self.database.execute("SELECT * FROM Arc WHERE number = ?", (num,))
            row = self.database.fetchone()

        return row

    def add_comic(
        self, image_filename: str, arc_row: Row, comic_title: str, url: str
    ) -> Optional[Row]:
        """
        Add comic to info database if it doesn't exist, otherwise return existing row.

            Parameters:
                image_filename (str): name of saved image to parse info for database from
                arc_row (Row): database row of arc
                comic_title (str): title of current comic
                url (str): Website page to view comic

            Returns:
                row (Optional[Row]): database row of added comic

        """
        logging.debug("Checking if comic needs to be added to database")
        title_release = image_filename.split("_")[3]
        release = "-".join(title_release.split("-")[0:3])

        self.database.execute("SELECT * FROM Comic WHERE release = ?", (release,))
        row = self.database.fetchone()

        if not row:
            logging.info('Inserting new comic: "%s"', comic_title)
            self.database.execute(
                "INSERT INTO Comic VALUES (?,?,?,?,?)",
                (release, comic_title, image_filename, url, arc_row[0]),
            )
            self.database.execute("SELECT * FROM Comic WHERE release = ?", (release,))
            row = self.database.fetchone()

        return row

    def add_alt(self, comic: Row, alt: str) -> Optional[Row]:
        """
        Add alt text to info database if it doesn't exist, otherwise return existing row.

            Parameters:
                comic_row (Row): database row of comic
                alt (str): alt text to save for current comic

            Returns:
                row (Optional[Row]): database row of added alt text

        """
        logging.debug("Checking if alt text needs to be added to database")
        self.database.execute("SELECT * FROM Alt WHERE comicId = ?", (comic[0],))
        row = self.database.fetchone()

        if not row:
            logging.debug('Inserting new alt: "%s"', comic[0])
            self.database.execute("INSERT INTO Alt VALUES (?,?)", (comic[0], alt))
            self.database.execute("SELECT * FROM Alt WHERE comicId = ?", (comic[0],))
            row = self.database.fetchone()

        return row

    def add_tags(self, comic: Row, tags: list[str]) -> list[Row]:
        """
        Add tags to info database if it doesn't exist, otherwise return existing rows.

            Parameters:
                comic_row (Row): database row of comic
                tags (list[str]): tags to save for current comic

            Returns:
                added_tags (list[Row]): list of rows of added tags

        """
        logging.debug("Checking if tags needs to be added to database")
        added_tags = []
        for tag in tags:
            self.database.execute(
                "SELECT * FROM Tag WHERE comicId = ? AND tag = ?", (comic[0], tag)
            )
            row = self.database.fetchone()

            if not row:
                self.database.execute("INSERT INTO Tag VALUES (?,?)", (comic[0], tag))
                self.database.execute(
                    "SELECT * FROM Tag WHERE comicId = ? AND tag = ?", (comic[0], tag)
                )
                row = self.database.fetchone()
                added_tags.append(row)
        logging.debug("Inserted new tags: %s", [tag[1] for tag in added_tags])
        return added_tags

    def _naming_info(
        self, soup: Union[BeautifulSoup, Tag], image_url: str
    ) -> None:
        """
        Get book/arc number, image filename, final filename, and raw filename for current comic

            Parameters:
                soup (Union[BeautifulSoup, Tag]): comic page soup
                image_url (str): url for image

            Returns:
                book_arc (str): book / arc combo, ie: 1003 (Book 10, Arc 3)
                image_filename (str): filename of image to pull down
                final_filename (str): filename to save image as
                raw_filename (str): temp raw file before adding hover text, if needed
        """
        strip_name, ext = splitext(image_url.split("/")[-1])

        if ext.lower() != ".png":
            self.url = self.get_next(soup)
            return True, None, None, None, None


        if self.cur:
            parts = self._search_soup(soup, self.book_list, "href").split("/")
            book_number = parts[-3].split("-")[1].zfill(2)
            arcs = parts[-2].split("-")
            self.url = self.get_archive_url(soup)
        else:
            parts = self.url.split("/")
            book_number = parts[-4].split("-")[1].zfill(2)
            arcs = parts[-3].split("-")
        arc_number = arcs[0].zfill(2)
        arc_name = "-".join(arcs[1:])
        book_arc = f"{book_number}{arc_number}"
        book_arc_dir = join(self.loc, book_arc)
        image_filename = (
            f"{self.short_name}_{book_arc}_{arc_name}_{strip_name}{ext.lower()}"
        )

        if not isdir(book_arc_dir):
            makedirs(book_arc_dir)

        final_filename, raw_filename = self.get_name_info(image_filename, book_arc_dir)

        return False, book_arc, image_filename, final_filename, raw_filename

    def process(self) -> None:
        """
        Archive the web comic. Downloads latest if `cur` is True, otherwise downloads all the
            ones from given url.

            Parameters:
                None

            Returns:
                None
        """
        while True:
            logging.info("Getting soup for %s", self.url)
            soup = self.get_soup()

            img_soup = self.get_image(soup)
            skip_comic, book_arc, image_filename, final_filename, raw_filename = self._naming_info(
                soup, img_soup["src"]
            )
            if skip_comic:
                continue

            logging.info("Saving Arc to Database")
            full_arc_name = self.get_arc_name(soup)
            arc_row = self.add_arc(image_filename, full_arc_name)

            logging.info("Saving Comic to Database")
            comic_title = self.get_title(soup)
            comic_row = self.add_comic(image_filename, arc_row, comic_title, self.url)

            alt_text = self._get_alt(img_soup)
            if alt_text:
                logging.info("Saving Alt Text to Database")
                self.add_alt(comic_row, alt_text)

            logging.info("Saving Tags to Database")
            tags = self._get_tags(soup)
            self.add_tags(comic_row, tags)

            self.download_and_save(img_soup, final_filename, raw_filename)
            self.save_to_archive(self.name, final_filename)
            self.save_to_archive(f"{self.name} - {book_arc}", final_filename)

            self.conn.commit()
            logging.info('Done processing comic "%s"', final_filename)

            self.url = self.get_next(soup)
            self.wait_if_need()

            if self.last_comic:
                break

        self.conn.close()
        logging.info('Completed processing "Dumbing of Age"')


def main(arguments: Optional[list[str]] = None) -> None:
    """
    Archive the "Dumbing of Age" webcomic from the command line.
    """
    comics, workdir, savedir, _ = main_setup("DumbingOfAge", arguments)

    doa = DumbingOfAge(comics["dumbingofage"], workdir, savedir)
    doa.process()


if __name__ == "__main__":
    main()
