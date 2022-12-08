import subprocess
import re
from bs4 import BeautifulSoup
from requests import get
from json import load, dump
from os.path import exists
from PIL import Image, ImageDraw, ImageFont
from math import floor, ceil
from textwrap import fill

BASE = "https://snap.fan"

def getsoup(url):
    cmd = f'curl "{url}" -A "foobar"'
    res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    soup = BeautifulSoup(res.stdout, "html.parser")
    return soup

def gather(URL):
    info = []
    while True:
        soup = getsoup(URL)

        cards = soup.find("div", {"class":"l-sidebar__main"}) \
            .find("div", {"class": "row"}) \
            .find_all("div", recursive=False)

        for card in cards:
            url = card.find("a", {"class":"d-block"}).get("href")
            try:
                name = card.find("div", {"class":"game-card-image"}).attrs.get("data-card-def-tooltip-app")
            except AttributeError:
                name = getsoup(f"{BASE}{url}").find("title").getText().replace("Marvel Snap ", "").replace(" - snap.fan", "")
            img = card.find("img").get("src")
            txt = card.find("div", {"class": "small"}).getText()
            info.append((f"{BASE}{url}", name, txt, img))

        nxt = soup.find("div", {"class":"pagination__control--next"})
        if not nxt:
            break
        nxt = nxt.find_all("a")
        if not nxt:
            break
        URL = f"{BASE}{nxt[-1]['href']}"
    return info

def getimg(url, loc, name):
    name = re.sub(r'[^a-zA-Z0-9]', '', name)
    filename = f"{loc}/{name}.webp"
    if not exists(filename):
        with open(filename, 'wb') as fp:
            res = get(url, stream=True)
            if not res.ok:
                print(res)
            else:
                for bk in res.iter_content(1024):
                    if not bk:
                        break
                    fp.write(bk)
    return filename

def insert(cards,locs):
    dbdata = {"cards":{}, "locations":{}}
    for i in cards:
        idx = re.sub(r'[^a-zA-Z0-9]', '', i[1].lower())
        dbdata["cards"][idx] = {
            "url": i[0],
            "name": i[1],
            "txt": i[2],
            "img": getimg(i[3], "cards", i[1]),
        }

    for i in locs:
        idx = re.sub(r'[^a-zA-Z0-9]', '', i[1].lower())
        dbdata["locations"][idx] = {
            "url": i[0],
            "name": i[1],
            "txt": i[2],
            "img": getimg(i[3], "locations", i[1]),
        }

    return dbdata

# def trans(im):
#     im = im.convert('RGBA') #.convert('P', palette=Image.ADAPTIVE, colors=255)
#     alpha = im.getchannel('A')
#     mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
#     im.paste(255, mask)
#     im.info['transparency'] = 255
#     return im, mask


def combo(card, cw, ch, tt, mult):
    cnw, cnh = cw, floor(ch*mult)

    crd = Image.open(card["img"])

    img = Image.new("RGBA", (cnw, cnh))

    img1 = ImageDraw.Draw(img)
    img1.rectangle([(0,0), (cnw, cnh)], fill=(0,0,0))
    img.paste(crd, (0, 0))

    mf = ImageFont.truetype("monofur.ttf", 42)
    txt = fill(card["txt"], width=tt)
    _, _, tw, _ = img1.textbbox((0,0), txt, font=mf)
    img1.text((((cw-tw)/2),ch+10), txt, font=mf, fill=(255,255,255))

    img.save(f"combo/{card['img']}", "webp")


def process_cards(dbfile, dl=False):
    dbdata = {"cards":{}, "locations":{}}
    if dl:
        cards = gather(f"{BASE}/cards/")
        locs = gather(f"{BASE}/locations/")

        dbdata = insert(cards, locs)
        with open(dbfile, "w") as fp:
            dump(dbdata, fp, indent=4)
    else:
        with open(dbfile, "r") as fp:
            dbdata = load(fp)


    cw, ch, ct = 615, 615, 27
    lw, lh, lt = 512, 512, 20

    for card in dbdata["cards"].values():
        combo(card, cw, ch, ct, 1.25)

    for loc in dbdata["locations"].values():
        combo(loc, lw, lh, lt, 1.35)

    return dbdata

if __name__ == "__main__":
    process_cards("./data.db")
