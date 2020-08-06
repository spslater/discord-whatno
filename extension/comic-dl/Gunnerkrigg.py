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

from Comic import Comic

class Gunnerkrigg(Comic):
	def __init__(self, ymlFile, workdir, savedir):
		super().__init__(ymlFile, 'Gunnerkrigg', workdir, savedir)


	def getChapter(self, soup, num):
		opts = soup.find('select', {'name': 'chapter'}).find_all('option')
		for idx, opt in enumerate(opts):
			if int(opt['value']) > num:
				return opts[idx-1]
		return opts[-1]		

	def getChapterInfo(self, chp):
		val = chp.text.split(':')
		if len(val) == 1:
			return '061', val[0]
		else:
			return val[0].split(' ')[-1].zfill(3), val[-1][1:]

	def getPage(self, chp, num):
		return str(int(num) - int(chp['value']) + 1).zfill(3)

	def setNameInfo(self, soup, img):
		fullnumber, ext = path.splitext(img)
		num = int(fullnumber.split('/')[-1])
		chp = self.getChapter(soup, num)
		cpNum, cpName = self.getChapterInfo(chp)
		page = self.getPage(chp, num)

		self.arc = cpNum + ' - ' + cpName
		dirs = self.arc + '/'
		imgName = self.loc[:-1] + '_' + cpNum + '-' + page + ext

		super().setNameInfo(imgName, dirs)

	def getNext(self, soup):
		nxt = super().getNext(soup)
		if nxt:
			return self.base + nxt
		return nxt

	def getSoup(self, url=None, retries=10):
		self.url = url if url else self.url
		if self.cur:
			soup = super().getSoup(self.url)
			prev = self.getPrev(soup)
			self.url = self.base + "?p=" + str(int(prev.split('=')[-1]) + 1)
		return super().getSoup()

	def saveToArchive(self):
		cmdArchive = self.savedir + self.name + '/' + self.name + ' - ' + self.arc + '.cbz'
		allArchive = self.savedir + self.name + '/' + self.name + '.cbz'
		super().saveToArchive(cmdArchive)
		super().saveToArchive(allArchive)

	def downloadAndSave(self, imgSoup):
		imgSoup['src'] = self.base + imgSoup['src']
		super().downloadAndSave(imgSoup)

def main(wd=None, sd=None):
	workdir = wd if wd else argv[1]
	savedir = sd if sd else argv[2]

	chdir(workdir)

	g = Gunnerkrigg('data.yml', workdir, savedir)	

	while True:
		soup = g.getSoup()
		nxt = g.getNext(soup)

		imgSoup = g.getImage(soup)
		img = g.base + imgSoup['src']
		g.setNameInfo(soup, img)

		g.downloadAndSave(imgSoup)
		g.saveToArchive()

		logging.info('Done')

		if g.lastComic:
			break

		g.url = nxt
		g.waitIfNeed()

	logging.info('Completed Comic')


if __name__ == "__main__":
	logging.basicConfig(
		format='%(asctime)s\t[%(levelname)s]\t%(module)s\t%(message)s',
		datefmt='%Y-%m-%d %H:%M:%S',
		level=logging.INFO,
		handlers=[
			logging.FileHandler(argv[1] + 'Gunnerkrigg/output.log'),
			logging.StreamHandler(stdout)
		]
	)
	main()
