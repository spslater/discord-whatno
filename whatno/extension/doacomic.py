"""DoA Comic Reread Bot

Discord bot for publishing a weeks worth of DoA
comics every day as part of a community reread.

:class DoaReread: Discord Bot that publishes a weeks
    of DoA comics every day
"""
import logging
import re
from datetime import time, timedelta, datetime
from json import dump, load
from pathlib import Path
from time import sleep

from discord import Colour, Embed, Forbidden, HTTPException, NotFound
from discord.ext.commands import Cog, command, is_owner
from discord.ext.tasks import loop
from discord.ext import bridge
from sqlite3 import Connection, IntegrityError, Row, connect
from typing import Union

from .helpers import TimeTravel, calc_path


logger = logging.getLogger(__name__)

off_hour, off_mins = TimeTravel.timeoffset()
CP_HOUR = 12 + off_hour
CP_MINS = 0 + off_mins
PUBLISH_TIME = time(CP_HOUR, CP_MINS)



def setup(bot):
    """Setup the DoA Cogs"""
    cog_reread = DoaComicCog(bot)
    bot.add_cog(cog_reread)



class DictRow:
    def __init__(self, cursor, row):
        self._keys = []
        for idx, col in enumerate(cursor.description):
            setattr(self, col[0], row[idx])

    def __repr__(self):
        vals = [f"{k}: {getattr(self,k)}" for k in self._keys]
        return "DictRow(" + " | ".join(vals) + ")"

    def __getitem__(self, key):
        return getattr(self, key, None)

    def __setitem__(self, key, value):
        self._keys.append(key)
        setattr(self, key, value)

class ComicDB:
    """Comic DB Interface"""

    def __init__(self, dbfile, readonly=True):
        self.readonly = readonly
        self.filename: Path = dbfile
        if not self.filename:
            raise ValueError("No database to pull comic info from provided")
        self.conn = None

    def setup(self):
        logger.debug("running setup on the comic database")
        script = calc_path("./doabase.sql")
        with open(script, "r", encoding="utf-8") as fp:
            sql_script = fp.read()

        with self as db:
            db.executescript(sql_script)

    def open(self):
        """Open a connection to the database and return a cursor"""
        self.conn: Connection = (
            connect(f"file:{self.filename}?mode=ro", uri=True)
            if self.readonly
            else connect(self.filename)
        )
        self.conn.row_factory = DictRow
        return self.conn.cursor()

    def close(self):
        """Close connection to the database"""
        if not self.readonly:
            self.conn.commit()
        return self.conn.close()

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return exc_type is None


class Schedule:
    """Manage schedule database"""

    def __init__(self, schedule):
        self.schedule_filename: Path = schedule
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

    def __enter__(self):
        self.load()
        return self.schedule

    def __exit__(self, exc_type, exc_value, traceback):
        self.save()
        return exc_type is None


class ComicEmbeds:
    """Embed information for when refreshing comics"""

    def __init__(self, embeds):
        self.filename: Path = embeds
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



