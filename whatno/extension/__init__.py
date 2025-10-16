"""Import all of the cogs"""

from .cog_doacomic import setup as doacomic
from .cog_instadown import setup as instadown
from .cog_rereads import setup as rereads
from .cog_rssposter import setup as rssposter
from .cog_snaplookup import setup as snaplookup
from .cog_stats import setup as stats
from .cog_wnmessage import setup as wnmessage
from .cog_wntest import setup as wntest

ALL_COGS = [
    "doacomic",
    "instadown",
    "rereads",
    "rssposter",
    "snaplookup",
    "stats",
    "wnmessage",
    "wntest",
]

COG_DICT = {
    "doacomic": doacomic,
    "instadown": instadown,
    "rereads": rereads,
    "rssposter": rssposter,
    "snaplookup": snaplookup,
    "stats": stats,
    "wnmessage": wnmessage,
    "wntest": wntest,
}