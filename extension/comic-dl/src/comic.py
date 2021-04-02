"""
Download a web comic to archive for offline reading.

Classes:
    Comic

Methods:
    main_setup
"""

import logging
import sys
from os import chdir, getcwd, makedirs, remove, rename, system
from os.path import basename, isdir, join, splitext
from textwrap import fill
from time import sleep
from typing import Optional, Union, NamedTuple
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import build_opener, install_opener, urlretrieve

from bs4 import BeautifulSoup
from bs4.element import Tag
from PIL import Image, ImageDraw, ImageFont
from pysean import cli, logs
from requests import get, RequestException
from yaml import load, Loader

#pylint: disable=invalid-name
class RGBA(NamedTuple):
    """Wrapper for RGBA color value tuple"""
    r: int
    g: int
    b: int
    a: int


class Comic:
    """
    Comic archiver base class
    """

    # pylint: disable=too-many-instance-attributes

    def __init__(self, comic, name, workdir, savedir):
        self.comic = comic
        self.short_name = name
        self.workdir = workdir
        self.savedir = savedir
        self.current_image_directory = None

        self.cur = comic["cur"]
        self.url = comic["home"] if ("home" in comic and self.cur) else comic["url"]
        self.base = comic["base"] if "base" in comic else comic["home"]
        self.discard_query = (
            comic["discard_query"] if "discard_query" in comic else True
        )
        self.loc = join(self.workdir, "archive", comic["loc"])
        if not isdir(self.loc):
            makedirs(self.loc)
        self.name = comic["name"]
        self.save_alt = comic["alt"] if "alt" in comic else False
        self.alt_size = comic["alt_size"] if "alt_size" in comic else 16
        self.alt_color = self._alt_get_color(comic)
        self.image_list = comic["img"]
        self.next_list = comic["nxt"]
        self.prev_list = comic["prev"] if "prev" in comic else None

        self.last_comic = False
        self.cur_count = 0
        self.max_count = 25
        self.sleep_time = 5
        self.exception_wait = 2

    def exception_sleep(self, e: Exception, current: int, retries: int) -> None:
        """
        Wait a bit to try making network request.
        Helps prevent network timeouts and spamming forign servers.

            Parameters:
                e (exception): Exception to raise if reached max number of retries.
                current (int): Number of times already waited for.
                retries (int): Maximum number of tries to wait for.

            Returns:
                None
        """
        logging.warning(
            "Waiting for %d seconds to try again. Remaining atempts: %d",
            self.exception_wait,
            retries - current,
            exc_info=True,
        )
        sleep(self.exception_wait)
        self.exception_wait *= self.exception_wait
        if current == retries:
            logging.exception(e)
            raise e

    def _download(self, image_url: str, save_as: str, retries: int = 5) -> None:
        """
        Downloads an image.

            Parameters:
                image_url (str): URL to download image from.
                save_as (str): Filepath to save downloaded image to.
                retries (int): Number of times to retry when a url exception happens.

            Returns:
                None
        """

        logging.info('Downloading "%s" from %s', save_as, image_url)
        for x in range(0, retries):
            try:
                opener = build_opener()
                opener.addheaders = [
                    ("User-agent", "Whatno Comic Reader / (WhatnoComicReader v0.2.0)")
                ]
                install_opener(opener)
                urlretrieve(image_url, save_as)
                break
            except URLError as e:
                self.exception_sleep(e, x, retries)

    @staticmethod
    def _search_soup(
        soup: Union[BeautifulSoup, Tag],
        path: list[dict],
        value: Optional[str] = None,
    ) -> Union[Tag, str]:
        """
        Given path, searches thru the soup for the end value (if given) or just the sub-soup.

            Parameters:
                soup (Union[BeautifulSoup, Tag]): Soup to search thru.
                path (list[dict]): List of dictionaries to describe search path
                value (Optional[str]): Specific html value to return from found soup

            Returns:
                soup (Union[Tag, str]): The tag that was found if no value passed
                    or the value found in that tag
        """
        for nxt in path:
            dic = {}
            if "class" in nxt:
                dic["class"] = nxt["class"]
            if "id" in nxt:
                dic["id"] = nxt["id"]
            if "index" in nxt:
                soup = soup.find_all(
                    name=nxt.get("tag"), attrs=dic, recursive=nxt.get("recursive", True)
                )[nxt["index"]]
            else:
                soup = soup.find(name=nxt.get("tag"), attrs=dic)
        return soup[value] if soup and value else soup

    def search(
        self, soup: Union[BeautifulSoup, Tag], path: list[dict]
    ) -> list[Tag]:
        """
        Search a soup for all instances of the last thing in the path.

            Parameters:
                soup (Union[BeautifulSoup, Tag]): Soup to search thru.
                path (list[dict]): List of dictionaries to describe search path

            Returns:
                matches (list[Tag]): List of tags that match the last item in the path
        """
        soup = self._search_soup(soup, path[:-1])
        last = path[-1]
        dic = {}
        if "class" in last:
            dic["class"] = last["class"]
        if "id" in last:
            dic["id"] = last["id"]
        return soup.find_all(last["tag"], dic)

    def get_soup(self, url: Optional[str] = None, retries: int = 10) -> Optional[BeautifulSoup]:
        """
        Get the soup for the requested url.

            Parameters:
                url (Optional[str]): Url to get soup for or instance url if none given
                retries (int): number of times to retry before erroring out

            Returns:
                soup (BeautifulSoup): soup from the requested url

            Raises:
                RequestException
        """
        url = url if url else self.url
        logging.info("Getting soup for %s", url)
        for x in range(1, retries + 1):
            try:
                return BeautifulSoup(
                    get(
                        url,
                        headers={
                            "User-agent": "Whatno Comic Reader / (WhatnoComicReader v0.2.0)"
                        },
                    ).text,
                    "html.parser",
                )
            except RequestException as e:
                self.exception_sleep(e, x, retries)
        return None

    def get_next(self, soup: Union[BeautifulSoup, Tag]) -> str:
        """
        Get the next comic url.

            Parameters:
                soup (Union[BeautifulSoup, Tag]): soup to search thru

            Returns:
                url (str): url of next comic
        """
        logging.debug("Getting next url")
        val = self._search_soup(soup, self.next_list, "href")
        if val is None:
            self.last_comic = True
        return val

    def get_prev(self, soup: Union[BeautifulSoup, Tag]) -> str:
        """
        Get the previous comic url.

            Parameters:
                soup (Union[BeautifulSoup, Tag]): soup to search thru

            Returns:
                url (str): url of prev comic
        """
        logging.debug("Getting previous url")
        return self._search_soup(soup, self.prev_list, "href")

    def get_image(self, soup: Union[BeautifulSoup, Tag]) -> str:
        """
        Get the current comics image url.

            Parameters:
                soup (Union[BeautifulSoup, Tag]): soup to search thru

            Returns:
                url (str): url of comic image
        """
        logging.debug("Getting image soup")
        return self._search_soup(soup, self.image_list)

    @staticmethod
    def _alt_get_color(comic: dict) -> RGBA:
        alt_color = comic.get("alt_color")
        if alt_color:
            r_value = alt_color[0]
            g_value = alt_color[1]
            b_value = alt_color[2]
            a_value = alt_color[3] if len(alt_color) > 3 else 255
            return RGBA(r_value,g_value,b_value,a_value)
        return RGBA(224, 238, 239, 255)

    def _get_alt(self, img: Tag) -> Optional[str]:
        """
        Get the alt text of the comic if it exists.

            Parameters:
                img (Tag): html tag of the image to pull info from

            Returns:
                alt_text (Optional[str]): alt text if found otherwise it returns None
        """
        if self.save_alt:
            if img.has_attr("alt"):
                return img["alt"]
            if img.has_attr("title"):
                return img["title"]
        return None

    def _save_image_with_alt(
        self, input_filename: str, output_filename: str, alt_raw: str
    ) -> None:
        """
        Add alt text to downloaded image, removing the orignal download.

            Parameters:
                input_filename (str): path to the file originally downloaded
                output_filename (str): path to save the image with alt text on it
                alt_raw (str): alt text to save to the file

            Returns:
                None
        """
        logging.info('Adding alt text to image "%s"', output_filename)
        comic = Image.open(input_filename).convert("RGBA")
        c_width, c_height = comic.size

        font = ImageFont.truetype(join(self.workdir, "src/font/Ubuntu-R.ttf"), self.alt_size)
        draw_font = ImageDraw.Draw(
            Image.new("RGB", (c_width, c_height * 2), (255, 255, 255))
        )
        alt = fill(alt_raw, width=(int((c_width - 20) / 11)))
        _, alt_height = draw_font.textsize(alt, font=font)

        height = c_height + 10 + alt_height + 10
        output = Image.new("RGBA", (c_width, height), self.alt_color)

        draw = ImageDraw.Draw(output)

        output.paste(comic, (0, 0), mask=comic)
        draw.text((10, c_height + 10), alt, font=font, fill="black")

        output.save(output_filename, "PNG")
        logging.info("Removing raw image")
        remove(input_filename)

    @staticmethod
    def _convert_to_png(input_filename: str, output_filename: str) -> None:
        """
        Convert image to png and remove the non-png image.

            Parameters:
                input_filename (str): Non png image to convert
                output_filename (str): File path to save image to, with png extension

            Returns:
                None
        """
        _, ext = splitext(input_filename)
        if ext != ".png":
            logging.info('Converting image to png "%s"', output_filename)
            comic = Image.open(input_filename).convert("RGB")
            comic.save(output_filename, "PNG")
            remove(input_filename)
        else:
            logging.info('No need to convert image "%s"', output_filename)
            rename(input_filename, output_filename)

    def download_and_save(
        self, img_soup: Tag, final_filename: str, raw_filename: str
    ) -> None:
        """
        Download image and archive it.

            Parameters:
                img_soup (Tag): img tag to get src url from
                final_filename (str): path to save final image to
                raw_filename (str): path to save intermediate raw image to

            Returns:
                None
        """
        logging.info('Downloading and saving "%s"', final_filename)
        image_url = img_soup["src"]
        if self.discard_query:
            parsed_url = urlparse(image_url)
            image_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"

        alt_text = self._get_alt(img_soup)
        if alt_text:
            logging.debug("Saving with alt text")
            self._download(image_url, raw_filename)
            self._save_image_with_alt(raw_filename, final_filename, alt_text)
        else:
            logging.debug("Saving with no alt")
            self._download(image_url, raw_filename)
            self._convert_to_png(raw_filename, final_filename)

    def save_to_archive(self, archive: str, filename: str) -> None:
        """
        Add image to cbz archive.

            Parameters:
                archive (str): cbz archive name
                filename (str): image file to add to archive

            Returns:
                None
        """
        logging.info('Adding to archive: "%s"', archive)

        save_location = join(self.savedir, self.name)
        save_as = basename(filename)
        if not isdir(save_location):
            makedirs(save_location)

        cmd = f'cd {self.current_image_directory} && zip -ur \
            "{save_location}/{archive}.cbz" "{save_as}" > /dev/null'
        logging.debug("Running shell command: `%s`", cmd)
        system(cmd)

    def get_name_info(self, img_name: str, dir_name: str) -> tuple[str, str]:
        """
        Get the final and raw file paths for the image download.

            Parameters:
                img_name (str): name of the image to download
                dir_name (str): subdirectory to save image into

            Returns:
                final_filename (str), raw_filename (str): the path for the final image,
                    and the path for the raw image
        """
        logging.debug(
            'Getting name info for image "%s" and directory "%s"', img_name, dir_name
        )
        self.current_image_directory = join(self.loc, dir_name)
        img, _ = splitext(img_name)
        final_filename = join(self.current_image_directory, f"{img}.png")
        raw_filename = join(self.current_image_directory, f"raw_{img_name}")

        if not isdir(self.current_image_directory):
            makedirs(self.current_image_directory)

        return final_filename, raw_filename

    def wait_if_need(self) -> None:
        """
        Sleep for a bit to try and prevent http timeout. Done after every `max_count` comics.

            Parameters:
                None

            Returns:
                None
        """
        logging.debug(
            "Checking to see if a wait is needed before parsing next comic. %d / %d",
            self.cur_count,
            self.max_count,
        )
        if self.cur_count == self.max_count:
            self.cur_count = 0
            logging.debug("Sleeping for %d secs.", self.sleep_time)
            sleep(self.sleep_time)
        else:
            self.cur_count += 1

def main_setup(comic_dir: str, arguments: Optional[list[str]] = None) -> None:
    """
    Sets up the arguments for running the individual comics from the command line.

        Parameters:
            comic_dir (str): directory in the archive folder to save comics to
            arguments (Optional[list[str]]): list of aruments to pass into argument parser

        Returns:
            comics (dict):
            workdir (str):
            savedir (str):
    """
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
            'Missing fields in data yaml "%s" or supplied from the cli: %s',
            args.yaml,
            missing_string,
        )
        sys.exit(1)

    workdir = join(args.basedir, workdir_raw)
    savedir = join(args.basedir, savedir_raw)

    chdir(workdir)

    log_file = join(workdir, comic_dir, "output.log")
    logs.init(logfile=log_file, args=args)

    return comics, workdir, savedir, args.start
