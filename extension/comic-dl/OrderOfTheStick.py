#!/usr/bin/env python3

import logging

from os import chdir
from sys import argv, stdout

from Comic import Comic

class OrderOfTheStick(Comic):
	def __init__(self, ymlFile, workdir, savedir):
		super().__init__(ymlFile, 'OrderOfTheStick', workdir, savedir)
		self.images = None
		self.curName = None
		self.curNum = None

		self.generateImages(self.getSoup(self.url))
		self.url = self.getNext()

	def setSaveInfo(self):
		imgName = self.loc[:-1] + '_' + self.curNum + '_' + self.curName + '.png'
		dirName = self.chpNum + '-' + self.chpName + '/'

		super().setNameInfo(imgName, dirName)

	def generateImages(self, soup):
		self.images = self.searchAll(soup, {'tag':'a', 'class':'ComicList'})
		if self.cur:
			self.images = [ self.images[0] ]
		
	def getNext(self):
		endImg = self.images.pop(-1)
		end = endImg.find('a')['href']
		self.curName = ' - '.join(endImg.text.split(' - ')[1:])
		self.curNum = endImg.text.split(' - ')[0]
		self.setSaveInfo()
		return self.base + end[1:]

def main(wd=None, sd=None):
	workdir = wd if wd else argv[1]
	savedir = sd if sd else argv[2] if argv[2][-1] == '/' else (argv[2] + '/')

	chdir(workdir)

	oots = OrderOfTheStick('data.yml', workdir, savedir)
	
	while True:
		soup = oots.getSoup()
		oots.generateImages(soup)
		nxt = oots.getNext(soup)

		oots.setSaveInfo(soup)

		img = oots.getImage(soup)
		oots.downloadAndSave(img)

		chpArchive = savedir + oots.name + '/' + oots.name + ' - ' + oots.chpNum + ' - ' + oots.chpName + '.cbz'
		allArchive = savedir + oots.name + '/' + oots.name + '.cbz'
		oots.saveToArchive(chpArchive)
		oots.saveToArchive(allArchive)
		logging.info('Done')

		if oots.lastComic:
			break

		oots.url = nxt
		oots.waitIfNeed()

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
