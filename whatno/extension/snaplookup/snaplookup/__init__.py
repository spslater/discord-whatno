"""Marvel Snap Cog"""
from .snap import *


def setup(bot):
    """Setup the DoA Cogs"""
    cog_snap = SnapCog(bot, envfile="./.env")
    bot.add_cog(cog_snap)
