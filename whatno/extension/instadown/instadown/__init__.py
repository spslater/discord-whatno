"""Insta Downloader Cog"""
from .instadown import *

def setup(bot):
    """Setup the Insta Downloader Cogs"""
    cog_insta = InstaDownCog(bot)
    bot.add_cog(cog_insta)
