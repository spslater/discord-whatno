import logging
from os import getcwd
from os.path import join
from sys import exit

from pysean import cli, logs
from yaml import load, Loader


if __name__ == "__main__":
    parser = cli.init(log_default="output.log")
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

    args = parser.parse_args()

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

    logs.init(args=args)

    for name, info in comics.items():
        logging.info(f"Updating {name}")
        module = __import__("src", fromlist=[name])
        getattr(module, name)(info, workdir, savedir).process()
    logging.info("Done Updating All Comics")
