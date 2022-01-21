"""Generate historical data for the server"""
import re
import logging
from csv import reader
from json import load

from .helpers import calc_path, TimeTravel

logger = logging.getLogger(__name__)

MAX_TIME = 10 * 3600

PATS = [
    (re.compile(r"(?P<user>.*?) joined (?P<channel>.*?)"), "join"),
    (re.compile(r"(?P<user>.*?) left (?P<channel>.*?)"), "left"),
    (re.compile(r"(?P<user>.*?) moved from (?P<ch1>.*?) to (?P<ch2>.*?)"), "move"),
    (re.compile(r"(?P<user>.*?) (deafen|defeat)ed"), "deaf_on"),
    (re.compile(r"(?P<user>.*?) un(deafen|defeat)ed"), "deaf_off"),
    (re.compile(r"(?P<user>.*?) turned on video"), "video_on"),
    (re.compile(r"(?P<user>.*?) turned off video"), "video_off"),
    (re.compile(r"(?P<user>.*?) started (stream|scream)ing"), "stream_on"),
    (re.compile(r"(?P<user>.*?) stopped (stream|scream)ing"), "stream_off"),
]


async def _get_history(bot, start, stop):
    kuibot = 639324610772467714
    vctcccc = 620013384049623080
    start = f"{start.strip()} 00:00:00"
    after = TimeTravel.fromstr(start)
    stop = f"{stop.strip()} 00:00:00"
    before = TimeTravel.fromstr(stop)
    return await bot.get_history(
        vctcccc,
        user_id=kuibot,
        after=after,
        before=before,
    )


async def get_acts(bot, start, stop):
    """get the actions listed by kuibot in voice chat"""
    acts = []
    async for msg in _get_history(bot, start, stop):
        for pat, act in PATS:
            if match := pat.match(msg.content):
                user = match.group("user")
                timestamp = msg.created_at.timestamp()
                data = (user, timestamp, act)
                if act in ("join", "left"):
                    data = (*data, match.group("channel"))
                elif act == "move":
                    data = (*data, match.group("ch1"), match.group("ch2"))
                logger.debug(data)
                acts.append(data)
    return acts


def _spec():
    with open(calc_path("../historic.json")) as fp:
        data = load(fp)

    spec = {}
    for entry in data:
        name = entry[0]
        if name not in spec:
            spec[name] = []
        spec[name].append(entry)
    return spec


def _combos():
    combos = []
    with open(calc_path("users.txt"), "r") as fp:
        for row in reader(fp, delimiter=","):
            combos.append(row)
    return combos


def _full(spec, combos):
    full = {}
    for combo in combos:
        uid = int(combo[0])
        names = combo[1:]
        events = []
        for name in names:
            events.extend(spec[name])
        full[uid] = events
    return full


def _get_cid(guild, name):
    gv1 = 248732519204126721
    channel = [vc.id for vc in guild.voice_channels if vc.name == name]
    return channel[0] if channel else gv1


def get_data(guild):
    """generate data to save to database"""
    gid = guild.id
    full = _full(_spec(), _combos())
    tsdata = {}

    join = None
    deaf = None
    video = None
    stream = None
    for user, events in full.items():
        info = []
        for event in sorted(events, key=lambda x: x[1]):
            ets = event[1]
            act = event[2]

            if act == "move":
                cid = _get_cid(guild, event[3])
                if join is not None:
                    cid = _get_cid(guild, event[3])
                    diff = min(ets - join, MAX_TIME)
                    info.append((cid, "voice", join, diff))
                    if deaf:
                        info.append((cid, "deaf", join, diff))
                        deaf = None
                    if video:
                        info.append((cid, "video", join, diff))
                        video = None
                    if stream:
                        info.append((cid, "stream", join, diff))
                        stream = None
                join = event[1]
                continue

            if act in ("join", "left"):
                if act == "join":
                    join = event[1]
                elif join is not None and act == "left":
                    cid = _get_cid(guild, event[3])
                    diff = min(ets - join, MAX_TIME)
                    info.append((cid, "voice", join, diff))
                    if deaf:
                        info.append((cid, "deaf", join, diff))
                        deaf = None
                    if video:
                        info.append((cid, "video", join, diff))
                        video = None
                    if stream:
                        info.append((cid, "stream", join, diff))
                        stream = None
                    join = None
                continue

            if act in ("deaf_on", "deaf_off"):
                if join is None:
                    deaf = None
                elif act == "deaf_on":
                    deaf = ets
                elif deaf is not None and act == "deaf_off":
                    diff = min(ets - deaf, MAX_TIME)
                    info.append((join[0], "deaf", deaf, diff))
                    deaf = None
                continue

            if act in ("video_on", "video_off"):
                if join is None:
                    video = None
                elif act == "video_on":
                    video = ets
                elif video is not None and act == "video_off":
                    cid = join[0]
                    diff = min(ets - video, MAX_TIME)
                    info.append((join[0], "video", video, diff))
                    video = None
                continue

            if act in ("stream_on", "stream_off"):
                if join is None:
                    stream = None
                elif stream is None and act == "stream_on":
                    stream = ets
                elif stream is not None and act == "stream_off":
                    diff = min(ets - stream, MAX_TIME)
                    info.append((join[0], "stream", stream, diff))
                    stream = None
                continue
        tsdata[user] = info
    return tsdata, gid
