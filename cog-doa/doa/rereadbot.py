"""DoA Comic Reread Bot

Discord bot for publishing a weeks worth of DoA
comics every day as part of a community reread.

:class DoaReread: Discord Bot that publishes a weeks
    of DoA comics every day
"""
import logging
import re
from datetime import time, timedelta
from json import dump, load
from os import getenv
from pathlib import Path
from time import sleep

from discord import Colour, Embed, Forbidden, HTTPException, NotFound

from discord.ext.commands import Cog, command, is_owner
from discord.ext.tasks import loop
from dotenv import load_dotenv

from .comic import ComicInfo
from .helpers import TimeTravel, calc_path


logger = logging.getLogger(__name__)

off_hour, off_mins = TimeTravel.timeoffset()
CP_HOUR = 12 + off_hour
CP_MINS = 0 + off_mins
PUBLISH_TIME = time(CP_HOUR, CP_MINS)


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

    def __init__(self, bot, envfile):
        super().__init__()
        self.bot = bot

        envpath = calc_path(envfile)
        load_dotenv(envpath)

        self.guild = None
        self.channel = None

        self.latest_channel = int(getenv("DOA_LATEST_CHANNEL"))
        self.latest_bot = int(getenv("DOA_LATEST_BOT"))

        self.comics = ComicInfo(getenv("DOA_DATABASE"), getenv("DOA_SCHEDULE"))
        self.embeds = ComicEmbeds(getenv("DOA_EMBEDS"))
        # function transformed by the @loop annotation
        # pylint: disable=no-member
        self.schedule_comics.start()
        logger.info("Completed DoA Reread setup! :D")

    def cog_unload(self):
        # function transformed by the @loop annotation
        # pylint: disable=no-member
        self.schedule_comics.cancel()

    async def fetch_message(self, channel_id, message_id):
        """Get message from channel and message ids"""
        channel = self.bot.get_channel(channel_id)
        return await channel.fetch_message(message_id)

    def _is_latest_react(self, message):
        is_channel = message.channel.id == self.latest_channel
        is_bot = message.author.id == self.latest_bot
        return is_channel and is_bot

    @Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Watch for reacts to things in the servers"""
        msg = await self.fetch_message(payload.channel_id, payload.message_id)
        if self._is_latest_react(msg):
            logger.debug("react add %s | %s",payload.emoji,payload.user_id)

    @Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Watch for reacts to things in the servers"""
        msg = await self.fetch_message(payload.channel_id, payload.message_id)
        if self._is_latest_react(msg):
            logger.debug("react remove %s | %s",payload.emoji,payload.user_id)

    async def _save_reacts(self, message):
        """Save react info to database"""
        mid = message.id
        url = message.embeds[0].url
        self.comics.new_latest(mid, url)

        reacts = []
        for react in message.reactions:
            emoji = str(react.emoji)
            async for user in react.users():
                try:
                    uid = re.match(r"<@!*([0-9]+)>", user.mention).group(1)
                except AttributeError:
                    logger.debug(
                        "no user id match in %s for %s: %s",
                        mid,
                        user,
                        user.mention,
                    )
                else:
                    if uid != self.latest_bot:
                        reacts.append((mid, uid, emoji))
        logger.info(
            "Saving %s reacts from %s for comic %s | %s",
            len(reacts),
            message.created_at,
            mid,
            url,
        )

    @Cog.listener("on_message")
    async def latest_publish(self, message):
        """Saving the reacts for the previous days comic"""
        if not self._is_latest_react(message):
            return
        logger.info("Saving the reacts for the previous days comic")
        now = TimeTravel.timestamp()
        before = TimeTravel.utcfromtimestamp(now - 3600)
        after = before - timedelta(days=1, hours=12)
        history = await self.bot.get_history(
            channel_id=self.latest_channel,
            user_id=self.latest_bot,
            before=before,
            after=after,
            oldest_first=False,
        )
        message = (await history.flatten())[0]
        await self._save_reacts(message)

    @is_owner()
    @command()
    async def save_reacts(self, ctx, fromstr=None):
        """When the bot connects to discord and is ready"""
        if fromstr is None:
            fromstr = "2021-08-01 00:00:00"
        else:
            fromstr = f"{fromstr.strip()} 00:00:00"
        logger.info("Manually saving reacts since %s", fromstr)
        after = TimeTravel.fromstr(fromstr)
        async for message in (
            await self.bot.get_history(
                channel_id=self.latest_channel,
                user_id=self.latest_bot,
                after=after,
            )
        ):
            await self._save_reacts(message)
        await ctx.send(f"Saved reacts on comics since {fromstr} \N{OK HAND SIGN}")

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
                logger.debug("Getting channel.")
                channels = []
                try:
                    logger.debug("Trying to get channel from specific guild.")
                    channels = self.guild.fetch_channels()
                except RuntimeError:
                    logger.debug(
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
        logger.info(
            "Publishing next batch of comics at %s",
            # function transformed by the @loop annotation
            # pylint: disable=no-member
            self.schedule_comics.next_iteration,
        )

    async def send_comic(self, date=None, channel_id=None):
        """Send the comics for todays given to primary channel"""
        logger.info(
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
                logger.debug(comic.to_dict())
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
        logger.info("Publish complete! :)")

    async def refresh_embed(self, msg, embed) -> bool:
        """Perform embed refresh"""
        if embed:
            embed.colour = Colour.random()
            try:
                await msg.edit(embed=embed)
                return True
            except (HTTPException, Forbidden) as e:
                logger.warning(
                    'Unable to refresh message "%s": %s',
                    msg.id,
                    e,
                )
        return False

    @command()
    async def refresh(self, ctx, *date):
        """Refresh the comic to get the embed working"""
        logger.info("refreshing dates: %s", date)
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
        logger.debug("refresh message ids: %s", message_ids)
        msg = None
        for mid in message_ids:
            try:
                msg = await ctx.channel.fetch_message(mid)
            except (Forbidden, NotFound):
                pass
            else:
                embed = msg.embeds[0] if msg else None
                if embed:
                    logger.debug("Refreshing Embed: %s", embed.to_dict())
                    await self.refresh_embed(msg, embed)
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
        logger.info("manually publishing comics for date %s", date)
        msg = await ctx.send("\N{OK HAND SIGN} Sendings Comics")
        await self.send_comic(date, ctx.message.channel.id)
        await msg.delete()
