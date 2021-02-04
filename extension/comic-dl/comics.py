#!/usr/bin/env python3

import logging
from sys import argv, stdout
from yaml import load, Loader

def main():
	with open(argv[1]) as yml:
		data = load(yml.read(), Loader=Loader)

	workdir = argv[2] + data['workdir']
	savedir = argv[2] + data['savedir']

	logging.basicConfig(
		format='%(asctime)s\t[%(levelname)s]\t%(module)s\t%(message)s',
		datefmt='%Y-%m-%d %H:%M:%S',
		level=logging.INFO,
		handlers=[
			logging.FileHandler(workdir + 'output.log'),
			logging.StreamHandler(stdout)
		]
	)

	for comic in data['comics']:
		logging.info('Updating ' + comic)
		__import__(comic).main(workdir, savedir)
	logging.info('Done Updating All Comics')


if __name__ == "__main__":
	main()
