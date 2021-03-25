"""
Archive the "Order of the Stick" webcomic and update an info database

Classes:
    OrderOfTheStick

Methods:
    main
"""
import logging
from typing import Optional, Union

from bs4 import BeautifulSoup
from bs4.element import Tag

from .comic import Comic, main_setup


class OrderOfTheStick(Comic):
    """
    Order of the Stick comic archiver

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
        super().__init__(comic, "OrderOfTheStick", workdir, savedir)
        self.images = None
        self.cur_name = None
        self.cur_number = None

        soup = self.get_soup(self.url)
        self.generate_images(soup)
        self.url = self.get_next()

    def generate_images(self, soup: Union[BeautifulSoup, Tag]) -> None:
        """
        Set the list of image urls attribute

            Parameters:
                soup (Union[BeautifulSoup, Tag]): soup to search for the images

            Returns:
                None
        """
        logging.debug("Generating image list")
        self.images = self.search(soup, [{"tag": "p", "class": "ComicList"}])
        if self.cur:
            self.images = [self.images[0]]

    def get_next(
        self, soup: Optional[Union[BeautifulSoup, Tag]] = None
    ) -> Optional[str]:
        """
        Get the url for the next comic

            Parameters:
                soup: (Optional[Union[BeautifulSoup, Tag]]): Can pass in soup for page
                    to load images list if they don't exist already

            Returns:
                url (Optional[str]): url for the next image
        """
        if self.images is None and soup is not None:
            self.generate_images(soup)

        try:
            end_image = self.images.pop(-1)
        except IndexError:
            self.last_comic = True
            return None
        else:
            end = end_image.find("a")["href"]
            self.cur_name = (
                " - ".join(end_image.text.split(" - ")[1:])
                .replace("/", " ")
                .replace(": ", " - ")
            )
            self.cur_number = end_image.text.split(" - ")[0].zfill(4)
            return f"{self.base}{end[1:]}"

    def set_start_url(self, start_url: str):
        """
        Sets the url to start getting comics from

            Parameters:
                start_url (str): comic url to start from

            Returns:
                None
        """
        logging.debug("Setting start url: %s", start_url)
        while self.url != start_url:
            self.url = self.get_next()

    def process(self):
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

            image_name = f"{self.short_name}_{self.cur_number}_{self.cur_name}.png"
            directory_name = ""
            final_filename, raw_filename = self.get_name_info(
                image_name, directory_name
            )

            self.download_and_save(img_soup, final_filename, raw_filename)
            self.save_to_archive(self.name, final_filename)

            logging.info('Done processing comic "%s"', final_filename)

            self.url = self.get_next()
            self.wait_if_need()

            if self.last_comic:
                break
        logging.info('Completed Processing "Order of the Stick"')


def main(arguments: Optional[list[str]] = None) -> None:
    """
    Archive the "Order of the Stick" webcomic from the command line.

        Parameters:
            arguments (Optional[list[str]]): list of arguments to pass to the arg parser
    """
    comics, workdir, savedir, start_url = main_setup("OrderOfTheStick", arguments)

    oots = OrderOfTheStick(comics["orderofthestick"], workdir, savedir)
    if start_url:
        oots.set_start_url(start_url)
    oots.process()

    logging.info("Completed Comic")


if __name__ == "__main__":
    main()
