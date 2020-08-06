#!/usr/bin/env python3

import logging

from os import chdir
from sys import argv, stdout

from Comic import Comic

class BittersweetCandyBowl(Comic):
	def __init__(self, ymlFile, workdir, savedir):
		super().__init__(ymlFile, 'BittersweetCandyBowl', workdir, savedir)
		self.chpNum = None
		self.chpName = None
		self.curPg = None
		self.totPg = None

	def getChapterName(self, full):
		split = 'chapter posted' if 'chapter posted' in full else 'page posted'
		return full.split(split)[0].strip()[:-1]

	def parseChapterInfo(self, info):
		try:
			int(info[0])
			num = info.split('.')[0]
			name = self.getChapterName(info.split('.')[1])
			return [num,name]
		except:
			num = self.url.split('/')[-2][1:]
			if '.' in num:
				front = num.split('.')[0].zfill(3)
				back = num.split('.')[1]
				num = front + '.' + back
			name = self.getChapterName(info.split(':')[1])
			return [num,name]

	def setChapterInfo(self, soup):
		if self.cur:
			info = soup.find('h3', {'class':'comicdate'}).text.strip().split(', page')
			pgInfo = info[1].strip().split(' ')

			self.chpName = soup.find('h2', {'class':'comictitle'}).text.strip()[1:-2]
			self.chpNum = info[0].split(' ')[1].zfill(3)
			self.curPg = pgInfo[0].zfill(2)
			self.totPg = pgInfo[2][:-1].zfill(2)
		else:
			info = soup.find('div', {'class':'progbar_enclosure_chapter'}).text.strip().split('\n')
			chpInfo = self.parseChapterInfo(info[0])
			pgInfo = info[1].split(' ')

			self.chpNum = chpInfo[0].zfill(3)
			self.chpName = chpInfo[1]
			self.curPg = pgInfo[1].zfill(2)
			self.totPg = pgInfo[-1].zfill(2)

	def setNameInfo(self, soup):
		self.setChapterInfo(soup)

		imgName = self.loc[:-1] + '_' + self.chpNum + '-' + self.chpName + '_' + self.curPg + '-' + self.totPg + '.png'
		dirName = self.chpNum + '-' + self.chpName + '/'
		super().setNameInfo(imgName, dirName)

	def getNext(self, soup):
		end = super().getNext(soup)
		if end:
			return self.base + end[1:]
		return end

	def saveToArchive(self):
		chpArchive = self.name + ' - ' + self.chpNum + ' - ' + self.chpName + '.cbz'
		allArchive = self.name + '.cbz'
		super().saveToArchive(chpArchive)
		super().saveToArchive(allArchive)
		

def main(wd=None, sd=None):
	workdir = wd if wd else argv[1]
	savedir = sd if sd else argv[2] if argv[2][-1] == '/' else (argv[2] + '/')

	chdir(workdir)

	bcb = BittersweetCandyBowl('data.yml', workdir, savedir)
	
	while True:
		soup = bcb.getSoup()
		nxt = bcb.getNext(soup)

		imgSoup = bcb.getImage(soup)
		bcb.setNameInfo(soup)

		bcb.downloadAndSave(imgSoup)
		bcb.saveToArchive()

		logging.info('Done')

		if bcb.lastComic:
			break

		bcb.url = nxt
		bcb.waitIfNeed()

	logging.info('Completed Comic')

if __name__ == "__main__":
	logging.basicConfig(
			format='%(asctime)s\t[%(levelname)s]\t%(module)s\t%(message)s',
			datefmt='%Y-%m-%d %H:%M:%S',
			level=logging.INFO,
			handlers=[
				logging.FileHandler(argv[1] + 'BittersweetCandyBowl/output.log'),
				logging.StreamHandler(stdout)
			]
	)
	main()
