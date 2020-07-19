#!/usr/bin/env python3

from os import makedirs, path, remove, system, chdir
from bs4 import BeautifulSoup as bs
from requests import get
from urllib.request import urlretrieve
from urllib.parse import urlparse
from yaml import load, Loader
from PIL import Image, ImageFont, ImageDraw
from textwrap import fill
from time import sleep
from tinydb import TinyDB, where

COMICS = "~/media/reading/webcomics/"

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

def getTags(soup):
	tagList = []
	tags = soup.find('div', {'class':'post-tags'}).find_all('a')
	for tag in tags:
		tagList.append(tag.text)
	return tagList
	
def saveTags(imgName, tags, db):
	for tag in tags:
		db.table('tags').insert({'img': imgName, 'tag': tag})

def addAltToDatabase(imgName, alt, db):
	db.table('alts').insert({'img': imgName, 'alt': alt})

def addAltToImage(inName, outName, altRaw):
	comic = Image.open(inName).convert("RGBA")
	c_width, c_height = comic.size

	font = ImageFont.truetype('./font/Ubuntu-R.ttf', 16)
	drawFont = ImageDraw.Draw(Image.new('RGB', (c_width, c_height*2), (255, 255, 255)))
	alt = fill(altRaw, width=(int((c_width-20)/11)))
	alt_width, alt_height = drawFont.textsize(alt, font=font)

	height = c_height+10+alt_height+10
	output = Image.new('RGBA', (c_width, height), (224, 238, 239, 255))

	draw = ImageDraw.Draw(output)

	output.paste(comic, (0,0), mask=comic)
	draw.text((10,c_height+10), alt, font=font, fill="black")

	output.save(outName)

def download(img, saveAs, retries=5):
	dur = 2
	for x in range(1,retries+1):
		try:
			urlretrieve(img, saveAs)
			break
		except Exception as e:
			print('\t' + type(e).__name__ + ' exception occured. Waiting for ' + dur + ' seconds to try again. Remaining atempts: ' + str(retries-x-1))
			sleep(dur)
			dur *= dur
			if x == retries:
				raise e

def getText(url, retries=10):
	dur = 2
	for x in range(1, retries+1):
		try:
			return get(url).text
		except Exception as e:
			print('\t' + type(ex).__name__ + ' exception occured. Waiting for ' + dur + ' seconds to try again. Remaining atempts: ' + str(retries-x-1))
			sleep(dur)
			dur *= dur
			if x == retries:
				raise e

def main():
	chdir('/home/uniontown/projects/comics')

	with open('./comics.yml') as yml:
		comics = load(yml.read(), Loader=Loader)

	for comic in comics:
		cur = comic['cur'] if ('cur' in comic) else False
		url = comic['home'] if (cur and 'home' in comic) else comic['url']
		loc = comic['loc'] if ('loc' in comic) else (urlparse(url).netloc.split('.')[-2] + '/')
		name = comic['name'] if ('name' in comic) else loc[:-1]
		getAlt = comic['alt'] if ('alt' in comic) else False
		nxtList = comic['nxt']
		dbName = loc + comic['db']

		db = TinyDB(dbName)
		
		lastComic = False

		curCount = 0
		maxCount = 25

		while True:
			print('\tGetting soup for ' + url)
			soup = bs(getText(url), 'html.parser')

			try:
				nxt = getNext(soup, nxtList)
			except:
				lastComic = True

			imgTag = soup.find(id='comic').find('img')

			img = imgTag['src']
			alt = None
			if getAlt:
				if imgTag.get('alt', False):
					alt = imgTag['alt']
				elif imgTag.get('title', False):
					alt = imgTag['title']

			_, ext = path.splitext(img)
			if ext.lower() != '.png':
				url = nxt
				continue

			if cur:
				parts = getNext(soup, comic['book']).split('/')
				book = parts[-3].split('-')[1].zfill(2)
				arcs = parts[-2].split('-')
			else:
				parts = url.split('/')
				book = parts[-4].split('-')[1].zfill(2)
				arcs = parts[-3].split('-')
			arc = arcs[0].zfill(2)
			arcName = '-'.join(arcs[1:])
			strip = img.split('/')[-1]
			dirs = loc + book + arc + '/'
			imgName = loc[:-1] + '_' + book + arc + '_' + arcName + '_' + strip

			print('\tSaveing Tags to Database')
			tags = getTags(soup)
			saveTags(imgName, tags, db)

			if not path.isdir(dirs):
				makedirs(dirs)

			saveRaw = dirs + "raw_" + imgName
			saveAs = dirs + imgName

			if getAlt and alt:
				print('\tDownloading')
				download(img, saveRaw)
				print('\tAdding Alt Text')
				addAltToImage(saveRaw, saveAs, alt)
				print('Saveing Alt to database')
				addAltToDatabase(imgName, alt, db)
				print('\tRemoving raw')
				remove(saveRaw)
			else:
				print('\tDownloading with no alt')
				download(img, saveAs)

			zip_cmd = 'cd ' + dirs + ' && zip -ur ' + COMICS + '"' + name + '/' + name + ' - ' + book + arc + '.cbz" ' + imgName + ' > /dev/null'
			zip_all = 'cd ' + dirs + ' && zip -ur ' + COMICS + '"' + name + '/' + name + '.cbz" ' + imgName + ' > /dev/null'
			print('\tAdding to cbz')
			system(zip_cmd)
			system(zip_all)
			print('\tDone')

			if lastComic:
				break

			url = nxt
			if curCount == maxCount:
				curCount = 0
				print("Sleeping for 30 secs.")
				sleep(30)
			else:
				curCount += 1

if __name__ == "__main__":
	main()
