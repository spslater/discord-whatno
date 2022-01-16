"""Generate historical data for the server"""
from csv import reader
from json import load

from .helpers import calc_path

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
                if join is None and act == "join":
                    join = event[1]
                elif join is not None and act == "left":
                    info.append(("voice", join, (ets - join)))
                    if deaf:
                        info.append(("deaf", join, (ets - join)))
                        deaf = None
                    if video:
                        info.append(("video", join, (ets - join)))
                        video = None
                    if stream:
                        info.append(("stream", join, (ets - join)))
                        stream = None
                    join = None
                continue

            if act in ("deaf_on", "deaf_off"):
                if deaf is None and act == "deaf_on":
                    deaf = ets
                elif deaf is not None and act == "deaf_off":
                    info.append(("deaf", deaf, (ets - deaf)))
                    deaf = None
                elif join is not None and act == "deaf_off":
                    info.append(("deaf", join, (ets - join)))
                continue

            if act in ("video_on", "video_off"):
                if video is None and act == "video_on":
                    video = event[1]
                elif video is not None and act == "video_off":
                    info.append(("video", video, (event[1] - video)))
                    video = None
                # elif join is not None and act == "video_off":
                #     info.append(("video", join, (event[1] - join)))
                continue

            if act in("stream_on", "stream_off"):
                if stream is None and act == "stream_on":
                    stream = event[1]
                elif stream is not None and act == "stream_off":
                    info.append(("stream", stream, (event[1] - stream)))
                    stream = None
                # elif join is not None and act == "stream_off":
                #     info.append(("stream", join, (event[1] - join)))
                continue
        tsdata[user] = info
    return tsdata, guild, channel

if __name__ == "__main__":
    get_data()
