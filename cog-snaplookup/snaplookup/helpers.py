"""Helper methods for the DoA Cogs"""
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

def calc_path(filename):
    """Calculate a filepath based off of current file"""
    if filename is None:
        return None
    filepath = Path(filename)
    if not filepath.is_absolute():
        filepath = Path(__file__, "..", filepath)
    return filepath.resolve()

def strim(s):
    return re.sub(r'[^a-zA-Z0-9]', '', s.lower())


def chunk(sequence, size):
    """Split a sequence into same sized subgroups"""
    for idx in range(0, len(sequence), size):
        yield sequence[idx : idx + size]


def generate_chunker(size):
    """Generate a chunk function that always splits into groups of size"""
    return lambda sequence: chunk(sequence, size)
