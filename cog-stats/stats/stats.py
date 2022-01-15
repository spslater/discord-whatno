"""Stats Bot for Voice and Messages"""
import logging
import re
from collections import namedtuple
from json import dump
from os import getenv

from discord.ext.commands import Cog, command, is_owner
from discord.ext.tasks import loop
from dotenv import load_dotenv

from .helpers import calc_path, TimeTravel
from .database import VoiceDB

logger = logging.getLogger(__name__)

VoiceCon = namedtuple("VoiceCon", ["user", "guild", "channel"])
VoiceData = namedtuple(
    "VoiceData",
    [
        "jointime",
        "mute",
        "mutetime",
        "deaf",
        "deaftime",
        "stream",
        "streamtime",
        "video",
        "videotime",
    ],
)
VoiceDiff = namedtuple("VoiceDiff", ["voice", "mute", "deaf", "stream", "video"])


class StatsCog(Cog):
    """Actual DoA Reread Cog"""

    def __init__(self, bot, envfile):
        super().__init__()
        self.bot = bot

        envpath = calc_path(envfile)
        load_dotenv(envpath)

        self.database_file = getenv("VOICE_DATABASE")
        self._database().setup()

        self.current = {}
        # function transformed by the @loop annotation
        # pylint: disable=no-member
        self.periodic_save.start()

    def _database(self, readonly=False):
        return VoiceDB(self.database_file, readonly)

    def cog_unload(self):
        # function transformed by the @loop annotation
        # pylint: disable=no-member
        self.periodic_save.cancel()

    @Cog.listener("on_ready")
    async def load_current(self):
        self._save_current()

    @staticmethod
    def _state_data(state, timestamp):
        return VoiceData(
            timestamp,
            state.self_mute,
            timestamp if state.self_mute else None,
            state.self_deaf,
            timestamp if state.self_deaf else None,
            state.self_stream,
            timestamp if state.self_stream else None,
            state.self_video,
            timestamp if state.self_video else None,
        )

    @staticmethod
    def _diff_state(first: VoiceData, second: VoiceData):
        voicediff = second.jointime - first.jointime

        mute = second.mute and first.mute
        mutediff = None
        if mute:
            mutediff = second.mutetime - first.mutetime

        deaf = second.deaf and first.deaf
        deafdiff = None
        if deaf:
            deafdiff = second.deaftime - first.deaftime

        stream = second.stream and first.stream
        streamdiff = None
        if stream:
            streamdiff = second.streamtime - first.streamtime

        video = second.video and first.video
        videodiff = None
        if video:
            videodiff = second.videotime - first.videotime

        return VoiceDiff(voicediff, mutediff, deafdiff, streamdiff, videodiff)

    def current_voice(self):
        """setup current users in voice"""
        now = TimeTravel.timestamp()
        current = []
        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                for user, state in channel.voice_states.items():
                    id_ = VoiceCon(user, guild.id, channel.id)
                    data = self._state_data(state, now)
                    current.append((id_, data))
        return current

    @staticmethod
    def _log_voice_change(member, before, after):
        before_info = (
            before.channel.id if before.channel else None,
            before.channel.name if before.channel else None,
            before.self_deaf,
            before.self_mute,
            before.self_stream,
            before.self_video,
        )
        after_info = (
            after.channel.id if after.channel else None,
            after.channel.name if after.channel else None,
            after.self_deaf,
            after.self_mute,
            after.self_stream,
            after.self_video,
        )
        logger.info(
            "%s (%s): %s -> %s",
            member.name,
            member.id,
            before_info,
            after_info,
        )

    def _save_state_change(self, id_, before, after):
        diff = self._diff_state(before, after)

        name = id_.user
        guild = id_.guild
        channel = id_.channel
        time = before.jointime

        history = []
        history.append((name, guild, channel, "voice", time, diff.voice))
        if diff.mute:
            history.append((name, guild, channel, "mute", time, diff.mute))
        if diff.deaf:
            history.append((name, guild, channel, "deaf", time, diff.deaf))
        if diff.stream:
            history.append((name, guild, channel, "stream", time, diff.stream))
        if diff.video:
            history.append((name, guild, channel, "video", time, diff.video))

        with self._database() as db:
            db.executemany("INSERT INTO History VALUES (?,?,?,?,?,?)", history)

    @Cog.listener("on_voice_state_update")
    async def voice_change(self, member, before, after):
        """log the new voice status of a user"""
        now = TimeTravel.timestamp()

        self._log_voice_change(member, before, after)

        join = before.channel is None
        leave = after.channel is None

        if join is None and leave is None:
            return

        guild = before.channel.guild.id if not join else after.channel.guild.id
        channel = before.channel.id if not join else after.channel.id
        id_ = VoiceCon(member.id, guild, channel)

        after_data = self._state_data(after, now)

        if join:
            self.current[id_] = after_data
            return

        prev_state = self.current[id_]
        new_state = self._state_data(before, now)
        self._save_state_change(id_, prev_state, new_state)

        if leave:
            del self.current[id_]
        else:
            self.current[id_] = after_data

    def _save_current(self):
        for id_, data in self.current_voice():
            if id_ in self.current:
                prev = self.current[id_]
                self._save_state_change(id_, prev, data)
            self.current[id_] = data

    @loop(minutes=1)
    async def periodic_save(self):
        """periodically save the voice stats"""
        await self.bot.wait_until_ready()
        self._save_current()
        logger.info(
            "periodically save the voice stats, next at %s",
            # function transformed by the @loop annotation
            # pylint: disable=no-member
            self.periodic_save.next_iteration,
        )

    @is_owner()
    @command()
    async def save(self, ctx):
        """test cog works"""
        logger.info("saving all current users and resetting info")
        self._save_current()
        await ctx.send("saved :)")

    @command(name="vc")
    async def single_voice_stat(self, ctx, all_=None):
        """get info about the user"""
        user = ctx.author.id
        guild = ctx.channel.guild.id

        rows = None
        with self._database() as db:
            if all_:
                rows = db.execute(
                    """
                    SELECT voicestate, sum(duration) as total
                    FROM History
                    WHERE user = ?
                    GROUP BY voicestate
                    """,
                    (user,),
                ).fetchall()
            else:
                rows = db.execute(
                    """
                    SELECT voicestate, sum(duration) as total
                    FROM History
                    WHERE user = ? and guild = ?
                    GROUP BY voicestate
                    """,
                    (user, guild),
                ).fetchall()
        results = {}
        for row in rows:
            if row["voicestate"] in results:
                results[row["voicestate"]] += row["total"]
            else:
                results[row["voicestate"]] = row["total"]

        in_voice = user in [vc.user for vc in self.current.keys()]

        output = "```\n"
        if in_voice:
            output += "Currently in Voice 🟢\n"
        for state, value in results.items():
            output += f"{state}: {value}\n"
        output += "```"
        await ctx.send(output)

    @is_owner()
    @command(name="kbh")
    async def download_kuibot_history(self, _, date=None):
        kuibot = 639324610772467714
        vctcccc = 620013384049623080
        if date is None:
            date = "2019-11-30"
        date = f"{date.strip()} 00:00:00"
        since = TimeTravel.fromstr(date)
        history = await self.bot.get_history(vctcccc, user_id=kuibot, after=since)

        pats = [
            (re.compile(r"(?P<user>.*?) joined .*?"), "join"),  # pat_join
            (re.compile(r"(?P<user>.*?) left .*?"), "left"),  # pat_left
            (re.compile(r"(?P<user>.*?) moved from .*? to .*?"), "move"),  # pat_move
            (
                re.compile(r"(?P<user>.*?) un(deafen|defeat)ed"),
                "deaf_on",
            ),  # pat_deaf_on
            (
                re.compile(r"(?P<user>.*?) (deafen|defeat)ed"),
                "deaf_off",
            ),  # pat_deaf_off
            (
                re.compile(r"(?P<user>.*?) turned off video"),
                "video_on",
            ),  # pat_video_on
            (
                re.compile(r"(?P<user>.*?) turned on video"),
                "video_off",
            ),  # pat_video_off
            (
                re.compile(r"(?P<user>.*?) started (stream|scream)ing"),
                "stream_on",
            ),  # pat_stream_on
            (
                re.compile(r"(?P<user>.*?) started (stream|scream)ing"),
                "stream_off",
            ),  # pat_stream_off
        ]

        acts = []
        async for msg in history:
            for pat, act in pats:
                if match := pat.match(msg.content):
                    user = match.group("user")
                    timestamp = msg.created_at.timestamp()
                    data = (user, timestamp, act)
                    logger.info(data)
                    acts.append(data)
        with open(calc_path("../historic.json"), "w+") as fp:
            dump(acts, fp)
        logger.info("done dumping")
