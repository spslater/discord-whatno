"""Instagram and TikTok downloader"""

import logging
from asyncio import create_subprocess_shell, subprocess
from os import remove, rename, stat
from shutil import which
from uuid import uuid4

from discord import File
from discord.ext.bridge import bridge_command
from discord.ext.commands import Cog
from more_itertools import ichunked

logger = logging.getLogger(__name__)

MAX_FILE = 25000000


def setup(bot):
    """Setup the Insta Downloader Cogs"""
    cog_insta = InstaDownCog(bot)
    bot.add_cog(cog_insta)


class ExternalCommands(Exception):
    """Missing shell commands"""


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
        if self.ytdl is None:
            raise ExternalCommands("Missing yt-dlp")

        self.ffmpeg = which("ffmpeg")
        if self.ffmpeg is None:
            raise ExternalCommands("Missing ffmpeg")

    @staticmethod
    def _bad_msg(msg):
        if "instagram.com/reel" in msg:
            return False
        if "tiktok.com" in msg and ("video" in msg or "/t/" in msg):
            return False
        if "youtube.com/shorts/" in msg:
            return False
        return True

    @bridge_command()
    # function name is used as command name
    # pylint: disable=invalid-name
    async def dl(self, ctx):
        """process incoming messages"""
        msg = ctx.message.content
        chnl = ctx.channel
        gld = ctx.guild
        if self._bad_msg(msg):
            return

        logger.debug("downloading msg: %s", msg)
        await ctx.defer()
        reqs = msg.split("\n")
        res = []
        errs = []
        for req in reqs:
            try:
                res, errs = await self.bot.blocker(self.download, ctx, req, res, errs)
            except Exception as e:
                logger.debug("Unknown Awaitable: %s", e)
                raise e

        for fnames in ichunked(res, 10):
            fps = [File(f) for f in fnames]
            logger.debug("videos: %s", fps)
            await chnl.send(files=fps)

        if errs:
            err_msg = "\n".join(errs)
            await chnl.send(err_msg)

        for fname in res:
            try:
                remove(fname)
            except FileNotFoundError:
                pass

    async def download(self, ctx, req, res, errs):
        """Dowload the videos requested in the string"""
        try:
            name, url = req.rsplit(" ", 1)
            name = str(uuid4())[0:8] + " " + name
        except ValueError as e:
            if req.startswith("http"):
                name = str(uuid4())
                url = req
            else:
                logger.debug("invalid url: does not begin with http")
                errs.append(str(e))
                return res, errs
        name = name.replace("%dl ", "", 1)

        msg = await ctx.send("downloading " + name)
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
            await msg.edit("scaling the image: " + scale)
            sm_name = self.f_sm / name
            res, errs, cont = await self.resize(tmp, sm_name, scale, res, errs)
            if cont:
                await msg.edit(
                    "scaling worked! will upload shortly (deleting message soon)",
                    delete_after=30,
                )
                return res, errs

        logger.debug("too big :( still too big, giving up, very sad")
        errs.append(f"{name} | ffmpg unable to scale small enough")
        await msg.edit("unable to scale video to small enough, not able to upload")
        return res, errs

    async def ytdlp(self, url, name):
        """Run youtube-dl and return if successful"""
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

    # TODO: combine res and errs into a NamedTuple?
    # pylint: disable=too-many-arguments
    async def resize(self, tmp, sm_name, scale, res, errs):
        """
        Process the video with ffmpg to try and get
        it within the filesize upload limit
        """
        # ffmpeg -i gamerrage.mp4 -filter:v scale=270:-1 -c:a copy gamerrage-sm.mp4
        logger.debug("running ffmpg")
        ff_proc = await create_subprocess_shell(
            (
                f"{self.ffmpeg} -hide_banner -loglevel error -i {tmp} "
                f"-filter:v scale=iw*{scale}:-1 -c:a copy {sm_name}"
            ),
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
