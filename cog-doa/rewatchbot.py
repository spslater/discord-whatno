#!/usr/bin/env python3

import logging

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from datetime import datetime, timedelta
from os import getenv
from sqlite3 import connect
from sys import stdout, exc_info

from discord import Client, Embed, Colour
from dotenv import load_dotenv

class ComicReread(Client):
	def __init__(self, database_filename, midweek, guild_name=None, guild_id=None, channel_name=None, channel_id=None):
		super().__init__()
		self.conn = connect(database_filename)
		self.database = self.conn.cursor()
		self.midweek = midweek
		self.guild_name = guild_name
		self.guild_id = guild_id
		self.guild = None
		self.channel_name = channel_name
		self.channel_id = channel_id
		self.channel = None
		if self.channel_id is None and self.channel_name is None:
			raise RuntimeError('Channel Id or Name not added to Client.')

	def get_guild(self):
		if self.guild is None:
			logging.debug('Getting guild.')
			if self.guild_id is None and self.guild_name is None:
				raise RuntimeError('Guild Id or Name not added to Client.')
			elif self.guild_id is None and self.guild_name is not None:
				for guild in self.fetch_guilds():
					if guild.name == self.guild_name:
						self.guild_id = int(guild.id)
						break
				if self.guild_id is None:
					raise RuntimeError('Guild Name not found in list of guilds.')
			self.guild = super().get_guild(self.guild_id)
		return self.guild

	def get_channel(self):
		if self.channel is None:
			if self.channel_id is None:
				logging.debug('Getting channel.')
				channels = None
				try:
					logging.debug('Trying to get channel from specific guild.')
					if self.guild is None:
						self.get_guild()
					channels = self.guild.fetch_channels()
				except RuntimeError:
					logging.debug('Error getting from guild, trying to get from all availible channels.')
					channels = self.get_all_channels()

				for c in channels:
					if c.name == self.channel_name:
						self.channel_id = int(c.id)
						break
				if self.channel_id is None:
					raise RuntimeError('Channel Name not found in list of available channels.')
			self.channel = super().get_channel(self.channel_id)
		return self.channel

	def date_from_week(self, yr, wk, wd):
		ywd = "{}-{}-{}".format(yr, wk, wd)
		iso_date = datetime.strptime(ywd, "%G-%V-%u")
		return datetime.strftime(iso_date, "%Y-%m-%d")

	def build_date_tuple(self, date_string):
		yr, wk, _ = datetime.strptime(date_string, "%Y-%m-%d").isocalendar()
		return (
			self.date_from_week(yr, wk, 1),
			self.date_from_week(yr, wk, 2),
			self.date_from_week(yr, wk, 3),
			self.date_from_week(yr, wk, 4),
			self.date_from_week(yr, wk, 5),
			self.date_from_week(yr, wk, 6),
			self.date_from_week(yr, wk, 7),
		)

	def get_tags(self, date_string):
		self.database.execute('SELECT tag FROM Tag WHERE comicId = ?', (date_string,))
		rows = self.database.fetchall()
		tags = [ r[0] for r in rows ]
		return ', '.join(tags)

	def build_embeds(self, date_string):
		embeds = []

		days = self.build_date_tuple(date_string)
		logging.debug('Getting comics on following days: {}', (days,))
		self.database.execute("""
			SELECT
				Comic.release as release,
				Comic.title as title,
				Comic.image as image,
				Comic.url as url,
				Alt.alt as alt
			FROM Comic
			JOIN Alt ON Comic.release = Alt.comicId
			WHERE release IN {}
		""".format(days))

		rows = self.database.fetchall()
		logging.debug('{} comics from current week'.format(len(rows)))
		for row in rows:
			release = row[0]
			title = row[1]
			image = row[2].split('_', maxsplit=3)[3]
			url = row[3]
			alt = '||{}||'.format(row[4])
			header = '[{}]({})'.format(title, url)
			img_url = 'https://www.dumbingofage.com/comics/{}'.format(image)
			tags = self.get_tags(release)
			footer = '{} - {}'.format(release, tags)

			logging.debug('Generating embed for "{}" from {}'.format(title, release))
			embed = Embed(title=title, url=url, description=alt, colour=Colour.random())
			embed.set_image(url=img_url)
			embed.set_footer(text=footer)
			embeds.append(embed)

		return embeds

	async def on_ready(self):
		logging.info('{} has connected to Discord!'.format(self.user))
		logging.info('Getting comics for midweek "{}".'.format(self.midweek))

		channel = self.get_channel()

		embeds = self.build_embeds(self.midweek)

		for e in embeds:
			await channel.send(embed=e)

		self.conn.close()
		await self.logout()

	async def on_error(self, *args, **kwargs):
		err_type, err_value, err_traceback = exc_info()
		logging.debug('Error cause by call with args and kwargs: {} {}'.format(args, kwargs))
		logging.error('{}: {}'.format(err_type, err_value))
		raise err_type(err_value)


