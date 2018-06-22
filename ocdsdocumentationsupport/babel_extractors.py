"""
Babel extractors used in setup.py

See http://babel.pocoo.org/en/latest/messages.html
"""

import csv
import json
import os
from io import StringIO

from ocdsdocumentationsupport import TRANSLATABLE_CODELIST_HEADERS, TRANSLATABLE_SCHEMA_KEYWORDS


def codelists_extract(fileobj, keywords, comment_tags, options):
    """
    Yields each header, and the Title, Description and Extension values of a codelist CSV file.
    """

    # standard-maintenance-scripts validates the headers of codelist CSV files.
    reader = csv.DictReader(StringIO(fileobj.read().decode()))
    for header in reader.fieldnames:
        yield 0, '', header, ''

    # Don't translate the titles of the hundreds of currencies.
    if os.path.basename(fileobj.name) != 'currency.csv':
        for row_number, row in enumerate(reader, 1):
            for key, value in row.items():
                value = value.strip()
                if key in TRANSLATABLE_CODELIST_HEADERS and value:
                    yield row_number, '', value, [key]


def jsonschema_extract(fileobj, keywords, comment_tags, options):
    """
    Yields the "title" and "description" values of a JSON Schema file.
    """
    def gather_text(data, pointer=''):
        if isinstance(data, list):
            for index, item in enumerate(data):
                yield from gather_text(item, pointer='{}/{}'.format(pointer, index))
        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    value = value.strip()
                    if key in TRANSLATABLE_SCHEMA_KEYWORDS and value:
                        yield value, '{}/{}'.format(pointer, key)
                yield from gather_text(value, pointer='{}/{}'.format(pointer, key))

    data = json.loads(fileobj.read().decode())
    for text, pointer in gather_text(data):
        yield 1, '', text, [pointer]
