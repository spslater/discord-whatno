"""Stats Bot for Voice and Messages"""
import logging
import re
from asyncio import create_subprocess_shell
from io import StringIO
from os import stat, rename, remove
# from subprocess import run
from uuid import uuid4
from pathlib import Path

from discord import File
from discord.ext.commands import Cog

from .helpers import calc_path, generate_chunker

logger = logging.getLogger(__name__)

chnk = generate_chunker(10)

MAX_FILE = 25000000

async def resize(tmp, sm_name, scale, res, errs):
    # ffmpeg -i gamerrage.mp4 -filter:v scale=270:-1 -c:a copy gamerrage-sm.mp4
    logger.debug("running ffmpg")
    ff_ret = await create_subprocess_shell(f"ffmpeg -i {tmp} -filter:v scale=iw*{scale}:-1 -c:a copy {sm_name}")
    cont = False
    await ff_ret.wait()
    if ff_ret.returncode != 0:
        logger.debug("ret: %s | %s\n%s", ff_ret.returncode)
        errs.append(f"{sm_name} | ffmpg @ {scale}: {ff_ret.returncode}")
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

async def ytdlp(url, name):
    stderr = StringIO()
    stdout = StringIO()
    ret = await create_subprocess_shell(f"/usr/local/bin/yt-dlp '{url}' -o {name}")
    await ret.wait()
    if ret.returncode != 0:
        logger.debug("ret: %s | %s\n%s", ret.returncode)
        return False
    return True


scales = ["4/5", "3/4", "3/5", "1/2", "2/5", "1/4", "1/5"]
async def download(req, res, errs):
    try:
        name, url = req.rsplit(" ", 1)
    except ValueError as e:
        if req.startswith("http"):
            name = str(uuid4())
            url = req
        else:
            logger.debug("only link, no name, prob do a random name in future?")
            errs.append(str(e))
            return res, errs
    name = name.replace(" ", "_") + ".mp4"
    tmp = calc_path("./tmp/" + name)
    logger.debug("downloading %s as %s", url, tmp)
    got = await ytdlp(url, tmp)
    logger.debug("downloaded: %s", stat(tmp))
    if (stat(tmp).st_size / MAX_FILE) < 1:
        sm_name = calc_path("./re/" + name)
        res, errs, cont = resize(tmp, sm_name, "1", res, errs)
        if cont:
            return res, errs
        logger.debug("error re-encoding the file")
    for scale in scales:
        logger.debug("too big :( trying %s", scale)
        sm_name = calc_path("./sm/" + name)
        res, errs, cont = await resize(tmp, sm_name, scale, res, errs)
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

        Path(calc_path("./tmp")).mkdir(parents=True, exist_ok=True)
        Path(calc_path("./sm")).mkdir(parents=True, exist_ok=True)
        Path(calc_path("./re")).mkdir(parents=True, exist_ok=True)

    def _bad_msg(self, msg):
        if "instagram.com/reel" in msg:
            return False
        if "tiktok.com" in msg and ("video" in msg or "/t/" in msg):
            return False
        return True

    @Cog.listener("on_message")
    async def process_on_message(self, message):
        """process incoming messages"""
        msg = message.content
        chnl = message.channel
        gld = message.guild
        if not (chnl.id in (1034220450793934960, 722988880273342485, 1120438914986024981, 1151022713377394698) or gld.id in (0,)) or self._bad_msg(msg):
            return

        logger.debug("downloading msg: %s", msg)
        async with chnl.typing():
            reqs = msg.split("\n")
            res = []
            errs = []
            for req in reqs:
                res, errs = await download(req, res, errs)

            for fnames in chnk(res):
                logger.debug("videos: %s", fnames)
                fps = [File(calc_path(f)) for f in fnames]
                await chnl.send(files=fps)

            if errs:
                err_msg = "\n".join(errs)
                await chnl.send(err_msg)

            for fname in res:
                try:
                    remove(calc_path(fname))
                except FileNotFoundError:
                    pass

