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
from sqlite3 import connect
from yaml import load, Loader

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

	db.execute('UPDATE Arc SET url = ? WHERE number = ?', (url, num))
	db.execute('SELECT * FROM Arc WHERE number = ?', (num,))
	row = db.fetchone()

	return row

def addComic(db, img, arc, fulltitle, url):
	release = '-'.join(img.split('_')[3].split('-')[0:3])

	db.execute('UPDATE Comic SET url = ? WHERE release = ?', (url, release))
	db.execute('SELECT * FROM Comic WHERE release = ?', (release,))
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

	with open('./backfill.yml') as yml:
		comic = load(yml.read(), Loader=Loader)

	cur = comic['cur'] if ('cur' in comic) else False
	url = comic['home'] if (cur and 'home' in comic) else comic['url']
	loc = comic['loc'] if ('loc' in comic) else (urlparse(url).netloc.split('.')[-2] + '/')
	name = comic['name'] if ('name' in comic) else loc[:-1]
	getAlt = comic['alt'] if ('alt' in comic) else False
	nxtList = comic['nxt']
	dbName = loc + (comic['db'] if ('db' in comic) else (name + '.db'))
	output = loc + (comic['log'] if ('log' in comic) else (path.basename(__file__) + '.log'))
	loglevel = getLevel(comic['level']) if ('level' in comic) else logging.INFO

	logging.basicConfig(format='%(asctime)s\t[%(levelname)s]\t%(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=loglevel, filename=output)

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

		logging.info('Updating Arc in Database')
		fullArcName = getArc(soup)
		arcRow = addArc(db, imgName, fullArcName)

		logging.info('Updating Comic in Database')
		comicTitle = getTitle(soup)
		comicRow = addComic(db, imgName, arcRow, comicTitle, url)

		logging.info('Done')

		conn.commit()

		if lastComic:
			break

		url = nxt
		if curCount == maxCount:
			curCount = 0
			logging.debug("Sleeping for 10 secs.")
			sleep(10)
		else:
			curCount += 1

	conn.close()

if __name__ == "__main__":
	main()
