#!/usr/bin/env python3

from os import makedirs, path, remove, system, rename
from textwrap import fill
from urllib.parse import urlparse
from urllib.request import urlretrieve, build_opener, install_opener
from time import sleep

import logging

from bs4 import BeautifulSoup as bs
from PIL import Image, ImageFont, ImageDraw
from requests import get
from yaml import load, Loader

class Comic:
	def __init__(self, ymlFile, name, workdir, savedir):
		self.workdir = workdir
		self.savedir = savedir
		with open(ymlFile) as yml:
			comic = load(yml.read(), Loader=Loader)[name]

		self.cur = comic['cur']
		self.url = comic['home'] if self.cur else comic['url']
		self.base = comic['home']
		self.loc = comic['loc']
		self.name = comic['name']
		self.saveAlt = comic['alt'] if 'alt' in comic else False
		self.imageList = comic['img']
		self.nextList = comic['nxt']
		self.prevList = comic['prev'] if 'prev' in comic else None

		self.lastComic = False
		self.curCount = 0
		self.maxCount = 25
		self.sleepTime = 5

	def download(self, img, saveAs, retries=5):
		logging.info('Downloading')
		dur = 2
		for x in range(0,retries):
			try:
				opener = build_opener()
				opener.addheaders = [('User-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:78.0) Gecko/20100101 Firefox/78.0')]	
				install_opener(opener)
				urlretrieve(img, saveAs)
				break
			except Exception as e:
				logging.warning(type(e).__name__ + ' exception occured. Waiting for ' + str(dur) + ' seconds to try again. Remaining atempts: ' + str(retries-x))
				sleep(dur)
				dur *= dur
				if x == retries:
					logging.exception(e)
					raise e

	def searchSoup(self, soup, path, value=None):
		soup = soup
		for nxt in path:
			dic = {}
			if 'class' in nxt:
				dic["class"] = nxt['class']
			if 'id' in nxt:
				dic["id"] = nxt['id']
			soup = soup.find(nxt['tag'], dic)

		return soup[value] if value else soup

	def searchAll(self, soup, path):
		soup = self.searchSoup(soup, path[:-1])
		last = path[-1]
		dic = {}
		if 'class' in last:
			dic["class"] = last['class']
		if 'id' in last:
			dic["id"] = last['id']
		return soup.find_all(last['tag'], dic)

	def getSoup(self, url=None, retries=10):
		url = url if url else self.url
		logging.info('Getting soup for ' + url)
		dur = 2
		for x in range(1, retries+1):
			try:
				text = get(url).text
				return bs(text, 'html.parser')
			except Exception as e:
				logging.warning(type(e).__name__ + ' exception occured. Waiting for ' + str(dur) + ' seconds to try again. Remaining atempts: ' + str(retries-x-1))
				sleep(dur)
				dur *= dur
				if x == retries:
					logging.exception(e)
					raise e

	def getNext(self, soup):
		try:
			val = self.searchSoup(soup, self.nextList, 'href')
			return val
		except:
			self.lastComic = True
			return None
	
	def getPrev(self, soup):
		return self.searchSoup(soup, self.prevList, 'href')

	def getImage(self, soup):
		return self.searchSoup(soup, self.imageList)

	def getAlt(self, img):
		if self.saveAlt:
			return img['alt'] if img.has_attr('alt') else img['title'] if img.has_attr('title') else None
		else:
			return None

	def saveImage(self, url, name):
		logging.info('Downloading image: ' + name)
		self.download(url, name)

	def saveAltToImage(self, inName, outName, altRaw):
		logging.info('Adding alt text to image: ' + outName)
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

		output.save(outName, "PNG")
		logging.info('Removing raw image')
		remove(inName)

	def convertToPNG(self, inName, outName):
		_, ext = path.splitext(inName)
		if ext != '.png':
			logging.info('Converting image to png: ' + outName)
			comic = Image.open(inName).convert("RGBA")
			comic.save(outName, "PNG")
			remove(inName)
		else:
			logging.info('No need to convert image: ' + outName)
			rename(inName, outName)
		

	def downloadAndSave(self, imgSoup):
		raw = self.dirs + self.saveRaw
		fin = self.dirs + self.saveAs

		img = imgSoup['src']

		alt = self.getAlt(imgSoup)
		if alt:
			logging.info('Saving with alt text')
			self.saveImage(img, raw)
			self.saveAltToImage(raw, fin, alt)
		else:
			logging.info('Saving with no alt')
			self.saveImage(img, raw)
			self.convertToPNG(raw, fin)

	def saveToArchive(self, archive):
		cmd = 'cd "' + self.dirs + '" && zip -ur "' + archive + '" "' + self.saveAs + '" > /dev/null'
		logging.info('Adding to archive: ' + archive)
		system(cmd)

	def setNameInfo(self, imgName, dirName):
		self.dirs = self.loc + dirName
		img, ext = path.splitext(imgName)
		self.saveAs = img + '.png'
		self.saveRaw = "raw_" + imgName

		if not path.isdir(self.dirs):
			makedirs(self.dirs)

	def waitIfNeed(self):
		if self.curCount == self.maxCount:
			self.curCount = 0
			logging.debug("Sleeping for " + str(self.sleepTime) + " secs.")
			sleep(self.sleepTime)
		else:
			self.curCount += 1
