"""Stats Bot for Voice and Messages"""
import logging
import re
from json import dump, dumps, load
from os import getenv

from discord import ChannelType, HTTPException, NotFound, File
from discord.ext.commands import Cog, command, group, is_owner
from discord.ext.tasks import loop
from dotenv import load_dotenv
from tinydb.table import Document

from .helpers import calc_path, strim, generate_chunker, PrettyStringDB
from .snaplookup import process_cards

logger = logging.getLogger(__name__)

chnk = generate_chunker(10)


class SnapCog(Cog):
    """Voice Snap Cog"""

    def __init__(self, bot, envfile):
        super().__init__()
        self.bot = bot

        envpath = calc_path(envfile)
        load_dotenv(envpath)

        self.database_file = calc_path("data.db")
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
        process_cards(self.info, dl=True)

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
            reqs = []
            for match in matches:
                reqs.extend([strim(m) for m in match[2:-2].split("|")])
            res = []
            for req in reqs:
                doc = self.cards.get(doc_id=req) or self.locs.get(doc_id=req)
                if doc:
                    res.append(f"combo/{doc['localImage']}")
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

            for fnames in chnk(res):
                logger.debug("cards: %s", fnames)
                fps = [File(calc_path(f)) for f in fnames]
                await chnl.send(files=fps)
