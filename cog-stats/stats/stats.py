"""Stats Bot for Voice and Messages"""
import logging
import re
from collections import namedtuple
from json import dump, dumps
from os import getenv

from discord import ChannelType, HTTPException, NotFound
from discord.ext.commands import Cog, command, group, is_owner
from discord.ext.tasks import loop
from discord.utils import escape_markdown
from dotenv import load_dotenv

from .database import StatDB
from .helpers import TimeTravel, calc_path, sec_to_human
from .historic import get_acts, get_data

logger = logging.getLogger(__name__)

STATES = ["voice", "mute", "deaf", "stream", "video"]

VoiceCon = namedtuple("VoiceCon", ["user", "guild", "channel"])
VoiceState = namedtuple("VoiceState", ["state", "time"])
VoiceDiff = namedtuple("VoiceDiff", ["voice", "mute", "deaf", "stream", "video"])
Voice = namedtuple("Voice", ["voice", "mute", "deaf", "stream", "video"])

MSG_INSERT = "INSERT OR IGNORE INTO Message VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"
TEXT_CHANNELS = (
    ChannelType.text,
    ChannelType.private,
    ChannelType.group,
    ChannelType.news,
    ChannelType.public_thread,
    ChannelType.private_thread,
)


ROLLING = (90,)

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
        return StatDB(self.database_file, readonly)

    def cog_unload(self):
        self._save_current()
        # function transformed by the @loop annotation
        # pylint: disable=no-member
        self.periodic_save.cancel()
        self.periodic_compress.cancel()

    #########################
    ### Voice Processing  ###
    #########################

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

        if inserts:
            logger.debug("db inserts: %s", inserts)
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
        logger.info("%s: %s", id_, self.current)
        prev_state = self.current[id_]
        new_state = self._start_state(state, now)
        return self._save_state_change(id_, prev_state, new_state, now)

    @staticmethod
    def _set_timestamp(current, new_ts):
        voice = VoiceState("voice", new_ts) if current.voice else None
        mute = VoiceState("mute", new_ts) if current.mute else None
        deaf = VoiceState("deaf", new_ts) if current.deaf else None
        stream = VoiceState("stream", new_ts) if current.stream else None
        video = VoiceState("video", new_ts) if current.video else None
        return Voice(voice=voice, mute=mute, deaf=deaf, stream=stream, video=video)

    @Cog.listener("on_voice_state_update")
    async def voice_change(self, member, before, after):
        """log the new voice status of a user"""
        now = TimeTravel.timestamp()

        self._log_voice_change(member, before, after)

        join = before.channel is None
        leave = after.channel is None
        move = not join and not leave and before.channel.id != after.channel.id

        if join and leave:
            return

        guild = before.channel.guild.id if not join else after.channel.guild.id
        if move:
            b_id = VoiceCon(member.id, guild, before.channel.id)
            a_id = VoiceCon(member.id, guild, after.channel.id)
            # "leave" previous channel
            updated = self._get_new_state(b_id, after, now)
            del self.current[b_id]
            # "join" new channel
            self.current[a_id] = self._set_timestamp(updated, now)
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
        current = self.current_voice()
        for id_, data in current:
            if id_ in self.current:
                prev = self.current[id_]
                self._update_state(id_, prev, data, now)
            else:
                self.current[id_] = data
        return bool(current)

    @loop(seconds=5)
    async def periodic_save(self):
        """periodically save the voice stats"""
        await self.bot.wait_until_ready()
        if self._save_current():
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
            val += f"{d} day{'s' if d != 1 else ''}"
        if d and (h or m or s):
            val += ", "
        if h:
            val += f"{h} hr{'s' if h != 1 else ''}"
        if h and (m or s):
            val += ", "
        if m:
            val += f"{m} min{'s' if m != 1 else ''}"
        if m and s:
            val += ", "
        if s:
            val += f"{s} sec{'s' if s != 1 else ''}"
        return val

    async def _generate_voice_output(self, results, early, stats, in_voice, user, guild):
        member = await guild.fetch_member(user)
        e_time = f" - past {ROLLING[0]} days"
        if early:
            e_time = f" - since {TimeTravel.pretty_ts(early)}"
        output = f"```\n{member.nick or member.name}{e_time}\n"
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

    async def _user_stat(self, user, guild, alltime=False):
        rows = None
        logger.debug("get all time stats: %s", alltime)
        since = TimeTravel.tsinpast(*ROLLING)
        with self._database() as db:
            if alltime:
                rows = db.execute(
                    """
                    SELECT voicestate, sum(duration) as total, min(starttime) as early
                    FROM History
                    WHERE user = ? and guild = ?
                    GROUP BY voicestate
                    """,
                    (user, guild.id),
                ).fetchall()
            else:
                rows = db.execute(
                    """
                    SELECT voicestate, sum(duration) as total
                    FROM History
                    WHERE user = ? and guild = ? and starttime > ?
                    GROUP BY voicestate
                    """,
                    (user, guild.id, since),
                ).fetchall()
        results = {}
        early = None
        for row in rows:
            logger.debug("checking row: %s", tuple(row))
            if alltime and (early is None or row["early"] < early):
                early = row["early"]
            if row["voicestate"] in results:
                results[row["voicestate"]] += row["total"]
            else:
                results[row["voicestate"]] = row["total"]
        logger.debug("early time: %s", early)

        in_voice = user in [vc.user for vc in self.current]
        stats = None
        for key, value in self.current.items():
            if key.user == user:
                stats = value
                break

        return await self._generate_voice_output(results, early, stats, in_voice, user, guild)

    @group(name="vc")
    async def voice_stat(self, ctx):
        """get info about the user"""
        if ctx.invoked_subcommand:
            return

        output = await self._user_stat(ctx.author.id, ctx.channel.guild, alltime=False)
        await ctx.send(output)

    @staticmethod
    async def _get_member(guild, user):
        pat = re.compile(r".*?" + user + r".*?", flags=re.IGNORECASE)
        async for member in guild.fetch_members(limit=None):
            if member.nick and pat.search(member.nick):
                return member.id
            if member.name and pat.search(member.name):
                return member.id
        return None

    @voice_stat.command(name="all")
    async def voice_stat_user_all(self, ctx):
        """get info about any user by id"""
        logger.info("geting specific user vc data for all time")
        output = await self._user_stat(ctx.author.id, ctx.channel.guild, alltime=True)
        await ctx.send(output)

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

        output = await self._user_stat(user_id, ctx.channel.guild)
        await ctx.send(output)

    @voice_stat.command(name="top")
    async def voice_top(self, ctx, all_=None):
        """Get top 10 users from each guild"""
        logger.info("getting top users for guild")
        async with ctx.typing():
            guild = ctx.channel.guild

            rows = []
            since = TimeTravel.tsinpast(*ROLLING)
            with self._database() as db:
                if all_:
                    early = db.execute(
                        """
                        SELECT min(starttime) as early
                        FROM History
                        GROUP BY starttime
                        LIMIT 1
                        """
                    ).fetchone()['early']
                    rows = db.execute(
                        """
                        SELECT user, sum(duration) as total
                        FROM History
                        WHERE guild = ? AND voicestate = "voice"
                        GROUP BY user
                        ORDER BY total DESC
                        LIMIT 10
                        """,
                        (guild.id,)
                    ).fetchall()
                else:
                    rows = db.execute(
                        """
                        SELECT user, sum(duration) as total
                        FROM History
                        WHERE guild = ? AND voicestate = "voice" AND starttime > ?
                        GROUP BY user
                        ORDER BY total DESC
                        LIMIT 10
                        """,
                        (guild.id,since,),
                    ).fetchall()
            users = [(r["user"], r["total"]) for r in rows]
            output = "```\n"
            if not all_:
                output += f"Last {ROLLING[0]} days\n"
            else:
                output += f"Since {TimeTravel.pretty_ts(early)}\n"
            for idx, (user, value) in enumerate(users):
                try:
                    member = await guild.fetch_member(user)
                except NotFound:
                    name = f"(user left) {user}"
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
            db.executemany("INSERT INTO History VALUES (?,?,?,?,?,?,?,?)", entries)

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

    #########################
    ### MessageProcessing ###
    #########################

    def _get_message_author(self, mid):
        if mid:
            with self._database() as db:
                rows = db.execute(
                    """SELECT user FROM Message WHERE message = ? LIMIT 1;""", (mid,)
                )
                res = rows.fetchone()
                if res:
                    return int(res["user"])
        return None

    @staticmethod
    def _get_message_data(message):
        text = None
        attach = None
        embed = None
        ref = None
        if message.content:
            text = escape_markdown(message.content)
        if message.attachments:
            attach = dumps([a.url for a in message.attachments])
        if message.embeds:
            embed = dumps([e.to_dict() for e in message.embeds])
        if message.reference:
            ref = message.reference.message_id

        return text, attach, embed, ref

    @staticmethod
    def _get_paylaod_data(msgdict):
        text = None
        attach = None
        embed = None
        ref = None
        if msgdict.get("content"):
            text = escape_markdown(msgdict["content"])
        if msgdict.get("attachments"):
            attach = dumps([a["url"] for a in msgdict["attachments"]])
        if msgdict.get("embeds"):
            embed = dumps(msgdict["embeds"])
        if msgdict.get("referenced_message"):
            ref = msgdict["referenced_message"]["id"]

        return text, attach, embed, ref

    async def _proc_message(self, tstp, event, message=None, payload=None, hist=False):
        mid = None
        aid = None
        gid = None
        cid = None
        # tstp
        # event
        text = None
        attach = None
        embed = None
        ref = None
        # hist
        tsc = None

        if message:
            mid = message.id
            gid = message.guild.id
            cid = message.channel.id
        else:
            try:
                mid = payload.message_id
            except AttributeError:
                pass
            gid = payload.guild_id
            cid = payload.channel_id

        if event == "create":
            aid = message.author.id
            text, attach, embed, ref = self._get_message_data(message)
            tstp = message.created_at.timestamp()

        if event == "edit":
            message = message or await (
                await self.bot.fetch_channel(cid)
            ).fetch_message(mid)
            if message:
                aid = message.author.id
                text, attach, embed, ref = self._get_message_data(message)
                tstp = (
                    message.edited_at.timestamp()
                    if message.edited_at
                    else (
                        payload.data.get("edited_timestamp", tstp) if payload else tstp
                    )
                )
            else:
                aid = self._get_message_author(mid)
                text, attach, embed, ref = self._get_payload_data(payload.data)
                if payload.data.get("edited_timestamp"):
                    tstp = TimeTravel.tsfromdiscord(
                        payload.data.get("edited_timestamp")
                    )

        tsc = TimeTravel.sqlts(tstp)

        if event == "delete":
            if mid is None:
                mids = {}
                for tmid in payload.message_ids:
                    cached = [
                        msg.author.id
                        for msg in payload.cached_messages
                        if msg.id == tmid
                    ]
                    mids[tmid] = cached[0] if cached else self._get_message_author(tmid)
                entries = []
                for tmid, taid in mids.items():
                    entries.append(
                        (
                            tmid,
                            taid,
                            gid,
                            cid,
                            tstp,
                            event,
                            text,
                            attach,
                            embed,
                            ref,
                            hist,
                            tsc,
                        )
                    )
                return entries
            aid = (
                payload.cached_message.author.id
                if payload.cached_message
                else self._get_message_author(mid)
            )

        return (mid, aid, gid, cid, tstp, event, text, attach, embed, ref, hist, tsc)

    @Cog.listener("on_message")
    async def process_on_message(self, message):
        """Process message details"""
        tstp = TimeTravel.timestamp()
        data = await self._proc_message(tstp, "create", message=message)

        logger.debug(
            "message %s created by %s: %s, %s, %s",
            data[0],
            data[1],
            len(message.content),
            len(message.attachments),
            len(message.embeds),
        )

        with self._database() as db:
            db.execute(MSG_INSERT, data)

    @Cog.listener("on_raw_message_edit")
    async def process_on_message_edit(self, payload):
        """process message on edit"""
        tstp = TimeTravel.timestamp()
        data = await self._proc_message(tstp, "edit", payload=payload)

        logger.debug(
            "message %s edited to: %s",
            payload.message_id,
            payload.data.get("content"),
        )

        with self._database() as db:
            db.execute(MSG_INSERT, data)

    @Cog.listener("on_raw_message_delete")
    async def process_on_message_delete(self, payload):
        """process message on delete"""
        tstp = TimeTravel.timestamp()
        data = await self._proc_message(tstp, "delete", payload=payload)

        logger.debug("message %s deleted", payload.message_id)

        with self._database() as db:
            db.execute(MSG_INSERT, data)

    @Cog.listener("on_raw_bulk_message_delete")
    async def process_on_message_bulk_delete(self, payload):
        """process message on bulk delete"""
        tstp = TimeTravel.timestamp()
        entries = await self._proc_message(tstp, "delete", payload=payload)

        logger.debug("bulk message delete: %s", payload.message_ids)

        with self._database() as db:
            db.executemany(MSG_INSERT, entries)

    @group(name="txt")
    async def message_stat(self, ctx):
        """get info about the user message"""
        if ctx.invoked_subcommand:
            return

    @message_stat.command("ch")
    async def get_past_messages_channel(self, ctx, channel):
        """gather previous messages"""
        tstp = TimeTravel.timestamp()
        try:
            ckch = await self.bot.fetch_channel(int(channel))
        except HTTPException:
            await ctx.send(f"unable to access channel with id {channel}")
            return
        entries = []
        if ckch is None:
            await ctx.send(f"unable to find channel with id {channel}")
            return
        logger.debug("downloading messages for channel %s", ckch.name)
        total = 0
        msg = await ctx.send(f"{ckch.name}: downloaded {total}")
        async for message in ckch.history(limit=None, oldest_first=True):
            if message.created_at:
                data = await self._proc_message(
                    tstp,
                    "create",
                    message=message,
                    hist=True,
                )
                entries.append(data)
            if message.edited_at:
                data = await self._proc_message(
                    tstp,
                    "edit",
                    message=message,
                    hist=True,
                )
                entries.append(data)
            total += 1
            if not total % 100:
                await msg.edit(f"{ckch.name}: downloaded {total}")

        logger.debug("hist for %s: %s", ckch.name, len(entries))
        with self._database() as db:
            db.executemany(MSG_INSERT, entries)

        await msg.edit(f"{ckch.name}: updated {len(entries)}")

    @message_stat.command("gd")
    async def get_past_messages_guild(self, ctx, guild):
        """gather messages from guild text channels"""
        try:
            ckgd = await self.bot.fetch_guild(int(guild))
        except HTTPException:
            await ctx.send(f"unable to access guild with id {guild}")
            return
        if ckgd is None:
            await ctx.send(f"unable to find guild with id {guild}")
            return

        for ckch in await ckgd.fetch_channels():
            if ckch.type in TEXT_CHANNELS:
                await self.get_past_messages_channel(ctx, ckch.id)

        await ctx.send(f"all downloaded for guild {ckgd.name}")
