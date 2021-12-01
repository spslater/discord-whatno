"""Helper functions"""
from os import getenv


def allow_slash():
    """Guild ids to allow slash commands for"""
    return [
        int(g.strip())
        for g in getenv("DISCORD_ALLOW_SLASH", "").split(",")
        if g.strip()
    ]
