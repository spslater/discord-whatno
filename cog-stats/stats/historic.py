"""Generate historical data for the server"""
from csv import reader
from json import load

from .helpers import calc_path

MAX_TIME = 10*3600


def get_data():
    guild = 248732519204126720
    channel = 248732519204126721

    with open(calc_path("../historic.json")) as fp:
        data = load(fp)

    spec = {}
    for entry in data:
        name = entry[0]
        if name not in spec:
            spec[name] = []
        spec[name].append(entry)

    combos = []
    with open(calc_path("users.txt"), "r") as fp:
        for row in reader(fp, delimiter=","):
            combos.append(row)

    full = {}
    for combo in combos:
        uid = int(combo[0])
        names = combo[1:]
        events = []
        for name in names:
            events.extend(spec[name])
        full[uid] = events

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

            if act in ("join", "left"):
                if act == "join":
                    join = event[1]
                elif join is not None and act == "left":
                    diff = min(ets-join, MAX_TIME)
                    info.append(("voice", join, diff))
                    if deaf:
                        info.append(("deaf", join, diff))
                        deaf = None
                    if video:
                        info.append(("video", join, diff))
                        video = None
                    if stream:
                        info.append(("stream", join, diff))
                        stream = None
                    join = None
                continue

            if act in ("deaf_on", "deaf_off"):
                if join is None:
                    deaf = None
                elif act == "deaf_on":
                    deaf = ets
                elif deaf is not None and act == "deaf_off":
                    diff = min(ets-deaf, MAX_TIME)

                    info.append(("deaf", deaf, diff))
                    deaf = None
                continue

            if act in ("video_on", "video_off"):
                if join is None:
                    video = None
                elif act == "video_on":
                    video = ets
                elif video is not None and act == "video_off":
                    diff = min(ets-video, MAX_TIME)
                    info.append(("video", video, diff))
                    video = None
                continue

            if act in("stream_on", "stream_off"):
                if join is None:
                    stream = None
                elif stream is None and act == "stream_on":
                    stream = ets
                elif stream is not None and act == "stream_off":
                    diff = min(ets-stream, MAX_TIME)
                    info.append(("stream", stream, diff))
                    stream = None
                continue
        tsdata[user] = info
    return tsdata, guild, channel

if __name__ == "__main__":
    get_data()
