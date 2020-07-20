#!/usr/bin/env python3

from os import makedirs, path, remove, system, chdir
from sys import argv, stdout
from textwrap import fill
from time import sleep
from urllib.parse import urlparse
from urllib.request import urlretrieve

import logging
import re

from bs4 import BeautifulSoup as bs
from PIL import Image, ImageFont, ImageDraw
from requests import get
from sqlite3 import connect, Cursor
from yaml import load, Loader

def createTables(db : Cursor):
	 db.executescript("""
			CREATE TABLE Arc(
				number PRIMARY KEY,
				name TEXT UNIQUE NOT NULL,
				url TEXT UNIQUE NOT NULL
			);

			CREATE TABLE Comic(
				release PRIMARY KEY,
				title TEXT NOT NULL,
				image TEXT UNIQUE NOT NULL,
				url TEXT UNIQUE NOT NULL,
				arcId
						REFERENCES Arc(rowid)
						ON DELETE CASCADE
						ON UPDATE CASCADE
						NOT NULL
			);

			CREATE TABLE Alt(
				comicId
						UNIQUE
						REFERENCES Comic(release)
						ON DELETE CASCADE
						ON UPDATE CASCADE
						NOT NULL,
				alt TEXT NOT NULL
			);

			CREATE TABLE Tag(
				comicId
						REFERENCES Comic(release)
						ON DELETE CASCADE
						ON UPDATE CASCADE
						NOT NULL,
				tag TEXT NOT NULL
			);
	 """)


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
			logging.warning(type(e).__name__ + ' exception occured. Waiting for ' + dur + ' seconds to try again. Remaining atempts: ' + str(retries-x-1))
			sleep(dur)
			dur *= dur
			if x == retries:
				logging.exception(e)
				raise e

def getText(url, retries=10):
	dur = 2
	for x in range(1, retries+1):
		try:
			return get(url).text
		except Exception as e:
			logging.warning(type(ex).__name__ + ' exception occured. Waiting for ' + dur + ' seconds to try again. Remaining atempts: ' + str(retries-x-1))
			sleep(dur)
			dur *= dur
			if x == retries:
				logging.exception(e)
				raise e

def getTitle(soup):
	return soup.find('h2', {'class': 'post-title'}).find('a').text

def getArc(soup):
		return soup.find('li', {'class': 'storyline-root'}).find('a').text[5:]

def addArc(db, img, fullname):
	data = img.split('_')
	num = data[1]
	name = data[2]
	url = 'https://www.dumbingofage.com/category/comic/book-' + (num[1] if num[0] == '0' else num) + '/' + num[2:4] + '-' + name + '/'

	db.execute('SELECT * FROM Arc WHERE number = ?', (num,))
	row = db.fetchone()

	if not row:
		logging.debug('Inserting new arc: ' + fullname)
		db.execute('INSERT INTO Arc VALUES (?,?,?)', (num, fullname, url))
		db.execute('SELECT * FROM Arc WHERE number = ?', (num,))
		row = db.fetchone()

	return row

def addComic(db, img, arc, fulltitle, url):
	titleRelease = img.split('_')[3]
	title = '.'.join('-'.join(titleRelease.split('-')[3:]).split('.')[:-1])
	release = '-'.join(titleRelease.split('-')[0:3])

	db.execute('SELECT * FROM Comic WHERE release = ?', (release,))
	row = db.fetchone()

	if not row:
		logging.debug('Inserting new comic: ' + fulltitle)
		db.execute('INSERT INTO Comic VALUES (?,?,?,?,?)', (release, fulltitle, img, url, arc[0]))
		db.execute('SELECT * FROM Comic WHERE release = ?', (release,))
		row = db.fetchone()

	return row

def addAlt(db, comic, alt):
	db.execute('SELECT * FROM Alt WHERE comicId = ?', (comic[0],))
	row = db.fetchone()

	if not row:
		logging.debug('Inserting new alt: ' + comic[0])
		db.execute('INSERT INTO Alt VALUES (?,?)', (comic[0], alt))
		db.execute('SELECT * FROM Alt WHERE comicId = ?', (comic[0],))
		row = db.fetchone()

	return row

