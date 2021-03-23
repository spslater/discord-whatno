import logging
from os import makedirs, remove, rename, system
from os.path import basename, isdir, join, splitext
from textwrap import fill
from time import sleep
from urllib.request import build_opener, install_opener, urlretrieve

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from requests import get


class Comic:
    def __init__(self, comic, name, workdir, savedir):
        self.comic = comic
        self.short_name = name
        self.workdir = workdir
        self.savedir = savedir

        self.cur = comic["cur"]
        self.url = comic["home"] if ("home" in comic and self.cur) else comic["url"]
        self.base = comic["base"] if "base" in comic else comic["home"]
        self.loc = join(self.workdir, "archive", comic["loc"])
        self.name = comic["name"]
        self.save_alt = comic["alt"] if "alt" in comic else False
        self.image_list = comic["img"]
        self.next_list = comic["nxt"]
        self.prev_list = comic["prev"] if "prev" in comic else None

        self.last_comic = False
        self.cur_count = 0
        self.max_count = 25
        self.sleep_time = 5
        self.exception_wait = 2

    def exception_sleep(self, e, current, retries):
        logging.warning(
            f"Waiting for {self.exception_wait} seconds to try again. Remaining atempts: {retries-current}",
            exc_info=True,
        )
        sleep(self.exception_wait)
        self.exception_wait *= self.exception_wait
        if current == retries:
            logging.exception(e)
            raise e

    def _download(self, image_url, save_as, retries=5):
        logging.info(f'Downloading "{save_as}" from {image_url}')
        for x in range(0, retries):
            try:
                opener = build_opener()
                opener.addheaders = [
                    ("User-agent", "Whatno Comic Reader / (WhatnoComicReader v0.2.0)")
                ]
                install_opener(opener)
                urlretrieve(image_url, save_as)
                break
            except Exception as e:
                self.exception_sleep(e, x, retries)

    def _search_soup(self, soup, path, value=None):
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
        return soup[value] if value else soup

    def search(self, soup, path, value=None):
        soup = self._search_soup(soup, path[:-1], value)
        last = path[-1]
        dic = {}
        if "class" in last:
            dic["class"] = last["class"]
        if "id" in last:
            dic["id"] = last["id"]
        return soup.find_all(last["tag"], dic)

    def get_soup(self, url=None, retries=10):
        url = url if url else self.url
        logging.info(f"Getting soup for {url}")
        for x in range(1, retries + 1):
            try:
                return BeautifulSoup(get(url).text, "html.parser")
            except Exception as e:
                self.exception_sleep(e, x, retries)

    def get_next(self, soup):
        logging.debug(f"Getting next url")
        try:
            val = self._search_soup(soup, self.next_list, "href")
            return val
        except Exception:
            self.last_comic = True
            return None

    def get_prev(self, soup):
        logging.debug(f"Getting previous url")
        return self._search_soup(soup, self.prev_list, "href")

    def get_image(self, soup):
        logging.debug(f"Getting image soup")
        return self._search_soup(soup, self.image_list)

    def _get_alt(self, img):
        if self.save_alt:
            if img.has_attr("alt"):
                return img["alt"]
            if img.has_attr("title"):
                return img["title"]
        return None

    def _save_image_with_alt(self, input_filename, output_filename, alt_raw):
        logging.info(f'Adding alt text to image "{output_filename}"')
        comic = Image.open(input_filename).convert("RGBA")
        c_width, c_height = comic.size

        font = ImageFont.truetype("./font/Ubuntu-R.ttf", 16)
        drawFont = ImageDraw.Draw(
            Image.new("RGB", (c_width, c_height * 2), (255, 255, 255))
        )
        alt = fill(alt_raw, width=(int((c_width - 20) / 11)))
        _, alt_height = drawFont.textsize(alt, font=font)

        height = c_height + 10 + alt_height + 10
        output = Image.new("RGBA", (c_width, height), (224, 238, 239, 255))

        draw = ImageDraw.Draw(output)

        output.paste(comic, (0, 0), mask=comic)
        draw.text((10, c_height + 10), alt, font=font, fill="black")

        output.save(output_filename, "PNG")
        logging.info("Removing raw image")
        remove(input_filename)

    def _convert_to_png(self, input_filename, output_filename):
        _, ext = splitext(input_filename)
        if ext != ".png":
            logging.info(f'Converting image to png "{output_filename}"')
            comic = Image.open(input_filename).convert("RGB")
            comic.save(output_filename, "PNG")
            remove(input_filename)
        else:
            logging.info(f'No need to convert image "{output_filename}"')
            rename(input_filename, output_filename)

    def download_and_save(self, img_soup, final_filename, raw_filename):
        logging.info(f'Downloading and saving "{final_filename}"')
        image_url = img_soup["src"]

        alt_text = self._get_alt(img_soup)
        if alt_text:
            logging.debug("Saving with alt text")
            self._download(image_url, raw_filename)
            self._save_image_with_alt(raw_filename, final_filename, alt_text)
        else:
            logging.debug("Saving with no alt")
            self._download(image_url, raw_filename)
            self._convert_to_png(raw_filename, final_filename)

    def save_to_archive(self, archive, final_filename):
        logging.info(f'Adding to archive: "{archive}"')

        save_location = join(self.savedir, self.name)
        save_as = basename(final_filename)
        if not isdir(save_location):
            makedirs(save_location)

        cmd = f'cd {self.current_image_directory} && zip -ur "{save_location}/{archive}.cbz" "{save_as}" > /dev/null'
        logging.debug(f"Running shell command: `{cmd}`")
        system(cmd)

    def get_name_info(self, img_name, dir_name):
        logging.debug(
            f'Getting name info for image "{img_name}" and directory "{dir_name}"'
        )
        self.current_image_directory = join(self.loc, dir_name)
        img, _ = splitext(img_name)
        final_filename = join(self.current_image_directory, f"{img}.png")
        raw_filename = join(self.current_image_directory, f"raw_{img_name}")

        if not isdir(self.current_image_directory):
            makedirs(self.current_image_directory)

        return final_filename, raw_filename

    def wait_if_need(self):
        logging.debug(
            f"Checking to see if a wait is needed before parsing next comic. {self.cur_count} / {self.max_count}"
        )
        if self.cur_count == self.max_count:
            self.cur_count = 0
            logging.debug(f"Sleeping for {self.sleep_time} secs.")
            sleep(self.sleep_time)
        else:
            self.cur_count += 1
