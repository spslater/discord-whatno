import logging
import re
from asyncio import create_subprocess_shell, sleep, subprocess
from collections import namedtuple
from datetime import datetime, time, timedelta
from json import dump
from json import load as json_load
from pathlib import Path
from string import Formatter
from textwrap import fill

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from discord import Colour, Embed, Forbidden, HTTPException, NotFound, File
from discord.ext.bridge import bridge_group
from discord.ext.commands import Cog, is_owner
from discord.ext.tasks import loop
from PIL import Image, ImageDraw, ImageFont
from yaml import Loader
from yaml import load as yml_load

from .helpers import TimeTravel, calc_path

logger = logging.getLogger(__name__)

off_hour, off_mins = TimeTravel.timeoffset()
UPDATE_FREQUENCY = 1
EVERY_X = []
for h in range(0,24):
    h_off = h + off_hour
    for m in range(0,60,UPDATE_FREQUENCY):
        m_off = m + off_mins
        EVERY_X.append(time(h_off%24,m_off%60))

def setup(bot):
    """Setup the DoA Cogs"""
    cog_reread = RereadCog(bot)
    bot.add_cog(cog_reread)

class Formating(Formatter):
    def __init__(self, unformatted):
        super().__init__()
        self.unformatted = unformatted
        self.fields = [f[1] for f in self.parse(unformatted) if f[1]]

    def format(self, *args, **kwargs):
        return super().format(self.unformatted, *args, **kwargs)

class Schedule:
    """Manage schedule database"""

    def __init__(self, schedule):
        self.schedule_filename = schedule
        if not self.schedule_filename:
            raise ValueError("No schedule for when to publish rereads provided")
        self.schedule = None

    def __getitem__(self, key):
        if self.schedule is None:
            self.load()
        return self.schedule[key]

    def __setitem__(self, key, value):
        if self.schedule is None:
            self.load()
        self.schedule[key] = value

    def load(self):
        """Load schedule from file"""
        with open(self.schedule_filename, mode="r", encoding="utf-8") as fp:
            self.schedule = json_load(fp)

    def save(self):
        """Save schedule to file"""
        if self.schedule:
            with open(self.schedule_filename, mode="w+", encoding="utf-8") as fp:
                dump(self.schedule, fp, sort_keys=True, indent="\t")

    def __enter__(self):
        self.load()
        return self.schedule

    def __exit__(self, exc_type, exc_value, traceback):
        self.save()
        return exc_type is None


class RereadInfo:
    """Manage and get Reread information"""

    def __init__(self, config, files, storage):
        self.title = config.get("title")
        self.schedule_file = storage / config.get("schedule", "schedule.db")
        self.image_pattern = Formating(config.get("pattern", "{title}"))
        self.url_pattern = Formating(config.get("url", "{url}"))
        self.files = files / config.get("files")
        self.publish = self._get_times(config.get("publish", "12:00"))
        self.frequency = config.get("frequency", 1)
        self.rate = config.get("rate", False)
        channels = config.get("channels", [])
        if not isinstance(channels, list):
            channels = [channels]
        self.channels = [int(c) for c in channels]

    @staticmethod
    def _get_times(times):
        if isinstance(times, str):
            times = [times]
        return [TimeTravel.parse_time(t) for t in times]

    def _schedule(self):
        return Schedule(self.schedule_file)

    def format_data(self, formatter, data):
        kwargs = {}
        logger.debug("format data: %s | %s", formatter.unformatted, formatter.fields)
        for field in formatter.fields:
            if (val := data.get(field)) is not None:
                logger.debug("adding field to format: %s | %s | %s", field, val, data)
                kwargs[field] = val
        return formatter.format(**kwargs)

    def increment(self):
        with self._schedule() as schedule:
            schedule["next"] += self.frequency

    def todays_reread(self, date=None):
        """Get information for reread reread"""
        with self._schedule() as schedule:
            idx = schedule.get("next", -1)
            if date is not None:
                start = TimeTravel.strptime(schedule.get("start"))
                nxt = TimeTravel.strptime(date)
                idx = (nxt - start).days * self.frequency

            filedicts = schedule["rereads"][idx:idx+self.frequency]
        logger.debug("Getting following files: %s", filedicts)

        if not filedicts:
            return []

        entries = []
        logger.debug("%s rereads for current day", len(filedicts))
        for reread in filedicts:
            title = reread.get("title")
            url = self.format_data(self.url_pattern, reread)
            image = self.format_data(self.image_pattern, reread)
            logger.debug("url: %s | image: %s", url, image)
            image_url = image
            if not image.startswith("https://"):
                image_url = f"attachment://{image}"

            data = {
                "title": title,
                "url": url,
                "image": image,
                "image_url": image_url,
            }

            if alt := reread.get("alt"):
                data["alt"] = alt
                data["alt_sub"] = reread.get(alt_sub, "")

            if release := reread.get("release"):
                data["release"] = release

            entries.append(data)
        logger.debug(entries)
        return entries