def addTag(db, comic, tag):
	db.execute('SELECT * FROM Tag WHERE comicId = ? AND tag = ?', (comic[0], tag))
	row = db.fetchone()

	if not row:
		db.execute('INSERT INTO Tag VALUES (?,?)', (comic[0], tag))
		db.execute('SELECT * FROM Tag WHERE comicId = ? AND tag = ?', (comic[0], tag))
		row = db.fetchone()

	return row

def getLevel(level):
	if level == 'DEBUG':
		return logging.DEBUG
	elif level == 'INFO':
		return logging.INFO
	elif level == 'WARN':
		return logging.WARNING
	elif level == 'ERROR':
		return logging.ERROR

def main():
	workdir = argv[1]
	savedir = argv[2]

	chdir(workdir)

	with open('./comics.yml') as yml:
		comic = load(yml.read(), Loader=Loader)

	cur = comic['cur'] if ('cur' in comic) else False
	url = comic['home'] if (cur and 'home' in comic) else comic['url']
	loc = comic['loc'] if ('loc' in comic) else (urlparse(url).netloc.split('.')[-2] + '/')
	name = comic['name'] if ('name' in comic) else loc[:-1]
	getAlt = comic['alt'] if ('alt' in comic) else False
	nxtList = comic['nxt']
	dbName = loc + (comic['db'] if ('db' in comic) else (name + '.db'))
	output = loc + (comic['log'] if ('log' in comic) else (name + '.log'))
	loglevel = getLevel(comic['level']) if ('level' in comic) else logging.INFO

	logging.basicConfig(
		format='%(asctime)s\t[%(levelname)s]\t%(message)s', 
		datefmt='%Y-%m-%d %H:%M:%S', 
		level=loglevel, 
		handlers=[
			logging.FileHandler(output),
			logging.StreamHandler(stdout)
		]
	)

	conn = connect(dbName)
	db = conn.cursor()
	
	lastComic = False

	curCount = 0
	maxCount = 25

	while True:
		logging.info('Getting soup for ' + url)
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

		logging.info('Saving Arc to Database')
		fullArcName = getArc(soup)
		arcRow = addArc(db, imgName, fullArcName)

		logging.info('Saving Comic to Database')
		comicTitle = getTitle(soup)
		comicRow = addComic(db, imgName, arcRow, comicTitle, url)

		logging.info('Saving Tags to Database')
		for tag in getTags(soup):
			addTag(db, comicRow, tag)

		if not path.isdir(dirs):
			makedirs(dirs)

		saveRaw = dirs + "raw_" + imgName
		saveAs = dirs + imgName

		if getAlt and alt:
			logging.info('Downloading')
			download(img, saveRaw)
			logging.info('Adding Alt Text')
			addAltToImage(saveRaw, saveAs, alt)
			logging.info('Saving Alt to Database')
			addAlt(db, comicRow, alt)
			logging.info('Removing raw')
			remove(saveRaw)
		else:
			logging.info('Downloading with no alt')
			download(img, saveAs)

		zip_cmd = 'cd ' + dirs + ' && zip -ur ' + savedir + '"' + name + '/' + name + ' - ' + book + arc + '.cbz" ' + imgName + ' > /dev/null'
		zip_all = 'cd ' + dirs + ' && zip -ur ' + savedir + '"' + name + '/' + name + '.cbz" ' + imgName + ' > /dev/null'
		logging.info('Adding to cbz')
		system(zip_cmd)
		system(zip_all)
		logging.info('Done')

		conn.commit()

		if lastComic:
			break

		url = nxt
		if curCount == maxCount:
			curCount = 0
			logging.debug("Sleeping for 30 secs.")
			sleep(30)
		else:
			curCount += 1

	logging.info('Completed Comic')
	conn.close()

if __name__ == "__main__":
	main()
