import subprocess
import re
from json import load, dump
from os.path import exists
from math import floor, ceil
from textwrap import fill

from PIL import Image, ImageDraw, ImageFont
from requests import get
from tinydb.table import Document

from .helpers import calc_path, CleanHTML

CARDS_URL = "https://snap.fan/api/cards/"
LOCS_URL = "https://snap.fan/api/locations/"

AGENT = { "User-Agent": "plz let me thru :)" }

def gather_cards():
    print(CARDS_URL)
    pg = get(CARDS_URL, headers=AGENT).json()
    nxt = None
    res = []
    while nxt := pg.get("next"):
        res.extend(pg.get("results", []))
        print(nxt)
        pg = get(nxt, headers=AGENT).json()

    dic = {}
    for c in res:
        c["description"] = CleanHTML().process(c["description"])
        key = c["key"].lower()
        dic[key] = c
        print(key)
    return dic

def gather_locs():
    print(LOCS_URL)
    pg = get(LOCS_URL, headers=AGENT).json()
    dic = {}
    for l in pg.get("data", []):
        l["description"] = CleanHTML().process(l["description"])
        key = l["key"].lower()
        dic[key] = l
        print(key)
    return dic


def getimg(url, loc, name):
    filename = f"{loc}/{name}.webp"
    print(filename)
    location = calc_path(filename)
    if not exists(location):
        with open(location, "wb") as fp:
            res = get(url, stream=True)
            if not res.ok:
                print(res)
            else:
                for bk in res.iter_content(1024):
                    if not bk:
                        break
                    fp.write(bk)
    return filename

def should_update(old, new):
    return (
        old.get("description") != new.get("description") or
        old.get("power") != new.get("power") or
        old.get("cost") != new.get("cost") or
        old.get("displayImageUrl") != new.get("displayImageUrl")
    )

def insert(db, cards, locs, dl=False):
    c_tbl = db.table("cards")
    for key, new in cards.items():
        if old := c_tbl.get(doc_id=key):
            if should_update(old, new):
                new["localImage"] = getimg(new["displayImageUrl"], f"cards", key)
        else:
            new["localImage"] = getimg(new["displayImageUrl"], f"cards", key)
        c_tbl.upsert(Document(new, doc_id=key))

    t_tbl = db.table("locations")
    for key, new in locs.items():
        if old := t_tbl.get(doc_id=key):
            if should_update(old, new):
                new["localImage"] = getimg(new["displayImageUrl"], f"locations", key)
        else:
            new["localImage"] = getimg(new["displayImageUrl"], f"locations", key)
        t_tbl.upsert(Document(new, doc_id=key))

    return db


def combo(card, cw, ch, tt, mult):
    cnw, cnh = cw, floor(ch * mult)

    imgPath = calc_path(card["localImage"])
    crd = Image.open(imgPath)

    img = Image.new("RGBA", (cnw, cnh))

    img1 = ImageDraw.Draw(img)
    img1.rectangle([(0, 0), (cnw, cnh)], fill=(0, 0, 0))
    img.paste(crd, (0, 0))

    mf = ImageFont.truetype(str(calc_path("monofur.ttf")), 36)
    txt = fill(card["description"], width=tt)
    _, _, tw, _ = img1.textbbox((0, 0), txt, font=mf)
    img1.text((((cw - tw) / 2), ch + 10), txt, font=mf, fill=(255, 255, 255))

    comboPath = calc_path(f"combo/{card['localImage']}")
    print(f"combo/{card['localImage']}")
    img.save(comboPath, "webp")


def process_cards(db, dl=False):
    if dl:
        cards = gather_cards()
        locs = gather_locs()

        db = insert(db, cards, locs, dl)

    cw, ch, ct = 615, 615, 27
    lw, lh, lt = 512, 512, 20

    for card in db.table("cards").all():
        combo(card, cw, ch, ct, 1.25)

    for loc in db.table("locations").all():
        combo(loc, lw, lh, lt, 1.35)

    return db
