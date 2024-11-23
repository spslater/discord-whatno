"""DoA Comic Reread Bot"""

# pylint: disable=too-many-lines
import logging
import re
from asyncio import create_subprocess_shell, sleep, subprocess
from collections import namedtuple
from datetime import datetime, time, timedelta
from json import dump
from json import load as json_load
from pathlib import Path
from sqlite3 import IntegrityError
from textwrap import fill

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from discord import Colour, Embed, Forbidden, HTTPException, NotFound
from discord.ext.bridge import bridge_command
from discord.ext.commands import Cog, is_owner
from discord.ext.tasks import loop
from PIL import Image, ImageDraw, ImageFont
from yaml import Loader
from yaml import load as yml_load

from .helpers import ContextDB, TimeTravel, calc_path

logger = logging.getLogger(__name__)

off_hour, off_mins = TimeTravel.timeoffset()
CP_HOUR = 12 + off_hour
CP_MINS = 0 + off_mins
PUBLISH_TIME = time(CP_HOUR, CP_MINS)

DL_HOUR = 3 + off_hour
DL_MINS = 0 + off_mins
DOWNLOAD_TIME = time(DL_HOUR, DL_MINS)


def setup(bot):
    """Setup the DoA Cogs"""
    cog_reread = DoaComicCog(bot)
    bot.add_cog(cog_reread)


# pylint: disable=too-few-public-methods
class ComicDB(ContextDB):
    """Comic DB Interface"""

    def __init__(self, dbfile, readonly=True):
        super().__init__(dbfile, "./doabase.sql", readonly)


class Schedule:
    """Manage schedule database"""

    def __init__(self, schedule):
        self.schedule_filename = schedule
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


