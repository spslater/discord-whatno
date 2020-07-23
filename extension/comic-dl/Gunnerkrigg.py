#!/usr/bin/env python3

from os import makedirs, path, remove, system, chdir
from sys import argv, stdout
from time import sleep
from urllib.parse import urlparse
from urllib.request import urlretrieve

import logging
import re

from bs4 import BeautifulSoup as bs
from pprint import pprint
from requests import get

def getChapter(soup, num):
	opts = soup.find('select', {'name': 'chapter'}).find_all('option')
	for idx, opt in enumerate(opts):
		if int(opt['value']) > num:
			return opts[idx-1]
	return opts[-1]		

def getChapterInfo(chp):
	val = chp.text.split(':')
	if len(val) == 1:
		return '061', val[0]
	else:
		return val[0].split(' ')[-1].zfill(3), val[-1][1:]

def getPage(chp, num):
	return str(int(num) - int(chp['value']) + 1).zfill(3)

def getNext(soup):
	return soup.find('a', {'class':'right'})['href']

def download(img, saveAs, retries=5):
	dur = 2
	for x in range(1,retries+1):
		try:
			urlretrieve(img, saveAs)
			break
		except Exception as e:
			logging.warning(type(e).__name__ + ' exception occured. Waiting for ' + str(dur) + ' seconds to try again. Remaining atempts: ' + str(retries-x-1))
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
			logging.warning(type(e).__name__ + ' exception occured. Waiting for ' + str(dur) + ' seconds to try again. Remaining atempts: ' + str(retries-x-1))
			sleep(dur)
			dur *= dur
			if x == retries:
				logging.exception(e)
				raise e

def getSoup(url, base, cur):
	if not cur:
		return bs(getText(url), 'html.parser')
	else:
		soup = bs(getText(url), 'html.parser')
		prev = soup.find('div', {'class':'extra'}).find('div', {'class':'nav'}).find('a', {'class':'left'})['href']
		new = "?p=" + str(int(prev.split('=')[-1]) + 1)
		return bs(getText(base + new), 'html.parser')
	

def main(wd=None, sd=None):
	workdir = wd if wd else argv[1]
	savedir = sd if sd else argv[2]

	chdir(workdir)

	cur = True
	url = 'https://www.gunnerkrigg.com/' if cur else 'https://www.gunnerkrigg.com/?p=1'
	base = 'https://www.gunnerkrigg.com/'
	loc = 'Gunnerkrigg/'
	name = 'Gunnerkrigg'
	output = loc + 'output.log'
	loglevel = logging.INFO

	logging.basicConfig(
		format='%(asctime)s\t[%(levelname)s]\t%(message)s', 
		datefmt='%Y-%m-%d %H:%M:%S', 
		level=loglevel, 
		handlers=[
			logging.FileHandler(output),
			logging.StreamHandler(stdout)
		]
	)

	lastComic = False

	curCount = 0
	maxCount = 25

	while True:
		logging.info('Getting soup for ' + url)
		soup = getSoup(url, base, cur)

		try:
			nxt = base + getNext(soup)
		except Exception as e:
			lastComic = True

		img = base + soup.find('img', {'class', 'comic_image'})['src']

		fullnumber, ext = path.splitext(img)
		num = int(fullnumber.split('/')[-1])
		chp = getChapter(soup, num)
		cpNum, cpName = getChapterInfo(chp)
		page = getPage(chp, num)
		arc = cpNum + ' - ' + cpName
		dirs = loc + arc + '/'
		imgName = loc[:-1] + '_' + cpNum + '-' + page + ext

		if not path.isdir(dirs):
			makedirs(dirs)

		saveAs = dirs + imgName

		logging.info('Downloading Image: ' + saveAs)
		download(img, saveAs)

		zip_cmd = 'cd "' + dirs + '" && zip -ur ' + savedir + '"' + name + '/' + name + ' - ' + arc + '.cbz" ' + imgName + ' > /dev/null'
		zip_all = 'cd "' + dirs + '" && zip -ur ' + savedir + '"' + name + '/' + name + '.cbz" ' + imgName + ' > /dev/null'
		logging.info('Adding to cbz')
		system(zip_cmd)
		system(zip_all)
		logging.info('Done')


		if lastComic:
			break

		url = nxt
		if curCount == maxCount:
			curCount = 0
			logging.info("Sleeping for 3 secs.")
			sleep(3)
		else:
			curCount += 1

	logging.info('Completed Comic')


if __name__ == "__main__":
	main()
