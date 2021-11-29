"""Test the bot from the CLI"""
import logging
from threading import Thread, Event
from . import WhatnoBot, ExtensionWatcher

stop = Event()

bot = WhatnoBot().parse()
logger = logging.getLogger(__name__)
watcher = ExtensionWatcher(path="./whatno/extension/", bot=bot)
thread = Thread(target=watcher.watch, name="watcher", args=[stop])

thread.start()
bot.run()
stop.set()
thread.join()
