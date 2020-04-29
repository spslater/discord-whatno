#!/usr/bin/env python3

from os import mkdir, path
from bs4 import BeautifulSoup as bs
from requests import get
from urllib.request import urlretrieve as download

url = "https://www.dumbingofage.com/2010/comic/book-1/01-move-in-day/home/"
loc = 'DumbingOfAge/'

while True:
	soup = bs(get(url).text, 'html.parser')

	img = soup.find(id='comic').find('img')['src']
	try:
		nxt = soup.find(id='comic-foot').find("a", {"class":'navi navi-next'})['href']
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