"""Comic Rereading Discord Bot"""
from .rereadbot import *

async def setup(bot):
    """Setup the DoA Cogs"""
    bot.add_cog(DoaRereadCog(bot, envfile="./.env"))
