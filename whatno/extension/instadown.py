"""Instagram and TikTok downloader"""
import logging
import re
from asyncio import create_subprocess_shell, subprocess
from os import stat, rename, remove
from shutil import which
from uuid import uuid4
from pathlib import Path

from more_itertools import ichunked

from discord import File
from discord.ext.commands import Cog
from discord.ext import bridge

logger = logging.getLogger(__name__)

MAX_FILE = 25000000

def setup(bot):
    """Setup the Insta Downloader Cogs"""
    cog_insta = InstaDownCog(bot)
    bot.add_cog(cog_insta)

class InstaDownCog(Cog):
    """Insta Down Cog"""
    scales = ["1", "4/5", "3/4", "3/5", "1/2", "2/5", "1/4", "1/5"]

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.dl_folder = bot.storage / "instadown"
        self.dl_folder.mkdir(exist_ok=True)

        self.f_tmp = self.dl_folder / "tmp"
        self.f_tmp.mkdir(exist_ok=True)

        self.f_sm = self.dl_folder / "sm"
        self.f_sm.mkdir(exist_ok=True)

        self.ytdl = which("yt-dlp")
        self.ffmpeg = which("ffmpeg")
        if self.ytdl is None or self.ffmpeg is None:
            raise Exception("Missing external commands")

    def _bad_msg(self, msg):
        if "instagram.com/reel" in msg:
            return False
        if "tiktok.com" in msg and ("video" in msg or "/t/" in msg):
            return False
        return True

    @bridge.bridge_command()
    async def dl(self, ctx):
        """process incoming messages"""
        msg = ctx.message.content
        chnl = ctx.channel
        gld = ctx.guild
        # have this loaded from file and add a reload command
        if not (chnl.id in (1034220450793934960, 722988880273342485, 1120438914986024981) or gld.id in (1090020461682901113,)) or self._bad_msg(msg):
            return

        logger.debug("downloading msg: %s", msg)
        ctx.defer()
        reqs = msg.split("\n")
        res = []
        errs = []
        for req in reqs:
            res, errs = await self.download(req, res, errs)

        for fnames in ichunked(res, 10):
            logger.debug("videos: %s", fnames)
            fps = [File(f) for f in fnames]
            await chnl.send(files=fps)

        if errs:
            err_msg = "\n".join(errs)
            await chnl.send(err_msg)

        for fname in res:
            try:
                remove(fname)
            except FileNotFoundError:
                pass

    async def download(self, req, res, errs):
        try:
            name, url = req.rsplit(" ", 1)
        except ValueError as e:
            if req.startswith("http"):
                name = str(uuid4())
                url = req
            else:
                logger.debug("invalid url: does not begin with http")
                errs.append(str(e))
                return res, errs

        name = name.replace(" ", "_") + ".mp4"
        tmp = self.f_tmp / name
        logger.debug("downloading %s as %s", url, tmp)
        got = await self.ytdlp(url, tmp)
        if not got:
            errs.append(f"{name} | unable to download")
            return res, errs
        logger.debug("downloaded: %s", stat(tmp))

        for scale in self.scales:
            logger.debug("too big :( trying %s", scale)
            sm_name = self.f_sm / name
            res, errs, cont = await self.resize(tmp, sm_name, scale, res, errs)
            if cont:
                return res, errs

        logger.debug("too big :( still too big, giving up, very sad")
        errs.append(f"{name} | ffmpg unable to scale small enough")
        return res, errs


    async def ytdlp(self, url, name):
        yt_proc = await create_subprocess_shell(
            f"{self.ytdl} '{url}' -o {name}",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await yt_proc.communicate()
        returncode = yt_proc.returncode

        if returncode != 0:
            logger.debug("ret: %s | %s\n%s", returncode, stdout, stderr)
            return False
        return True

    async def resize(self, tmp, sm_name, scale, res, errs):
        # ffmpeg -i gamerrage.mp4 -filter:v scale=270:-1 -c:a copy gamerrage-sm.mp4
        logger.debug("running ffmpg")
        ff_proc = await create_subprocess_shell(
            f"{self.ffmpeg} -hide_banner -loglevel error -i {tmp} -filter:v scale=iw*{scale}:-1 -c:a copy {sm_name}",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await ff_proc.communicate()
        returncode = ff_proc.returncode

        cont = False
        if returncode != 0:
            logger.debug("ret: %s | %s\n%s", returncode, stdout, stderr)
            errs.append(f"{sm_name} | ffmpg @ {scale}: {returncode}")
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

if __name__ == "__main__":
    from sys import argv
    from asyncio import run
    storage = Path(argv[1]).resolve()
    request = argv[2]

    class DummyBot:
        def __init__(self):
            self.storage = storage

    cog = InstaDownCog(DummyBot())
    res, err = run(cog.download(request, [], []))
    print(res)
    print(err)
