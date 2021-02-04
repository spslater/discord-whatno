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
	def __init__(
			self,
			database_filename,
			midweek,
			guild_name=None,
			guild_id=None,
			channel_name=None,
			channel_id=None,
			info=False,
			info_file=None,
			message=None,
			message_file=None,
			send_comic=True,
		):
		super().__init__()
		self.database_filename = database_filename
		self.conn = None
		self.database = None
		self.midweek = midweek
		self.guild_name = guild_name
		self.guild_id = guild_id
		self.guild = None
		self.channel_name = channel_name
		self.channel_id = channel_id
		self.channel = None
		self.info = info
		self.info_file = info_file
		self.message = message
		self.message_file = message_file
		self.send_comic = send_comic
		if self.channel_id is None and self.channel_name is None:
			raise RuntimeError('Channel Id or Name not added to Client.')

	def get_connection(self):
		if self.conn is None:
			self.conn = connect(self.database_filename)
		return self.conn

	def get_database(self):
		if self.database is None:
			self.database = self.get_connection().cursor()
		return self.database

	def get_guild(self):
		if self.guild is None:
			logging.debug('Getting guild.')
			if self.guild_id is None and self.guild_name is None:
				channel = self.get_channel()
				self.guild = channel.guild
				self.guild_id = self.guild.id
				self.guild_name = self.guild.name
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
			if self.guild is None:
				self.get_guild()
		if self.channel.guild.id != self.guild_id:
			logging.warn('Guild provided channel ({}) belongs to does not match provied guild ({}).'.format(
				self.channel.guild.name,
				self.guild_name,
			))
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
		self.get_database().execute('SELECT tag FROM Tag WHERE comicId = ?', (date_string,))
		rows = self.get_database().fetchall()
		tags = [ r[0] for r in rows ]
		return ', '.join(tags)

	def build_embeds(self, date_string):
		embeds = []

		days = self.build_date_tuple(date_string)
		logging.debug('Getting comics on following days: {}', (days,))
		self.get_database().execute("""
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

		rows = self.get_database().fetchall()
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

	def print_info(self):
		info = ''
		info += 'Accessing Guild: {} ({})\n'.format(self.get_guild().name, self.get_guild().id)
		info += 'Accessing Channel: {} ({})\n'.format(self.get_channel().name, self.get_channel().id)
		info += 'Total Number of Guilds: {}\n'.format(len(self.guilds))
		for guild in self.guilds:
			info += 'Guild: {} ({})\n'.format(guild.name, guild.id)
			info += '\tTotal Number of Channels: {}\n'.format(len(guild.channels))
			for channel in guild.channels:
				info += '\tChannel: {} ({})\n'.format(channel.name, channel.id)

		if self.info:
			print(info)

		if self.info_file is not None:
			with open(self.info_file, 'w+') as fp:
				fp.write(info)


	async def send_message(self):
		channel = self.get_channel()
		if self.message is not None:
			logging.debug('Sending a plaintext message')
			await channel.send(self.message)

		if self.message_file is not None:
			logging.debug('Loading text from file: {}'.format(self.message_file))
			with open(self.message_file, 'r') as fp:
				data = fp.read()
				await channel.send(data)


	async def send_weekly_comics(self):
		logging.info('Getting comics for midweek "{}".'.format(self.midweek))

		channel = self.get_channel()
		embeds = self.build_embeds(self.midweek)
		for e in embeds:
			await channel.send(embed=e)


	async def on_ready(self):
		logging.info('{} has connected to Discord!'.format(self.user))

		channel = self.get_channel()
		guild = self.get_guild()

		if self.info or self.info_file is not None:
			logging.info('Printing info about Client.')
			self.print_info()

		if self.message is not None or self.message_file is not None:
			logging.info('Sending a message to channel "{}" on guild "{}"'.format(channel, guild))
			await self.send_message()

		if self.send_comic:
			logging.info('Sending Comics to channel "{}" on guild "{}".'.format(channel, guild))
			await self.send_weekly_comics()

		if self.conn is not None:
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
	parser.add_argument('-nc', '--no-comics', dest='send_comic', default=True, action='store_false',
		help="Do not send the weekly comics to the server.")
	parser.add_argument('-i', '--info', dest='info', default=False, action='store_true',
		help="Print out availble guilds and channels and other random info I add. Prints to stdout, not the log file.")
	parser.add_argument('-if', '--info-file', dest='infofile',
		help="File to save info print to, won't print to stdout if set and -i flag not used.", metavar='FILENAME')
	parser.add_argument('-m', '--message', dest='message',
		help="Send a plaintext message to the configured channel", metavar='MESSAAGE')
	parser.add_argument('-mf', '--message-file', dest='messagefile',
		help="Send plaintext contents of a file as a message to the configured channel", metavar='FILENAME')

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
		info=args.info,
		info_file=args.infofile,
		message=args.message,
		message_file=args.messagefile,
		send_comic=args.send_comic,
	).run(TOKEN)

	if args.week is None:
		current_week = datetime.strptime(week, '%Y-%m-%d')
		next_week = current_week + timedelta(days=7)
		with open(args.weekfile, 'w+') as fp:
			fp.write(datetime.strftime(next_week, '%Y-%m-%d'))

