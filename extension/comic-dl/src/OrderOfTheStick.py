import logging
from os import chdir, getcwd
from os.path import join, splitext

from pysean import cli, logs
from yaml import load, Loader

from .Comic import Comic


class OrderOfTheStick(Comic):
    def __init__(self, comic, workdir, savedir):
        super().__init__(comic, "OrderOfTheStick", workdir, savedir)
        self.images = None
        self.cur_name = None
        self.cur_number = None

        soup = self.get_soup(self.url)
        self.generate_images(soup)
        self.url = self.get_next()

    def generate_images(self, soup):
        logging.debug(f"Generating image list")
        self.images = self.search(soup, [{"tag": "p", "class": "ComicList"}])
        if self.cur:
            self.images = [self.images[0]]

    def get_next(self):
        try:
            end_image = self.images.pop(-1)
            end = end_image.find("a")["href"]
            self.cur_name = (
                " - ".join(end_image.text.split(" - ")[1:])
                .replace("/", " ")
                .replace(": ", " - ")
            )
            self.cur_number = end_image.text.split(" - ")[0].zfill(4)
            return f"{self.base}{end[1:]}"
        except Exception:
            self.last_comic = True
            return None

    def set_start_url(self, start_url):
        logging.debug(f"Setting start url: {start_url}")
        while self.url != start_url:
            self.url = self.get_next()

    def process(self):
        while True:
            logging.info(f"Getting soup for {self.url}")
            soup = self.get_soup()

            img_soup = self.get_image(soup)

            image_name = f"{self.short_name}_{self.cur_number}_{self.cur_name}.png"
            directory_name = ""
            final_filename, raw_filename = self.get_name_info(
                image_name, directory_name
            )

            self.download_and_save(img_soup, final_filename, raw_filename)
            self.save_to_archive(self.name, final_filename)

            logging.info(f'Done processing comic "{final_filename}"')

            self.url = self.get_next()
            self.wait_if_need()

            if self.last_comic:
                break
        logging.info(f'Completed Processing "Order of the Stick"')


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

    log_file = join(workdir, "OrderOfTheStick", "output.log")
    logs.init(logfile=log_file, args=args)

    oots = OrderOfTheStick(comics["OrderOfTheStick"], workdir, savedir)
    if args.start:
        oots.set_start_url(args.start)
    oots.process()

    logging.info("Completed Comic")


if __name__ == "__main__":
    main()
