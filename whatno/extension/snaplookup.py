"""Stats Bot for Voice and Messages"""
import logging
import re
from asyncio import TaskGroup
from json import dump, dumps, load
from math import floor
from textwrap import fill

from aiohttp import ClientSession
from discord import ChannelType, HTTPException, NotFound, File
from discord.ext.commands import Cog, command, group, is_owner
from discord.ext.tasks import loop
from more_itertools import ichunked
from PIL import Image, ImageDraw, ImageFont
from tinydb.table import Document

if __name__ != "__main__":
    from .helpers import calc_path, strim, PrettyStringDB, aget_json, CleanHTML

logger = logging.getLogger(__name__)


def setup(bot):
    """Setup the DoA Cogs"""
    cog_snap = SnapCog(bot)
    bot.add_cog(cog_snap)


class SnapData:
    CARDS_URL = "https://snap.fan/api/cards/"
    LOCS_URL = "https://snap.fan/api/locations/"

    AGENT = { "User-Agent": "Snaplook/1.0 Whatno Discord Bot (Sean Slater)" }

    def __init__(self, snapdir, combo, db):
        self.database = db

        self.snapdir = snapdir
        self.combo = combo

        self.card_tbl = self.database.table("cards")
        self.loc_tbl = self.database.table("locations")


    @staticmethod
    def should_update(old, new):
        return (
            old.get("description") != new.get("description") or
            old.get("power") != new.get("power") or
            old.get("cost") != new.get("cost") or
            old.get("displayImageUrl") != new.get("displayImageUrl")
        )

    async def process(self, dl=False):
        if dl:
            logger.debug("Downloading the cards and locations")
            async with ClientSession(headers=self.AGENT) as session:
                cards = await self.gather_cards(session)
                locs = await self.gather_locs(session)

                await self.insert(cards, locs, session)

        cw, ch, ct = 615, 615, 27
        lw, lh, lt = 512, 512, 20

        logger.debug("Combining the card images with their text")
        async with TaskGroup() as tg:
            for card in self.card_tbl.all():
                tg.create_task(self.img_combo(card, cw, ch, ct, 1.25), name=card["key"])

            for loc in self.loc_tbl.all():
                tg.create_task(self.img_combo(loc, lw, lh, lt, 1.35), name=loc["key"])


    async def gather_cards(self, session):
        pg = await aget_json(session, self.CARDS_URL)
        nxt = None
        res = []
        while nxt := pg.get("next"):
            res.extend(pg.get("results", []))
            pg = await aget_json(session, nxt)

        dic = {}
        for c in res:
            c["description"] = CleanHTML().process(c["description"])
            key = c["key"].lower()
            dic[key] = c
        return dic


    async def gather_locs(self, session):
        pg = await aget_json(session, self.LOCS_URL)
        dic = {}
        for l in pg.get("data", []):
            l["description"] = CleanHTML().process(l["description"])
            key = l["key"].lower()
            dic[key] = l
        return dic


    async def insert(self, cards, locs, session):
        for key, new in cards.items():
            url = new["displayImageUrl"]
            if old := self.card_tbl.get(doc_id=key):
                if self.should_update(old, new):
                    new["localImage"] = await self.getimg(url, "cards", key, session)
            else:
                new["localImage"] = await self.getimg(url, "cards", key, session)
            self.card_tbl.upsert(Document(new, doc_id=key))

        for key, new in locs.items():
            url = new["displayImageUrl"]
            if old := self.loc_tbl.get(doc_id=key):
                if self.should_update(old, new):
                    new["localImage"] = await self.getimg(url, "locations", key, session)
            else:
                new["localImage"] = await self.getimg(url, "locations", key, session)
            self.loc_tbl.upsert(Document(new, doc_id=key))


    async def getimg(self, url, loc, name, session):
        filename = f"{loc}/{name}.webp"
        location = self.snapdir / filename
        with open(location, "wb") as fp:
            async with session.get(url) as res:
                async for chunk in res.content.iter_chunked(1024):
                    fp.write(chunk)
        return filename


    async def img_combo(self, card, cw, ch, tt, mult):
        cnw, cnh = cw, floor(ch * mult)

        imgPath = self.snapdir / card["localImage"]
        crd = Image.open(imgPath)

        img = Image.new("RGBA", (cnw, cnh))

        img1 = ImageDraw.Draw(img)
        img1.rectangle([(0, 0), (cnw, cnh)], fill=(0, 0, 0))
        img.paste(crd, (0, 0))

        mf = ImageFont.truetype(str(calc_path("monofur.ttf")), 36)
        txt = fill(card["description"], width=tt)
        _, _, tw, _ = img1.textbbox((0, 0), txt, font=mf)
        img1.text((((cw - tw) / 2), ch + 10), txt, font=mf, fill=(255, 255, 255))

        comboPath = self.combo / card['localImage']
        img.save(comboPath, "webp")



