import logging
import re
from os import chdir, getcwd, makedirs
from os.path import exists, isdir, join, splitext
from textwrap import fill

from pysean import cli, logs
from sqlite3 import connect, OperationalError
from yaml import load, Loader

from .Comic import Comic


class DumbingOfAge(Comic):
    def __init__(self, comic, workdir, savedir):
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
        self.db = self.conn.cursor()
        try:
            self.createTables()
        except OperationalError:
            pass
        self.book_list = comic["book"]

    def createTables(self):
        self.db.executescript(
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

    def _get_tags(self, soup):
        tagList = []
        tags = soup.find("div", {"class": "post-tags"}).find_all("a")
        for tag in tags:
            tagList.append(tag.text)
        return tagList

    def get_archive_url(self, soup):
        logging.debug(f"Getting archive url from landing page")
        prev = self.get_prev(soup)
        prev_soup = self.get_soup(prev)
        return self.get_next(prev_soup)

    def get_title(self, soup):
        logging.debug(f"Getting title of current comic")
        return soup.find("h2", {"class": "post-title"}).find("a").text

    def get_arc_name(self, soup):
        logging.debug(f"Getting current arc name")
        return soup.find("li", {"class": "storyline-root"}).find("a").text[5:]

    def add_arc(self, image_filename, fullname):
        logging.debug(f"Checking if arc needs to be added to database")
        data = image_filename.split("_")
        num = data[1]
        name = data[2]
        book = int(num[0:2])
        arc = int(num[2:4])
        url = f"https://www.dumbingofage.com/category/comic/book-{book}/{arc}-{name}/"

        self.db.execute("SELECT * FROM Arc WHERE number = ?", (num,))
        row = self.db.fetchone()

        if not row:
            logging.info(f'Inserting new arc: "{fullname}"')
            self.db.execute("INSERT INTO Arc VALUES (?,?,?)", (num, fullname, url))
            self.db.execute("SELECT * FROM Arc WHERE number = ?", (num,))
            row = self.db.fetchone()

        return row

    def add_comic(self, image_filename, arc_row, comic_title, url):
        logging.debug(f"Checking if comic needs to be added to database")
        titleRelease = image_filename.split("_")[3]
        release = "-".join(titleRelease.split("-")[0:3])

        self.db.execute("SELECT * FROM Comic WHERE release = ?", (release,))
        row = self.db.fetchone()

        if not row:
            logging.info(f'Inserting new comic: "{comic_title}"')
            self.db.execute(
                "INSERT INTO Comic VALUES (?,?,?,?,?)",
                (release, comic_title, image_filename, url, arc_row[0]),
            )
            self.db.execute("SELECT * FROM Comic WHERE release = ?", (release,))
            row = self.db.fetchone()

        return row

    def add_alt(self, comic, alt):
        logging.debug(f"Checking if alt text needs to be added to database")
        self.db.execute("SELECT * FROM Alt WHERE comicId = ?", (comic[0],))
        row = self.db.fetchone()

        if not row:
            logging.debug(f'Inserting new alt: "{comic[0]}"')
            self.db.execute("INSERT INTO Alt VALUES (?,?)", (comic[0], alt))
            self.db.execute("SELECT * FROM Alt WHERE comicId = ?", (comic[0],))
            row = self.db.fetchone()

        return row

    def add_tags(self, comic, tags):
        logging.debug(f"Checking if tags needs to be added to database")
        added_tags = []
        for tag in tags:
            self.db.execute(
                "SELECT * FROM Tag WHERE comicId = ? AND tag = ?", (comic[0], tag)
            )
            row = self.db.fetchone()

            if not row:
                self.db.execute("INSERT INTO Tag VALUES (?,?)", (comic[0], tag))
                added_tags.append(tag)
        logging.debug(f"Inserted new tags: {added_tags}")

    def process(self):
        while True:
            logging.info(f"Getting soup for {self.url}")
            soup = self.get_soup()

            img_soup = self.get_image(soup)
            image_url = img_soup["src"]
            strip_name, ext = splitext(image_url.split("/")[-1])

            if ext.lower() != ".png":
                self.url = self.get_next(soup)
                continue

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

            if not isdir(book_arc_dir):
                makedirs(book_arc_dir)

            final_filename, raw_filename = self.get_name_info(
                image_filename, book_arc_dir
            )
            self.download_and_save(img_soup, final_filename, raw_filename)
            self.save_to_archive(self.name, final_filename)
            self.save_to_archive(f"{self.name} - {book_arc}", final_filename)

            self.conn.commit()
            logging.info(f'Done processing comic "{final_filename}"')

            self.url = self.get_next(soup)
            self.wait_if_need()

            if self.last_comic:
                break

        self.conn.close()
        logging.info('Completed processing "Dumbing of Age"')


def main(arguments=None):
    parser = cli.init()
    parser.add_argument(
        "yaml",
        help="yaml file that contains info for what and where to download",
        metavar="YAML",
    )
    parser.add_argument(
        "--basedir",
        default=getcwd(),
        help="base directory to append workdir and savedir to",
        metavar="DIR",
    )
    parser.add_argument(
        "--workdir", help="working directory where resource and comic files are saved"
    )
    parser.add_argument("--savedir", help="archive directory to save cbz files")
    parser.add_argument(
        "--start", dest="start", help="start from comic url", metavar="URL"
    )
    args = parser.parse_args(arguments)

    with open(args.yaml, "r") as yml:
        data = load(yml.read(), Loader=Loader)

    workdir_raw = args.workdir if args.workdir else data.get("workdir", None)
    savedir_raw = args.savedir if args.savedir else data.get("savedir", None)
    comics = data.get("comics", None)

    missing = []
    if workdir_raw is None:
        missing.append("workdir")
    if savedir_raw is None:
        missing.append("savedir")
    if comics is None:
        missing.append("comics")
    if missing:
        missing_string = ", ".join(missing)
        logging.error(
            f'Missing fields in data yaml "{args.yaml}" or supplied from the cli: {missing_string}'
        )
        exit(1)

    workdir = join(args.basedir, workdir_raw)
    savedir = join(args.basedir, savedir_raw)

    chdir(workdir)

    log_file = join(workdir, "DumbingOfAge", "output.log")
    logs.init(logfile=log_file, args=args)

    doa = DumbingOfAge(comics["DumbingOfAge"], workdir, savedir)
    doa.process()


if __name__ == "__main__":
    main()
