import subprocess
import re
from json import load, dump
from os.path import exists
from math import floor, ceil
from textwrap import fill

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from requests import get
from tinydb.table import Document

BASE = "https://snap.fan"


def getsoup(url):
    cmd = f'curl "{url}" -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/111.0" -H "Cookie: csrftoken=7BZuoxRp4GHtGQjRgwLcEoMY6uL5Ec7CHbS1pIgdA23eXJx7cLG0WchZYy5jiqwu; dnsDisplayed=undefined; ccpaApplies=false; signedLspa=undefined; permutive-id=6c6e39d4-37ce-46a5-8ed1-2aa3bc00ffee; ccpaUUID=aed8919b-eca9-4a8d-9a1e-0bd069922ec9; consentUUID=40d3cd6e-d154-4481-a8f2-9ef35db89927; messages=.eJyLjlaKj88qzs-Lz00tLk5MT1XSMdAxMtVRCi5NTgaKpJXm5FQqFGem56WmKGTmKSQWKxSnJubpKcXqDCmdsQB0kU-V:1pT5RW:dQ3prHvXu98REezg9GheRijrZqTFQw8IqcwC7r7XyRM"'
    res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    print(res.returncode)
    print(res.stdout)
    soup = BeautifulSoup(res.stdout, "html.parser")
    return soup


def gather(URL):
    info = []
    while True:
        soup = getsoup(URL)

        cards = (
            soup.find("div", {"class": "l-sidebar__main"})
            .find("div", {"class": "row"})
            .find_all("div", recursive=False)
        )

        for card in cards:
            url = card.find("a", {"class": "d-block"}).get("href")
            name = (
                getsoup(f"{BASE}{url}")
                .find("title")
                .getText()
                .replace(" - Marvel Snap", "")
                .replace("Marvel Snap ", "")
                .replace(" - snap.fan", "")
            )
            img = card.find("img").get("src")
            txt = card.find("div", {"class": "small"}).getText()
            info.append((f"{BASE}{url}", name, txt, img))

        nxt = soup.find("div", {"class": "pagination__control--next"})
        if not nxt:
            break
        nxt = nxt.find_all("a")
        if not nxt:
            break
        URL = f"{BASE}{nxt[-1]['href']}"
    return info


def getimg(url, loc, name):
    name = re.sub(r"[^a-zA-Z0-9]", "", name)
    filename = f"{loc}/{name}.webp"
    if not exists(filename):
        with open(filename, "wb") as fp:
            res = get(url, stream=True)
            if not res.ok:
                print(res)
            else:
                for bk in res.iter_content(1024):
                    if not bk:
                        break
                    fp.write(bk)
    return filename


def insert(db, cards, locs):
    c_tbl = db.table("cards")
    for i in cards:
        idx = re.sub(r"[^a-zA-Z0-9]", "", i[1].lower())
        c_tbl.upsert(
            Document(
                {
                    "url": i[0],
                    "name": i[1],
                    "txt": i[2],
                    "img": getimg(i[3], "cards", i[1]),
                },
                doc_id=idx,
            )
        )

    t_tbl = db.table("locations")
    for i in locs:
        idx = re.sub(r"[^a-zA-Z0-9]", "", i[1].lower())
        t_tbl.upsert(
            Document(
                {
                    "url": i[0],
                    "name": i[1],
                    "txt": i[2],
                    "img": getimg(i[3], "locations", i[1]),
                },
                doc_id=idx,
            )
        )

    return db


# def trans(im):
#     im = im.convert('RGBA') #.convert('P', palette=Image.ADAPTIVE, colors=255)
#     alpha = im.getchannel('A')
#     mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
#     im.paste(255, mask)
#     im.info['transparency'] = 255
#     return im, mask


def combo(card, cw, ch, tt, mult):
    cnw, cnh = cw, floor(ch * mult)

    crd = Image.open(card["img"])

    img = Image.new("RGBA", (cnw, cnh))

    img1 = ImageDraw.Draw(img)
    img1.rectangle([(0, 0), (cnw, cnh)], fill=(0, 0, 0))
    img.paste(crd, (0, 0))

    mf = ImageFont.truetype("monofur.ttf", 36)
    txt = fill(card["txt"], width=tt)
    _, _, tw, _ = img1.textbbox((0, 0), txt, font=mf)
    img1.text((((cw - tw) / 2), ch + 10), txt, font=mf, fill=(255, 255, 255))

    img.save(f"combo/{card['img']}", "webp")


def process_cards(db, dl=False):
    if dl:
        cards = gather(f"{BASE}/cards/")
        locs = gather(f"{BASE}/locations/")

        db = insert(db, cards, locs)

    cw, ch, ct = 615, 615, 27
    lw, lh, lt = 512, 512, 20

    for card in db.table("cards").all():
        combo(card, cw, ch, ct, 1.25)

    for loc in db.table("locations").all():
        combo(loc, lw, lh, lt, 1.35)

    return db

