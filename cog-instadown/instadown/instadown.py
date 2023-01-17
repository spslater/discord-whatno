"""Stats Bot for Voice and Messages"""
import logging
import re
from os import stat, rename, remove
from subprocess import run

from discord import File
from discord.ext.commands import Cog

from .helpers import calc_path, generate_chunker

logger = logging.getLogger(__name__)

chnk = generate_chunker(10)

MAX_FILE = 8000000

def resize(tmp, sm_name, scale, res, errs):
    # ffmpeg -i gamerrage.mp4 -filter:v scale=270:-1 -c:a copy gamerrage-sm.mp4
    logger.debug("running ffmpg")
    ff_ret = run(f"ffmpeg -i {tmp} -filter:v scale={scale}:-1 -c:a copy {sm_name}", shell=True, capture_output=True)
    cont = False
    if ff_ret.returncode != 0:
        logger.debug("ret: %s | %s\n%s", ff_ret.returncode, ff_ret.stdout, ff_ret.stderr)
        errs.append(f"{name} | ffmpg @ {scale}: {ff_ret.returncode}")
        cont = True
    elif (stat(sm_name).st_size / MAX_FILE) < 1:
        logger.debug("small enough, moving tiny file to tmp")
        rename(sm_name, tmp)
        res.append(tmp)
        cont = True

    try:
        remove(sm_name)
    except FileNotFoundError:
        pass
    return res, errs, cont

def ytdlp(url, name):
    ret = run(f"/usr/local/bin/yt-dlp {url} -o {name}", shell=True, capture_output=True)
    if ret.returncode != 0:
        logger.debug("ret: %s | %s\n%s", ret.returncode, ret.stdout, ret.stderr)
        return False
    return True


def download(req, res, errs):
    name, url = req.rsplit(" ", 1)
    name = name.replace(" ", "_") + ".mp4"
    tmp = calc_path("./tmp/" + name)
    logger.debug("downloading %s as %s", url, tmp)
    got = ytdlp(url, tmp)
    logger.debug("downloaded: %s", stat(tmp))
    if (stat(tmp).st_size / MAX_FILE) < 1:
        res.append(tmp)
        return res, errs
    logger.debug("too big :( trying 640")
    sm_name = calc_path("./sm/" + name)
    res, errs, cont = resize(tmp, sm_name, "640", res, errs)
    if cont:
        return res, errs
    logger.debug("too big :( trying 270")
    res, errs, cont = resize(tmp, sm_name, "270", res, errs)
    if cont:
        return res, errs
    logger.debug("too big :( trying 128")
    res, errs, cont = resize(tmp, sm_name, "128", res, errs)
    if cont:
        return res, errs
    logger.debug("too big :( still too big, giving up, very sad")
    errs.append(f"{name} | ffmpg unable to scale small enough")
    return res, errs


class InstaDownCog(Cog):
    """Insta Down Cog"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot


    @Cog.listener("on_message")
    async def process_on_message(self, message):
        """process incoming messages"""
        msg = message.content
        chnl = message.channel
        if chnl.id not in (1034220450793934960, 722988880273342485) or "instagram.com/reel" not in msg:
            return

        logger.debug("downloading msg: %s", msg)
        async with chnl.typing():
            reqs = msg.split("\n")
            res = []
            errs = []
            for req in reqs:
                res, errs = download(req, res, errs)

            for fnames in chnk(res):
                logger.debug("videos: %s", fnames)
                fps = [File(calc_path(f)) for f in fnames]
                await chnl.send(files=fps)

            if errs:
                err_msg = "\n".join(errs)
                await chnl.send(err_msg)