class RereadCog(Cog, name="General Reread"):
    """Actual Genreal Reread Cog"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

        self.f_reread = self.bot.storage / "reread"

        with self.bot.env.prefixed("REREAD_"):
            self.configfile = self.f_reread / self.bot.env.path("CONFIG")
            self.files = self.f_reread / self.bot.env.path("FILES")
            embeds = self.f_reread / self.bot.env.path("EMBEDS")

        self._load_configs()
        self.publish_rereads.start()
        logger.info("Completed General Reread setup! :D")

    def cog_unload(self):
        self.publish_rereads.cancel()

    @staticmethod
    def build_embed(entry):
        """Basic way to generate the embeds"""
        title = entry.get("title")
        url = entry.get("url")
        image_url = entry.get("image_url")

        embed = Embed(title=title, url=url, colour=Colour.random())
        if alt := entry.get("alt"):
            alt_sub = entry.get("alt_sub", "")
            embed.add_field(name=alt, value=alt_sub)
        embed.set_image(url=image_url)
        if release := entry.get("release"):
            embed.set_footer(text=release)

        return embed

    def _load_configs(self):
        with open(self.configfile, mode="r", encoding="utf-8") as yml:
            configs = yml_load(yml.read(), Loader=Loader)

        self.rereads = []
        for conf in configs.values():
            if conf["active"]:
                self.rereads.append(RereadInfo(config=conf, files=self.files, storage=self.f_reread))
        logger.debug("rereads loaded: %s", self.rereads)


    @loop(time=EVERY_X)
    async def publish_rereads(self):
        """Schedule the rereads to auto publish"""
        await self.bot.wait_until_ready()
        await self.bot.blocker(self.send_reread)
        logger.info("Publishing next batch of rereads at %s", self.publish_rereads.next_iteration)

    async def send_reread(self, date=None, time=None, channel_ids=None, increment=True):
        """Send the rereads for todays given to primary channel"""
        if not time:
            now = datetime.now()
            tstr = TimeTravel.nearest(now.hour, now.minute, 1, UPDATE_FREQUENCY)
            time = TimeTravel.parse_time(tstr)
            logger.debug("no time given, closest calculated time: %s", time)
        elif isinstance(time, str):
            time = TimeTravel.parse_time(time)
            logger.debug("time was a string, converted to: %s", time)
        logger.info("Sending rereads for %s %s", (date or TimeTravel.datestr()), time)

        logger.debug("checking against all rereads: %s", self.rereads)
        for reread in self.rereads:
            logger.debug("checking %s if it's time to publish: %s", reread.title, reread.publish)
            if time not in reread.publish:
                logger.debug("skipping because time does not match: %s", time)
                continue

            logger.debug("getting channels to sent rereads to")
            sendtos = {}
            for cid in channel_ids or reread.channels:
                channel = self.bot.get_channel(cid)
                guild = channel.guild.id
                if guild not in sendtos:
                    sendtos[guild] = []
                sendtos[guild].append(channel)

            rereads = [(e["image"], self.build_embed(e)) for e in reread.todays_reread(date)]

            logger.debug("sending %s rereads out", len(rereads))
            for image_name, embeds in rereads:
                logger.debug(embeds.to_dict())
                file = None
                if not image_name.startswith("https://"):
                    logger.debug("prepping file to send out: %s", image_name)
                    location = reread.files / image_name
                    file = File(location, filename=image_name)
                for gid, channels in sendtos.items():
                    for channel in channels:
                        logger.debug("sending rereads: %s | %s", embeds, file)
                        msg = await channel.send(file=file, embed=embeds)
                        if reread.rate:
                            await msg.add_reaction('1️⃣')
                            await msg.add_reaction('2️⃣')
                            await msg.add_reaction('3️⃣')
                            await msg.add_reaction('4️⃣')
                            await msg.add_reaction('5️⃣')
                    await sleep(1)

            if increment:
                reread.increment()
        logger.info("Publish complete! :)")

    async def refresh_embed(self, msg, embed) -> bool:
        """Perform embed refresh"""
        if embed:
            embed.colour = Colour.random()
            try:
                await msg.edit(embed=embed)
                return True
            except (HTTPException, Forbidden) as e:
                logger.warning('Unable to refresh message "%s": %s', msg.id, e)
        return False


    @is_owner()
    @bridge_group()
    async def reread(self, ctx):
        """reread sub commands"""
        if ctx.invoked_subcommand:
            return
        msg = (
            "```\n"
            "refresh(*mids): refresh multiple messages in "
            'the given channel by "editing" them\n'
            "publish(date, time): publish the specified day and time rereads "
            "if no day is given current day or no time is given use the closest"
            "```"
        )
        await ctx.send(msg)


    @is_owner()
    @reread.command()
    async def refresh(self, ctx, *mids):
        """Refresh the reread to get the embed working"""
        if not (ctx.message.reference or mids):
            logger.debug("refreshing data: no data sent")
            await ctx.send("Need to reply to reread you want refreshed or send message id")
            return
        logger.info("refreshing data: %s | %s", ctx.message.reference, mids)

        msgs = []
        if ref := ctx.message.reference:
            logger.debug("refresh message ids: %s", ref.message_id)
            try:
                msg = await ctx.channel.fetch_message(ref.message_id)
            except (Forbidden, NotFound):
                pass
            else:
                msgs.append(msg)
        else:
            logger.debug("refresh message ids: %s", mids)
            for mid in mids:
                try:
                    msg = await self.bot.get_message(int(mid))
                except (Forbidden, NotFound):
                    continue
                if msg is not None:
                    msgs.append(msg)
        for msg in msgs:
            if embed := msg.embeds[0]:
                logger.debug("Refreshing Embed: %s", embed.to_dict())
                await self.refresh_embed(msg, embed)
        await ctx.message.add_reaction("\N{OK HAND SIGN}")

    @is_owner()
    @reread.command()
    async def publish(self, ctx, date=None, time=None, increment=None):
        """Publish the days rereads, date (YYYY-MM-DD)
        is provided will publish rereads for those days"""
        if not date:
            date = TimeTravel.datestr()
        if not time:
            now = datetime.now()
            time = TimeTravel.nearest(now.hour, now.minute, 1, UPDATE_FREQUENCY)
        time = TimeTravel.parse_time(time)
        logger.info("manually publishing rereads for date and time: %s %s", date, time)
        await ctx.send("\N{OK HAND SIGN} Sendings Rereads")
        await self.bot.blocker(
            self.send_reread,
            date=date,
            time=time,
            increment=(increment is not None),
        )

    @is_owner()
    @reread.command()
    async def reload(self, ctx):
        """Reload configs"""
        self._load_configs()
        await ctx.message.add_reaction("\N{OK HAND SIGN}")
