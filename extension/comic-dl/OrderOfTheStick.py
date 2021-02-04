#!/usr/bin/env python3

import logging

from os import chdir, path
from time import sleep
from sys import argv, stdout

from pprint import pprint

from Comic import Comic

class OrderOfTheStick(Comic):
	def __init__(self, ymlFile, workdir, savedir):
		super().__init__(ymlFile, 'OrderOfTheStick', workdir, savedir)
		self.images = None
		self.curName = None
		self.curNum = None

		self.generateImages(self.getSoup(self.url))
		self.url = self.getNext()

	def setNameInfo(self):
		imgName = self.loc[:-1] + '_' + self.curNum + '_' + self.curName + '.png'
		dirName = ''

		super().setNameInfo(imgName, dirName)

	def generateImages(self, soup):
		self.images = self.searchAll(soup, [{'tag':'p', 'class':'ComicList'}])
		if self.cur:
			self.images = [ self.images[0] ]
		
	def getNext(self):
		try:
			endImg = self.images.pop(-1)
			end = endImg.find('a')['href']
			self.curName = ' - '.join(endImg.text.split(' - ')[1:]).replace('/', ' ').replace(': ', ' - ')
			self.curNum = endImg.text.split(' - ')[0].zfill(4)
			return self.base + end[1:]
		except:
			self.lastComic = True
			return None

	def getImage(self, soup):
			return (soup.find('table')
										.find_all('tr')[1]
										.find('tr')
										.find_all('td', recursive=False)[1]
										.find('table')
										.find('table')
										.find_all('tr', recursive=False)[1]
										.find('img'))

	def downloadAndSave(self, soup):
		_, ext = path.splitext(soup['src'])
		if ext != '.png':
			self.saveRaw = self.saveRaw + ext

		super().downloadAndSave(soup)

	def saveToArchive(self):
		super().saveToArchive(self.name + '.cbz')
	
	def setStart(self, addr):
		while self.url != addr:
			self.url = self.getNext()

	def getSoup(self, url=None, retries=10):
		soup = super().getSoup(url, retries)
		if not soup:
			logging.info('Soup was empty, waiting to try again')
			sleep(5)
			soup = super().getSoup(url, retries)
		return soup
		

def main(wd=None, sd=None):
	workdir = wd if wd else argv[1]
	savedir = sd if sd else argv[2] if argv[2][-1] == '/' else (argv[2] + '/')

	chdir(workdir)

	oots = OrderOfTheStick('data.yml', workdir, savedir)

	if len(argv) > 3:
		oots.setStart(argv[3])
	
	while True:
		soup = oots.getSoup()

		imgSoup = oots.getImage(soup)
		oots.setNameInfo()

		oots.downloadAndSave(imgSoup)
		oots.saveToArchive()
		
		logging.info('Done')

		oots.url = oots.getNext()
		oots.waitIfNeed()

		if oots.lastComic:
			break

	logging.info('Completed Comic')

if __name__ == "__main__":
	logging.basicConfig(
			format='%(asctime)s\t[%(levelname)s]\t%(module)s\t%(message)s',
			datefmt='%Y-%m-%d %H:%M:%S',
			level=logging.INFO,
			handlers=[
				logging.FileHandler(argv[1] + 'OrderOfTheStick/' + 'output.log'),
				logging.StreamHandler(stdout)
			]
	)
	main()
