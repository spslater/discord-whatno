"""DoA Comic Reread Bot

Discord bot for publishing a weeks worth of DoA
comics every day as part of a community reread.

:class DoaReread: Discord Bot that publishes a weeks
    of DoA comics every day
"""
import logging
import re
from datetime import datetime, time, timedelta
from json import dump, load
from os import getenv
from pathlib import Path
from sqlite3 import Row
from time import sleep
from typing import Union

from discord import Colour, Embed, Emoji, Forbidden, HTTPException, NotFound

# from discord.commands import slash_command
from discord.ext.commands import Cog, command
from discord.ext.tasks import loop
from dotenv import load_dotenv

from .comic import ComicDB

# from .helpers import TimeTravel, calc_path, allow_slash
from .helpers import TimeTravel, calc_path

# ALLOW_SLASH = allow_slash()

logger = logging.getLogger(__name__)

off_hour, off_mins = TimeTravel.timeoffset()
CP_HOUR = 12 + off_hour
CP_MINS = 0 + off_mins
PUBLISH_TIME = time(CP_HOUR, CP_MINS)


class Schedule:
    """Manage schedule database"""

    def __init__(self, schedule):
        self.schedule_filename: Path = calc_path(schedule)
        if not self.schedule_filename:
            raise ValueError("No schedule for when to publish comics provided")
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
        with open(self.schedule_filename, "r") as fp:
            self.schedule = load(fp)

    def save(self):
        """Save schedule to file"""
        if self.schedule:
            with open(self.schedule_filename, "w+") as fp:
                dump(self.schedule, fp, sort_keys=True, indent="\t")


class ComicInfo:
    """Manage and get Comic information"""

    def __init__(self, database, schedule):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.connection: ComicDB = ComicDB(database)
        self.database = None
        self.schedule: Schedule = Schedule(schedule)

    def _get_tags(self, date_string: str) -> list[str]:
        """Comma seperated tags from a comic"""
        self.database.execute(
            "SELECT tag FROM Tag WHERE comicId = ?",
            (date_string,),
        )
        rows = self.database.fetchall()
        return [r["tag"] for r in rows]

    def released_on(self, dates: Union[str, list[str]]) -> list[Row]:
        """Get database rows for comics released on given dates"""
        if isinstance(dates, str):
            dates = [dates]
        self.database.execute(
            f"""SELECT
                Comic.release as release,
                Comic.title as title,
                Comic.image as image,
                Comic.url as url,
                Alt.alt as alt
            FROM Comic
            JOIN Alt ON Comic.release = Alt.comicId
            WHERE release IN {dates}"""
        )
        results = self.database.fetchall()
        return results

    def todays_reread(self, date=None):
        """Get information for comic reread"""
        self.database = self.connection.open()
        date_string = date or TimeTravel.datestr()
        self.schedule.load()
        days = tuple(self.schedule["days"][date_string])
        self._logger.debug("Getting comics on following days: %s", days)

        entries = []
        comics = self.released_on(days)
        self._logger.debug("%s comics from current week", len(comics))
        for comic in comics:
            release = comic["release"]
            image = comic["image"].split("_", maxsplit=3)[3]
            tags = [
                f"[{tag}](https://www.dumbingofage.com/tag/{re.sub(' ', '-', tag)}/)"
                for tag in self._get_tags(release)
            ]

            entries.append(
                {
                    "title": comic["title"],
                    "url": comic["url"],
                    "alt": f"||{comic['alt']}||",
                    "tags": ", ".join(tags),
                    "image": f"https://www.dumbingofage.com/comics/{image}",
                    "release": release,
                }
            )

        self.database = self.connection.close()
        return entries

    def update_schedule(self):
        """Update the schedule every week"""
        self._logger.info("Checking schedule to see if it needs updating")
        old_week = self.schedule["next_week"]
        now = TimeTravel.datestr()
        while old_week <= now:
            new_week = datetime.strptime(old_week, "%Y-%m-%d") + timedelta(days=7)
            new_week_str = datetime.strftime(new_week, "%Y-%m-%d")
            self.schedule["next_week"] = new_week_str

            last_day = sorted(self.schedule["days"].keys())[-1]
            next_day = datetime.strptime(last_day, "%Y-%m-%d") + timedelta(days=1)
            next_day_str = datetime.strftime(next_day, "%Y-%m-%d")

            self.schedule["days"][next_day_str] = TimeTravel.week_dates(new_week_str)

            old_week = self.schedule["next_week"]

        self.schedule.save()