class ComicInfo:
    """Manage and get Comic information"""

    def __init__(self, database, schedule):
        self.database_file = database
        self.schedule_file = schedule
        ComicDB(self.database_file, False).setup()

    def _database(self, readonly=True):
        return ComicDB(self.database_file, readonly)

    def _schedule(self):
        return Schedule(self.schedule_file)

    def _get_tags(self, date_string: str) -> list[str]:
        """Comma seperated tags from a comic"""
        with self._database() as database:
            rows = database.execute(
                "SELECT tag FROM Tag WHERE comicId = ?",
                (date_string,),
            ).fetchall()
        return [r["tag"] for r in rows]

    def new_latest(self, mid, url):
        """Save latest comic published to latest channel"""
        with self._database(readonly=False) as database:
            if url.endswith(".png"):
                og = url
                img = f"%{url.split('/')[-1]}"
                res = database.execute(
                    "SELECT url FROM Comic WHERE image LIKE ?",
                    (img,),
                )
                url = res.fetchone()["url"]
            try:
                database.execute("INSERT INTO Latest VALUES (?,?)", (mid, url))
            except IntegrityError:
                pass

    def save_reacts(self, reacts):
        """Save live reacts from recent comic"""
        with self._database(readonly=False) as database:
            for react in reacts:
                try:
                    database.execute("INSERT INTO React VALUES (?,?,?)", react)
                except IntegrityError:
                    pass

    def save_discussion(self, comic, message):
        """Save the message that was part of a comics discussion"""
        content = message.content if message.content.strip() else None
        if message.attachments:
            logger.debug("%s attaches: %s", message.id, message.attachments)
        attach = message.attachments[0].url if message.attachments else None
        embed = str(message.embeds[0].to_dict()) if message.embeds else None
        with self._database(readonly=False) as database:
            data = (
                message.id,
                message.created_at.timestamp(),
                message.author.id,
                comic,
                content,
                attach,
                embed,
            )
            try:
                database.execute(
                    "INSERT INTO Discussion VALUES (?,?,?,?,?,?,?)",
                    data,
                )
            except IntegrityError:
                database.execute(
                    """
                    UPDATE Discussion
                    SET
                        msg = ?,
                        time = ?,
                        user = ?,
                        comic = ?,
                        content = ?,
                        attach = ?,
                        embed = ?
                    WHERE msg = ?
                    """,
                    (*data, message.id),
                )

    def _add_reacts(self, results: list[DictRow]) -> list[DictRow]:
        """Add the reacts as a list of tuples"""
        with self._database() as database:
            for result in results:
                reacts = database.execute(
                    f"""SELECT reaction, count(reaction) as num
                        FROM React
                        WHERE msg = {result['msg']} AND uid != 639324610772467714
                        GROUP BY msg, reaction
                        ORDER BY reaction ASC"""
                ).fetchall()
                if reacts:
                    #setattr(result, "reacts", [(react["reaction"], react["num"]) for react in reacts])
                    result["reacts"] = [(react["reaction"], react["num"]) for react in reacts]
                print(result)
        print(results)
        return results

    def released_on(self, dates: Union[str, list[str]]) -> list[DictRow]:
        """Get database rows for comics released on given dates"""
        if isinstance(dates, str):
            dates = [dates]
        with self._database() as database:
            results = database.execute(
                f"""SELECT
                    Comic.release as release,
                    Comic.title as title,
                    Comic.image as image,
                    Comic.url as url,
                    Alt.alt as alt,
                    Latest.msg as msg
                FROM Comic
                JOIN Alt ON Comic.release = Alt.comicId
                JOIN Latest ON Comic.url = Latest.url
                WHERE release IN {dates}"""
            ).fetchall()
        results = self._add_reacts(results)
        return results

    def todays_reread(self, date=None):
        """Get information for comic reread"""
        with self._schedule() as schedule:
            date_string = date or TimeTravel.datestr()
            days = tuple(schedule["days"][date_string])
            logger.debug("Getting comics on following days: %s", days)

        entries = []
        comics = self.released_on(days)
        logger.debug("%s comics from current week", len(comics))
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
                    "tags": ", ".join(tags) or "no tags today",
                    "image": f"https://www.dumbingofage.com/comics/{image}",
                    "release": release,
                    "reacts": comic["reacts"],
                }
            )
        return entries

    def update_schedule(self):
        """Update the schedule every week"""
        logger.info("Checking schedule to see if it needs updating")
        with self._schedule() as schedule:
            old_week = schedule["next_week"]
            now = TimeTravel.datestr()
            while old_week <= now:
                new_week = datetime.strptime(old_week, "%Y-%m-%d") + timedelta(days=7)
                new_week_str = datetime.strftime(new_week, "%Y-%m-%d")
                schedule["next_week"] = new_week_str

                last_day = sorted(schedule["days"].keys())[-1]
                next_day = datetime.strptime(last_day, "%Y-%m-%d") + timedelta(days=1)
                next_day_str = datetime.strftime(next_day, "%Y-%m-%d")

                schedule["days"][next_day_str] = TimeTravel.week_dates(new_week_str)

                old_week = schedule["next_week"]



