from .snaplookup import process_cards
from .helpers import PrettyStringDB

process_cards(PrettyStringDB("./snaplookup/data.db"), True)
