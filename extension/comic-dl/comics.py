#!/usr/bin/env python3

from os import mkdir, path
from bs4 import BeautifulSoup as bs
from requests import get
from urllib.request import urlretrieve as download
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


with open('./comics.yml') as yml:
	comics = load(yml.read(), Loader=Loader)

for comic in comics:
	url = comic['url']
	loc = comic['dirs']
	nxtList = comic['nxt']

	while True:
		soup = bs(get(url).text, 'html.parser')
		img = soup.find(id='comic').find('img')['src']

		try:
			nxt = getNext(soup, nxtList)
		except:
			break

		parts = url.split('/')
		book = parts[-4].split('-')[1].zfill(2)
		arc = parts[-3].split('-')[0].zfill(2)
		strip = img.split('/')[-1]

		if not path.isdir(loc+book+arc):
			mkdir(loc+book+arc)

		saveAs = loc + book + arc + '/' + book + arc + '_' + strip
		if not path.exists(saveAs):
			download(img, saveAs)
			print("DOWN\t"+saveAs)
		else:
			print("SKIP\t"+saveAs)
		url = nxt