if __name__ == '__main__':

	parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
	parser.add_argument('-l', '--log', dest='logfile',
		help="Log file.", metavar="LOGFILE")
	parser.add_argument('-q', '--quite', dest='quite', default=False, action='store_true',
		help="Quite output")
	parser.add_argument('--mode', dest='mode', default='INFO',
		choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
		help="Logging level for output", metavar="MODE")

	parser.add_argument('-e, --env', dest='envfile', default='.env',
		help="Environment file to load.", metavar='ENV')
	parser.add_argument('-d, --database', dest='database',
		help="Sqlite3 database with comic info.", metavar='SQLITE3')
	parser.add_argument('-t', '--token', dest='token',
		help="Discord API Token.", metavar='TOKEN')
	parser.add_argument('-gn', '--guild-name', dest='guild_name',
		help="Name of Guild to post to.", metavar='GUILDNAME')
	parser.add_argument('-gi', '--guild-id', dest='guild_id', type=int,
		help="Id of Guild to post to.", metavar='GUILDID')
	parser.add_argument('-cn', '--channel-name', dest='channel_name',
		help="Name of Guild to post to.", metavar='CHANNELNAME')
	parser.add_argument('-ci', '--channel-id', dest='channel_id', type=int,
		help="Id of Guild to post to.", metavar='CHANNELID')
	parser.add_argument('-w', '--week', dest='week',
		help="Date to pull week of comics from.", metavar='YYYY-MM-DD')
	parser.add_argument('-wf', '--weekfile', dest='weekfile', default='midweek.txt',
		help="File to load midweek date from. If week is passed in, this file will be ignore.", metavar='WEEKFILE')

	args = parser.parse_args()

	log_level = {
		'DEBUG': logging.DEBUG,
		'INFO': logging.INFO,
		'WARNING': logging.WARNING,
		'ERROR': logging.ERROR,
		'CRITICAL': logging.CRITICAL,
	}

	handler_list = [
		logging.StreamHandler(stdout),
		logging.FileHandler(args.logfile)
	] if args.logfile else [
		logging.StreamHandler(stdout)
	]

	logging.basicConfig(
		format='%(asctime)s\t[%(levelname)s]\t{%(module)s}\t%(message)s',
		datefmt='%Y-%m-%d %H:%M:%S',
		level=log_level[args.mode],
		handlers=handler_list
	)
	if args.quite:
		logging.disable(logging.CRITICAL)

	load_dotenv(args.envfile, verbose=(args.mode == 'DEBUG'))

	if args.week is None:
		with open(args.weekfile, 'r') as fp:
			week = fp.read().strip()
	else:
		week = args.week

	TOKEN = args.token if args.token else getenv('DISCORD_TOKEN')
	GUILD_NAME = args.guild_name if args.guild_name else getenv('GUILD_NAME')
	GUILD_ID = args.guild_id if args.guild_id else int(getenv('GUILD_ID'))
	CHANNEL_NAME = args.channel_name if args.channel_name else getenv('CHANNEL_NAME')
	CHANNEL_ID = args.channel_id if args.channel_id else int(getenv('CHANNEL_ID'))
	DATABASE = args.database if args.database else getenv('DATABASE')

	ComicReread(
		database_filename=DATABASE,
		midweek=week,
		guild_name=GUILD_NAME,
		guild_id=GUILD_ID,
		channel_name=CHANNEL_NAME,
		channel_id=CHANNEL_ID,
	).run(TOKEN)

	if args.week is None:
		current_week = datetime.strptime(week, '%Y-%m-%d')
		next_week = current_week + timedelta(days=7)
		with open(args.weekfile, 'w+') as fp:
			fp.write(datetime.strftime(next_week, '%Y-%m-%d'))

