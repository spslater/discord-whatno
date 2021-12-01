"""DoA Comic Reread Bot

Discord bot for publishing a weeks worth of DoA
comics every day as part of a community reread.

:class DoaReread: Discord Bot that publishes a weeks
    of DoA comics every day
"""
import logging
import re
from datetime import datetime, timedelta
from json import dump, load
from os import getenv
from pathlib import Path
from sqlite3 import Row
from time import sleep
from threading import Timer
from typing import Union

from discord import Embed, Colour, HTTPException, Forbidden
from discord.ext.commands import Cog, command
from discord.commands import slash_command
from dotenv import load_dotenv

from .helpers import calc_path, TimeTravel
from .comic import ComicDB


ALLOW_SLASH = [365677277821796354, 248732519204126720]

logger = logging.getLogger(__name__)


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

    def todays_reread(self):
        """Get information for comic reread"""
        self.database = self.connection.open()
        date_string = datetime.strftime(datetime.now(), "%Y-%m-%d")
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
        now = datetime.strftime(datetime.now(), "%Y-%m-%d")
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
        self.filename: Path = calc_path(embeds)
        if not self.filename:
            raise ValueError("No embeds file for previously publish comics provided")
        self.data = None

    def __getitem__(self, key):
        if self.data is None:
            self.load()
        return self.data[key]

    def __setitem__(self, key, value):
        if self.data is None:
            self.load()
        self.data[key] = value

    def __delitem__(self, key):
        if self.data is None:
            self.load()
        del self.data[key]

    def get(self, key, default=None):
        """Get value or default from data"""
        return self.data.get(key, default=default)

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

        self.comics = ComicInfo(getenv("DATABASE"), getenv("SCHEDULE"))
        self.embeds = ComicEmbeds(getenv("EMBEDS"))
        self.publish = None
        self._schedule_comic()

        self._logger.info("Completed DoA Reread setup! :D")

    async def _setup_connection(self):
        given_guild = getenv("DISCORD_GUILD")
        guild_id = guild_name = None
        try:
            guild_id = int(given_guild)
        except (TypeError, ValueError):
            guild_name = given_guild

        if guild_id is None and guild_name is not None:
            async for guild in self.fetch_guilds():
                if guild.name == guild_name:
                    guild_id = int(guild.id)
                    break
        if guild_id is None:
            raise RuntimeError("Provided Guild is not an available guild")
        self.guild = self.get_guild(guild_id)

        given_channel = getenv("DISCORD_CHANNEL")
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
        self.channel = self.get_channel(channel_id)

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

    def _schedule_comic(self):
        waitdate, waitfor = TimeTravel.next_noon()
        self._logger.info(
            "Publishing next batch of comics at %s (%ss)",
            waitdate,
            waitfor,
        )
        self.publish = Timer(waitfor, self.send_comic)
        self.publish.start()

    async def send_comic(self):
        """Send the comics for todays given to primary channel"""
        self._logger.info("Sending comics for today.")
        if self.guild is None and self.channel is None:
            await self._setup_connection()
        for entry in self.comics.todays_reread():
            embed = self.build_comic_embed(entry)
            self._logger.debug(embed.to_dict())
            msg = await self.channel.send(embed=embed)
            self.embeds[entry["release"]] = msg
            sleep(3)
        self.comics.update_schedule()
        self._schedule_comic()

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
    async def refresh(self, ctx, date=None):
        """Prefix Command for refreshing comic"""
        if not (ctx.message.reference or date):
            await ctx.send(
                (
                    "Need to reply to comic you want refreshed or "
                    "send date it was released in format `YYYY-MM-DD`"
                )
            )
            return
        with ctx.typing():
            ref = ctx.message.reference
            mid = ref.message_id if ref else self.embeds.get(date)
            msg = await ctx.channel.fetch_message(mid)
            embed = msg.embeds[0] if msg else None
            if embed:
                await self.refresh_embed(msg, embed)

    @slash_command(guild_ids=ALLOW_SLASH, name="refresh")
    async def slash_refresh(self, ctx, date):
        """Slash command for refresh comic"""
        msg = self.embeds.get(date)
        embed = msg.embeds[0] if msg else None
        if not embed:
            await ctx.respond("No comic with that date is available to refresh")
            return
        refreshed = self.refresh_embed(msg, embed)
        if refreshed:
            await ctx.respond("Refreshed comic :D (hopefully it reloads properly)")
        else:
            await ctx.respond("Unable to refresh comic :(")
