#!/usr/bin/env python3

from os import path, chdir
from bs4 import BeautifulSoup as bs
from requests import get
from urllib.parse import urlparse
from yaml import load, Loader
from time import sleep
from sqlite3 import connect
import re

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

def getTitle(soup):
	return soup.find('h2', {'class': 'post-title'}).find('a').text

def getArc(soup):
	full = soup.find('li', {'class': 'storyline-root'}).find('a').text
	val = full.split(' - ')
	if len(val) == 1:
		val = full.split(' – ')
	return val[1]

def addArc(db, img, fullname):
	num = img.split('_')[1]

	db.execute('UPDATE Arc SET name=? WHERE number = ?', (fullname, num))
	db.execute('SELECT * FROM Arc WHERE number = ?', (num,))
	return db.fetchone()

def addComic(db, img, fulltitle):
	release = '-'.join(img.split('_')[3].split('-')[0:3])

	db.execute('UPDATE Comic SET title = ? WHERE release = ?', (fulltitle, release))
	db.execute('SELECT * FROM Comic WHERE release = ?', (release,))
	return db.fetchone()

def main():
	chdir('/home/uniontown/projects/comics')

	with open('./backfill.yml') as yml:
		comics = load(yml.read(), Loader=Loader)

	for comic in comics:
		cur = comic['cur'] if ('cur' in comic) else False
		url = comic['home'] if (cur and 'home' in comic) else comic['url']
		loc = comic['loc'] if ('loc' in comic) else (urlparse(url).netloc.split('.')[-2] + '/')
		name = comic['name'] if ('name' in comic) else loc[:-1]
		getAlt = comic['alt'] if ('alt' in comic) else False
		nxtList = comic['nxt']
		dbName = loc + comic['db']

		conn = connect(dbName)
		db = conn.cursor()
		
		lastComic = False

		curCount = 0
		maxCount = 25

		while True:
			print('Getting soup for ' + url)
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

			print('\tUpdating Arc in Database')
			arcName = getArc(soup)
			arcRow = addArc(db, imgName, arcName)
			print('\tUpdating Comic in Database')
			comicTitle = getTitle(soup)
			comicRow = addComic(db, imgName, comicTitle)
			print('\tDone')

			conn.commit()

			if lastComic:
				break

			url = nxt
			if curCount == maxCount:
				curCount = 0
				print("Sleeping for 30 secs.")
				sleep(30)
			else:
				curCount += 1

		conn.close()

if __name__ == "__main__":
	main()
