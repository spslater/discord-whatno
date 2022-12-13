"""Helper methods for the DoA Cogs"""
import logging
import re
from io import UnsupportedOperation
from os import fsync
from json import dumps
from pathlib import Path
from tinydb import JSONStorage, TinyDB
from tinydb.table import Document, Table

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


class PrettyJSONStorage(JSONStorage):
    """Story TinyDB data in a pretty format"""

    def write(self, data):
        self._handle.seek(0)
        serialized = dumps(data, indent=4, sort_keys=True, **self.kwargs)
        try:
            self._handle.write(serialized)
        except UnsupportedOperation as e:
            raise IOError(
                f'Cannot write to the database. Access mode is "{self._mode}"'
            ) from e

        self._handle.flush()
        fsync(self._handle.fileno())

        self._handle.truncate()

class StrTable(Table):
    document_id_class = str

class PrettyStringDB(TinyDB):
    table_class = StrTable
    default_storage_class = PrettyJSONStorage