class ComicEmbeds:
    """Embed information for when refreshing comics"""

    def __init__(self, embeds):
        self.filename = embeds
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
        with open(self.filename, mode="r", encoding="utf-8") as fp:
            self.data = json_load(fp)

    def save(self):
        """Save data to file"""
        if self.data:
            with open(self.filename, mode="w+", encoding="utf-8") as fp:
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

    def _get_tags(self, date_string):
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
            if url is not None and url.endswith(".png"):
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

    def _add_reacts(self, results):
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
                    result["reacts"] = [(react["reaction"], react["num"]) for react in reacts]
                print(result)
        print(results)
        return results

    def released_on(self, dates):
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
            days = tuple(schedule["days"].get(date_string, []))
            logger.debug("Getting comics on following days: %s", days)

        if not days:
            return []

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

            entries.append({
                "title": comic["title"],
                "url": comic["url"],
                "alt": f"||{comic['alt']}||",
                "tags": ", ".join(tags) or "no tags today",
                "image": f"https://www.dumbingofage.com/comics/{image}",
                "release": release,
                "reacts": comic["reacts"],
            })
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

            dlconfig = self.f_doa / self.bot.env.path("DOWNLOAD")

        self.comics = ComicInfo(database, schedule)
        self.embeds = ComicEmbeds(embeds)
        self.download = DumbingOfAge(dlconfig, self.f_doa, database)
        # function transformed by the @loop annotation
        # pylint: disable=no-member
        self.schedule_comics.start()
        self.process_comic.start()
        logger.info("Completed DoA Reread setup! :D")

    def cog_unload(self):
        # function transformed by the @loop annotation
        # pylint: disable=no-member
        self.schedule_comics.cancel()
        self.process_comic.cancel()

    async def fetch_message(self, channel_id, message_id):
        """Get message from channel and message ids"""
        channel = self.bot.get_channel(channel_id)
        return await channel.fetch_message(message_id)

    def _is_latest_react(self, message):
        is_channel = message.channel.id == self.latest_channel
        is_bot = message.author.id == self.latest_bot
        return is_channel and is_bot

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
        logger.info(
            "Processed %s comics after %s and before %s",
            processed,
            after,
            before,
        )

    @Cog.listener("on_message")
    async def latest_publish(self, message):
        """Saving the reacts for the previous days comic"""
        if not self._is_latest_react(message):
            return
        logger.info("Saving the reacts for the previous days comic")
        after = datetime.now() - timedelta(days=1, hours=12)
        await self.bot.blocker(self._process_comic, after)

    @is_owner()
    @bridge_command()
    async def latest(self, ctx, after_str, before_str=None):
        """Save info about the comic from date provided"""
        logger.info(
            "Manually saving reacts after %s and before %s",
            after_str,
            before_str,
        )
        await ctx.message.add_reaction("\N{OK HAND SIGN}")
        after_str = f"{after_str.strip()} 00:00:00"
        after = TimeTravel.fromstr(after_str) - timedelta(hours=6)
        before = None
        if before_str:
            before_str = f"{before_str.strip()} 00:00:00"
            before = TimeTravel.fromstr(before_str) + timedelta(hours=6)
        await self.bot.blocker(self._process_comic, after, before)
        await ctx.send(f"Saved comics after {after} and before {before} \N{OK HAND SIGN}")

    @staticmethod
    def build_comic_embed(entry):
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
            embed.add_field(
                name="reacts",
                value=" ".join([f"{r[0]}: {r[1]}" for r in reacts]),
                inline=False,
            )
        embed.set_image(url=img_url)
        embed.set_footer(text=release)

        return embed

    @loop(time=PUBLISH_TIME)
    async def schedule_comics(self):
        """Schedule the comics to auto publish"""
        await self.bot.wait_until_ready()
        await self.bot.blocker(self.send_comic)
        logger.info(
            "Publishing next batch of comics at %s",
            # function transformed by the @loop annotation
            # pylint: disable=no-member
            self.schedule_comics.next_iteration,
        )

    @loop(time=DOWNLOAD_TIME)
    async def process_comic(self):
        """Auto download the comis info"""
        await self.bot.wait_until_ready()

        prev_cur = self.download.cur
        self.download.cur = True
        await self.bot.blocker(self.download.process, self.download.home)
        self.download.cur = prev_cur
        logger.info(
            "Downloading todays comic info, checking tomorrow at %s",
            # function transformed by the @loop annotation
            # pylint: disable=no-member
            self.process_comic.next_iteration,
        )

    async def send_comic(self, date=None, channel_id=None):
        """Send the comics for todays given to primary channel"""
        logger.info(
            "Sending comics for today. (%s)",
            (date or TimeTravel.datestr()),
        )
        channels = self.channels if channel_id else channel_id
        if channels is None:
            logger.debug("No channels are scheduled to be published in.")
            return
        comics = [
            (e["release"], self.build_comic_embed(e)) for e in self.comics.todays_reread(date)
        ]
        self.embeds.load()
        for cid in channels:
            channel = self.bot.get_channel(cid)
            embed_ids = []
            for release, comic in comics:
                logger.debug(comic.to_dict())
                msg = await channel.send(embed=comic)
                embed_ids.append((release, msg.id))
                await sleep(1)
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
        """Save reacts to the database"""
        logger.debug("reaction: %s", payload.emoji)
        if payload.emoji != "🔁":
            return
        msg = await self.fetch_message(payload.channel_id, payload.message_id)
        reply = msg.reference and msg.content == "%refresh"
        self_react = msg.author.id == self.bot.user.id
        if not reply and not self_react:
            logger.debug("not reply or react?")
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

    @is_owner()
    @bridge_command()
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
            [ref.message_id] if ref else [self.embeds.get(ctx.guild.id, {}).get(d) for d in date]
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
        await ctx.message.add_reaction("\N{OK HAND SIGN}")

    @is_owner()
    @bridge_command()
    async def publish(self, ctx, date=None):
        """Publish the days comics, date (YYYY-MM-DD)
        is provided will publish comics for those days"""
        if not date:
            date = TimeTravel.datestr()
        logger.info("manually publishing comics for date %s", date)
        await ctx.send("\N{OK HAND SIGN} Sendings Comics")
        await self.bot.blocker(self.send_comic, date, [ctx.message.channel.id])

    @is_owner()
    @bridge_command()
    async def comicfrom(self, ctx, start):
        """Save info for comic starting from given url"""
        logger.info("downloading comic info from %s", start)
        await ctx.defer()
        prev_cur = self.download.cur
        self.download.cur = False
        await self.bot.blocker(self.download.process, start)
        self.download.cur = prev_cur
        await ctx.send("\N{OK HAND SIGN}")


# pylint: disable=invalid-name
RGBA = namedtuple("RGBA", ["r", "g", "b", "a"])
NameInfo = namedtuple("NameInfo", ["book", "image", "final", "raw", "imgdir"])


