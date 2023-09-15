"""Stats Cog"""
from .stats import *


def setup(bot):
    """Setup the DoA Cogs"""
    cog_stats = StatsCog(bot, envfile="./.env")
    bot.add_cog(cog_stats)
