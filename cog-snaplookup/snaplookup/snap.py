"""Stats Bot for Voice and Messages"""
import logging
import re
from json import dump, dumps, load
from os import getenv

from discord import ChannelType, HTTPException, NotFound, File
from discord.ext.commands import Cog, command, group, is_owner
from discord.ext.tasks import loop
from dotenv import load_dotenv

from .helpers import calc_path, strim, generate_chunker
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
        self.info = {"cards":{}, "locations":{}}
        with open(self.database_file, "r") as fp:
            self.info = load(fp)

        # function transformed by the @loop annotation
        # pylint: disable=no-member
        self.periodic_check.start()

    def cog_unload(self):
        # function transformed by the @loop annotation
        # pylint: disable=no-member
        self.periodic_check.cancel()
        self.save_database()

    @loop(hours=24)
    async def periodic_check(self):
        """periodically get the new cards"""
        await self.bot.wait_until_ready()
        logger.info("gathering a")
        self.info = process_cards(self.database_file, dl=True)

    def save_database(self):
        with open("data.db", "w") as fp:
            dump(self.info, fp, indent=4)

    def _lookup(self, name):
        lu = None
        try:
            lu = self.info["cards"][name]
        except KeyError:
            try:
                lu = self.info["locations"][name]
            except KeyError:
                lu = None
        return lu

    @Cog.listener("on_message")
    async def process_on_message(self, message):
        """process incoming messages"""
        msg = message.content
        matches = re.findall("\{\{.*?\}\}", msg, flags=re.IGNORECASE)
        if not matches:
            return

        logger.info("processing: %s|%s,%s,%s,%s|%s", message.created_at, message.guild.id, message.channel.id, message.id, message.author.id, matches)
        chnl = message.channel
        async with chnl.typing():
            reqs = []
            for match in matches:
                tmp = [(m.strip(), strim(m)) for m in match[2:-2].split("|")]
                reqs.extend(tmp)
            errs = []
            res = []
            for og, req in reqs:
                lu = self._lookup(req)
                if lu is None:
                    errs.append(og)
                    continue
                res.append(f"combo/{lu['img']}")

            if not res:
                return

            if errs:
                await chnl.send("unable to find following cards / locations:\n"+", ".join(errs))
            for fnames in chnk(res):
                logger.debug("cards: %s", fnames)
                fps = [File(calc_path(f)) for f in fnames]
                await chnl.send(files=fps)


    # @Cog.listener("on_message_edit")
    # async def process_on_message_edit(self, payload):
    #     """process message on edit"""
    #     # tstp = TimeTravel.timestamp()
