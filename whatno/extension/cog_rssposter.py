"""RSS Poster Bot"""

import logging
from datetime import datetime
from time import mktime
from asyncio import sleep

import feedparser
import dateparser
from yaml import Loader, load, dump, Dumper

from discord.ext.bridge import bridge_group
from discord.ext.commands import Cog, is_owner
from discord.ext.tasks import loop


logger = logging.getLogger(__name__)

AGENT = "RSS Poster/1.0 Whatno Discord Bot (Sean Slater)"

def setup(bot):
    """Setup the DoA Cogs"""
    cog_rssposter = RssPosterCog(bot)
    bot.add_cog(cog_rssposter)


class RssPosterCog(Cog, name="RSS Poster"):
    """RSS Poster Cog"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

        self.rssdir = self.bot.storage / "rssposter"
        self.rssdir.mkdir(exist_ok=True)

        self.config_file = self.rssdir / self.bot.env.path("RSS_CONFIG", "config.yml")

        # function transformed by the @loop annotation
        # pylint: disable=no-member
        self.process_rss.start()
        logger.info("Completed DoA Reread setup! :D")

    def cog_unload(self):
        # function transformed by the @loop annotation
        # pylint: disable=no-member
        self.process_rss.cancel()

    @loop(minutes=15)
    async def process_rss(self):
        """Process the RSS feed and publish if recent enough"""
        await self.bot.wait_until_ready()

        if not self.config_file.exists():
            logger.info(
                "No config file, checking next at %s",
                # function transformed by the @loop annotation
                # pylint: disable=no-member
                self.process_rss.next_iteration,
            )
            return

        with open(self.config_file, "r") as fp:
            data = load(fp, Loader=Loader)

        updates = []

        for name, info in data.items():
            url = info.get('url')
            cid = info.get('channel')
            if url is None or cid is None:
                continue

            if 'last_post' in info:
                last_post = dateparser.parse(info['last_post'])
            else: 
                last_post = datetime.min
            latest_only = info.get('latest_only', False)

            feed = feedparser.parse(url, agent=AGENT)
            new = []
            for entry in feed.entries:
                pub_parsed = datetime.fromtimestamp(mktime(entry.published_parsed))
                if pub_parsed <= last_post:
                    continue
                new.append((pub_parsed, entry.link))
            if not new:
                continue
            new.sort(key=lambda x: x[0])
            if latest_only and new:
                new = new[-1:]

            channel = self.bot.get_channel(cid)
            for post in new:
                await channel.send(post[1])
                await sleep(1)

            data[name]['last_post'] = new[-1][0].isoformat()
            updates.append((name, channel, len(new)))

        with open(self.config_file, "w") as fp:
            fp.write(dump(data, Dumper=Dumper))

        logger.info(
            "Posted recent rss posts, checking next at %s | %s",
            # function transformed by the @loop annotation
            # pylint: disable=no-member
            self.process_rss.next_iteration,
            ' | '.join([f'{u[0]} - {u[2]} to {u[1]}' for u in updates])
        )

    @is_owner()
    @bridge_group()
    async def rss(self, ctx):
        """rss sub commands"""
        if ctx.invoked_subcommand:
            return
        msg = "```\ncheck(): process the list and check all feeds again```"
        await ctx.send(msg)

    @is_owner()
    @rss.command()
    async def check(self, ctx):
        await self.process_rss()
        await ctx.message.add_reaction("\N{OK HAND SIGN}")