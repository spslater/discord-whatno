#!/usr/bin/env python3

from os import makedirs, path, remove, system
from bs4 import BeautifulSoup as bs
from requests import get
from urllib.request import urlretrieve as download
from urllib.parse import urlparse
from yaml import load, Loader
from PIL import Image, ImageFont, ImageDraw
from textwrap import wrap

def getNext(soup, nxtList):
	soup = soup
	for nxt in nxtList:
		dic = {}
		if 'class' in nxt:
			dic["class"] = nxt['class']
		if 'id' in nxt:
			dic["id"] = nxt['id']

		soup = soup.find(nxt['tag'], dic)

	return soup['href']

def addAltToImage(inName, outName, altRaw):
	comic = Image.open(inName)
	c_width, c_height = comic.size

	font = ImageFont.truetype('./font/Ubuntu-R.ttf', 16)
	drawFont = ImageDraw.Draw(Image.new('RGB', (c_width, c_height*2), (255, 255, 255)))
	altWrap = wrap(altRaw, width=(c_width-20)/8)
	alt = '\n'.join(altWrap)
	alt_width, alt_height = drawFont.textsize(alt, font=font)

	height = c_height+10+alt_height+10
	output = Image.new('RGBA', (c_width, height), (224, 238, 239, 255))

	draw = ImageDraw.Draw(output)

	output.paste(comic, (0,0), mask=comic)
	draw.text((10,c_height+10), alt, font=font, fill="black")

	output.save(outName)



with open('./comics.yml') as yml:
	comics = load(yml.read(), Loader=Loader)

for comic in comics:
	url = comic['url']
	loc = comic['dirs'] if ('dirs' in comic) else (urlparse(url).netloc.split('.')[-2] + '/')
	name = comic['name'] if ('name' in comic) else loc[:-1]
	getAlt = comic['alt'] if ('alt' in comic) else False
	nxtList = comic['nxt']

	while True:
		soup = bs(get(url).text, 'html.parser')

		imgTag = soup.find(id='comic').find('img')

		img = imgTag['src']
		alt = None
		if getAlt:
			if imgTag.get('alt', False):
				alt = imgTag['alt']
			elif imgTag.get('title', False):
				alt = imgTag['title']

		try:
			nxt = getNext(soup, nxtList)
		except:
			break

		parts = url.split('/')
		book = parts[-4].split('-')[1].zfill(2)
		arc = parts[-3].split('-')[0].zfill(2)
		strip = img.split('/')[-1]
		dirs = loc + book + arc + '/'

		if not path.isdir(dirs):
			makedirs(dirs)

		saveRaw = dirs + "raw_" + book + arc + '_' + strip
		saveAs = dirs + book + arc + '_' + strip

		if not path.exists(saveRaw):
			print(saveAs)
			if getAlt and alt:
				print('\tDownloading')
				download(img, saveRaw)
				print('\tAdding Alt Text')
				addAltToImage(saveRaw, saveAs, alt)
				print('\tRemoving raw')
				remove(saveRaw)
			else:
				print('\tDownloading with no alt')
				download(img, saveAs)

		url = nxt
	
	system('bash ./combine.sh ' + loc[:-1] + ' "' + name + '"')