class DumbingOfAge:
    """Downloading the comic from the website and saving it to a database"""

    AGENT = {"User-agent": "WhatnoComicReader/1.0 Whatno Discord Bot (Sean Slater)"}
    MAX_COUNT = 25
    SLEEP_TIME = 5

    def __init__(self, yml_file, savedir, database):
        with open(yml_file, mode="r", encoding="utf-8") as yml:
            self.comic = yml_load(yml.read(), Loader=Loader)

        self.storage = savedir
        self.database_file = database

        self.cur = self.comic["cur"]
        self.home = self.comic["home"]
        self.url = self.comic["url"]
        self.name = self.comic["name"]
        self.archive = self.storage / "archive"
        self.archive.mkdir(parents=True, exist_ok=True)

        self.last_comic = False
        self.cur_count = 0
        self.exception_wait = 2

    def _database(self, readonly=False):
        return ComicDB(self.database_file, readonly)

    async def exception_sleep(self, current, retries):
        """Sleep when an exception is raised"""
        logger.warning(
            "Waiting for %d seconds to try again. Remaining atempts: %d",
            self.exception_wait,
            retries - current,
            exc_info=True,
        )
        await sleep(self.exception_wait)
        self.exception_wait *= self.exception_wait
        if current == retries:
            e = Exception("Requests timing out too many times")
            logger.exception(e)
            raise e

    async def _download(self, image_url, save_as, retries=5):
        logger.info('Downloading "%s" from %s', save_as, image_url)
        async with ClientSession(headers=self.AGENT) as session:
            with open(save_as, "wb") as fp:
                for x in range(1, retries + 1):
                    async with session.get(image_url) as res:
                        if res.status != 200:
                            await self.exception_sleep(x, retries)
                            continue
                        async for chunk in res.content.iter_chunked(1024):
                            fp.write(chunk)
                        break
                fp.flush()

    @staticmethod
    def _search_soup(soup, path, value=None):
        for nxt in path:
            dic = {}
            if "class" in nxt:
                dic["class"] = nxt["class"]
            if "id" in nxt:
                dic["id"] = nxt["id"]
            if "index" in nxt:
                soup = soup.find_all(
                    name=nxt.get("tag"), attrs=dic, recursive=nxt.get("recursive", True)
                )[nxt["index"]]
            else:
                soup = soup.find(name=nxt.get("tag"), attrs=dic)
        return soup[value] if soup and value else soup

    def search(self, soup, path):
        """Navigate thru soup given list of tags and attrs"""
        soup = self._search_soup(soup, path[:-1])
        last = path[-1]
        dic = {}
        if "class" in last:
            dic["class"] = last["class"]
        if "id" in last:
            dic["id"] = last["id"]
        return soup.find_all(last["tag"], dic)

    async def get_soup(self, url, retries=10):
        """Async generate the soup from the given url"""
        logger.info("Getting soup for %s", url)
        async with ClientSession(headers=self.AGENT) as session:
            for x in range(1, retries + 1):
                async with session.get(url) as r:
                    if r.status != 200:
                        await self.exception_sleep(x, retries)
                        continue
                    text = await r.text()
                return BeautifulSoup(text, "html.parser")
        return None

    def get_next(self, soup):
        """Search soup for the next url"""
        logger.debug("Getting next url")
        val = self._search_soup(soup, self.comic["nxt"], "href")
        if val is None:
            self.last_comic = True
        return val

    def get_prev(self, soup):
        """Search soup for the previous url"""
        logger.debug("Getting previous url")
        return self._search_soup(soup, self.comic["prev"], "href")

    def get_image(self, soup):
        """Search soup for the img tag"""
        logger.debug("Getting image soup")
        return self._search_soup(soup, self.comic["img"])

    def _get_alt(self, img):
        if img.has_attr("alt"):
            return img["alt"]
        if img.has_attr("title"):
            return img["title"]
        return None

    def _save_image_with_alt(self, input_filename, output_filename, alt_raw):
        logger.info('Adding alt text to image "%s"', output_filename)
        comic = Image.open(input_filename).convert("RGBA")
        c_width, c_height = comic.size

        font = ImageFont.truetype(str(calc_path("ubuntu.ttf")), 16)
        draw_font = ImageDraw.Draw(Image.new("RGB", (c_width, c_height * 2), (255, 255, 255)))
        alt = fill(alt_raw, width=int((c_width - 20) / 11))
        _, alt_top, _, alt_bottom = draw_font.multiline_textbbox((0, 0), alt, font=font)
        alt_height = alt_bottom - alt_top

        height = c_height + 10 + alt_height + 10
        output = Image.new("RGBA", (c_width, height), RGBA(224, 238, 239, 255))

        draw = ImageDraw.Draw(output)

        output.paste(comic, (0, 0), mask=comic)
        draw.text((10, c_height + 10), alt, font=font, fill="black")

        output.save(output_filename, "PNG")
        logger.info("Removing raw image")
        input_filename.unlink()

    @staticmethod
    def _convert_to_png(input_filename, output_filename):
        ext = input_filename.suffix
        if ext != ".png":
            logger.info('Converting image to png "%s"', output_filename)
            comic = Image.open(input_filename).convert("RGB")
            comic.save(output_filename, "PNG")
            input_filename.unlink()
        else:
            logger.info('No need to convert image "%s"', output_filename)
            input_filename.rename(output_filename)

    async def download_and_save(self, img_soup, final_filename, raw_filename):
        """Get comic and save it"""
        logger.info('Downloading and saving "%s"', final_filename)
        image_url = img_soup["src"]

        alt_text = self._get_alt(img_soup)
        if alt_text:
            logger.debug("Saving with alt text")
            await self._download(image_url, raw_filename)
            self._save_image_with_alt(raw_filename, final_filename, alt_text)
        else:
            logger.debug("Saving with no alt")
            await self._download(image_url, raw_filename)
            self._convert_to_png(raw_filename, final_filename)

    async def save_to_archive(self, archive, filename, cur_img_dir):
        """Add image to cbz archives"""
        logger.info('Adding to archive: "%s"', archive)
        save_as = filename.name
        cmd = f'cd {cur_img_dir} && zip -ur \
            "{self.archive}/{archive}.cbz" "{save_as}" > /dev/null'
        logger.debug("Running shell command: `%s`", cmd)
        await create_subprocess_shell(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def get_name_info(self, img_name, dir_name):
        """calcluate names to store the images in"""
        logger.debug('Getting name info for image "%s" and directory "%s"', img_name, dir_name)
        current_image_directory = self.archive / dir_name
        current_image_directory.mkdir(parents=True, exist_ok=True)

        img = img_name.stem
        final_filename = current_image_directory / f"{img}.png"
        raw_filename = current_image_directory / f"raw_{img_name}"

        return current_image_directory, final_filename, raw_filename

    async def wait_if_need(self):
        """Async sleep for a couple seconds to not get rate limited"""
        logger.debug(
            "Checking to see if a wait is needed before parsing next comic. %d / %d",
            self.cur_count,
            self.MAX_COUNT,
        )
        if self.cur_count == self.MAX_COUNT:
            self.cur_count = 0
            logger.debug("Sleeping for %d secs.", self.SLEEP_TIME)
            await sleep(self.SLEEP_TIME)
        else:
            self.cur_count += 1

    @staticmethod
    def _get_tags(soup):
        tag_list = []
        tags = soup.find("div", {"class": "post-tags"}).find_all("a")
        for tag in tags:
            tag_list.append(tag.text)
        return tag_list

    async def get_archive_url(self, soup):
        """Search soup for the url of the comic"""
        logger.debug("Getting archive url from landing page")
        prev = self.get_prev(soup)
        prev_soup = await self.get_soup(prev)
        return self.get_next(prev_soup)

    def get_title(self, soup):
        """Search soup for the title"""
        logger.debug("Getting title of current comic")
        title_tag = self._search_soup(soup, [{"tag": "h2", "class": "post-title"}, {"tag": "a"}])
        if title_tag:
            return title_tag.text
        return None

    def get_arc_name(self, soup):
        """Search soup for the arc"""
        logger.debug("Getting current arc name")
        arc_tag = self._search_soup(soup, [{"tag": "li", "class": "storyline-root"}, {"tag": "a"}])
        if arc_tag:
            return arc_tag.text[5:]
        return None

    def add_arc(self, image_filename, arc_name):
        """Add arc to the database"""
        logger.debug("Checking if arc needs to be added to database")
        data = image_filename.name.split("_")
        num = data[1]
        name = data[2]
        book = int(num[0:2])
        arc = int(num[2:4])
        url = f"https://www.dumbingofage.com/category/comic/book-{book}/{arc}-{name}/"

        with self._database() as database:
            database.execute("SELECT * FROM Arc WHERE number = ?", (num,))
            row = database.fetchone()

            if not row:
                logger.info('Inserting new arc: "%s"', arc_name)
                database.execute("INSERT INTO Arc VALUES (?,?,?)", (num, arc_name, url))
                database.execute("SELECT * FROM Arc WHERE number = ?", (num,))
                row = database.fetchone()

        return row

    def add_comic(self, image_filename, arc_row, comic_title, url):
        """Add comic to the database"""
        logger.debug("Checking if comic needs to be added to database")
        title_release = image_filename.name.split("_")[3]
        release = "-".join(title_release.split("-")[0:3])

        with self._database() as database:
            database.execute("SELECT * FROM Comic WHERE release = ?", (release,))
            row = database.fetchone()

            if not row:
                logger.info('Inserting new comic: "%s"', comic_title)
                database.execute(
                    "INSERT INTO Comic VALUES (?,?,?,?,?)",
                    (release, comic_title, str(image_filename), url, arc_row["number"]),
                )
                database.execute("SELECT * FROM Comic WHERE release = ?", (release,))
                row = database.fetchone()

        return row

    def add_alt(self, comic, alt):
        """Add alt text to the database"""
        logger.debug("Checking if alt text needs to be added to database")

        with self._database() as database:
            database.execute("SELECT * FROM Alt WHERE comicId = ?", (comic["release"],))
            row = database.fetchone()

            if not row:
                logger.debug('Inserting new alt: "%s"', comic["release"])
                database.execute("INSERT INTO Alt VALUES (?,?)", (comic["release"], alt))
                database.execute("SELECT * FROM Alt WHERE comicId = ?", (comic["release"],))
                row = database.fetchone()

        return row

    def add_tags(self, comic, tags):
        """Add tags to the database"""
        logger.debug("Checking if tags needs to be added to database")
        added_tags = []
        with self._database() as database:
            for tag in tags:
                database.execute(
                    "SELECT * FROM Tag WHERE comicId = ? AND tag = ?", (comic["release"], tag)
                )
                row = database.fetchone()

                if not row:
                    database.execute("INSERT INTO Tag VALUES (?,?)", (comic["release"], tag))
                    database.execute(
                        "SELECT * FROM Tag WHERE comicId = ? AND tag = ?",
                        (comic["release"], tag),
                    )
                    row = database.fetchone()
                    added_tags.append(row)
        logger.debug("Inserted new tags: %s", [tag["tag"] for tag in added_tags])
        return added_tags

    async def _naming_parts(self, soup, name, ext):
        if self.cur:
            parts = self._search_soup(soup, self.comic["book"], "href").split("/")
            book_number = parts[-3].split("-")[1].zfill(2)
            arcs = parts[-2].split("-")
            self.url = await self.get_archive_url(soup)
        else:
            parts = self.url.split("/")
            book_number = parts[-4].split("-")[1].zfill(2)
            arcs = parts[-3].split("-")
        arc_number = arcs[0].zfill(2)
        arc_name = "-".join(arcs[1:])
        book_arc = f"{book_number}{arc_number}"
        img_filename = Path(f"DumbingOfAge_{book_arc}_{arc_name}_{name}{ext}")
        return book_arc, img_filename

    async def _naming_info(self, soup, image_url):
        raw_name = Path(image_url.split("/")[-1])
        ext = raw_name.suffix.lower()
        basename = raw_name.stem

        if ext != ".png":
            self.url = self.get_next(soup)
            return True, None, None, None, None

        book_arc, image_filename = await self._naming_parts(soup, basename, ext)

        book_arc_dir = self.archive / book_arc
        book_arc_dir.mkdir(parents=True, exist_ok=True)

        cur_img_dir, final_filename, raw_filename = self.get_name_info(
            image_filename,
            book_arc_dir,
        )

        return False, NameInfo(
            book_arc,
            image_filename,
            final_filename,
            raw_filename,
            cur_img_dir,
        )

    async def process(self, url=None):
        """Get the current comic and add it to the database"""
        if url:
            self.url = url
        while True:
            logger.info("Getting soup for %s", self.url)
            soup = await self.get_soup(self.url)

            img_soup = self.get_image(soup)
            skip_comic, ni = await self._naming_info(soup, img_soup["src"])
            if skip_comic:
                continue

            logger.info("Saving Arc to Database")
            full_arc_name = self.get_arc_name(soup)
            arc_row = self.add_arc(ni.image, full_arc_name)

            logger.info("Saving Comic to Database")
            comic_title = self.get_title(soup)
            comic_row = self.add_comic(ni.image, arc_row, comic_title, self.url)

            alt_text = self._get_alt(img_soup)
            if alt_text:
                logger.info("Saving Alt Text to Database")
                self.add_alt(comic_row, alt_text)

            logger.info("Saving Tags to Database")
            tags = self._get_tags(soup)
            self.add_tags(comic_row, tags)

            await self.download_and_save(img_soup, ni.final, ni.raw)
            await self.save_to_archive(self.name, ni.final, ni.imgdir)
            await self.save_to_archive(f"{self.name} - {ni.book}", ni.final, ni.imgdir)

            logger.info('Done processing comic "%s"', ni.final)

            self.url = self.get_next(soup)
            await self.wait_if_need()

            if self.last_comic:
                break

        logger.info('Completed processing "Dumbing of Age"')
