"""
Archive Webcomics by dynamically loading them from the src directory.

Methods:
    main
"""
import logging
import sys
from importlib import import_module
from os import getcwd
from os.path import join

from pysean import cli, logs
from yaml import load, Loader


def main():
    """Main function to parse and archive web comics"""
    parser = cli.init(log_default="output.log")
    parser.add_argument(
        "yaml",
        help="yaml file that contains info for what and where to download",
        metavar="YAML",
    )
    parser.add_argument(
        "--workdir", help="working directory where resource and comic files are saved"
    )
    parser.add_argument("--savedir", help="archive directory to save cbz files")
    parser.add_argument("--only", help="only run these comics", nargs="*")

    args = parser.parse_args()

    with open(args.yaml, "r") as yml:
        data = load(yml.read(), Loader=Loader)

    workdir = args.workdir if args.workdir else data.get("workdir", None)
    savedir = args.savedir if args.savedir else data.get("savedir", None)
    comics = data.get("comics", None)

    missing = []
    if workdir is None:
        missing.append("workdir")
    if savedir is None:
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

    logs.init(args=args)

    for name, info in comics.items():
        if not args.only or name in args.only:
            logging.info("Updating %s", name)
            module = import_module(f"src.{name.lower()}")
            getattr(module, name)(info, workdir, savedir).process()
    logging.info("Done Updating All Comics")


if __name__ == "__main__":
    main()