class DoaComicCog(Cog, name="DoA Comic"):
    """Actual DoA Comic Cog"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

        self.f_doa = self.bot.storage / "doa"

        with self.bot.env.prefixed("DOA_"):
            self.latest_channel = self.bot.env.int("LATEST_CHANNEL")
            self.latest_bot = self.bot.env.int("LATEST_BOT")
            self.channels = self.bot.env.list("COMIC_CHANNELS", subcast=int)

            database = self.f_doa / self.bot.env.path("DATABASE")
            schedule = self.f_doa / self.bot.env.path("SCHEDULE")
            embeds = self.f_doa / self.bot.env.path("EMBEDS")

        self.comics = ComicInfo(database, schedule)
        self.embeds = ComicEmbeds(embeds)
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
            logger.debug("react add %s | %s", payload.emoji, payload.user_id)

    @Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Watch for reacts to things in the servers"""
        msg = await self.fetch_message(payload.channel_id, payload.message_id)
        if self._is_latest_react(msg):
            logger.debug("react remove %s | %s", payload.emoji, payload.user_id)

    async def _save_reacts(self, message):
        """Save react info to database"""
        if not message.embeds:
            return

        mid = message.id
        url = message.embeds[0].url
        self.comics.new_latest(mid, url)

        reacts = []
        for react in message.reactions:
            emoji = str(react.emoji)
            async for user in react.users():
                if user.id != self.latest_bot:
                    logger.debug("human react, saving: %s", emoji)
                    reacts.append((mid, user.id, emoji))
                else:
                    logger.debug("bot react, not saving: %s", emoji)
        self.comics.save_reacts(reacts)
        logger.debug(
            "Saved %s reacts from %s for comic %s | %s",
            len(reacts),
            message.created_at,
            mid,
            url,
        )

    async def _process_comic(self, after, before=None):
        logger.debug("Processing comics after %s and before %s", after, before)
        history = await self.bot.get_history(
            channel_id=self.latest_channel,
            after=after,
            before=before,
        )
        processed = 0
        prev = None
        async for message in history:
            if message.author.id == self.latest_bot:
                await self._save_reacts(message)
                prev = message.id
                processed += 1
            elif prev:
                logger.debug("saving discussion for %s: %s", prev, message)
                self.comics.save_discussion(prev, message)
        logger.info("Processed %s comics after %s and before %s", processed, after, before)

    @Cog.listener("on_message")
    async def latest_publish(self, message):
        """Saving the reacts for the previous days comic"""
        if not self._is_latest_react(message):
            return
        logger.info("Saving the reacts for the previous days comic")
        after = datetime.now() - timedelta(days=1, hours=12)
        await self._process_comic(after)

    @is_owner()
    @bridge.bridge_command()
    async def latest(self, ctx, after_str, before_str=None):
        """Save info about the comic from date provided"""
        logger.info(
            "Manually saving reacts after %s and before %s",
            after_str,
            before_str,
        )
        await ctx.message.add_reaction("<:wave_Joyce:780682895907618907>")
        after_str = f"{after_str.strip()} 00:00:00"
        after = TimeTravel.fromstr(after_str) - timedelta(hours=6)
        before = None
        if before_str:
            before_str = f"{before_str.strip()} 00:00:00"
            before = TimeTravel.fromstr(before_str) + timedelta(hours=6)
        await self._process_comic(after, before)
        await ctx.send(f"Saved comics after {after} and before {before} \N{OK HAND SIGN}")

    async def _setup_connection(self):
        given_channels = []
        for given_channel in self.comic_channels:
            channel_id = channel_name = None
            try:
                channel_id = int(given_channel)
            except (TypeError, ValueError):
                channel_name = given_channel

            if channel_id is None:
                channels = self.get_all_channels()

                for channel in channels:
                    if channel.name == channel_name:
                        channel_id = int(channel.id)
                        break
                if channel_id is None:
                    raise RuntimeError("Provided channel is not an available channels")
            given_channels.append(channel_id)
        self.channels = given_channels

    @staticmethod
    def build_comic_embed(entry: dict[str, str]) -> Embed:
        """Basic way to generate the embeds"""
        title = entry.get("title")
        url = entry.get("url")
        alt = entry.get("alt")
        tag_text = entry.get("tags")
        img_url = entry.get("image")
        release = entry.get("release")
        reacts = entry.get("reacts")

        embed = Embed(title=title, url=url, colour=Colour.random())
        embed.add_field(name=alt, value=tag_text)
        if reacts:
            embed.add_field(name="reacts", value=" ".join([f"{r[0]}: {r[1]}" for r in reacts]), inline=False)
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
        channels = self.channels if channel_id else channel_id
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

    @Cog.listener("on_raw_reaction_add")
    async def react_refresh(self, payload):
        logger.debug("reaction: %s", payload.emoji )
        if payload.emoji != "🔁":
            logger.debug("skipping???" )
            return
        msg = await self.fetch_message(payload.channel_id, payload.message_id)
        reply = msg.reference and msg.content == "%refresh"
        self_react = msg.author.id == self.user.id
        if not reply and not self_react:
            logger.debug("not reply or react?" )
            return
        if reply:
            ref = msg.reference
        elif self_react:
            ref = msg
        embed = ref.embeds[0]
        if embed:
            logger.debug("Refreshing Embed: %s", embed.to_dict())
            await self.refresh_embed(ref, embed)

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

    @bridge.bridge_command()
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

    @bridge.bridge_command()
    async def publish(self, ctx, date=None):
        """Publish the days comics, date (YYYY-MM-DD)
        is provided will publish comics for those days"""
        if not date:
            date = TimeTravel.datestr()
        logger.info("manually publishing comics for date %s", date)
        msg = await ctx.send("\N{OK HAND SIGN} Sendings Comics")
        await self.send_comic(date, [ctx.message.channel.id])