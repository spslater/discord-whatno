"""Stats Bot for Voice and Messages"""

import datetime
import logging
import re
from asyncio import TaskGroup
from collections import namedtuple
from math import floor
from textwrap import fill

import pytz
from aiohttp import ClientSession
from discord import File
from discord.ext.commands import Cog
from discord.ext.tasks import loop
from more_itertools import ichunked
from PIL import Image, ImageDraw, ImageFont
from tinydb.table import Document

from .helpers import CleanHTML, PrettyStringDB, aget_json, calc_path, strim

logger = logging.getLogger(__name__)

Combos = namedtuple("Combos", ["width", "height", "text", "mult"])

CARD_LOOP = [
    datetime.time(3, 15, 0, tzinfo=pytz.timezone('US/Eastern')),
    datetime.time(9, 15, 0, tzinfo=pytz.timezone('US/Eastern')),
    datetime.time(15, 15, 0, tzinfo=pytz.timezone('US/Eastern')),
    datetime.time(21, 15, 0, tzinfo=pytz.timezone('US/Eastern')),
]


def setup(bot):
    """Setup the DoA Cogs"""
    cog_snap = SnapCog(bot)
    bot.add_cog(cog_snap)


class SnapData:
    """Manage data from snap.fan api"""

    CARDS_URL = "https://snap.fan/api/cards/"
    LOCS_URL = "https://snap.fan/api/locations/"

    CARD_COMBO = Combos(615, 615, 27, 1.25)
    LOC_COMBO = Combos(512, 512, 20, 1.35)

    AGENT = {"User-Agent": "Snaplook/1.0 Whatno Discord Bot (Sean Slater)"}

    def __init__(self, snapdir, combo, db):
        self.database = db

        self.snapdir = snapdir
        self.combo = combo

        self.card_tbl = self.database.table("cards")
        self.loc_tbl = self.database.table("locations")

    @staticmethod
    def should_update(old, new):
        """Check if the new info differs enough to be recombined"""
        return (
            old.get("description") != new.get("description")
            or old.get("power") != new.get("power")
            or old.get("cost") != new.get("cost")
            or old.get("displayImageUrl") != new.get("displayImageUrl")
        )

    async def process(self, dnld=False):
        """Get info on the cards and download them"""
        if dnld:
            logger.debug("Downloading the cards and locations")
            async with ClientSession(headers=self.AGENT) as session:
                cards = await self.gather_cards(session)
                locs = await self.gather_locs(session)

                await self.insert(cards, locs, session)

        logger.debug("Combining the card images with their text")
        async with TaskGroup() as t_group:
            for card in self.card_tbl.all():
                comboed = self.img_combo(card, self.CARD_COMBO)
                t_group.create_task(comboed, name=card["key"])

            for loc in self.loc_tbl.all():
                comboed = self.img_combo(loc, self.LOC_COMBO)
                t_group.create_task(comboed, name=loc["key"])

    async def gather_cards(self, session):
        """Make http requests to get json info on the cards"""
        page = await aget_json(session, self.CARDS_URL)
        nxt = None
        res = []
        while nxt := page.get("next"):
            res.extend(page.get("results", []))
            page = await aget_json(session, nxt)

        dic = {}
        for val in res:
            val["description"] = CleanHTML().process(val["description"])
            key = val["key"].lower()
            dic[key] = val
        return dic

    async def gather_locs(self, session):
        """Make http requests to get json info on the locations"""
        page = await aget_json(session, self.LOCS_URL)
        dic = {}
        for loc in page.get("data", []):
            loc["description"] = CleanHTML().process(loc["description"])
            key = loc["key"].lower()
            dic[key] = loc
        return dic

    async def insert(self, cards, locs, session):
        """Insert card and location info into the database"""
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
                    new["localImage"] = await self.getimg(
                        url,
                        "locations",
                        key,
                        session,
                    )
            else:
                new["localImage"] = await self.getimg(url, "locations", key, session)
            self.loc_tbl.upsert(Document(new, doc_id=key))

    async def getimg(self, url, loc, name, session):
        """Download and save the image for a card or location"""
        filename = f"{loc}/{name}.webp"
        location = self.snapdir / filename
        with open(location, "wb") as fp:
            async with session.get(url) as res:
                async for chunk in res.content.iter_chunked(1024):
                    fp.write(chunk)
        return filename

    async def img_combo(self, card, cmbd):
        """Combine the text and image of cards"""
        cnw, cnh = cmbd.width, floor(cmbd.height * cmbd.mult)

        img_path = self.snapdir / card["localImage"]
        crd = Image.open(img_path)

        img = Image.new("RGBA", (cnw, cnh))

        img1 = ImageDraw.Draw(img)
        img1.rectangle([(0, 0), (cnw, cnh)], fill=(0, 0, 0))
        img.paste(crd, (0, 0))

        mono = ImageFont.truetype(str(calc_path("monofur.ttf")), 36)
        txt = fill(card["description"], width=cmbd.text)
        _, _, t_width, _ = img1.textbbox((0, 0), txt, font=mono)
        dims = (((cmbd.width - t_width) / 2), cmbd.height + 10)
        img1.text(dims, txt, font=mono, fill=(255, 255, 255))

        combo_path = self.combo / card["localImage"]
        img.save(combo_path, "webp")


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

        self.database_file = self.snapdir / self.bot.env.path(
            "SNAPLOOKUP_DATABASE",
            "snapdata.db",
        )
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

    @loop(time=CARD_LOOP)
    async def periodic_check(self):
        """periodically get the new cards"""
        await self.bot.wait_until_ready()
        logger.info("updating the card information")
        snapdata = SnapData(self.snapdir, self.combo, self.info)
        await self.bot.blocker(snapdata.process, dnld=True)

    def get_requests(self, matches, message):
        """Pull card / location requests from the message"""
        reqs = []
        for match in matches:
            reqs.extend([strim(m) for m in match[2:-2].split("|")])
        res = []
        for req in reqs:
            doc = self.cards.get(doc_id=req) or self.locs.get(doc_id=req)
            if doc:
                res.append(self.combo / doc["localImage"])
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
        matches = re.findall(r"\{\{.*?\}\}", msg, flags=re.IGNORECASE)
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
