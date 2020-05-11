#!/usr/bin/env python3

from os import makedirs, path, remove, system, path, chdir
from bs4 import BeautifulSoup as bs
from requests import get
from urllib.request import urlretrieve
from urllib.parse import urlparse
from yaml import load, Loader
from PIL import Image, ImageFont, ImageDraw
from textwrap import fill
from time import sleep

COMICS = "~/media/reading/comics/"

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

def download(img, saveAs, retries=5):
	dur = 2
	for x in range(1,retries+1):
		try:
			urlretrieve(img, saveAs)
			break
		except Exception as e:
			print('\t' + type(e).__name__ + ' exception occured. Waiting for ' + dur + ' seconds to try again. Remaining atempts: ' + str(retries-x-1))
			sleep(dur)
			dur *= dur
			if x == retries:
				raise e

def getText(url, retries=10):
	dur = 2
	for x in range(1, retries+1):
		try:
			return get(url).text
		except Exception as e:
			print('\t' + type(e).__name__ + ' exception occured. Waiting for ' + dur + ' seconds to try again. Remaining atempts: ' + str(retries-x-1))
			sleep(dur)
			dur *= dur
			if x == retries:
				raise e

def main():
	chdir('/home/uniontown/projects/comics')

	with open('./sundaekids.yml') as yml:
		comic = load(yml.read(), Loader=Loader)[0]

	url = comic['url']
	loc = comic['loc']
	name = comic['name']
	nxtList = comic['nxt']
	
	lastComic = False

	count = 1

	while True:
		print('Getting soup for ' + url)
		soup = bs(getText(url), 'html.parser')

		try:
			nxt = getNext(soup, nxtList)
		except:
			lastComic = True

		posts = soup.find_all('div', {'class': 'post-item'})
		posts.reverse()
		for post in posts:
			img = post.find('img')['src']

			_, imgExt = path.splitext(img)
			imgSrc = '-'.join(img.split('-')[:-1]) + imgExt

			imgName = loc[:-1] + '_' + str(count).zfill(3) + '_' + imgSrc.split('/')[-1]


			print('\t' + imgSrc)

			if not path.isdir(loc):
				makedirs(loc)

			saveAs = loc + imgName

			print('\t\t' + saveAs)
			print('\tDownloading')
			download(img, saveAs)

			zip_all = 'cd ' + loc + ' && zip -ur ' + COMICS + '"' + name + '/' + name + '.cbz" ' + imgName + ' > /dev/null'
			system(zip_all)
			print('\tDone')
			count += 1

		if lastComic:
			break

		url = nxt

		# print("Sleeping for 10 secs.")
		# sleep(10)

if __name__ == "__main__":
	main()
