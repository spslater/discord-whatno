"""Comic Rereading Discord Bot"""
from .rereadbot import *


def setup(bot):
    """Setup the DoA Cogs"""
    cog_reread = DoaRereadCog(bot, envfile="./.env")
    bot.add_cog(cog_reread)