class SnapCog(Cog):
    """Voice Snap Cog"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

        self.snapdir = self.bot.storage / "snaplookup"

        self.cards = self.snapdir / "cards"
        self.locs = self.snapdir / "locations"
        self.combo = self.snapdir / "combo"

        self.cards.mkdir(exist_ok=True)
        self.locs.mkdir(exist_ok=True)
        self.combo.mkdir(exist_ok=True)
        (self.combo / "cards").mkdir(exist_ok=True)
        (self.combo / "locations").mkdir(exist_ok=True)

        self.database_file = self.snapdir / self.bot.env.path("SNAPLOOKUP_DATABASE", "snapdata.db")
        self.info = PrettyStringDB(self.database_file)
        self.cards = self.info.table("cards")
        self.locs = self.info.table("locations")
        self.requests = self.info.table("requests")

        # function transformed by the @loop annotation
        # pylint: disable=no-member
        self.periodic_check.start()

    def cog_unload(self):
        # function transformed by the @loop annotation
        # pylint: disable=no-member
        self.periodic_check.cancel()

    @loop(hours=24)
    async def periodic_check(self):
        """periodically get the new cards"""
        await self.bot.wait_until_ready()
        logger.info("updating the card information")
        await SnapData(self.snapdir, self.combo, self.info).process(dl=True)

    def get_requests(self, matches, message):
        reqs = []
        for match in matches:
            reqs.extend([strim(m) for m in match[2:-2].split("|")])
        res = []
        for req in reqs:
            doc = self.cards.get(doc_id=req) or self.locs.get(doc_id=req)
            if doc:
                res.append(self.combo / doc['localImage'])
                self.requests.upsert(
                    Document(
                        {
                            "guild": message.guild.id,
                            "channel": message.channel.id,
                            "message": message.id,
                            "author": message.author.id,
                            "card": doc["name"],
                        },
                        doc_id=message.created_at.timestamp(),
                    )
                )
        return res

    @Cog.listener("on_message")
    async def process_on_message(self, message):
        """process incoming messages"""
        msg = message.content
        matches = re.findall("\{\{.*?\}\}", msg, flags=re.IGNORECASE)
        if not matches:
            return

        logger.info(
            "processing: %s|%s,%s,%s,%s|%s",
            message.created_at,
            message.guild.id,
            message.channel.id,
            message.id,
            message.author.id,
            matches,
        )
        chnl = message.channel
        async with chnl.typing():
            res = self.get_requests(matches, message)
            for fnames in ichunked(res, 10):
                logger.debug("cards: %s", fnames)
                fps = [File(f) for f in fnames]
                await chnl.send(files=fps)


if __name__ == "__main__":
    from asyncio import run
    from datetime import datetime
    from os import environ
    from pathlib import Path
    from sys import argv

    from helpers import calc_path, strim, PrettyStringDB, aget_json, CleanHTML

    storage = Path(argv[1]).resolve()
    matches = re.findall("\{\{.*?\}\}", argv[2], flags=re.IGNORECASE)
    if not matches:
        print("no matches")
        exit(1)

    class Guild:
        def __init__(self):
            self.id = "gid"
    class Channel:
        def __init__(self):
            self.id = "cid"
    class Author:
        def __init__(self):
            self.id = "aid"
    class DummyMessage:
        def __init__(self):
            self.guild = Guild()
            self.channel = Channel()
            self.id = "mid"
            self.author = Author()
            self.created_at = datetime.now()

    class DummyEnv:
        def __init__(self):
            pass

        @staticmethod
        def path(name, default):
            return Path(environ.get("DISCORD_SNAPLOOKUP_" + name, default))

    class DummyBot:
        def __init__(self):
            self.storage = storage
            self.env = DummyEnv()

    cog = SnapCog(DummyBot())
    res = cog.get_requests(matches, DummyMessage())
    print(res)

    # snapdir = storage / "snaplookup"
    # combo = snapdir / "combo"
    # info = DummyEnv.path("DISCORD_SNAPDB", "data.db")
    # database = PrettyStringDB(info)
    # run(SnapData(snapdir, combo, database).process(dl=True))