class ComicEmbeds:
    """Embed information for when refreshing comics"""

    def __init__(self, embeds):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.filename: Path = calc_path(embeds)
        if not self.filename:
            raise ValueError("No embeds file for previously publish comics provided")
        self.data = None

    def __getitem__(self, key):
        if self.data is None:
            self.load()
        return self.data[str(key)]

    def __setitem__(self, key, value):
        if self.data is None:
            self.load()
        self.data[str(key)] = value

    def __delitem__(self, key):
        if self.data is None:
            self.load()
        del self.data[str(key)]

    def __contains__(self, key):
        if self.data is None:
            self.load()
        return str(key) in self.data

    def get(self, key, default=None):
        """Get value or default from data"""
        return self.data.get(str(key), default=default)

    def load(self):
        """Load data from file"""
        with open(self.filename, "r") as fp:
            self.data = load(fp)

    def save(self):
        """Save data to file"""
        if self.data:
            with open(self.filename, "w+") as fp:
                dump(self.data, fp, sort_keys=True, indent="\t")


class DoaRereadCog(Cog, name="DoA Reread"):
    """Actual DoA Reread Cog"""

    # pylint: disable=too-many-arguments
    def __init__(self, bot, envfile):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.bot = bot

        envpath = calc_path(envfile)
        load_dotenv(envpath)

        self.guild = None
        self.channel = None

        self.comics = ComicInfo(getenv("DOA_DATABASE"), getenv("DOA_SCHEDULE"))
        self._logger.info(
            "embed file: %s -> %s",
            getenv("DOA_EMBEDS"),
            calc_path(getenv("DOA_EMBEDS")),
        )
        self.embeds = ComicEmbeds(getenv("DOA_EMBEDS"))
        # function transformed by the @loop annotation
        # pylint: disable=no-member
        self.schedule_comics.start()
        self._logger.info("Completed DoA Reread setup! :D")

    def cog_unload(self):
        # function transformed by the @loop annotation
        # pylint: disable=no-member
        self.schedule_comics.cancel()

    @staticmethod
    def _parse_list(original, cast=str):
        return [cast(g.strip()) for g in original.split(",") if g.strip()]

    async def _setup_connection(self):
        given_channels = []
        for given_channel in self._parse_list(getenv("COMIC_CHANNELS")):
            channel_id = channel_name = None
            try:
                channel_id = int(given_channel)
            except (TypeError, ValueError):
                channel_name = given_channel

            if channel_id is None:
                self._logger.debug("Getting channel.")
                channels = []
                try:
                    self._logger.debug("Trying to get channel from specific guild.")
                    channels = self.guild.fetch_channels()
                except RuntimeError:
                    self._logger.debug(
                        (
                            "Error getting channels from guild, "
                            "trying to get from all availible channels."
                        )
                    )
                    channels = self.get_all_channels()

                for channel in channels:
                    if channel.name == channel_name:
                        channel_id = int(channel.id)
                        break
                if channel_id is None:
                    raise RuntimeError("Provided channel is not an available channels")
            given_channels.append(channel_id)
        self.channel = given_channels

    @staticmethod
    def build_comic_embed(entry: dict[str, str]) -> Embed:
        """Basic way to generate the embeds"""
        title = entry.get("title")
        url = entry.get("url")
        alt = entry.get("alt")
        tag_text = entry.get("tags")
        img_url = entry.get("image")
        release = entry.get("release")

        embed = Embed(title=title, url=url, colour=Colour.random())
        embed.add_field(name=alt, value=tag_text)
        embed.set_image(url=img_url)
        embed.set_footer(text=release)

        return embed

    @loop(time=PUBLISH_TIME)
    async def schedule_comics(self):
        """Schedule the comics to auto publish"""
        await self.bot.wait_until_ready()
        await self.send_comic()
        self._logger.info(
            "Publishing next batch of comics at %s",
            # function transformed by the @loop annotation
            # pylint: disable=no-member
            self.schedule_comics.next_iteration,
        )

    async def send_comic(self, date=None, channel_id=None):
        """Send the comics for todays given to primary channel"""
        self._logger.info(
            "Sending comics for today. (%s)",
            (date or TimeTravel.datestr()),
        )
        if channel_id is None:
            if self.channel is None:
                await self._setup_connection()
            channels = self.channel
        elif not isinstance(channel_id, list):
            channels = [int(channel_id)]
        else:
            channels = channel_id
        comics = [
            (e["release"], self.build_comic_embed(e))
            for e in self.comics.todays_reread(date)
        ]
        self.embeds.load()
        for cid in channels:
            channel = self.bot.get_channel(cid)
            embed_ids = []
            for release, comic in comics:
                self._logger.debug(comic.to_dict())
                msg = await channel.send(embed=comic)
                embed_ids.append((release, msg.id))
                sleep(1)
            gid = str(channel.guild.id)
            for comic_date, mid in embed_ids:
                if gid not in self.embeds:
                    self.embeds[gid] = {}
                self.embeds[gid][comic_date] = mid
        self.embeds.save()
        self.comics.update_schedule()
        self._logger.info("Publish complete! :)")

    async def refresh_embed(self, msg, embed) -> bool:
        """Perform embed refresh"""
        if embed:
            embed.colour = Colour.random()
            try:
                await msg.edit(embed=embed)
                return True
            except (HTTPException, Forbidden) as e:
                self._logger.warning(
                    'Unable to refresh message "%s": %s',
                    msg.id,
                    e,
                )
        return False

    @command()
    async def refresh(self, ctx, *date):
        """Refresh the comic to get the embed working"""
        self._logger.info("dates: %s", date)
        if not (ctx.message.reference or date):
            await ctx.send(
                (
                    "Need to reply to comic you want refreshed or "
                    "send date it was released in format `YYYY-MM-DD`"
                )
            )
            return
        ref = ctx.message.reference
        message_ids = (
            [ref.message_id]
            if ref
            else [self.embeds.get(ctx.guild.id, {}).get(d) for d in date]
        )
        self._logger.info("mids: %s", message_ids)
        msg = None
        for mid in message_ids:
            try:
                msg = await ctx.channel.fetch_message(mid)
            except (Forbidden, NotFound):
                pass
            else:
                embed = msg.embeds[0] if msg else None
                if embed:
                    self._logger.info("Refreshing Embed: %s", embed.to_dict())
                    await self.refresh_embed(msg, embed)
        #await ctx.message.add_reaction("\N{OK HAND SIGN}")
        try:
            await ctx.message.add_reaction("<:wave_Joyce:780682895907618907>")
        except:
            await ctx.message.add_reaction("\N{OK HAND SIGN}")

    @command(name="publish")
    async def force_publish(self, ctx, date=None):
        """Publish the days comics, date (YYYY-MM-DD)
        is provided will publish comics for those days"""
        if not date:
            date = TimeTravel.datestr()
        msg = await ctx.send("\N{OK HAND SIGN} Sendings Comics")
        await self.send_comic(date, ctx.message.channel.id)
        await msg.delete()

    # @slash_command(guild_ids=ALLOW_SLASH, name="refresh")
    # async def slash_refresh(self, ctx, date):
    #     """Slash command for refresh comic"""
    #     msg = self.embeds.get(date)
    #     embed = msg.embeds[0] if msg else None
    #     if not embed:
    #         await ctx.respond("No comic with that date is available to refresh")
    #         return
    #     refreshed = self.refresh_embed(msg, embed)
    #     if refreshed:
    #         await ctx.respond("Refreshed comic :D (hopefully it reloads properly)")
    #     else:
    #         await ctx.respond("Unable to refresh comic :(")
