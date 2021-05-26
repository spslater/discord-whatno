#!/usr/bin/env python3

import logging

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from datetime import datetime, timedelta
from os import getenv
from json import load, dump
from sqlite3 import connect
from sys import stdout, exc_info
from time import sleep
from traceback import format_tb

from discord import Client, Embed, Colour, NotFound, HTTPException, Forbidden
from dotenv import load_dotenv

class ComicReread(Client):
	def __init__(
			self,
			database_filename,
			schedule_filename,
			guild_name=None,
			guild_id=None,
			channel_name=None,
			channel_id=None,
			info=False,
			info_file=None,
			message=None,
			message_file=None,
			send_comic=True,
			delete=None,
			delete_file=None,
			embed_file=None,
			refresh=None,
			refresh_file=None,
		):
		super().__init__()

		self.database_filename = database_filename
		self.conn = None
		self.database = None

		self.schedule_filename = schedule_filename
		with open(self.schedule_filename, 'r') as fp:
			self.schedule = load(fp)

		self.guild_name = guild_name
		self.guild_id = guild_id
		self.guild = None

		self.channel_name = channel_name
		self.channel_id = channel_id
		self.channel = None

		self.send_comic = send_comic

		self.info = info
		self.info_file = info_file

		self.message = message
		self.message_file = message_file

		self.delete = delete
		self.delete_file = delete_file

		self.embed_file = embed_file

		self.refresh = refresh
		self.refresh_file = refresh_file

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
			logging.warn(f'Guild provided channel ({self.channel.guild.name}) belongs to does not match provied guild ({self.guild_name}).')
		return self.channel

	def date_from_week(self, yr, wk, wd):
		ywd = f"{yr}-{wk}-{wd}"
		iso_date = datetime.strptime(ywd, "%G-%V-%u")
		return datetime.strftime(iso_date, "%Y-%m-%d")

	def build_date_list(self, date_string):
		yr, wk, _ = datetime.strptime(date_string, "%Y-%m-%d").isocalendar()
		return [
			self.date_from_week(yr, wk, 1),
			self.date_from_week(yr, wk, 2),
			self.date_from_week(yr, wk, 3),
			self.date_from_week(yr, wk, 4),
			self.date_from_week(yr, wk, 5),
			self.date_from_week(yr, wk, 6),
			self.date_from_week(yr, wk, 7),
		]

	def get_tags(self, date_string):
		self.get_database().execute('SELECT tag FROM Tag WHERE comicId = ?', (date_string,))
		rows = self.get_database().fetchall()
		tags = [ r[0] for r in rows ]
		return ', '.join(tags)

	def build_embeds(self, date_string):
		embeds = []

		days = tuple(self.schedule['days'][date_string])
		logging.debug(f'Getting comics on following days: {days}')
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
		logging.debug(f'{len(rows)} comics from current week')
		for row in rows:
			release = row[0]
			title = row[1]
			image = row[2].split('_', maxsplit=3)[3]
			url = row[3]
			alt = f'||{row[4]}||'
			header = f'[{title}]({url})'
			img_url = f'https://www.dumbingofage.com/comics/{image}'
			tags = self.get_tags(release)
			footer = f'{release} - {tags}'

			logging.debug(f'Generating embed for "{title}" from {release}')
			embed = Embed(title=title, url=url, description=alt, colour=Colour.random())
			embed.set_image(url=img_url)
			embed.set_footer(text=footer)
			embeds.append(embed)

		if self.embed_file:
			prev = None
			try:
				with open(self.embed_file, 'r') as fp:
					prev = load(fp)
			except FileNotFoundError:
					prev = {}
			prev[date_string] = [ e.to_dict() for e in embeds ]
			with open(self.embed_file, 'w+') as fp:
				dump(prev, fp, sort_keys=True, indent='\t')

		return embeds

	def print_info(self):
		main_guild = self.get_guild()
		main_channel = self.get_channel()
		info = ''
		info += f'Accessing Guild: {main_guild.name} ({main_guild.id})\n'
		info += f'Accessing Channel: {main_channel.name} ({main_channel.id})\n'
		info += f'Total Number of Guilds: {len(self.guilds)}\n'
		for guild in self.guilds:
			info += f'Guild: {guild.name} ({guild.id})\n'
			info += f'\tTotal Number of Channels: {len(guild.channels)}\n'
			for channel in guild.channels:
				info += f'\tChannel: {channel.name} ({channel.id})\n'

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
			logging.debug(f'Loading text from file: {self.message_file}')
			with open(self.message_file, 'r') as fp:
				data = fp.read()
				await channel.send(data)

	async def delete_message(self):
		channel = self.get_channel()
		mids = []
		if self.delete is not None:
			logging.debug(f'Deleting {len(self.delete)} messages from cli')
			mids.extend(self.delete)

		if self.delete_file is not None:
			with open(self.delete_file, 'r') as fp:
				file_mids = [ int(m.strip()) for m in fp.read().splitlines() if m.strip() ]
				mids.extend(file_mids)
			logging.debug(f'Deleting {len(file_mids)} messages from file: {self.delete_file}')

		logging.info(f'Deleting {len(mids)} messages.')
		for mid in mids:
			logging.debug(f'Attemping to delete "{mid}".')
			try:
				msg = await channel.fetch_message(mid)
				await msg.delete()
			except (NotFound, HTTPException) as e:
				logging.warn(f'Unable to get message "{mid}": {e}')

	async def refresh_message(self):
		channel = self.get_channel()
		mids = []
		if self.refresh is not None:
			logging.debug(f'Reloading {len(self.refresh)} messages from cli')
			mids.extend(self.refresh)

		if self.refresh_file is not None:
			with open(self.refresh_file, 'r') as fp:
				file_mids = [ int(m.strip()) for m in fp.read().splitlines() if m.strip() ]
				mids.extend(file_mids)
			logging.debug(f'Reloading {len(file_mids)} messages from file: {self.refresh_file}')

		logging.info(f'Editing {len(mids)} messages.')
		for mid in mids:
			try:
				msg = await channel.fetch_message(mid)
				embed = msg.embeds[0]
				embed.colour = Colour.random()
				logging.debug(embed.__repr__())
				await msg.edit(embed=embed)
				sleep(1)
			except (NotFound, HTTPException, Forbidden) as e:
				logging.warn('Unable to get message "{mid}": {e}')

	async def send_weekly_comics(self):
		logging.info('Sending comics for today.')

		channel = self.get_channel()
		today = datetime.strftime(datetime.now(), '%Y-%m-%d')
		embeds = self.build_embeds(today)
		for e in embeds:
			logging.debug(embed.__repr__())
			await channel.send(embed=e)
			sleep(3)

	def update_schedule(self):
		old_week = self.schedule['next_week']
		if old_week == datetime.strftime(datetime.now(), '%Y-%m-%d'):
			new_week = old_week + timedelta(days=7)
			new_week_str = datetime.strftime(new_week, '%Y-%m-%d')
			self.schedule['next_week'] = new_week_str

			last_day = sorted(self.schedule['days'].keys())[-1]
			next_day = datetime.strptime(last_day, '%Y-%m-%d') + deltatime(days=1)
			next_day_str = datetime.strptime(last_day, '%Y-%m-%d')

			self.schedule['days'][next_day_str] = self.build_date_list(new_week_str)

			with open(self.schedule_file, 'w+') as fp:
				dump(self.schedule, fp, sort_keys=True, indent='\t')

	async def on_ready(self):
		logging.info(f'{self.user} has connected to Discord!')

		channel = self.get_channel()
		guild = self.get_guild()

		if self.info or self.info_file is not None:
			logging.info('Printing info about Client.')
			self.print_info()

		if self.message is not None or self.message_file is not None:
			logging.info(f'Sending a message to channel "{channel}" on guild "{guild}"')
			await self.send_message()

		if self.delete is not None or self.delete_file is not None:
			logging.info(f'Deleting messages in channel "{channel}" on guild "{guild}"')
			await self.delete_message()

		if self.refresh is not None or self.refresh_file is not None:
			logging.info(f'Reloading messages in channel "{channel}" on guild "{guild}"')
			await self.refresh_message()

		if self.send_comic:
			logging.info(f'Sending Comics to channel "{channel}" on guild "{guild}".')
			await self.send_weekly_comics()
			self.update_schedule()

		if self.conn is not None:
			self.conn.close()
		await self.logout()

	async def on_error(self, *args, **kwargs):
		err_type, err_value, err_traceback = exc_info()
		tb_list = '\n'.join(format_tb(err_traceback))
		tb_string = ' | '.join(tb_list.splitlines())
		logging.debug(f'Error cause by call with args and kwargs: {args} {kwargs}')
		logging.error(f'{err_type.__name__}: {err_value} | Traceback: {tb_string}')
		if self.conn is not None:
			self.conn.close()
		await self.logout()


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
	parser.add_argument('-s', '--schedule', dest='schedule',
		help="JSON file to load release information from.", metavar='FILENAME')
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
	parser.add_argument('--delete', dest='delete', nargs='*', type=int,
		help="Message ids to delete from channel", metavar='MID')
	parser.add_argument('--delete-file', dest='deletefile',
		help="Message ids to delete from channel", metavar='MID')
	parser.add_argument('--embed-file', dest='embedfile',
		help="File to print embeds to for debugging purposes", metavar='EMBED')
	parser.add_argument('--refresh', dest='refresh', nargs='*', type=int,
		help="Message ids to refresh from channel", metavar='MID')
	parser.add_argument('--refresh-file', dest='refreshfile',
		help="Message ids to refresh from channel", metavar='MID')

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
		handlers=handler_list,
	)
	if args.quite:
		logging.disable(logging.CRITICAL)

	load_dotenv(args.envfile, verbose=(args.mode == 'DEBUG'))

	TOKEN = args.token if args.token else getenv('DISCORD_TOKEN')
	GUILD_NAME = args.guild_name if args.guild_name else getenv('GUILD_NAME')
	GUILD_ID = args.guild_id if args.guild_id else int(getenv('GUILD_ID'))
	CHANNEL_NAME = args.channel_name if args.channel_name else getenv('CHANNEL_NAME')
	CHANNEL_ID = args.channel_id if args.channel_id else int(getenv('CHANNEL_ID'))
	DATABASE = args.database if args.database else getenv('DATABASE')
	SCHEDULE = args.schedule if args.schedule else getenv('SCHEDULE')
	EMBED = args.schedule if args.schedule else getenv('EMBED')

	ComicReread(
		database_filename=DATABASE,
		schedule_filename=SCHEDULE,
		guild_name=GUILD_NAME,
		guild_id=GUILD_ID,
		channel_name=CHANNEL_NAME,
		channel_id=CHANNEL_ID,
		info=args.info,
		info_file=args.infofile,
		message=args.message,
		message_file=args.messagefile,
		send_comic=args.send_comic,
		delete=args.delete,
		delete_file=args.deletefile,
		embed_file=EMBED,
		refresh=args.refresh,
		refresh_file=args.refreshfile,
	).run(TOKEN)

