"""Stats Bot for Voice and Messages"""
import logging
import re
from collections import namedtuple
from json import dump
from os import getenv

from discord import NotFound
from discord.ext.commands import Cog, command, group, is_owner
from discord.ext.tasks import loop
from dotenv import load_dotenv

from .helpers import calc_path, sec_to_human, TimeTravel
from .database import VoiceDB
from .historic import get_acts, get_data

logger = logging.getLogger(__name__)

STATES = ["voice", "mute", "deaf", "stream", "video"]

VoiceCon = namedtuple("VoiceCon", ["user", "guild", "channel"])
VoiceState = namedtuple("VoiceState", ["state", "time"])
VoiceDiff = namedtuple("VoiceDiff", ["voice", "mute", "deaf", "stream", "video"])
Voice = namedtuple("Voice", ["voice", "mute", "deaf", "stream", "video"])


class StatsCog(Cog):
    """Voice Stats Cog"""

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
        self.periodic_compress.start()

    def _database(self, readonly=False):
        return VoiceDB(self.database_file, readonly)

    def cog_unload(self):
        self._save_current()
        # function transformed by the @loop annotation
        # pylint: disable=no-member
        self.periodic_save.cancel()
        self.periodic_compress.cancel()

    @Cog.listener("on_ready")
    async def load_current(self):
        """Load current voice users into memory"""
        self._save_current()

    @staticmethod
    def _start_state(state, timestamp):
        return Voice(
            voice=VoiceState("voice", timestamp),
            mute=VoiceState("mute", timestamp) if state.self_mute else None,
            deaf=VoiceState("deaf", timestamp) if state.self_deaf else None,
            stream=VoiceState("stream", timestamp) if state.self_stream else None,
            video=VoiceState("video", timestamp) if state.self_video else None,
        )

    @staticmethod
    def _diff_state(first, second, now):
        voicediff = second.voice.time - first.voice.time

        mutediff = None
        if second.mute is not None and first.mute is not None:
            mutediff = second.mute.time - first.mute.time
        elif second.mute is None and first.mute is not None:
            mutediff = now - first.mute.time

        deafdiff = None
        if second.deaf is not None and first.deaf is not None:
            deafdiff = second.deaf.time - first.deaf.time
        elif second.deaf is None and first.deaf is not None:
            deafdiff = now - first.deaf.time

        streamdiff = None
        if second.stream is not None and first.stream is not None:
            streamdiff = second.stream.time - first.stream.time
        elif second.stream is None and first.stream is not None:
            streamdiff = now - first.stream.time

        videodiff = None
        if second.video is not None and first.video is not None:
            videodiff = second.video.time - first.video.time
        elif second.video is None and first.video is not None:
            videodiff = now - first.video.time

        return VoiceDiff(voicediff, mutediff, deafdiff, streamdiff, videodiff)

    def current_voice(self):
        """setup current users in voice"""
        now = TimeTravel.timestamp()
        current = []
        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                for user, state in channel.voice_states.items():
                    id_ = VoiceCon(user, guild.id, channel.id)
                    data = self._start_state(state, now)
                    current.append((id_, data))
        return current

    @staticmethod
    def _log_voice_change(member, before, after):
        before_info = (
            before.channel.id if before.channel else None,
            before.channel.name if before.channel else None,
            before.self_mute,
            before.self_deaf,
            before.self_stream,
            before.self_video,
        )
        after_info = (
            after.channel.id if after.channel else None,
            after.channel.name if after.channel else None,
            after.self_mute,
            after.self_deaf,
            after.self_stream,
            after.self_video,
        )
        logger.debug(
            "%s (%s): %s -> %s",
            member.name,
            member.id,
            before_info,
            after_info,
        )

    def _check_entry(self, uid, cid, state, tss):
        with self._database() as db:
            states = db.execute(
                """
                SELECT *
                FROM History
                WHERE user = ?
                  AND channel = ?
                  AND voicestate = ?
                  AND h_time = ?
                """,
                (uid, cid, state, tss),
            ).fetchone()
        return bool(states)

    def _update_state(self, id_, before, after, now):
        diff = self._diff_state(before, after, now)

        uid = id_.user
        gid = id_.guild
        cid = id_.channel

        updates = []
        inserts = []
        if diff.voice is not None:
            bts = before.voice.time
            tsc = TimeTravel.sqlts(bts)
            if self._check_entry(uid, cid, "voice", tsc):
                updates.append((diff.voice, uid, cid, "voice", tsc))
            else:
                inserts.append((uid, gid, cid, "voice", bts, diff.voice, False, tsc))

        if diff.mute is not None:
            bts = before.mute.time
            tsc = TimeTravel.sqlts(bts)
            if self._check_entry(uid, cid, "mute", tsc):
                updates.append((diff.mute, uid, cid, "mute", tsc))
            else:
                inserts.append((uid, gid, cid, "mute", bts, diff.mute, False, tsc))

        if diff.deaf is not None:
            bts = before.deaf.time
            tsc = TimeTravel.sqlts(bts)
            if self._check_entry(uid, cid, "deaf", tsc):
                updates.append((diff.deaf, uid, cid, "deaf", tsc))
            else:
                inserts.append((uid, gid, cid, "deaf", bts, diff.deaf, False, tsc))

        if diff.stream is not None:
            bts = before.stream.time
            tsc = TimeTravel.sqlts(bts)
            if self._check_entry(uid, cid, "stream", tsc):
                updates.append((diff.stream, uid, cid, "stream", tsc))
            else:
                inserts.append((uid, gid, cid, "stream", bts, diff.stream, False, tsc))

        if diff.video is not None:
            bts = before.video.time
            tsc = TimeTravel.sqlts(bts)
            if self._check_entry(uid, cid, "video", tsc):
                updates.append((diff.video, uid, cid, "video", tsc))
            elif diff.video is not None:
                inserts.append((uid, gid, cid, "video", bts, diff.video, False, tsc))

        if updates:
            logger.debug("db updates: %s", updates)
        if inserts:
            logger.debug("db inserts: %s", inserts)

        with self._database() as db:
            db.executemany(
                """
                UPDATE History
                SET duration = ?
                WHERE user = ?
                  AND channel = ?
                  AND voicestate = ?
                  AND h_time = ?
                """,
                updates,
            )
        with self._database() as db:
            db.executemany("INSERT INTO History VALUES (?,?,?,?,?,?,?,?)", inserts)

    @staticmethod
    def _new_state(status, before, after):
        bstate = getattr(before, status)
        astate = getattr(after, status)
        nstate = bstate
        if bstate is None and astate is not None:
            nstate = astate
        elif bstate is not None and astate is None:
            nstate = None
        return nstate

    def _save_state_change(self, id_, before, after, now):
        self._update_state(id_, before, after, now)

        voice = self._new_state("voice", before, after)
        mute = self._new_state("mute", before, after)
        deaf = self._new_state("deaf", before, after)
        stream = self._new_state("stream", before, after)
        video = self._new_state("video", before, after)

        return Voice(voice=voice, mute=mute, deaf=deaf, stream=stream, video=video)

    def _get_new_state(self, id_, state, now):
        prev_state = self.current[id_]
        new_state = self._start_state(state, now)
        return self._save_state_change(id_, prev_state, new_state, now)

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
        if before.channel and after.channel and before.channel.id != after.channel.id:
            b_id = VoiceCon(member.id, guild, before.channel.guild.id)
            a_id = VoiceCon(member.id, guild, after.channel.guild.id)
            # "leave" previous channel
            updated = self._get_new_state(b_id, after, now)
            del self.current[b_id]
            # "join" new channel
            self.current[a_id] = updated
            return

        channel = before.channel.id if not join else after.channel.id
        id_ = VoiceCon(member.id, guild, channel)

        if join:
            self.current[id_] = self._start_state(after, now)
            return

        updated = self._get_new_state(id_, after, now)

        if leave:
            del self.current[id_]
        else:
            self.current[id_] = updated

    def _save_current(self):
        now = TimeTravel.timestamp()
        for id_, data in self.current_voice():
            if id_ in self.current:
                prev = self.current[id_]
                self._update_state(id_, prev, data, now)
            else:
                self.current[id_] = data

    @loop(seconds=5)
    async def periodic_save(self):
        """periodically save the voice stats"""
        await self.bot.wait_until_ready()
        self._save_current()
        logger.debug(
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

    @staticmethod
    def _display_duration(value):
        d, h, m, s = sec_to_human(value)
        val = ""
        if d:
            val += f"{d} day{'s' if d > 1 else ''}"
        if d and (h or m or s):
            val += ", "
        if h:
            val += f"{h} hr{'s' if h > 1 else ''}"
        if h and (m or s):
            val += ", "
        if m:
            val += f"{m} min{'s' if m > 1 else ''}"
        if m and s:
            val += ", "
        if s:
            val += f"{s} sec{'s' if s > 1 else ''}"
        return val

    def _generate_voice_output(self, results, stats, in_voice):
        output = "```\n"
        for state, value in results.items():
            val = self._display_duration(value)
            green = (
                " 🟢"
                if in_voice and (getattr(stats, state, False) or state == "voice")
                else ""
            )
            output += f"{state}{green}: {val}\n"
        output += "```"
        return output

    def _user_stat(self, user, guild):
        rows = None
        with self._database() as db:
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

        in_voice = user in [vc.user for vc in self.current]
        stats = None
        for key, value in self.current.items():
            if key.user == user:
                stats = value
                break

        return self._generate_voice_output(results, stats, in_voice)

    @group(name="vc")
    async def voice_stat(self, ctx):
        """get info about the user"""
        if ctx.invoked_subcommand:
            return

        output = self._user_stat(ctx.author.id, ctx.channel.guild.id)
        await ctx.send(output)

    @staticmethod
    async def _get_member(guild, user):
        pat = re.compile(r".*?" + user + r".*?")
        for member in guild.fetch_members(limit=None):
            if member.nick and pat.search(member.nick):
                return member.id
            if member.name and pat.search(member.name):
                return member.id
        return None

    @voice_stat.command(name="user")
    async def voice_stat_user(self, ctx, user, *extra):
        """get info about any user by id"""
        logger.info("geting specific user vc data")
        user_id = None
        try:
            # bad if user's name is an number
            # but that's their fault
            user_id = int(user)
        except ValueError:
            user = (user + " " + " ".join(extra)).strip()
            user_id = await self._get_member(ctx.channel.guild, user)

        if user_id is None:
            await ctx.send("sorry, no user with that name found")
            return

        output = self._user_stat(user_id, ctx.channel.guild.id)
        await ctx.send(output)

    @voice_stat.command(name="top")
    async def voice_top(self, ctx, all_=None):
        """Get top 10 users from each guild"""
        logger.info("getting top users for guild")
        async with ctx.typing():
            guild = ctx.channel.guild

            rows = []
            with self._database() as db:
                if all_:
                    rows = db.execute(
                        """
                        SELECT user, sum(duration) as total
                        FROM History
                        WHERE voicestate = "voice"
                        GROUP BY user
                        ORDER BY total DESC
                        LIMIT 10
                        """,
                    ).fetchall()
                else:
                    rows = db.execute(
                        """
                        SELECT user, sum(duration) as total
                        FROM History
                        WHERE guild = ? AND voicestate = "voice"
                        GROUP BY user
                        ORDER BY total DESC
                        LIMIT 10
                        """,
                        (guild.id,),
                    ).fetchall()
            users = [(r["user"], r["total"]) for r in rows]
            output = "```\n"
            for idx, (user, value) in enumerate(users):
                try:
                    member = await guild.fetch_member(user)
                except NotFound:
                    name = user
                else:
                    name = member.nick or member.name
                val = self._display_duration(value)
                output += f"{idx+1}. {name}: {val}\n"
            output += "```"
            await ctx.send(output)

    @voice_stat.group("hist")
    async def historic_data(self, ctx):
        """Collect and add historic data"""
        if ctx.invoked_subcommand:
            return

    async def _get_kuibot_history(self, start, stop):
        kuibot = 639324610772467714
        vctcccc = 620013384049623080
        start = f"{start.strip()} 00:00:00"
        after = TimeTravel.fromstr(start)
        stop = f"{stop.strip()} 00:00:00"
        before = TimeTravel.fromstr(stop)
        return await self.bot.get_history(
            vctcccc,
            user_id=kuibot,
            after=after,
            before=before,
        )

    @is_owner()
    @historic_data.command(name="collect")
    async def download_kuibot_history(self, ctx, start="2019-11-30", stop="2022-01-15"):
        """Download historical kuibot messages"""
        logger.info("collecting kuibot messages")
        acts = await get_acts(self.bot, start, stop)
        with open(calc_path("../historic.json"), "w+") as fp:
            dump(acts, fp)

        logger.info("done dumping")
        await ctx.message.add_reaction("👍")

    @is_owner()
    @historic_data.command(name="add")
    async def add_kuibot_history(self, ctx):
        """Load historical data into the database"""
        logger.info("adding historic data")
        tsdata, gid = get_data(ctx.channel.guild)

        entries = []
        for user, data in tsdata.items():
            logger.info("%s: #data %s", user, len(data))
            user_entries = []
            for sin in data:
                tsc = TimeTravel.sqlts(sin[-1])
                entry = (user, gid, *sin, True, tsc)
                user_entries.append(entry)
            logger.debug("num entries: %s", len(user_entries))
            entries.extend(user_entries)

        logger.info("adding %s to db", len(entries))
        with self._database() as db:
            db.executemany("INSERT INTO History VALUES (?,?,?,?,?,?,?)", entries)

        await ctx.message.add_reaction("👍")

    def _compress_database(self):
        with self._database() as db:
            max_durs = db.execute(
                """
                SELECT user, channel, voicestate, h_time, max(duration) as maxdur
                FROM History
                GROUP BY user, channel, voicestate, h_time
                """
            ).fetchall()
        deletes = []
        for max_dur in max_durs:
            deletes.append(
                (
                    max_dur["user"],
                    max_dur["channel"],
                    max_dur["voicestate"],
                    max_dur["h_time"],
                    max_dur["maxdur"],
                )
            )
        with self._database() as db:
            db.executemany(
                """
                DELETE FROM History
                WHERE
                    user = ? AND
                    channel = ? AND
                    voicestate = ? AND
                    h_time = ? AND
                    duration != ?
                """,
                deletes,
            )

    @loop(hours=(7 * 24))
    async def periodic_compress(self):
        """periodically compress that database of duplicate data"""
        await self.bot.wait_until_ready()
        self._compress_database()
        logger.debug(
            "periodically compress that database of duplicate data, next at %s",
            # function transformed by the @loop annotation
            # pylint: disable=no-member
            self.periodic_compress.next_iteration,
        )

    @is_owner()
    @historic_data.command("compress")
    async def compress_duplicates(self, ctx):
        """Remove duplicate duration entries"""
        logger.info("removing duplicate duration entries")
        self._compress_database()
        await ctx.message.add_reaction("👍")
